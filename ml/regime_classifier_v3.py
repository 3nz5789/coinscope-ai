"""
regime_classifier_v3.py — CoinScopeAI v3 Regime Classifier
============================================================
Trains an ensemble classifier (Random Forest + XGBoost) on the
labeled dataset produced by regime_label_dataset_v1.py.

Labels: Trending | Mean-Reverting | Volatile | Quiet

Pipeline:
    1. Load ml/data/regime_labeled_v1.csv
    2. Feature engineering (drop raw OHLCV, keep indicators)
    3. Group-aware train/test split (split by session_id to prevent
       temporal leakage — candles from the same session stay together)
    4. Train Random Forest + XGBoost
    5. Ensemble voting (soft probabilities)
    6. Evaluate: accuracy, per-class F1, confusion matrix
    7. Save: ml/models/regime_classifier_v3.pkl
              ml/models/regime_classifier_v3_meta.json

Usage:
    python ml/regime_classifier_v3.py

Author: Scoopy / CoinScopeAI
Version: 3.0.0
"""

from __future__ import annotations

import json
import logging
import os
import sys
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("regime_trainer")

# ── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DATA_CSV   = os.path.join(BASE_DIR, "data", "regime_labeled_v1.csv")
MODEL_DIR  = os.path.join(BASE_DIR, "models")
MODEL_PKL  = os.path.join(MODEL_DIR, "regime_classifier_v3.pkl")
META_JSON  = os.path.join(MODEL_DIR, "regime_classifier_v3_meta.json")
REPORT_TXT = os.path.join(MODEL_DIR, "regime_classifier_v3_report.txt")

# ── Feature columns used for training ────────────────────────────────────
# Excluded: raw OHLCV, timestamps, session metadata, raw EMA values
# (we use derived features like price_vs_ema50 instead of absolute prices)
FEATURE_COLS = [
    # Returns
    "log_ret", "abs_ret", "roc_10",
    # Momentum
    "rsi", "stoch_k",
    "macd_hist",                    # MACD histogram carries more signal than raw MACD
    # Trend
    "adx", "di_split",             # primary trend strength features
    "ema_align",                    # 0-3 score: how many EMAs are stacked
    "price_vs_ema50", "price_vs_ema200",
    # Volatility
    "atr_pct", "atr_pct_zscore",
    "bb_width", "bb_width_zscore",
    "bb_pct_b",
    "vol_of_vol",
    # Volume
    "vol_zscore",
]

LABEL_COL   = "regime_label"
SESSION_COL = "session_id"
LABEL_ORDER = ["Trending", "Mean-Reverting", "Volatile", "Quiet"]


# ─────────────────────────────────────────────────────────────────────────────
#  DATA LOADING & SPLITTING
# ─────────────────────────────────────────────────────────────────────────────

def load_and_split(path: str, test_sessions_per_regime: int = 1):
    """
    Load dataset and produce group-aware train/test split.

    Hold out `test_sessions_per_regime` sessions per regime as the test set
    so that no temporal leakage occurs between train and test.
    """
    log.info("Loading dataset: %s", path)
    df = pd.read_csv(path)
    log.info("Loaded %d rows, %d columns.", len(df), len(df.columns))

    # Verify required columns
    missing = [c for c in FEATURE_COLS + [LABEL_COL, SESSION_COL] if c not in df.columns]
    if missing:
        log.error("Missing columns: %s", missing)
        sys.exit(1)

    # Drop rows with any NaN in feature columns
    before = len(df)
    df = df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    log.info("Dropped %d NaN rows (%.1f%%).", before - len(df),
             100 * (before - len(df)) / before)

    # Group-aware split: hold out last session per regime
    sessions = df[SESSION_COL].unique()
    test_sessions = []
    for regime in LABEL_ORDER:
        regime_sessions = sorted([s for s in sessions if s.startswith(regime)])
        test_sessions.extend(regime_sessions[-test_sessions_per_regime:])

    train_mask = ~df[SESSION_COL].isin(test_sessions)
    test_mask  =  df[SESSION_COL].isin(test_sessions)

    df_train = df[train_mask].copy()
    df_test  = df[test_mask].copy()

    log.info("Train: %d rows (%d sessions) | Test: %d rows (%d sessions)",
             len(df_train), df_train[SESSION_COL].nunique(),
             len(df_test),  df_test[SESSION_COL].nunique())

    X_train = df_train[FEATURE_COLS].values
    y_train = df_train[LABEL_COL].values
    X_test  = df_test[FEATURE_COLS].values
    y_test  = df_test[LABEL_COL].values

    return X_train, y_train, X_test, y_test, df_test


# ─────────────────────────────────────────────────────────────────────────────
#  MODEL BUILDING
# ─────────────────────────────────────────────────────────────────────────────

