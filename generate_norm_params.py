"""
Generate and save normalization parameters for v2 models.
These are needed by the paper trading signal engine to normalize
features the same way they were normalized during training.

The v2 training used V2DatasetBuilder which computes z-score params
from the training split. We replicate that here using the same data
and the same 60/20/20 split.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from ai.features.engine_v2 import LongTFFeatureEngine, LongTFFeatureConfig
from services.backtesting.data_loader import DataLoader

DATA_DIR = Path("data/raw")
MODEL_DIR = Path("models/v2")

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

# Use the same feature config as training
feature_config = LongTFFeatureConfig(
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
)

for symbol in SYMBOLS:
    print(f"\n{'='*60}")
    print(f"  Generating norm_params for {symbol} 4h")
    
    csv_path = DATA_DIR / f"{symbol}_4h.csv"
    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        continue
    
    df = DataLoader.from_csv(str(csv_path), symbol=symbol, timeframe="4h")
    print(f"  Data: {len(df)} candles")
    
    engine = LongTFFeatureEngine(feature_config)
    features = engine.extract(df)
    feat_cols = list(features.columns)
    print(f"  Features: {len(feat_cols)}")
    
    # Drop NaN rows
    valid = features.notna().all(axis=1)
    features_clean = features[valid].reset_index(drop=True)
    print(f"  Valid rows: {len(features_clean)}")
    
    # Use 60% training split (same as V2DatasetBuilder)
    train_end = int(len(features_clean) * 0.60)
    train_df = features_clean.iloc[:train_end]
    print(f"  Training rows: {len(train_df)}")
    
    # Compute norm params from training data only
    norm_params = {}
    for col in feat_cols:
        mean = float(train_df[col].mean())
        std = float(train_df[col].std())
        if std == 0 or np.isnan(std):
            std = 1.0
        norm_params[col] = (mean, std)
    
    # Save
    out_path = MODEL_DIR / f"norm_params_{symbol}_4h.joblib"
    joblib.dump(norm_params, str(out_path))
    print(f"  Saved: {out_path} ({len(norm_params)} features)")
    
    # Verify
    loaded = joblib.load(str(out_path))
    assert len(loaded) == len(norm_params)
    print(f"  Verified: {len(loaded)} params loaded back")

print(f"\n{'='*60}")
print("Done. Norm params saved for all symbols.")
