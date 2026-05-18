#!/usr/bin/env python3
"""
COI-101 step 3 — Train per-symbol 4-state GaussianHMM regime model.

Pipeline per symbol:
  1. Load 1h OHLCV from Postgres table `ohlcv_1h` (populated by step 1).
  2. Compute features: log_return, volatility (ATR14/close), volume_ratio,
     price_position (close within 20-bar range).
  3. Drop 20-bar warm-up. Chronological 80/20 split (no shuffle).
  4. Fit StandardScaler on train only; transform val.
  5. Fit GaussianHMM(n_components=4, covariance_type="full", n_iter=200,
     random_state=42).
  6. Label the 4 states {Trending, Mean-Reverting, Volatile, Quiet} by joint
     volatility + return characteristics (canonical CLAUDE.md taxonomy —
     Volatile, not Ranging).
  7. val_accuracy = one-step state prediction accuracy:
       For each val bar t, take the forward-filtered posterior at t-1,
       multiply by the transition matrix, argmax → predicted state at t.
       Compare to Viterbi-decoded state at t. Mean match rate.
  8. Save pickle to models/hmm_regime_v1_<UTC-ISO>.pkl (one file per run;
     contains all 5 symbols' models keyed by symbol).
  9. Upsert one row per symbol into `model_registry`. active=TRUE only when
     val_accuracy > 0.60 (the configurable --gate); else active=FALSE and
     the script exits non-zero.

Usage:
  DATABASE_URL=postgresql://coinscopeai:devpassword@localhost:5432/coinscopeai_dev \
      python3 scripts/train_hmm_regime.py
"""
from __future__ import annotations

import argparse
import logging
import os
import pickle
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import psycopg2
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from scipy.stats import multivariate_normal
from sklearn.preprocessing import StandardScaler

# Project-internal — must import from this exact module so train/serve features stay byte-identical.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from risk_management.regime_features import (  # noqa: E402
    ATR_WINDOW,
    FEATURE_SET,
    RANGE_WINDOW,
    compute_features,
)

SYMBOLS: Sequence[str] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
MODEL_TYPE = "hmm_regime"
MODEL_VERSION = "v1"
N_COMPONENTS = 4
COV_TYPE = "full"
N_ITER = 200
RANDOM_STATE = 42
TRAIN_FRAC = 0.80

REGIME_LABELS = ("Trending", "Mean-Reverting", "Volatile", "Quiet")

LOG = logging.getLogger("train_hmm_regime")


# ─── HMM filter / one-step prediction ───────────────────────────────────────

