"""
Diagnose why the paper trading engine isn't generating signals.
Tests the full pipeline: data → features → normalize → predict → filter.
"""
import sys
sys.path.insert(0, ".")

import numpy as np
import pandas as pd
import joblib

# 1. Load model
print("=" * 60)
print("STEP 1: Load model")
model = joblib.load("models/v2/logreg_BTCUSDT_4h.joblib")
print(f"  Model type: {type(model).__name__}")
print(f"  Feature names: {len(model._feature_names)}")
print(f"  Has predict_proba: {hasattr(model, 'predict_proba')}")

# 2. Fetch historical candles (same as engine prefill)
print("\n" + "=" * 60)
print("STEP 2: Fetch candles from testnet")
from services.paper_trading.exchange_client import BinanceFuturesTestnetClient
from services.paper_trading.config import ExchangeConfig

client = BinanceFuturesTestnetClient(ExchangeConfig())
client.ping()
print("  Exchange connection: OK")

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
for symbol in symbols:
    klines = client.get_klines(symbol=symbol, interval="4h", limit=200)
    print(f"  {symbol}: {len(klines)} candles fetched")

# 3. Test feature engine import
print("\n" + "=" * 60)
print("STEP 3: Test feature engine import")
try:
    from ai.features.engine_v2 import FeatureEngineV2
    print("  FOUND: ai.features.engine_v2.FeatureEngineV2")
except ImportError as e:
    print(f"  MISSING: FeatureEngineV2 - {e}")

try:
    from ai.features.engine_v2 import LongTFFeatureEngine
    print("  FOUND: ai.features.engine_v2.LongTFFeatureEngine")
except ImportError as e:
    print(f"  MISSING: LongTFFeatureEngine - {e}")

try:
    from ai.features.engine import FeatureEngine
    print("  FOUND: ai.features.engine.FeatureEngine")
    fe = FeatureEngine()
    print(f"  FeatureEngine methods: {[m for m in dir(fe) if not m.startswith('_') and callable(getattr(fe, m))]}")
except ImportError as e:
    print(f"  MISSING: FeatureEngine - {e}")

# 4. Test feature computation with both engines
print("\n" + "=" * 60)
print("STEP 4: Test feature computation")

# Build DataFrame from klines
klines = client.get_klines(symbol="BTCUSDT", interval="4h", limit=200)
df = pd.DataFrame(klines, columns=[
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades", "taker_buy_base",
    "taker_buy_quote", "ignore",
])
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")
print(f"  DataFrame shape: {df.shape}")
print(f"  Columns: {list(df.columns)}")

# Test with LongTFFeatureEngine (correct engine)
from ai.features.engine_v2 import LongTFFeatureEngine, LongTFFeatureConfig
ltf_engine = LongTFFeatureEngine()
features = ltf_engine.extract(df)
print(f"  LongTFFeatureEngine features: {len(features.columns)} features, {len(features)} rows")
print(f"  Feature names match model: {set(model._feature_names).issubset(set(features.columns))}")
missing = set(model._feature_names) - set(features.columns)
extra = set(features.columns) - set(model._feature_names)
if missing:
    print(f"  MISSING from features: {missing}")
if extra:
    print(f"  EXTRA in features (not in model): {len(extra)}")

# Test with FeatureEngine (what signal_engine falls back to)
fe = FeatureEngine()
features_v1 = fe.extract(df)
print(f"  FeatureEngine (v1) features: {len(features_v1.columns)} features")
missing_v1 = set(model._feature_names) - set(features_v1.columns)
print(f"  v1 missing model features: {len(missing_v1)} ({len(missing_v1)}/{len(model._feature_names)})")

# 5. Test the signal engine's _compute_features path
print("\n" + "=" * 60)
print("STEP 5: Test signal engine _compute_features")

from services.paper_trading.signal_engine import MLSignalEngine
sig_engine = MLSignalEngine()
sig_engine.load_model("models/v2/logreg_BTCUSDT_4h.joblib")

