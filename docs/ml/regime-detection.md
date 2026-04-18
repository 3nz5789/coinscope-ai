# Regime Detection

**Status:** current
**Audience:** developers working with regime outputs, the scorer, the Kelly sizer, or the risk gate
**Related:** [`ml-overview.md`](ml-overview.md), [`../risk/position-sizing.md`](../risk/position-sizing.md), [`../risk/risk-gate.md`](../risk/risk-gate.md)

CoinScopeAI runs **two regime detectors in parallel**. This is intentional. New readers often expect one; the repo has both because each serves a different purpose and the consolidation is a post-validation item.

This page explains what each detector does, who consumes it, and how to keep them coherent.

## The two systems at a glance

| | HMM detector | v3 classifier |
| --- | --- | --- |
| **Labels** | `bull`, `bear`, `chop` | `Trending`, `Mean-Reverting`, `Volatile`, `Quiet` |
| **Count** | 3 states | 4 labels |
| **Library** | `hmmlearn` | `scikit-learn` + `xgboost` |
| **Model type** | Hidden Markov Model on log-returns | Supervised classifier on engineered features |
| **Artifact** | `ml/artifacts/hmm.pkl` (default) | `ml/artifacts/regime_v3.joblib` (default) |
| **Refresh cadence** | `REGIME_REFRESH_SECONDS` (default 300s) | `REGIME_REFRESH_SECONDS` (default 300s) |
| **Primary consumers** | Kelly sizer's regime multiplier table; legacy gate alignment check | Scorer's per-regime scoring floor |
| **Age** | Original system | Added later for finer labels |

Both detectors are authoritative for their own consumers. Neither is "the truth"; they describe the market from different angles.

## HMM detector

A three-state Hidden Markov Model fit to recent log-returns of a reference basket (typically BTC and ETH). `hmmlearn` handles the Baum-Welch training offline; the engine loads the fitted model and runs Viterbi decoding at each refresh.

### Labels

- **bull** — the HMM has identified the current hidden state as the "trending up, low-volatility-of-volatility" state.
- **bear** — the "trending down" state, usually with higher realized volatility.
- **chop** — the high-variance, directionless state.

The label mapping (state-index → name) is fixed at training time and persisted with the artifact. The engine does not relabel at runtime.

### Consumers

- **Kelly sizer.** Uses the HMM label as the key into the regime multiplier table (bull 1.0, chop 0.5, bear 0.3). See [`../risk/position-sizing.md`](../risk/position-sizing.md).
- **Risk gate.** Uses the HMM label for the regime-alignment check (long in bear → reject).
- **Journal.** Labels are journaled on every regime flip.

### Why HMM

HMMs are well-suited to a small number of hidden states that change slowly. Three states are enough to express "trend up / trend down / noise," and the model's probabilistic state transitions give a smoother label stream than a per-candle threshold rule.

## v3 classifier

A supervised four-class classifier. Features are engineered from the live cache (volatility statistics, trend strength, autocorrelation measures, volume profile). scikit-learn pipelines compose the feature transformer with an xgboost classifier head.

### Labels

- **Trending** — directional, sustained moves in one direction.
- **Mean-Reverting** — range-bound, oscillation-dominated.
- **Volatile** — high realized variance, direction ambiguous.
- **Quiet** — low realized variance, compression.

These labels are finer-grained than the HMM's three-state view. In practice, an HMM-chop regime can be v3-Mean-Reverting *or* v3-Quiet, and the scorer cares about the difference.

### Consumers

- **Scorer.** Per-regime scoring floor. `Volatile` raises the floor (fewer, higher-confidence candidates). `Quiet` keeps the default floor but tightens slippage tolerances elsewhere.
- **Future strategy components.** New strategies introduced after validation will consume v3 labels by default; the HMM will remain the authority for sizing.

### Why v3

Supervised classifiers can learn from labeled historical data in ways an HMM cannot. The four-label taxonomy matches how we think about strategy selection: trending vs. mean-reverting strategies behave very differently in volatile vs. quiet conditions.

## How they coexist

The two detectors are never combined into one label. Each consumer reads the detector it cares about:

```
               ┌─── bull / bear / chop ──→ Kelly sizer multiplier
HMM detector ──┤
               └─── bull / bear / chop ──→ gate alignment check

                       ┌── Trending ────→ scorer floor (normal)
                       ├── Mean-Reverting→ scorer floor (normal)
v3 classifier ────────┤
                       ├── Volatile ────→ scorer floor (raised)
                       └── Quiet ───────→ scorer floor (normal) + tighter slippage
```

The `/regime/{symbol}` API returns both labels so the dashboard and operator can see them side by side.

## Keeping the two coherent

Coexisting models must not drift apart silently. A few rules:

- **Fit both on the same training window.** Retraining one without the other is a yellow flag and needs an explicit decision.
- **Alert on disagreement patterns.** If the HMM says chop but the v3 classifier persistently reports Trending for an extended window, something is wrong with one of them. A disagreement monitor is planned post-validation.
- **Document consumer changes in both directions.** If you change a scorer floor based on v3, and that implicitly affects the HMM-regime distribution the sizer sees, document it.

## Journaling

Every regime refresh writes a `regime_flip` event when either detector's label changes. The payload includes:

- `detector` — `hmm` or `v3`.
- `previous_label`, `new_label`.
- `confidence` — the detector's reported confidence or posterior.
- `as_of` — the cache timestamp used.

Regime flips are visible on the dashboard and via `/journal?event_type=regime_flip`.

## Failure modes

- **Artifact missing at boot.** Engine fails to start. Required env var was unset or path was wrong.
- **Feature vector shape mismatch.** Inference fails loudly; the detector reports no label for that refresh; the gate rejects with `stale_data`.
- **Label "pinned" for long windows.** Likely a training-data shift. Retrain post-validation.
- **Disagreement between detectors.** Possible in legitimate cases (HMM-bear / v3-Trending can happen during a strong down-move). Persistent wide disagreement is a signal to investigate.

## Testing

Unit tests cover:

- Correct label mapping from artifact state-index order.
- Feature vector assembly for each model.
- Failure modes (missing artifact, shape mismatch).
- Journaling on label change (but not on repeat labels).

Tests live at `coinscope_trading_engine/tests/test_regime_*`.

## Queued work (post-validation)

- Unified regime service that exposes both taxonomies via one module, so consumers do not reach across layers.
- Cross-detector monitor for disagreement patterns and label distribution drift.
- Retraining cadence and a documented re-deploy procedure.

These are listed in [`../product/implementation-backlog.md`](../product/implementation-backlog.md).
