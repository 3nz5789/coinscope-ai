# ML Overview

**Status:** current
**Audience:** anyone extending the ML layer or integrating its outputs
**Related:** [`regime-detection.md`](regime-detection.md), [`../architecture/component-map.md`](../architecture/component-map.md), [`../risk/position-sizing.md`](../risk/position-sizing.md)

The CoinScopeAI ML stack is deliberately classical: **scikit-learn + hmmlearn + xgboost**, all CPU, all offline training. No PyTorch, no TensorFlow, no GPU, no online learning. That's a real choice, not a gap.

If you expect a neural network on the hot path, you are in the wrong mental model.

## What ML does in this engine

Two jobs, no more:

1. **Regime classification.** Two models run in parallel — an HMM for bull/bear/chop and a v3 classifier for Trending/Mean-Reverting/Volatile/Quiet. The risk gate and sizer consume their outputs. Full detail in [`regime-detection.md`](regime-detection.md).
2. **Factor scoring support.** xgboost models contribute to a subset of the confluence factors (e.g., entry timing). The scorer composes their outputs with hand-crafted factors (RSI, EMA, ATR).

What ML explicitly does **not** do:

- It does not place orders.
- It does not gate trades — the gate is deterministic rules operating on ML outputs, not ML itself.
- It does not size positions — the Kelly sizer is deterministic.
- It does not train at runtime. Training is a separate pipeline in `/ml`.

## Stack

| Library | Used for | Why |
| --- | --- | --- |
| `scikit-learn` | Classical classifiers, preprocessing, pipelines | Ubiquitous, stable, deterministic. |
| `hmmlearn` | Hidden Markov Model for regime | Classical probabilistic state model, good fit for three-state regime. |
| `xgboost` | Gradient-boosted classifiers / regressors | Strong on tabular time-series features, CPU-friendly. |
| `pandas` / `numpy` | Data wrangling, feature computation | Standard. |
| `joblib` / `pickle` | Artifact serialization | Standard. scikit-learn saves via joblib; HMM via pickle. |

We do **not** use:

- PyTorch or TensorFlow. Older briefs mentioned them — that was wrong.
- ONNX or TorchScript. Models load as native pickles.
- Ray, Dask, or other parallel execution frameworks. Training is offline; inference is single-process.
- A model registry. Artifacts live as files in `ml/artifacts/` and are referenced by env-var path.

## Training pipeline (offline)

Training scripts live in `/ml`. They are run by the operator, not by the engine process. The typical flow:

1. Pull historical data from Binance (klines, funding, OI, liquidations).
2. Compute features in a notebook or script, produce a DataFrame.
3. Train the HMM or the v3 classifier.
4. Evaluate on a held-out window.
5. Serialize the fitted model to `ml/artifacts/<name>.pkl` or `.joblib`.
6. Commit the artifact path and any changed feature code together.

Training metadata (date, feature set, window) is kept in a sidecar file alongside the artifact.

Re-training cadence during validation: **not** in scope. The artifacts shipped at the start of validation are what run for the 30-day window. Re-training resumes after 2026-04-30.

## Inference pipeline (online)

At engine boot:

1. The app reads `REGIME_HMM_ARTIFACT` and `REGIME_V3_ARTIFACT` paths from config.
2. Each artifact is loaded into memory.
3. A missing artifact is a boot-time failure — no silent defaults.
4. Features are computed from the live cache on each regime refresh (default every 5 minutes, `REGIME_REFRESH_SECONDS`).
5. Both detectors emit labels; both are journaled; downstream consumers read the label they care about.

xgboost scorer models follow the same load-at-boot pattern, accessed by the scorer on each candidate evaluation.

## Feature contract

Each saved model expects a fixed ordered tuple of features. The contract lives next to the training script and is asserted at inference time. Mismatches fail loudly.

**Rule:** changing a feature contract is **engine-adjacent**, requires a retrain, a new artifact, and two reviewers per [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md). Loading an old artifact against a new feature list must fail, never silently align.

## Drift and alpha decay

The engine tracks live strategy edge against a rolling window (`ALPHA_DECAY_WINDOW_DAYS`). When observed edge falls below a fraction of historical edge (`ALPHA_DECAY_WARN_THRESHOLD`), an alert fires. Decay alerts are advisory, not halting — the operator decides whether to retrain, change the regime detector, or pause.

Drift of regime labels themselves (e.g., the HMM spending 90% of the week in "chop" where historically it's 60%) is not alerted automatically today. Post-validation, a regime-distribution monitor is a planned addition ([`../architecture/future-state-roadmap.md`](../architecture/future-state-roadmap.md)).

## Reproducibility

- Random seeds are fixed in training scripts.
- Training data snapshots are written to `ml/data/` (gitignored beyond a small sample set).
- Artifact filenames include the training window and a short hash of the feature list.
- Commit the training script, feature list, and artifact path in the same PR.

## Things that often confuse new readers

- **"But the dashboard looks like it's running a model."** No. The dashboard is read-only over the API. Nothing in the UI trains or re-evaluates anything.
- **"Why two regime systems?"** Historical. The HMM came first and is wired into the Kelly multiplier table and legacy gate checks. The v3 classifier was added later for finer-grained labels and drives scoring-floor behavior. Both are documented; neither is going away during validation. See [`regime-detection.md`](regime-detection.md).
- **"Where does the LLM fit in?"** Nowhere on the hot path. See [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md).
- **"Can I train on a GPU?"** You can train however you want, offline. The engine only cares that the artifact loads and infers on CPU in single-process mode.

## Reading order

1. [`regime-detection.md`](regime-detection.md) — the two regime systems in detail.
2. [`../risk/position-sizing.md`](../risk/position-sizing.md) — how regime labels influence size.
3. [`../architecture/data-flow.md`](../architecture/data-flow.md) — where regime outputs plug into the loop.
4. [`../decisions/adr-0003-llm-off-hot-path.md`](../decisions/adr-0003-llm-off-hot-path.md) — why we do not put an LLM here.
