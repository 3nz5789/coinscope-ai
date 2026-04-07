"""
CoinScopeAI — ML Training v3: Phase 2 Alpha Features
=======================================================
Trains v3 models using the V3FeatureEngine (v2 base + Phase 2 alpha proxies).
Runs walk-forward validation and compares against v2 baseline.

Usage:
    python -m ai.training.train_v3 --all
    python -m ai.training.train_v3 --symbol BTCUSDT
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ai.evaluation.metrics import Evaluator, compute_forward_returns
from ai.features.engine_v3 import V3FeatureConfig, V3FeatureEngine
from ai.features.dataset import TargetConfig
from ai.models.classifiers import (
    LGBMConfig, LGBMSignalClassifier,
    LogRegConfig, LogRegSignalClassifier,
    SignalClassifier,
)
from ai.training.walk_forward import WalkForwardTrainer, WFTrainConfig
from services.backtesting.data_loader import DataLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("coinscopeai.ai.training.v3")

# ── Paths ───────────────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "v3"
REPORT_DIR = Path(__file__).resolve().parent.parent.parent / "ai" / "reports" / "v3"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
TIMEFRAME = "4h"  # Best-performing timeframe from v2


def get_target_config() -> TargetConfig:
    """Same target config as v2 4h for fair comparison."""
    return TargetConfig(
        forward_horizon=6,       # 6 bars = 24h ahead
        long_threshold=0.008,    # 0.8% move required
        short_threshold=-0.008,
        use_log_returns=True,
    )


def get_v3_feature_config() -> V3FeatureConfig:
    """v3 feature config: v2 4h base + Phase 2 alpha proxy parameters."""
    return V3FeatureConfig(
        # v2 4h base parameters
        return_periods=[1, 3, 5, 10, 20, 40],
        volatility_periods=[5, 10, 20, 50, 100],
        rsi_periods=[7, 14, 21],
        ema_periods=[9, 21, 50, 100],
        volume_ma_periods=[5, 10, 20, 50],
        atr_periods=[7, 14, 21],
        regime_lookbacks=[20, 50, 100],
        zscore_window=50,
        momentum_periods=[7, 14, 30, 60],
        weekly_cycle_period=7,
        funding_proxy_period=8,
        trend_scales=[10, 30, 60],
        donchian_periods=[20, 50],
        include_temporal=True,
        # Phase 2 alpha proxy parameters
        funding_lookbacks=[8, 24, 48],
        funding_extreme_zscore=2.0,
        liq_vol_window=5,
        liq_cascade_threshold=2.5,
        liq_cluster_window=3,
        oi_lookbacks=[5, 10, 20],
        oi_divergence_window=14,
        basis_lookbacks=[10, 20, 50],
        basis_zscore_window=50,
        ob_lookbacks=[5, 10, 20],
        ob_depth_window=10,
    )


def create_model(model_type: str) -> SignalClassifier:
    if model_type == "lgbm":
        return LGBMSignalClassifier(LGBMConfig(
            n_estimators=1000,
            max_depth=5,
            learning_rate=0.025,     # Slightly slower for more features
            min_child_samples=80,
            early_stopping_rounds=100,
            subsample=0.8,
            colsample_bytree=0.7,    # More aggressive column sampling with 162 features
            reg_alpha=0.15,
            reg_lambda=1.5,
        ))
    elif model_type == "logreg":
        return LogRegSignalClassifier(LogRegConfig(
            C=0.3,                   # More regularization for more features
            max_iter=3000,
        ))
    else:
        raise ValueError(f"Unknown model type: {model_type}")


class V3DatasetBuilder:
    """Dataset builder using V3FeatureEngine."""

    def __init__(
        self,
        feature_config: V3FeatureConfig,
        target_config: TargetConfig,
        train_pct: float = 0.60,
        val_pct: float = 0.20,
        normalize: str = "zscore",
    ):
        self.feature_config = feature_config
        self.target_config = target_config
        self.train_pct = train_pct
        self.val_pct = val_pct
        self.normalize = normalize
        self._feature_engine = V3FeatureEngine(feature_config)
        self._feature_names: List[str] = []
        self._norm_params: Dict = {}

    @property
    def feature_names(self) -> List[str]:
        return self._feature_names

    @property
    def norm_params(self) -> Dict:
        return self._norm_params

    def build(self, df: pd.DataFrame):
        features = self._feature_engine.extract(df)
        self._feature_names = list(features.columns)

        target = self._generate_target(df["close"].values)
        features["_target"] = target
        features["_timestamp"] = df["timestamp"].values

        valid = features.notna().all(axis=1)
        features = features[valid].reset_index(drop=True)
        logger.info("V3 dataset: dropped %d NaN rows, %d remaining", (~valid).sum(), len(features))

        n = len(features)
        train_end = int(n * self.train_pct)
        val_end = int(n * (self.train_pct + self.val_pct))

        train_df = features.iloc[:train_end]
        val_df = features.iloc[train_end:val_end]
        test_df = features.iloc[val_end:]

        feat_cols = [c for c in features.columns if not c.startswith("_")]

        if self.normalize == "zscore":
            self._norm_params = {}
            for col in feat_cols:
                mean = train_df[col].mean()
                std = train_df[col].std()
                if std == 0 or np.isnan(std):
                    std = 1.0
                self._norm_params[col] = (float(mean), float(std))

            train_df = self._apply_norm(train_df, feat_cols)
            val_df = self._apply_norm(val_df, feat_cols)
            test_df = self._apply_norm(test_df, feat_cols)

        def extract_xy(split_df):
            X = split_df[feat_cols].values.astype(np.float32)
            y = split_df["_target"].values.astype(np.int32)
            ts = pd.DatetimeIndex(split_df["_timestamp"].values)
            return X, y, ts

        result = {
            "train": extract_xy(train_df),
            "val": extract_xy(val_df),
            "test": extract_xy(test_df),
        }

        for name in ["train", "val", "test"]:
            _, y, _ = result[name]
            unique, counts = np.unique(y, return_counts=True)
            dist = dict(zip(unique.tolist(), counts.tolist()))
            logger.info("V3 split '%s': %d samples, dist: %s", name, len(y), dist)

        return result

    def build_for_walk_forward(self, df: pd.DataFrame):
        features = self._feature_engine.extract(df)
        self._feature_names = list(features.columns)

        target = self._generate_target(df["close"].values)
        features["_target"] = target
        features["_timestamp"] = df["timestamp"].values

        valid = features.notna().all(axis=1)
        features = features[valid].reset_index(drop=True)

        feat_cols = [c for c in features.columns if not c.startswith("_")]
        X = features[feat_cols].values.astype(np.float32)
        y = features["_target"].values.astype(np.int32)
        ts = pd.DatetimeIndex(features["_timestamp"].values)

        return X, y, ts, feat_cols

    def _apply_norm(self, df, feat_cols):
        df = df.copy()
        for col in feat_cols:
            if col in self._norm_params:
                mean, std = self._norm_params[col]
                df[col] = (df[col] - mean) / std
        return df

    def _generate_target(self, close: np.ndarray) -> np.ndarray:
        n = len(close)
        h = self.target_config.forward_horizon
        target = np.full(n, np.nan)
        for i in range(n - h):
            if self.target_config.use_log_returns:
                fwd = np.log(close[i + h] / close[i])
            else:
                fwd = (close[i + h] - close[i]) / close[i]
            if fwd > self.target_config.long_threshold:
                target[i] = 1
            elif fwd < self.target_config.short_threshold:
                target[i] = -1
            else:
                target[i] = 0
        return target


def train_and_evaluate(
    symbol: str,
    model_type: str = "lgbm",
    run_walk_forward: bool = True,
) -> Dict:
    """Train, evaluate, and walk-forward validate a v3 model."""
    print(f"\n{'=' * 70}")
    print(f"  [v3] {symbol} {TIMEFRAME} — {model_type.upper()}")
    print(f"{'=' * 70}")

    # Load data
    csv_path = DATA_DIR / f"{symbol}_{TIMEFRAME}.csv"
    df = DataLoader.from_csv(str(csv_path), symbol=symbol, timeframe=TIMEFRAME)
    print(f"  Data: {len(df)} candles")

    # Configs
    target_config = get_target_config()
    feature_config = get_v3_feature_config()

    # Build dataset
    builder = V3DatasetBuilder(
        feature_config=feature_config,
        target_config=target_config,
        train_pct=0.60,
        val_pct=0.20,
        normalize="zscore",
    )
    dataset = builder.build(df)
    feature_names = builder.feature_names

    X_train, y_train, ts_train = dataset["train"]
    X_val, y_val, ts_val = dataset["val"]
    X_test, y_test, ts_test = dataset["test"]

    print(f"  Features: {len(feature_names)} (v2 had 112)")
    print(f"  Train: {len(y_train)} | Val: {len(y_val)} | Test: {len(y_test)}")

    for name, y in [("Train", y_train), ("Val", y_val), ("Test", y_test)]:
        unique, counts = np.unique(y, return_counts=True)
        dist = {int(k): int(v) for k, v in zip(unique, counts)}
        print(f"  {name} distribution: {dist}")

    # ── Train ────────────────────────────────────────────────
    print(f"\n  Training {model_type.upper()} (v3 config)...")
    model = create_model(model_type)

    X_train_clean = np.nan_to_num(X_train, nan=0.0, posinf=0.0, neginf=0.0)
    X_val_clean = np.nan_to_num(X_val, nan=0.0, posinf=0.0, neginf=0.0)
    X_test_clean = np.nan_to_num(X_test, nan=0.0, posinf=0.0, neginf=0.0)

    train_metrics = model.fit(
        X_train_clean, y_train,
        X_val=X_val_clean, y_val=y_val,
        feature_names=feature_names,
    )

    # ── Evaluate ─────────────────────────────────────────────
    print(f"\n  Evaluating on test set...")
    evaluator = Evaluator()

    close = df["close"].values.astype(float)
    fwd_returns = compute_forward_returns(close, target_config.forward_horizon)

    test_fwd = np.full(len(y_test), np.nan)
    ts_series = pd.Series(df["timestamp"].values)
    for i, ts in enumerate(ts_test):
        idx_matches = ts_series[ts_series == ts].index
        if len(idx_matches) > 0:
            orig_idx = idx_matches[0]
            if orig_idx < len(fwd_returns):
                test_fwd[i] = fwd_returns[orig_idx]

    test_pred = model.predict(X_test_clean)
    test_proba = model.predict_proba(X_test_clean)

    train_pred = model.predict(X_train_clean)
    train_directional = train_pred != 0
    is_hit_rate = 0.0
    if train_directional.sum() > 0:
        is_hit_rate = float((train_pred[train_directional] == y_train[train_directional]).mean())

    is_metrics_dict = {
        "accuracy": train_metrics.get("train_accuracy", 0),
        "f1_macro": train_metrics.get("train_f1_macro", 0),
        "hit_rate": is_hit_rate,
    }

    report = evaluator.evaluate(
        y_true=y_test,
        y_pred=test_pred,
        y_proba=test_proba,
        forward_returns=test_fwd,
        feature_importance=model.feature_importance(),
        is_metrics=is_metrics_dict,
    )

    print(f"\n  ── ML Metrics (Test Set) ──")
    print(f"    Accuracy:       {report.ml_metrics.accuracy:.4f}")
    print(f"    F1 (macro):     {report.ml_metrics.f1_macro:.4f}")
    print(f"    AUC-ROC:        {report.ml_metrics.auc_roc_ovr:.4f}")

    print(f"\n  ── Trading Metrics ──")
    print(f"    Signal Hit Rate:     {report.trading_metrics.signal_hit_rate:.4f}")
    print(f"    Long Hit Rate:       {report.trading_metrics.long_hit_rate:.4f}")
    print(f"    Short Hit Rate:      {report.trading_metrics.short_hit_rate:.4f}")
    print(f"    Avg Return (Long):   {report.trading_metrics.avg_return_long:.6f}")
    print(f"    Avg Return (Short):  {report.trading_metrics.avg_return_short:.6f}")
    print(f"    Signal PF:           {report.trading_metrics.signal_profit_factor:.4f}")
    print(f"    Signals: {report.trading_metrics.long_signals}L / "
          f"{report.trading_metrics.short_signals}S / "
          f"{report.trading_metrics.neutral_signals}N")

    if report.overfit_metrics:
        print(f"\n  ── Overfitting Detection ──")
        print(f"    IS Accuracy:  {report.overfit_metrics.is_accuracy:.4f}")
        print(f"    OOS Accuracy: {report.overfit_metrics.oos_accuracy:.4f}")
        print(f"    Degradation:  {report.overfit_metrics.accuracy_degradation:+.4f}")
        print(f"    Overfit Score: {report.overfit_metrics.overfit_score:.4f}")

    if report.top_features:
        print(f"\n  ── Top 15 Features ──")
        for name, imp in report.top_features[:15]:
            marker = " [NEW]" if any(name.startswith(p) for p in [
                "funding_", "liq_", "oi_", "basis_", "ob_"
            ]) else ""
            print(f"    {name:<35s} {imp:.4f}{marker}")

    # Save model with metadata
    model_path = MODEL_DIR / f"{model_type}_{symbol}_{TIMEFRAME}.joblib"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(model_path))

    # Save norm params and feature names alongside model
    meta = {
        "version": "v3",
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "model_type": model_type,
        "feature_names": feature_names,
        "norm_params": builder.norm_params,
        "target_config": {
            "forward_horizon": target_config.forward_horizon,
            "long_threshold": target_config.long_threshold,
            "short_threshold": target_config.short_threshold,
        },
    }
    meta_path = MODEL_DIR / f"{model_type}_{symbol}_{TIMEFRAME}_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    results = {
        "version": "v3",
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "model_type": model_type,
        "n_features": len(feature_names),
        "target_config": {
            "forward_horizon": target_config.forward_horizon,
            "long_threshold": target_config.long_threshold,
            "short_threshold": target_config.short_threshold,
        },
        "train_samples": len(y_train),
        "test_samples": len(y_test),
        "ml_metrics": {
            "accuracy": report.ml_metrics.accuracy,
            "precision": report.ml_metrics.precision_macro,
            "recall": report.ml_metrics.recall_macro,
            "f1_macro": report.ml_metrics.f1_macro,
            "auc_roc": report.ml_metrics.auc_roc_ovr,
        },
        "trading_metrics": {
            "signal_hit_rate": report.trading_metrics.signal_hit_rate,
            "long_hit_rate": report.trading_metrics.long_hit_rate,
            "short_hit_rate": report.trading_metrics.short_hit_rate,
            "avg_return_long": report.trading_metrics.avg_return_long,
            "avg_return_short": report.trading_metrics.avg_return_short,
            "signal_profit_factor": report.trading_metrics.signal_profit_factor,
            "total_signals": report.trading_metrics.total_signals,
            "long_signals": report.trading_metrics.long_signals,
            "short_signals": report.trading_metrics.short_signals,
        },
        "top_features": report.top_features[:20],
    }

    if report.overfit_metrics:
        results["overfit_metrics"] = {
            "is_accuracy": report.overfit_metrics.is_accuracy,
            "oos_accuracy": report.overfit_metrics.oos_accuracy,
            "accuracy_degradation": report.overfit_metrics.accuracy_degradation,
            "overfit_score": report.overfit_metrics.overfit_score,
        }

    # ── Walk-Forward ─────────────────────────────────────────
    if run_walk_forward:
        print(f"\n  ── Walk-Forward ML Training (v3) ──")
        wf_config = WFTrainConfig(
            n_splits=5,
            train_pct=0.70,
            window_type="expanding",
            min_train_samples=1000,
            purge_gap=target_config.forward_horizon,
        )

        X_full, y_full, ts_full, feat_names = builder.build_for_walk_forward(df)
        X_full_clean = np.nan_to_num(X_full, nan=0.0, posinf=0.0, neginf=0.0)

        wf_trainer = WalkForwardTrainer(wf_config)
        wf_result = wf_trainer.run(
            model_factory=lambda: create_model(model_type),
            X=X_full_clean,
            y=y_full,
            timestamps=ts_full.values,
            feature_names=feat_names,
        )

        wf_report = evaluator.evaluate(
            y_true=wf_result.all_oos_labels,
            y_pred=wf_result.all_oos_predictions,
            y_proba=wf_result.all_oos_probabilities,
            feature_importance=wf_result.aggregate_feature_importance,
        )

        print(f"    OOS Accuracy:    {wf_report.ml_metrics.accuracy:.4f}")
        print(f"    OOS F1 (macro):  {wf_report.ml_metrics.f1_macro:.4f}")
        print(f"    OOS Hit Rate:    {wf_report.trading_metrics.signal_hit_rate:.4f}")
        print(f"    OOS Signals: {wf_report.trading_metrics.long_signals}L / "
              f"{wf_report.trading_metrics.short_signals}S / "
              f"{wf_report.trading_metrics.neutral_signals}N")

        for w in wf_result.windows:
            acc = float(np.mean(w.test_predictions == w.test_labels))
            n_dir = int(np.sum(w.test_predictions != 0))
            print(f"    Window {w.window_idx}: acc={acc:.4f}, directional={n_dir}")

        results["walk_forward"] = {
            "oos_accuracy": wf_report.ml_metrics.accuracy,
            "oos_f1_macro": wf_report.ml_metrics.f1_macro,
            "oos_hit_rate": wf_report.trading_metrics.signal_hit_rate,
            "oos_long_signals": wf_report.trading_metrics.long_signals,
            "oos_short_signals": wf_report.trading_metrics.short_signals,
            "oos_profit_factor": wf_report.trading_metrics.signal_profit_factor,
        }

        # Top WF features (shows which alpha features matter OOS)
        wf_top = sorted(
            wf_result.aggregate_feature_importance.items(),
            key=lambda x: x[1], reverse=True,
        )[:15]
        print(f"\n    ── Top 15 WF Features ──")
        for name, imp in wf_top:
            marker = " [NEW]" if any(name.startswith(p) for p in [
                "funding_", "liq_", "oi_", "basis_", "ob_"
            ]) else ""
            print(f"      {name:<35s} {imp:.4f}{marker}")
        results["walk_forward"]["top_features"] = wf_top

    # Save results
    results_path = REPORT_DIR / f"{model_type}_{symbol}_{TIMEFRAME}_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


def main():
    parser = argparse.ArgumentParser(description="CoinScopeAI ML Training v3 (Phase 2 Alpha)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT")
    parser.add_argument("--model", type=str, default="lgbm", choices=["lgbm", "logreg"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-walk-forward", action="store_true")
    args = parser.parse_args()

    print("=" * 70)
    print(" CoinScopeAI — ML v3: Phase 2 Alpha Features")
    print(f" {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    all_results = {}

    if args.all:
        for symbol in SYMBOLS:
            for model_type in ["lgbm", "logreg"]:
                key = f"v3_{model_type}_{symbol}_{TIMEFRAME}"
                try:
                    results = train_and_evaluate(
                        symbol, model_type,
                        run_walk_forward=not args.no_walk_forward,
                    )
                    all_results[key] = results
                except Exception as e:
                    print(f"\n  ERROR [{key}]: {e}")
                    import traceback
                    traceback.print_exc()
    else:
        for model_type in ["lgbm", "logreg"]:
            key = f"v3_{model_type}_{args.symbol}_{TIMEFRAME}"
            try:
                results = train_and_evaluate(
                    args.symbol, model_type,
                    run_walk_forward=not args.no_walk_forward,
                )
                all_results[key] = results
            except Exception as e:
                print(f"\n  ERROR [{key}]: {e}")
                import traceback
                traceback.print_exc()

    # Print comparison summary
    if all_results:
        print(f"\n{'=' * 130}")
        print(f" v3 SUMMARY — Phase 2 Alpha Features (4h timeframe)")
        print(f"{'=' * 130}")
        print(f"{'Config':<35s} {'Feats':>5s} {'Acc':>6s} {'F1':>6s} {'AUC':>6s} "
              f"{'HitR':>6s} {'PF':>6s} {'WF_Acc':>7s} {'WF_F1':>6s} {'WF_Hit':>7s}")
        print(f"{'-' * 130}")

        for key, r in all_results.items():
            ml = r.get("ml_metrics", {})
            tr = r.get("trading_metrics", {})
            wf = r.get("walk_forward", {})
            print(f"{key:<35s} "
                  f"{r.get('n_features', 0):>5d} "
                  f"{ml.get('accuracy', 0):>6.3f} "
                  f"{ml.get('f1_macro', 0):>6.3f} "
                  f"{ml.get('auc_roc', 0):>6.3f} "
                  f"{tr.get('signal_hit_rate', 0):>6.3f} "
                  f"{tr.get('signal_profit_factor', 0):>6.3f} "
                  f"{wf.get('oos_accuracy', 0):>7.3f} "
                  f"{wf.get('oos_f1_macro', 0):>6.3f} "
                  f"{wf.get('oos_hit_rate', 0):>7.3f}")

        # Save aggregate
        agg_path = REPORT_DIR / "v3_aggregate_results.json"
        agg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(agg_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Aggregate results saved to: {agg_path}")


if __name__ == "__main__":
    main()
