# Architecture Decision Records

**Status:** current
**Audience:** anyone trying to understand *why* the engine is shaped the way it is
**Related:** [`TEMPLATE.md`](TEMPLATE.md), [`../architecture/system-overview.md`](../architecture/system-overview.md)

ADRs are short, durable records of architectural decisions. They capture the context, the choice, and the consequences so that a future reader (possibly you, six months from now) can tell whether a decision still makes sense or whether its premises have changed.

## When to write one

Write an ADR when:

- You're picking one technology over another for a structural concern (language, framework, data store, messaging layer).
- You're setting a rule that will constrain future PRs (e.g., "no LLM on the hot path").
- You're deviating from the "obvious" choice for a reason that will confuse later readers.

Don't write one for:

- Routine implementation choices (a helper module structure, a variable name).
- Temporary workarounds (those go in `docs/incidents/` or inline comments).
- Things already documented in a runbook or architecture doc.

## Numbering

ADRs are numbered sequentially: `adr-0001-*.md`, `adr-0002-*.md`, etc. Numbers are permanent. If a decision is superseded, write a new ADR referencing the old one; do not renumber.

## Statuses

- **proposed** — open for discussion.
- **accepted** — in force.
- **superseded by adr-XXXX** — replaced; the superseding ADR explains why.
- **deprecated** — no longer in force and not replaced; rare.

## Current ADRs

| # | Title | Status |
| --- | --- | --- |
| [0001](adr-0001-fastapi-and-uvicorn.md) | FastAPI and Uvicorn as the web stack | accepted |
| [0002](adr-0002-redis-celery-for-workers.md) | Redis + Celery for the async worker path | accepted |
| [0003](adr-0003-llm-off-hot-path.md) | No LLM on the trading hot path | accepted |

Future candidates (not written yet):

- ADR on why we hand-write adapters instead of using ccxt in the live path (covered briefly in [`../ops/exchange-integrations.md`](../ops/exchange-integrations.md)).
- ADR on fractional Kelly with a hard cap (covered in [`../risk/position-sizing.md`](../risk/position-sizing.md)).
- ADR on Docker Compose over Kubernetes for the validation-era footprint.

These may become ADRs post-validation if the team feels the rationales warrant a canonical record.

## How to propose a new ADR

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `adr-NNNN-short-title.md` (next number in sequence).
2. Fill it in. Keep it to ~1–2 pages.
3. Open a PR titled `adr: <short title>`.
4. Get review from at least one engineer who would be affected by the decision.
5. On merge, set status to `accepted`. If the discussion kills the ADR, set status to `deprecated` and keep it in the tree as a record of the conversation.

ADRs are reviewed like code. A thin ADR that handwaves the rationale is not useful; a 10-page ADR is not an ADR.

## What a good ADR looks like

- One decision per ADR.
- The context is concrete (what exists today, what forces pushed the decision).
- The decision is stated in one or two sentences.
- The alternatives considered are named with one-sentence reasons they lost.
- The consequences — both positive and negative — are honest.

If a reviewer reads the ADR and can't disagree on anything because everything is phrased as inevitable, it isn't doing its job.