def build_ensemble(le: LabelEncoder) -> VotingClassifier:
    """
    Build soft-voting ensemble of Random Forest + XGBoost.
    Both are well-suited to tabular indicator data.
    """
    n_classes = len(le.classes_)

    rf = RandomForestClassifier(
        n_estimators    = 400,
        max_depth       = 12,
        min_samples_leaf = 4,
        max_features    = "sqrt",
        class_weight    = "balanced",
        random_state    = 42,
        n_jobs          = -1,
    )

    xgb = XGBClassifier(
        n_estimators      = 400,
        max_depth         = 6,
        learning_rate     = 0.05,
        subsample         = 0.8,
        colsample_bytree  = 0.8,
        min_child_weight  = 3,
        gamma             = 0.1,
        reg_alpha         = 0.1,
        reg_lambda        = 1.0,
        num_class         = n_classes,
        objective         = "multi:softprob",
        eval_metric       = "mlogloss",
        use_label_encoder = False,
        random_state      = 42,
        n_jobs            = -1,
        verbosity         = 0,
    )

    ensemble = VotingClassifier(
        estimators = [("rf", rf), ("xgb", xgb)],
        voting     = "soft",
        weights    = [1, 1],         # equal weight; tune later if needed
    )
    return ensemble


# ─────────────────────────────────────────────────────────────────────────────
#  FEATURE IMPORTANCE
# ─────────────────────────────────────────────────────────────────────────────

def feature_importance(ensemble: VotingClassifier) -> list[tuple[str, float]]:
    """Extract and combine feature importances from RF and XGBoost."""
    rf_imp  = ensemble.estimators_[0].feature_importances_
    xgb_imp = ensemble.estimators_[1].feature_importances_
    combined = (rf_imp + xgb_imp) / 2
    pairs = sorted(zip(FEATURE_COLS, combined), key=lambda x: -x[1])
    return pairs


# ─────────────────────────────────────────────────────────────────────────────
#  INFERENCE WRAPPER  (used by api.py /regime endpoint)
# ─────────────────────────────────────────────────────────────────────────────