def _log_emissions(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    """Log P(obs | state) per (time, state). Avoids hmmlearn's private API."""
    T, _ = X.shape
    K = model.n_components
    out = np.empty((T, K), dtype=np.float64)
    for k in range(K):
        out[:, k] = multivariate_normal.logpdf(
            X, mean=model.means_[k], cov=model.covars_[k], allow_singular=True,
        )
    return out


def _forward_log_filtered(model: GaussianHMM, X: np.ndarray) -> np.ndarray:
    """Log filtered posteriors P(state_t | obs[1..t]). Shape (T, K)."""
    T = len(X)
    K = model.n_components
    log_em = _log_emissions(model, X)
    log_A = np.log(model.transmat_ + 1e-300)
    log_pi = np.log(model.startprob_ + 1e-300)

    log_alpha = np.empty((T, K))
    log_alpha[0] = log_pi + log_em[0]
    for t in range(1, T):
        # log_alpha[t, k] = logsumexp_j(log_alpha[t-1, j] + log_A[j, k]) + log_em[t, k]
        log_alpha[t] = logsumexp(log_alpha[t - 1][:, None] + log_A, axis=0) + log_em[t]
    # Row-normalise to get filtered posteriors
    return log_alpha - logsumexp(log_alpha, axis=1, keepdims=True)


def one_step_prediction_accuracy(
    model: GaussianHMM,
    X_train: np.ndarray,
    X_val: np.ndarray,
) -> float:
    """val_accuracy operational definition:

      predicted_state[t] = argmax_k Σ_j filtered_posterior_{t-1}(j) · A(j,k)
      actual_state[t]    = Viterbi-decoded state at t on the joined sequence
      accuracy           = mean over t in val of (predicted == actual)

    Forward filter is run on the concatenated [train, val] sequence so the
    first val prediction is correctly conditioned on the full training history.
    Train bars are excluded from the accuracy mean.
    """
    X_full = np.vstack([X_train, X_val])
    train_len = len(X_train)
    log_A = np.log(model.transmat_ + 1e-300)

    log_filtered = _forward_log_filtered(model, X_full)         # (T, K)
    # one-step ahead: predicted distribution at t+1 = filtered_t @ A
    # in log space: logsumexp_j(log_filtered[t, j] + log_A[j, k])
    log_pred_next = logsumexp(
        log_filtered[:-1, :, None] + log_A[None, :, :], axis=1,
    )                                                            # (T-1, K)
    predicted_next_state = np.argmax(log_pred_next, axis=1)      # length T-1

    viterbi_full = model.predict(X_full)                          # length T

    # Compare for indices in val. predicted_next_state[t-1] predicts state at t.
    val_indices = np.arange(train_len, len(X_full))
    actual = viterbi_full[val_indices]
    predicted = predicted_next_state[val_indices - 1]
    return float(np.mean(predicted == actual))


# ─── State → regime labelling ───────────────────────────────────────────────

@dataclass
class StateStats:
    state: int
    n: int
    mean_log_return_abs: float
    mean_volatility: float
    mean_volume_ratio: float


def _compute_state_stats(states: np.ndarray, features: pd.DataFrame) -> List[StateStats]:
    out: List[StateStats] = []
    for k in range(N_COMPONENTS):
        mask = states == k
        if not mask.any():
            out.append(StateStats(k, 0, 0.0, 0.0, 0.0))
            continue
        sub = features[mask]
        out.append(StateStats(
            state=k,
            n=int(mask.sum()),
            mean_log_return_abs=float(sub["log_return"].abs().mean()),
            mean_volatility=float(sub["volatility"].mean()),
            mean_volume_ratio=float(sub["volume_ratio"].mean()),
        ))
    return out


def label_states(stats: List[StateStats]) -> Dict[int, str]:
    """Deterministic mapping HMM_state_id → regime name.

    Logic (per CLAUDE.md regime taxonomy v3 ML):
      1. Sort states by mean volatility ascending.
      2. Lowest volatility           → "Quiet".
      3. Highest volatility          → "Volatile".
      4. Of the two middle states, the higher |mean log_return| → "Trending",
         the other                    → "Mean-Reverting".
    """
    by_vol = sorted(stats, key=lambda s: s.mean_volatility)
    quiet, mid_lo, mid_hi, volatile = by_vol
    middle_two = sorted([mid_lo, mid_hi], key=lambda s: s.mean_log_return_abs)
    mean_rev, trending = middle_two
    return {
        quiet.state: "Quiet",
        mean_rev.state: "Mean-Reverting",
        trending.state: "Trending",
        volatile.state: "Volatile",
    }


# ─── Postgres I/O ───────────────────────────────────────────────────────────

OHLCV_SQL = """
SELECT open_time, open::float8, high::float8, low::float8,
       close::float8, volume::float8, trades
  FROM ohlcv_1h
 WHERE symbol = %s
 ORDER BY open_time
"""

UPSERT_REGISTRY_SQL = """
INSERT INTO model_registry
    (model_type, symbol, version, path, trained_at, val_accuracy, feature_set, active)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (model_type, symbol, version) DO UPDATE SET
    path         = EXCLUDED.path,
    trained_at   = EXCLUDED.trained_at,
    val_accuracy = EXCLUDED.val_accuracy,
    feature_set  = EXCLUDED.feature_set,
    active       = EXCLUDED.active
"""


def load_ohlcv(conn, symbol: str) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(OHLCV_SQL, (symbol,))
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume", "trades",
    ])


def upsert_registry(conn, *, symbol: str, path: str, trained_at: datetime,
                    val_accuracy: float, active: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            UPSERT_REGISTRY_SQL,
            (MODEL_TYPE, symbol, MODEL_VERSION, path, trained_at,
             round(val_accuracy, 4), list(FEATURE_SET), active),
        )
    conn.commit()


# ─── Training driver ────────────────────────────────────────────────────────

@dataclass
class TrainResult:
    symbol: str
    train_bars: int
    val_bars: int
    val_accuracy: float
    state_stats: List[StateStats]
    regime_map: Dict[int, str]
    model: GaussianHMM = field(repr=False)
    scaler: StandardScaler = field(repr=False)


def train_symbol(features: pd.DataFrame, symbol: str) -> TrainResult:
    X = features[list(FEATURE_SET)].to_numpy(dtype=np.float64)
    if not np.isfinite(X).all():
        raise RuntimeError(f"[{symbol}] non-finite values in features")

    split = int(len(X) * TRAIN_FRAC)
    X_train_raw, X_val_raw = X[:split], X[split:]

    scaler = StandardScaler().fit(X_train_raw)
    X_train = scaler.transform(X_train_raw)
    X_val = scaler.transform(X_val_raw)

    model = GaussianHMM(
        n_components=N_COMPONENTS,
        covariance_type=COV_TYPE,
        n_iter=N_ITER,
        random_state=RANDOM_STATE,
        tol=1e-4,
    )
    model.fit(X_train)

    if not getattr(model.monitor_, "converged", False):
        LOG.warning(
            "[%s] EM did not converge after %d iter (history=%s)",
            symbol, N_ITER, model.monitor_.history[-3:],
        )

    train_states = model.predict(X_train)
    stats = _compute_state_stats(train_states, features.iloc[:split].reset_index(drop=True))
    regime_map = label_states(stats)

    acc = one_step_prediction_accuracy(model, X_train, X_val)

    return TrainResult(
        symbol=symbol,
        train_bars=len(X_train),
        val_bars=len(X_val),
        val_accuracy=acc,
        state_stats=stats,
        regime_map=regime_map,
        model=model,
        scaler=scaler,
    )


