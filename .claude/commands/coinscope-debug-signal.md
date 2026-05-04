---
name: coinscope-debug-signal
description: Debug a specific CoinScopeAI testnet signal — reconstruct context, validate rule path, cross-check risk gates, generate hypotheses, and propose patches or doc updates. Use when the user provides a symbol, side, and timestamp; pastes a /scan payload; or says a signal "looks wrong."
triggers:
  - "this BTC long from 10:35 looks wrong, debug it"
  - "explain why we got this signal and check for bugs"
  - "investigate this ETH short at 09:20; something is off"
  - "why did /scan return this?"
allowed-tools: Bash(curl *), Bash(python3 *), Read, Grep, Edit, Write
inputs:
  required:
    - symbol         # e.g. BTCUSDT
    - side           # long | short
    - timestamp_utc  # ISO-8601
  optional:
    - scan_payload   # raw /scan response if user has it
    - risk_gate_payload
    - regime_payload
phase_constraint: 30-day validation phase — engine is frozen; output is diagnosis + proposal, not a merged patch (unless explicit exception via coinscopeai-premortem).
---

# CoinScopeAI — Debug a Suspect Signal

Specialization of `bug-hunter-and-debugger` (skills_src/) anchored to the engine's six endpoints. Output is risk-first: we explain *why*, we check *what gates would have done*, we propose *durable* fixes — never quick patches.

## Inputs

The user must provide:
- Symbol, side, timestamp (UTC). If only symbol + time given, ask for the `/scan` payload or permission to re-run `/scan` against the engine on localhost.
- Optional: `/risk-gate`, `/position-size`, `/regime/{symbol}` payloads from the same window.

Engine base URL (dev): `http://localhost:8001`

## Steps

### 1. Reconstruct context
- Pull the `/scan` request + response for `{symbol}` at `{timestamp_utc}`.
- Pull `/regime/{symbol}` for ±15m around the timestamp if available.
- Note any `mock fallback` flag in either response — explicit, not silent.

### 2. Validate signal logic
- Restate the exact rule path: which features fired, which thresholds, which regime filter applied.
- Cross-check against the regime profile via `futures-market-researcher`:
  - Long breakout in Quiet → suspicious.
  - Short fade in Trending → suspicious.
  - Anything signal-vs-regime contradiction is flagged before risk-cap analysis.

### 3. Cross-check risk gates
- Re-run `/risk-gate` for the same hypothetical position (same size, same leverage).
- Verify caps applied as canonical: 10x leverage, 10% max DD, 5% daily loss, 5 max positions, 80% heat.
- Identify the first failing cap (if any) and any others that would have failed.

### 4. Hypothesize
List 2-4 plausible explanations with likelihood labels. Categories:
- Model behavior (correct).
- Implementation bug (off-by-one, lookahead, cache TTL).
- Stale data (cached funding/OI past TTL).
- Misconfigured threshold (drift from canonical — run `drift-detector` if uncertain).
- Cap interaction (correct but surprising).
- Mock fallback active (endpoint not live).

### 5. Diagnostics (instrument, don't print-debug)
- Add a `journal_note` event with the full feature vector at signal time.
- Re-run idempotency check: same params → same response twice.
- If a replay-class incident: add a frozen window under `tests/replays/` per `test-and-simulation-lab`.

### 6. Patch or document
- Bug confirmed → write the patch as a **proposal** under `business-plan/_decisions/`; do not merge during validation phase. Failing-test-first rule applies if the engine thaws.
- "Weird but correct" → no patch. Update `alerting-and-user-experience` so the next user isn't surprised.

## Output format

- `Summary` — one paragraph: bug / design choice / expected edge case.
- `Signal breakdown` — features, thresholds, regime label + confidence at signal time.
- `Risk & caps check` — gate outcome + first-failing-cap (or "all pass").
- `Hypotheses` — numbered, with "likelihood: low/medium/high".
- `Proposed actions` — tests, code changes, docs updates, with phase label.
- `Decision-log entry` — link if the change touches caps, thresholds, or framework.

## Anti-patterns

- "Looks fine to me" without checking `/risk-gate` and `/regime/{symbol}` payloads.
- Print-debugging into engine code during validation phase.
- Treating mock-fallback responses as live data.
- Promoting a quick patch without a regression test in `tests/`.
- Calling a fix "production-ready" — language is forbidden by Scoopy voice rules.

## Cross-references

- Skill: `skills_src/bug-hunter-and-debugger/SKILL.md`
- Skill: `skills_src/futures-market-researcher/SKILL.md`
- Skill: `skills_src/alerting-and-user-experience/SKILL.md`
- Skill: `skills_src/test-and-simulation-lab/SKILL.md`
- Caps: `skills/coinscopeai-trading-rules/SKILL.md`
- Engine API: `skills/coinscopeai-engine-api/SKILL.md`
- Drift check: `skills_src/drift-detector/SKILL.md`