# Build buffer-style DataFrame (no timestamp column)
buf_df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
print(f"  Buffer DataFrame columns: {list(buf_df.columns)}")

try:
    result = sig_engine._compute_features(buf_df)
    if result is not None:
        print(f"  _compute_features returned: {result.shape}")
    else:
        print("  _compute_features returned: None")
except Exception as e:
    print(f"  _compute_features ERROR: {e}")
    import traceback
    traceback.print_exc()

# 5b. Test with timestamp column added
buf_df2 = buf_df.copy()
buf_df2["timestamp"] = pd.to_datetime(buf_df2["open_time"], unit="ms")
try:
    sig_engine._feature_engine = None  # Reset
    result2 = sig_engine._compute_features(buf_df2)
    if result2 is not None:
        print(f"  _compute_features (with timestamp) returned: {result2.shape}")
    else:
        print("  _compute_features (with timestamp) returned: None")
except Exception as e:
    print(f"  _compute_features (with timestamp) ERROR: {e}")

# 6. Test full signal generation
print("\n" + "=" * 60)
print("STEP 6: Test full signal generation")

# Initialize buffer properly
sig_engine2 = MLSignalEngine(min_confidence=0.42, min_edge=0.05)
sig_engine2.load_model("models/v2/logreg_BTCUSDT_4h.joblib")

# Pre-fill buffer
hist_df = df.copy()
sig_engine2.initialize_buffer("BTCUSDT", hist_df)
print(f"  Buffer size: {len(sig_engine2._buffers['BTCUSDT'])}")

# Simulate a closed candle
last_candle = klines[-1]
signal = sig_engine2.process_candle(
    symbol="BTCUSDT",
    open_time=int(last_candle[0]),
    open_price=float(last_candle[1]),
    high=float(last_candle[2]),
    low=float(last_candle[3]),
    close=float(last_candle[4]),
    volume=float(last_candle[5]),
    is_closed=True,
)
print(f"  Signal result: {signal}")
if signal:
    print(f"  Direction: {signal.direction}")
    print(f"  Confidence: {signal.confidence:.4f}")
    print(f"  Edge: {signal.edge:.4f}")
    print(f"  Probabilities: {signal.probabilities}")

# 7. Check what the model actually predicts
print("\n" + "=" * 60)
print("STEP 7: Direct model prediction test")

# Use correct feature engine
ltf = LongTFFeatureEngine()
feats = ltf.extract(df)
latest = feats.iloc[-1:]

# Select model features
available = [f for f in model._feature_names if f in latest.columns]
print(f"  Available features: {len(available)}/{len(model._feature_names)}")
X = latest[available].copy()
for f in model._feature_names:
    if f not in X.columns:
        X[f] = 0.0
X = X[model._feature_names]
X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

proba = model.predict_proba(X.values)[0]
print(f"  Raw probabilities (S/N/L): {proba}")
print(f"  Predicted class: {np.argmax(proba)} ({['SHORT', 'NEUTRAL', 'LONG'][np.argmax(proba)]})")
print(f"  Max confidence: {np.max(proba):.4f}")

# With normalization (simulate what training did)
print("\n  --- With z-score normalization ---")
# We don't have saved norm_params, so compute from the 200 candles
feats_all = ltf.extract(df)
means = feats_all.mean()
stds = feats_all.std()
stds = stds.replace(0, 1.0)
feats_normed = (feats_all - means) / stds
latest_normed = feats_normed.iloc[-1:]
X_norm = latest_normed[available].copy()
for f in model._feature_names:
    if f not in X_norm.columns:
        X_norm[f] = 0.0
X_norm = X_norm[model._feature_names]
X_norm = X_norm.replace([np.inf, -np.inf], np.nan).fillna(0)

proba_norm = model.predict_proba(X_norm.values)[0]
print(f"  Normalized probabilities (S/N/L): {proba_norm}")
print(f"  Predicted class: {np.argmax(proba_norm)} ({['SHORT', 'NEUTRAL', 'LONG'][np.argmax(proba_norm)]})")
print(f"  Max confidence: {np.max(proba_norm):.4f}")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
