"""
COI-101 step 4 — HMM regime predictor that loads from `model_registry`.

Resolves the active model for a symbol, loads the persisted pickle, computes
features with the shared `regime_features` module (guarantees train/serve
parity), runs `predict_proba`, and returns the smoothed posterior at the last
bar as the regime distribution.

The caller (engine/api.py) is responsible for fetching OHLCV and for the
fallback path when this predictor returns `None`.
"""
from __future__ import annotations

import logging
import os
import pickle
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import psycopg2

from .regime_features import FEATURE_SET, compute_features

LOG = logging.getLogger("risk_management.regime_predictor")

MODEL_TYPE = "hmm_regime"


# ─── Registry row + loaded artifact ─────────────────────────────────────────

@dataclass(frozen=True)
class RegistryRow:
    model_type: str
    symbol: str
    version: str
    path: str
    trained_at: datetime
    val_accuracy: float
    feature_set: List[str]


@dataclass
class LoadedModel:
    row: RegistryRow
    hmm: object              # hmmlearn.hmm.GaussianHMM
    scaler: object           # sklearn.preprocessing.StandardScaler
    regime_map: Dict[int, str]   # hmm state_id → regime label
    state_labels: List[str]      # parallel to state_probs array indices


def _load_pickle(row: RegistryRow) -> Optional[LoadedModel]:
    """Return None if the pickle file is missing — caller falls back."""
    path = Path(row.path)
    if not path.is_absolute():
        # Resolve registry paths relative to repo root (parent of this file's package).
        repo_root = Path(__file__).resolve().parents[1]
        path = (repo_root / path).resolve()

    if not path.exists():
        LOG.warning(
            "hmm_regime model file missing for %s: registry path=%s, resolved=%s",
            row.symbol, row.path, path,
        )
        return None

    try:
        with path.open("rb") as fh:
            payload = pickle.load(fh)
    except (pickle.PickleError, OSError, EOFError) as exc:
        LOG.warning("hmm_regime pickle load failed for %s at %s: %s",
                    row.symbol, path, exc)
        return None

    sym_payload = payload.get("symbols", {}).get(row.symbol)
    if sym_payload is None:
        LOG.warning("hmm_regime pickle has no entry for symbol %s at %s",
                    row.symbol, path)
        return None

    regime_map = sym_payload["regime_map"]
    n_states = sym_payload["hmm"].n_components
    state_labels = [regime_map[i] for i in range(n_states)]

    feat_set = payload.get("feature_set", list(FEATURE_SET))
    if list(feat_set) != list(FEATURE_SET):
        LOG.warning(
            "hmm_regime feature_set mismatch for %s: registry=%s vs serving=%s",
            row.symbol, feat_set, list(FEATURE_SET),
        )

    return LoadedModel(
        row=row,
        hmm=sym_payload["hmm"],
        scaler=sym_payload["scaler"],
        regime_map=regime_map,
        state_labels=state_labels,
    )


# ─── Predictor ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegimePrediction:
    symbol: str
    label: str
    confidence: float
    state_probs: List[float]
    state_labels: List[str]
    model_version: str
    trained_at: datetime
    val_accuracy: float


class HMMRegimePredictor:
    """Thread-safe predictor with per-symbol model cache.

    Cache invalidates when the registry row's (path, trained_at) changes,
    so a retrain that flips the active row to a new pickle picks up
    automatically on the next call.
    """

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.environ.get(
            "DATABASE_URL",
            "postgresql://coinscopeai:devpassword@localhost:5432/coinscopeai_dev",
        )
        self._cache: Dict[str, LoadedModel] = {}
        self._lock = threading.Lock()

    # — internals —

    def _fetch_active_row(self, symbol: str) -> Optional[RegistryRow]:
        try:
            conn = psycopg2.connect(self.dsn)
        except psycopg2.Error as exc:
            LOG.warning("model_registry: cannot connect to Postgres: %s", exc)
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT model_type, symbol, version, path, trained_at,
                           val_accuracy, feature_set
                      FROM model_registry
                     WHERE model_type = %s AND symbol = %s AND active = TRUE
                     ORDER BY trained_at DESC
                     LIMIT 1
                    """,
                    (MODEL_TYPE, symbol),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return RegistryRow(
            model_type=row[0], symbol=row[1], version=row[2],
            path=row[3], trained_at=row[4],
            val_accuracy=float(row[5]), feature_set=list(row[6]),
        )

    def _get_model(self, symbol: str) -> Optional[LoadedModel]:
        row = self._fetch_active_row(symbol)
        if row is None:
            LOG.warning("model_registry: no active hmm_regime row for %s", symbol)
            return None

        with self._lock:
            cached = self._cache.get(symbol)
            if (cached is not None
                    and cached.row.path == row.path
                    and cached.row.trained_at == row.trained_at):
                return cached
            loaded = _load_pickle(row)
            if loaded is None:
                # Invalidate any stale cache entry pointing to a now-broken pkl.
                self._cache.pop(symbol, None)
                return None
            self._cache[symbol] = loaded
            return loaded

    # — public —

    def predict(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
    ) -> Optional[RegimePrediction]:
        """Predict regime at the LAST bar of `ohlcv`.

        Returns `None` if no active registry row, the pickle is missing, or
        there is not enough usable data after feature warm-up. In every such
        case the caller should engage its named fallback.
        """
        model = self._get_model(symbol)
        if model is None:
            return None

        features = compute_features(ohlcv)
        if features.empty:
            LOG.warning(
                "regime predict %s: 0 usable rows after warm-up (input bars=%d)",
                symbol, len(ohlcv),
            )
            return None

        X = features[list(FEATURE_SET)].to_numpy(dtype=np.float64)
        if not np.isfinite(X).all():
            LOG.warning("regime predict %s: non-finite features", symbol)
            return None

        X_scaled = model.scaler.transform(X)
        posteriors = model.hmm.predict_proba(X_scaled)
        last_posterior = posteriors[-1]                            # length n_states
        # Numerical guard: enforce sum-to-1 in the returned array (hmmlearn
        # already normalises, but float drift over 4 components is possible).
        last_posterior = last_posterior / last_posterior.sum()

        state_id = int(np.argmax(last_posterior))
        label = model.regime_map[state_id]
        confidence = float(last_posterior[state_id])

        return RegimePrediction(
            symbol=symbol,
            label=label,
            confidence=confidence,
            state_probs=[float(p) for p in last_posterior],
            state_labels=list(model.state_labels),
            model_version=model.row.version,
            trained_at=model.row.trained_at,
            val_accuracy=model.row.val_accuracy,
        )
