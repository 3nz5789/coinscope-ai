# ADR-0003: No LLM on the trading hot path

**Status:** accepted
**Date:** 2026-03-02
**Authors:** Scoopy, operator
**Related:** [`../ml/ml-overview.md`](../ml/ml-overview.md), [`../risk/risk-framework.md`](../risk/risk-framework.md), [`../architecture/data-flow.md`](../architecture/data-flow.md)

## Context

There is an ongoing industry push to put LLMs into more systems, including trading systems. The engine's author works extensively with Claude and LLM tooling is easy to reach for. It is worth being explicit about where LLMs belong in this system and where they do not.

The trading hot path is:

```
stream → scanner → scorer → regime gate → Kelly sizer → executor → exchange
```

Each step has a latency budget (see [`../architecture/data-flow.md`](../architecture/data-flow.md)) and a determinism requirement: the same inputs must produce the same decisions, and decisions must be auditable from journal entries alone.

LLMs are non-deterministic even at temperature zero, have bounded tail latency variance in practice, and cost dollars-per-thousand-tokens in a way that doesn't scale to per-candidate invocation at the engine's event rate.

There are good places for LLMs in this system. The hot path is not one of them.

## Decision

**No LLM invocation appears on the trading hot path.**

Specifically:

- The scanner does not call an LLM.
- The scorer does not call an LLM.
- The risk gate does not call an LLM.
- The Kelly sizer does not call an LLM.
- The executor does not call an LLM.
- The adapter does not call an LLM.

LLMs are acceptable for:

- **Research and development** — feature engineering notebooks, backtest analysis summaries, data exploration.
- **Documentation generation** — what's happening in this document tree is fine.
- **Operator assistance** — the `coinscopeai-skills` bundle and `@ScoopyAI_bot` on Telegram for operator commands. These are explicitly *out-of-band* from trading decisions.
- **Post-trade analysis** — narrative summaries of a day's journal for humans. Runs off the critical path.

Anything that reads from the live cache and returns a value that influences a trade must be deterministic code.

## Alternatives considered

- **Allow LLMs for "soft" scoring** (e.g., LLM-generated confidence on news events). Lost because: (a) news-driven strategies are not in scope during validation; (b) the determinism and latency cost is not worth the partial signal; (c) once allowed anywhere on the path, the fence is broken.
- **Use an LLM as a "safety layer" that reviews candidates before execution.** Lost because: (a) an LLM that says "no" unpredictably is a new failure mode; (b) the deterministic risk gate already serves this purpose.
- **Use an LLM for regime detection.** Lost because: (a) the HMM and v3 classifier are both fast and explainable; (b) an LLM regime detector would be harder to retrain and harder to audit.
- **Status quo — don't write this rule down.** Lost because every few weeks someone asks "can we add an LLM here?" and a fresh answer each time is worse than a cited ADR.

## Consequences

**Positive:**

- Determinism is preserved. The same stream replay yields the same decisions, which is a requirement for meaningful regression testing.
- Latency budget stays intact. The hot path's tail is bounded by code we wrote.
- No dollar-per-decision inference cost.
- Auditing a trade is reading code and journal entries, not inspecting LLM outputs.

**Negative / costs:**

- We cannot trivially incorporate unstructured signals (news, social, filings) into scoring. Teams that do this report mixed results; the cost of not doing it is uncertain but real.
- We cannot offer a "natural language explanation" for every trade decision out of the box. The journal's structured fields are what we have.
- New hires sometimes expect LLMs where there are none. That expectation needs correction early; this ADR is a tool for that.

**Neutral but worth noting:**

- The project's branding (Scoopy, AI-driven) does not imply LLM-driven. ML and LLM are distinct.
- Off-hot-path LLM usage is not only allowed, it's encouraged where it helps the operator.

## Revisit when

- A reproducibility-preserving way to use LLM outputs in trading decisions emerges (e.g., cached deterministic outputs over bounded input spaces with explicit invalidation).
- Post-validation, a research thread produces a quantified uplift from structured news scoring that justifies adding a non-LLM news classifier (note: even then, it's a classifier, not an LLM).
- The field changes such that deterministic, sub-millisecond, free LLMs exist. This is not imminent.

## Notes

This ADR is cited by [`../ml/ml-overview.md`](../ml/ml-overview.md) and [`../risk/risk-framework.md`](../risk/risk-framework.md). If it is ever changed, both of those docs need updating in the same PR.