class RegimeClassifierV3:
    """
    Thin inference wrapper around the trained ensemble + LabelEncoder.
    Saved alongside the model pickle so api.py can load it directly.

    Usage:
        clf = RegimeClassifierV3.load()
        result = clf.predict(feature_dict)
        # → {"regime": "Trending", "confidence": 0.87,
        #    "probabilities": {"Trending": 0.87, ...}}
    """

    def __init__(self, ensemble: VotingClassifier, le: LabelEncoder,
                 feature_cols: list[str]) -> None:
        self.ensemble     = ensemble
        self.le           = le
        self.feature_cols = feature_cols

    @classmethod
    def load(cls, path: str = MODEL_PKL) -> "RegimeClassifierV3":
        return joblib.load(path)

    def predict(self, features: dict | pd.Series | np.ndarray) -> dict:
        """
        Predict regime from a feature dict/Series/array.

        Parameters
        ----------
        features : dict mapping feature_name → value, OR a 1-D array
                   in the order of self.feature_cols.

        Returns
        -------
        dict with keys:
            regime        : str  ("Trending" | "Mean-Reverting" | "Volatile" | "Quiet")
            confidence    : float 0-1
            probabilities : dict label → probability
        """
        if isinstance(features, dict):
            x = np.array([features.get(c, 0.0) for c in self.feature_cols],
                         dtype=float).reshape(1, -1)
        elif isinstance(features, pd.Series):
            x = features[self.feature_cols].values.astype(float).reshape(1, -1)
        else:
            x = np.array(features, dtype=float).reshape(1, -1)

        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)

        proba  = self.ensemble.predict_proba(x)[0]
        idx    = int(np.argmax(proba))
        regime = self.le.inverse_transform([idx])[0]

        prob_dict = {
            str(self.le.inverse_transform([i])[0]): round(float(p), 4)
            for i, p in enumerate(proba)
        }
        return {
            "regime":        regime,
            "confidence":    round(float(proba[idx]), 4),
            "probabilities": prob_dict,
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict on a DataFrame; returns df with new columns appended."""
        X = df[self.feature_cols].fillna(0).values.astype(float)
        proba  = self.ensemble.predict_proba(X)
        labels = self.le.inverse_transform(np.argmax(proba, axis=1))
        confs  = proba.max(axis=1)
        out    = df.copy()
        out["regime_pred"]       = labels
        out["regime_confidence"] = np.round(confs, 4)
        for i, cls in enumerate(self.le.classes_):
            out[f"prob_{cls.replace('-', '_')}"] = np.round(proba[:, i], 4)
        return out


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)

    log.info("=" * 60)
    log.info("CoinScopeAI — Regime Classifier v3 Training")
    log.info("=" * 60)

    # ── Load & split ─────────────────────────────────────────────────────
    X_train, y_train, X_test, y_test, df_test = load_and_split(DATA_CSV)

    # ── Encode labels ────────────────────────────────────────────────────
    le = LabelEncoder()
    le.fit(LABEL_ORDER)
    y_train_enc = le.transform(y_train)
    y_test_enc  = le.transform(y_test)
    log.info("Label encoding: %s", dict(zip(le.classes_, le.transform(le.classes_))))

    # ── Build & train ────────────────────────────────────────────────────
    log.info("Building ensemble (RF-400 + XGB-400)...")
    ensemble = build_ensemble(le)

    log.info("Training on %d samples with %d features...", len(X_train), len(FEATURE_COLS))
    t0 = datetime.now()
    ensemble.fit(X_train, y_train_enc)
    elapsed = (datetime.now() - t0).total_seconds()
    log.info("Training complete in %.1f seconds.", elapsed)

    # ── Evaluate ─────────────────────────────────────────────────────────
    log.info("Evaluating on held-out test set (%d samples)...", len(X_test))
    y_pred_enc = ensemble.predict(X_test)
    y_pred     = le.inverse_transform(y_pred_enc)

    acc = accuracy_score(y_test_enc, y_pred_enc)
    log.info("Overall accuracy: %.4f  (%.1f%%)", acc, acc * 100)

    report = classification_report(
        y_test, y_pred,
        labels   = LABEL_ORDER,
        digits   = 4,
        zero_division = 0,
    )
    cm = confusion_matrix(y_test, y_pred, labels=LABEL_ORDER)

    # ── Feature importance ────────────────────────────────────────────────
    importance = feature_importance(ensemble)

    # ── Build report ─────────────────────────────────────────────────────
    report_lines = [
        "=" * 65,
        "REGIME CLASSIFIER v3  —  Training Report",
        f"Trained : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 65,
        "",
        f"Dataset         : {DATA_CSV}",
        f"Train samples   : {len(X_train):,}",
        f"Test samples    : {len(X_test):,}",
        f"Features        : {len(FEATURE_COLS)}",
        f"Training time   : {elapsed:.1f}s",
        "",
        f"Overall Accuracy: {acc:.4f}  ({acc*100:.1f}%)",
        "",
        "Per-class Classification Report:",
        report,
        "",
        "Confusion Matrix (rows=actual, cols=predicted):",
        f"Labels: {LABEL_ORDER}",
    ]

    # Format confusion matrix
    header = "          " + "".join(f"{lbl[:9]:>11}" for lbl in LABEL_ORDER)
    report_lines.append(header)
    for i, row_label in enumerate(LABEL_ORDER):
        row_str = f"{row_label[:9]:<10}" + "".join(f"{cm[i][j]:>11}" for j in range(len(LABEL_ORDER)))
        report_lines.append(row_str)

    report_lines += [
        "",
        "Top-10 Feature Importances (avg RF + XGB):",
    ]
    for feat, imp in importance[:10]:
        bar = "█" * int(imp * 200)
        report_lines.append(f"  {feat:<25} {imp:.4f}  {bar}")

    report_lines += [
        "",
        "Model saved to: " + MODEL_PKL,
        "Metadata saved to: " + META_JSON,
    ]

    report_text = "\n".join(report_lines)
    print("\n" + report_text + "\n")

    with open(REPORT_TXT, "w") as f:
        f.write(report_text)
    log.info("Report → %s", REPORT_TXT)

    # ── Save model ────────────────────────────────────────────────────────
    classifier = RegimeClassifierV3(ensemble, le, FEATURE_COLS)
    joblib.dump(classifier, MODEL_PKL, compress=3)
    log.info("Model → %s  (%.1f MB)", MODEL_PKL,
             os.path.getsize(MODEL_PKL) / 1e6)

    # ── Save metadata ─────────────────────────────────────────────────────
    per_class_report = classification_report(
        y_test, y_pred,
        labels        = LABEL_ORDER,
        output_dict   = True,
        zero_division = 0,
    )
    meta = {
        "version":        "3.0.0",
        "trained_at":     datetime.now(timezone.utc).isoformat(),
        "dataset":        DATA_CSV,
        "train_samples":  int(len(X_train)),
        "test_samples":   int(len(X_test)),
        "features":       FEATURE_COLS,
        "labels":         LABEL_ORDER,
        "label_encoding": {cls: int(le.transform([cls])[0]) for cls in le.classes_},
        "accuracy":       round(float(acc), 6),
        "training_secs":  round(elapsed, 1),
        "per_class_f1":   {
            lbl: round(float(per_class_report[lbl]["f1-score"]), 4)
            for lbl in LABEL_ORDER if lbl in per_class_report
        },
        "feature_importance": [
            {"feature": f, "importance": round(float(i), 5)}
            for f, i in importance
        ],
        "models": {
            "rf":  {"n_estimators": 400, "max_depth": 12},
            "xgb": {"n_estimators": 400, "max_depth": 6, "lr": 0.05},
        },
        "ensemble": "soft_voting_equal_weights",
    }
    with open(META_JSON, "w") as f:
        json.dump(meta, f, indent=2)
    log.info("Metadata → %s", META_JSON)

    # ── Quick sanity predict ───────────────────────────────────────────────
    log.info("Sanity check — predicting first 3 test rows:")
    for i in range(min(3, len(X_test))):
        result = classifier.predict(
            dict(zip(FEATURE_COLS, X_test[i]))
        )
        actual = y_test[i]
        match  = "✓" if result["regime"] == actual else "✗"
        log.info("  [%s] actual=%-16s pred=%-16s conf=%.3f",
                 match, actual, result["regime"], result["confidence"])

    log.info("Done ✓")


if __name__ == "__main__":
    main()