def save_pickle(results: List[TrainResult], trained_at: datetime, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = trained_at.strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"hmm_regime_v1_{ts}.pkl"
    payload = {
        "schema_version": 1,
        "model_type": MODEL_TYPE,
        "version": MODEL_VERSION,
        "trained_at": trained_at.isoformat(),
        "feature_set": list(FEATURE_SET),
        "regime_labels": list(REGIME_LABELS),
        "hyperparams": {
            "n_components": N_COMPONENTS,
            "covariance_type": COV_TYPE,
            "n_iter": N_ITER,
            "random_state": RANDOM_STATE,
            "atr_window": ATR_WINDOW,
            "range_window": RANGE_WINDOW,
            "train_frac": TRAIN_FRAC,
        },
        "symbols": {
            r.symbol: {
                "hmm": r.model,
                "scaler": r.scaler,
                "regime_map": r.regime_map,
                "val_accuracy": r.val_accuracy,
                "train_bars": r.train_bars,
                "val_bars": r.val_bars,
            }
            for r in results
        },
    }
    with path.open("wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return path


# ─── CLI ────────────────────────────────────────────────────────────────────

def _render_report(results: List[TrainResult], gate: float) -> str:
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("COI-101 step 3 — HMM regime training report")
    lines.append("=" * 78)
    header = f"{'symbol':<10} {'train':>6} {'val':>5} {'val_acc':>8} {'status':>7}  regime_map"
    lines.append(header)
    lines.append("-" * len(header))
    for r in results:
        status = "PASS" if r.val_accuracy > gate else "FAIL"
        rmap = " ".join(f"{sid}→{name}" for sid, name in sorted(r.regime_map.items()))
        lines.append(
            f"{r.symbol:<10} {r.train_bars:>6} {r.val_bars:>5} "
            f"{r.val_accuracy:>8.4f} {status:>7}  {rmap}"
        )
    lines.append("")
    lines.append("Per-state characteristics (training Viterbi assignments):")
    for r in results:
        lines.append(f"  [{r.symbol}]")
        for s in sorted(r.state_stats, key=lambda x: x.state):
            label = r.regime_map.get(s.state, "?")
            lines.append(
                f"    state={s.state} ({label:<14}) "
                f"n={s.n:>5}  |ret|={s.mean_log_return_abs:.5f}  "
                f"vol={s.mean_volatility:.5f}  vol_ratio={s.mean_volume_ratio:.3f}"
            )
    lines.append("=" * 78)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "DATABASE_URL",
            "postgresql://coinscopeai:devpassword@localhost:5432/coinscopeai_dev",
        ),
        help="Postgres DSN (env: DATABASE_URL).",
    )
    parser.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    parser.add_argument("--out-dir", default="models", help="Pickle output dir.")
    parser.add_argument("--gate", type=float, default=0.60,
                        help="Min val_accuracy required to mark a model active.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    trained_at = datetime.now(tz=timezone.utc).replace(microsecond=0)
    conn = psycopg2.connect(args.dsn)
    try:
        results: List[TrainResult] = []
        for sym in args.symbols:
            df = load_ohlcv(conn, sym)
            if df.empty:
                raise RuntimeError(f"[{sym}] no rows in ohlcv_1h")
            features = compute_features(df)
            res = train_symbol(features, sym)
            LOG.info("[%s] train=%d val=%d val_acc=%.4f",
                     sym, res.train_bars, res.val_bars, res.val_accuracy)
            results.append(res)

        pickle_path = save_pickle(results, trained_at, Path(args.out_dir))
        # Store registry path relative to repo root for portability.
        try:
            rel_path = str(pickle_path.relative_to(Path.cwd()))
        except ValueError:
            rel_path = str(pickle_path)

        any_failed = False
        for r in results:
            active = r.val_accuracy > args.gate
            any_failed = any_failed or (not active)
            upsert_registry(
                conn,
                symbol=r.symbol,
                path=rel_path,
                trained_at=trained_at,
                val_accuracy=r.val_accuracy,
                active=active,
            )
    finally:
        conn.close()

    print(_render_report(results, args.gate))
    print(f"\nPickle: {pickle_path}")
    print(f"Registry rows upserted: {len(results)}")
    print(f"Gate: val_accuracy > {args.gate:.2f}")
    if any_failed:
        print("RESULT: at least one symbol failed the gate; models inserted as active=FALSE.")
        return 1
    print("RESULT: all symbols passed the gate; models inserted as active=TRUE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
