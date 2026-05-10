# Confidence Scoring

**Status:** current
**Audience:** engineers working on the signal pipeline or regime classifier
**Related:** [`regime-detection.md`](regime-detection.md), [`../risk/position-sizing.md`](../risk/position-sizing.md), [`../risk/risk-gate.md`](../risk/risk-gate.md)

---

## What is confidence?

Confidence is a per-signal estimate of how reliable a regime label or signal score is likely to be, expressed as a value in `[0, 1]`. It is distinct from the confluence score:

| | Confluence score | Confidence |
|---|---|---|
| **What it measures** | Multi-factor signal strength (0–100) | Reliability of the regime classification |
| **Computed by** | `ConfluenceScorer` | `RegimeDetector` (HMM posterior) |
| **Used by** | Risk gate (signal accept/reject) | Signal suppression, Kelly multiplier selection |
| **Range** | 0–100 | 0.0–1.0 |

---

## How confidence is computed

The HMM regime detector produces a posterior probability distribution over states for each bar. Confidence is the probability assigned to the most likely state:

```
confidence = max(posterior[t])
```

Where `posterior[t]` is the vector of state probabilities at time `t`, computed via the forward-backward algorithm.

A high confidence value (e.g. `0.90`) means the HMM strongly believes the market is in one regime. A low value (e.g. `0.55`) means regime identity is ambiguous — the market is transitioning or the model is uncertain.

---

## Confidence threshold

**`MIN_REGIME_CONFIDENCE = 0.55`** (configurable via env var)

Signals are suppressed when confidence is below this floor. This is enforced in the scoring pipeline before signals reach the risk gate:

```python
if regime_result.confidence < settings.min_regime_confidence:
    logger.debug("Signal suppressed — low regime confidence: %.2f", regime_result.confidence)
    return None
```

Rationale: below 0.55 the regime label is essentially a coin flip between two states. Acting on regime-informed sizing in this state adds noise rather than edge.

---

## Confidence in the Kelly pipeline

Regime confidence also feeds into position sizing indirectly — the Kelly multiplier is selected by regime label, and a low-confidence label defaults to the more conservative multiplier:

| Confidence | Behaviour |
|---|---|
| `≥ 0.55` | Use the detected regime's Kelly multiplier (1.0×, 0.5×, or 0.3×) |
| `< 0.55` | Signal suppressed — no position sized |

This means there is no intermediate "reduced size for uncertain regime" path. The choice is binary: confident enough to act at regime-appropriate size, or suppressed entirely. This is intentional — partial confidence does not justify partial exposure.

---

## Confidence in Telegram alerts

Every alert includes regime label and confidence so the operator can calibrate their own judgment:

```
📊 BTCUSDT LONG  score=82  regime=Trending (conf=0.87)
Entry: 67,240  SL: 66,100  TP: 69,520
```

An alert with `conf=0.91` in a Trending regime is materially different from one with `conf=0.57` in the same regime. The operator should treat low-confidence alerts with more caution even when the confluence score is high.

---

## Confidence baseline

The confidence baseline (`docs/ml/confidence_scoring_baseline.md`) documents the distribution of confidence values observed across the testnet validation dataset, by regime:

| Regime | Median confidence | P10 | P90 |
|---|---|---|---|
| Trending | 0.82 | 0.61 | 0.94 |
| Mean-Reverting | 0.74 | 0.58 | 0.89 |
| Volatile | 0.79 | 0.62 | 0.93 |
| Quiet | 0.68 | 0.55 | 0.84 |

Quiet regime has the lowest median confidence — consistent with its definition as a low-information state that often precedes regime transitions.

---

## Tuning the threshold

`MIN_REGIME_CONFIDENCE` is locked during P0 validation at `0.55`. Post-validation, it should be tuned against the WFV dataset:

- **Raising** the threshold (e.g. to `0.65`) suppresses more signals but improves regime-label reliability for acted signals.
- **Lowering** it (e.g. to `0.45`) increases signal volume but degrades regime confidence across the acted set.

Any change requires a `strategy_change` issue and two reviewers. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

---

## Reading order

1. [`regime-detection.md`](regime-detection.md) — how the HMM is trained and how posteriors are computed
2. [`../risk/position-sizing.md`](../risk/position-sizing.md) — how regime label feeds into Kelly multiplier
3. [`../risk/risk-gate.md`](../risk/risk-gate.md) — where confidence suppression happens in the gate flow
