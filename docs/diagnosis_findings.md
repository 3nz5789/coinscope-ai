# Signal Generation Failure Diagnosis

## Root Causes Found

### Bug 1: API Mismatch — `compute()` vs `extract()`
- `signal_engine.py` line 308 calls `self._feature_engine.compute(df)` 
- Both `FeatureEngine` and `LongTFFeatureEngine` expose `extract(df)`, NOT `compute()`
- This causes: `'FeatureEngine' object has no attribute 'compute'`

### Bug 2: Wrong Class Name in Import
- `signal_engine.py` line 297 tries: `from ai.features.engine_v2 import FeatureEngineV2`
- The actual class name is `LongTFFeatureEngine`, not `FeatureEngineV2`
- Import fails, falls back to `FeatureEngine` (v1), which also fails on `compute()`

### Bug 3: Missing `timestamp` Column
- Buffer stores candles as dicts with `open_time` but no `timestamp`
- `LongTFFeatureEngine.extract()` requires a `timestamp` column for temporal features
- Even after fixing bugs 1 and 2, feature extraction would fail on missing timestamp

### Bug 4: No Normalization Params Saved with Model
- v2 models were saved as raw classifier objects (no metadata dict)
- `signal_engine.load_model()` checks for dict format but gets raw classifier
- Result: `_feature_names` comes from model, but `_norm_params` is empty
- Without norm_params, features are fed unnormalized → model predictions are unreliable

### Bug 5: v1 FeatureEngine Produces 54 Features, Model Expects 112
- Even if `compute()` → `extract()` was fixed, v1 engine only produces 54/112 features
- Signal engine would see <80% features available and return None (line 213-217)

## Impact Chain
1. Import `FeatureEngineV2` fails → falls back to `FeatureEngine` (v1)
2. Calls `compute()` → AttributeError → returns None
3. No features → no prediction → no signal → no trade

## What Works
- Candle buffer pre-fill: OK (200 candles per symbol)
- REST fallback: OK (correctly injects missed candles)
- Model loading: OK (112 features, predict_proba works)
- Direct prediction: OK (produces LONG signal with 0.60 confidence)
- Model IS generating actionable signals when fed correct features
