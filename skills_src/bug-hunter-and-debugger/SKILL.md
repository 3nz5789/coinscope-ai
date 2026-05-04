---
name: bug-hunter-and-debugger
description: Engine-API-tuned debug runbook for CoinScopeAI. Disciplined loop — Reproduce → Instrument → Hypothesize → Test → Patch → Verify — anchored to the engine's six endpoints (/scan, /risk-gate, /position-size, /regime/{symbol}, /performance, /journal). Use when a signal looks wrong, a gate behaves unexpectedly, regime labels persist when they shouldn't, performance numbers contradict the journal, or any production-affecting incident is reported. Triggers on "this signal looks wrong", "gate behaved strangely", "regime stuck", "debug this", "investigate this", "something is off", "incident", "RCA", "root cause", "/scan returned weird", "/risk-gate fail explanation".
---

# Bug Hunter and Debugger (Engine-API tuned)

A specialization of generic debugging for CoinScopeAI's engine. The engine is **frozen during the 30-day validation phase**, so the output of this skill is most often a documented diagnosis + proposal — not a merged patch. Patches require an explicit phase exception, logged via `coinscopeai-premortem` and the decision log.

## When to use

- A user (or Scoopy) flags a specific signal that "felt wrong."
- `/risk-gate` blocked or passed something the user didn't expect.
- A regime label persisted across a clear regime change.
- `/performance` numbers don't match the trades visible in `/journal`.
- An incident report names an engine endpoint or a specific symbol/timestamp.

## When NOT to use

- Routine PR review — use `engineering:code-review`.
- New-feature design — use `signal-design-and-backtest` or `scanner-engine-optimizer`.
- Drift between canonical docs (CLAUDE.md vs business-plan) — use `drift-detector`.

## The 6-step loop

### Step 1 — Reproduce

Capture the exact inputs:
- Symbol, side, timestamp (UTC).
- Endpoint involved: one or more of `/scan`, `/risk-gate`, `/position-size`, `/regime/{symbol}`, `/performance`, `/journal`.
- Request payload + response payload (or permission to re-run).

If you can't reproduce, the bug is "unverified" — say so and propose what data is needed.

### Step 2 — Instrument

Pick the smallest diagnostic that disambiguates hypotheses. Examples:
- Add a `journal_note` event with full feature vector at signal time.
- Re-run `/risk-gate` with the same params to compare against the original response (idempotency check).
- Pull `/regime/{symbol}` for ±15m around the incident.

Never add print-debugging to engine code during validation phase. Use the journal.

### Step 3 — Hypothesize

List 2-4 plausible explanations with likelihood labels. Categories:

| Category | Example |
|---|---|
| Model behavior (correct) | Regime model genuinely labeled it Trending |
| Implementation bug | Off-by-one in rolling window |
| Stale data | Funding cached past TTL |
| Misconfigured threshold | Cap or feature threshold drifted from canonical |
| Cap interaction | Heat cap hit before user expected (correct, but surprising) |
| Mock fallback active | Endpoint in mock mode without operator awareness |

### Step 4 — Test

For each hypothesis: a specific, falsifiable check. Examples:
- Replay the bar via `test-and-simulation-lab`.
- Re-run with feature flag toggled.
- Compare against canonical thresholds in `coinscopeai-trading-rules`.

### Step 5 — Patch (or document)

If a bug is confirmed:
- During validation phase → write the patch as a proposal, file under `business-plan/_decisions/` referencing the incident; do not merge.
- Outside validation phase → minimal patch + test in `test-and-simulation-lab` (failing-test-first rule).

If behavior is "weird but correct":
- No patch. Update docs / UX so the next user isn't surprised. Often this becomes work for `alerting-and-user-experience`.

### Step 6 — Verify

- Failing test now passes.
- Replay (if added) reproduces the original incident on `main` and passes on the patch.
- Journal entry created with the full RCA, cross-referenced from the decision log if the change is non-trivial.

## Endpoint-specific debug patterns

### `/scan`

- Confirm regime label aligns with the signal type (long breakout in Quiet is suspicious).
- Confluence score breakdown: which of the 0-12 components fired? Any single component dominating is a smell.
- Mock fallback active? Response should be flagged.

### `/risk-gate`

- Identify the **first failing cap** (leverage / DD / daily_loss / heat / max_positions / regime_restriction).
- Compare cap snapshot to canonical: 10x / 10% / 5% / 80% / 5 positions.
- Idempotency check: same request twice → same response.

### `/position-size`

- Sized against current heat? Current account equity? Current leverage cap?
- Output bounded by `min(leverage_cap, heat_cap, account_equity)` — verify the binding constraint matches expectation.

### `/regime/{symbol}`

- Confidence in [0,1]?
- Last update timestamp within the bar interval? (Stale label is the common bug.)
- Manual override active? Should be visible.

### `/performance`

- Reconcile per-symbol PnL with `/journal` trade events.
- Caps usage (`drawdown_used`, `daily_loss_used`) consistent with the worst-case rolling window?

### `/journal`

- Severity tags consistent with the alert layer in `alerting-and-user-experience`?
- Gaps in the timeline? (Missing journal entries during an incident are themselves a signal.)

## Anti-patterns

- "It works on my machine" — engine state is the only ground truth.
- Print-debugging into engine code during validation phase.
- Silent fix without a journal entry or decision-log row.
- Assuming a regime label is correct because the model said so — verify against `futures-market-researcher`.
- Treating mock-fallback behavior as live — surface it explicitly.

## Output contract

- `RCA summary` — one paragraph: bug / design choice / expected edge case.
- `Endpoint(s) involved` — explicit list.
- `Hypotheses` — numbered with likelihoods.
- `Test added` — link to file in `tests/` or `tests/replays/`.
- `Patch status` — merged / proposal-deferred (validation phase) / not needed.
- `Decision-log entry` — link if the change touches caps, thresholds, or framework.

## Cross-references

- Engine endpoints: `skills/coinscopeai-engine-api`
- Risk caps: `skills/coinscopeai-trading-rules`
- Domain check on regime: `skills_src/futures-market-researcher`
- Tests + replays: `skills_src/test-and-simulation-lab`
- Pre-merge gate for cap/threshold changes: `skills/coinscopeai-premortem`
- Alert UX (where many "weird but correct" cases land): `skills_src/alerting-and-user-experience`
- Generic debug fallback: `engineering:debug`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)
