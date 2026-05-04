---
name: test-and-simulation-lab
description: Maintain unit/integration tests and historical replay scenarios for CoinScopeAI signals, risk gates, and exchange clients — including high-volatility "replay days" that exercise regime flips, liquidation cascades, and funding spikes. Use when a new signal or risk-rule change needs regression coverage, when an incident produced a regression scenario worth keeping, when the engine API endpoints need contract tests, or when a replay day should be added to the corpus. Triggers on "write tests for", "regression test", "replay scenario", "simulate this day", "test the risk gate", "contract test for /scan", "replay days corpus", "stress test the engine".
---

# Test and Simulation Lab

Tests and replays are the cohort's safety net during the 30-day validation phase. Engine code is frozen — but tests, contracts, and replay scenarios are not. They are how regressions get caught before any thaw.

## When to use

- A signal change (designed via `signal-design-and-backtest`) needs regression coverage.
- An incident produced an interesting regression scenario worth preserving.
- A new engine endpoint contract needs lock-in (`/scan`, `/risk-gate`, `/position-size`, `/regime/{symbol}`, `/performance`, `/journal`).
- A high-volatility historical day needs to be added to the replay corpus.
- Before declaring any change "validated" — never on metrics alone, always with a replay pass.

## When NOT to use

- Code that lives outside the engine and isn't risk-affecting (e.g., dashboard CSS) — overkill.
- One-off ad-hoc analysis — use a notebook, don't pollute the corpus.

## Three test layers

### Layer 1 — Unit tests

Per module: one test file per source file, mirrored path. Cover:
- Happy path
- Each documented failure mode
- Each cap boundary (10x leverage, 5% daily loss, 10% DD, 5 max positions, 80% heat)
- Off-by-one for any rolling-window math

Tooling: `pytest`, `hypothesis` for property-based on numerical paths.

### Layer 2 — Contract tests (engine API)

For each endpoint, lock the request/response shape. A contract test fails if the shape changes, even if the value is plausible. Today's endpoints:

| Endpoint | Contract focus |
|---|---|
| `/scan` | Signal payload shape, score range, regime field present |
| `/risk-gate` | Pass/fail + first-failing-cap reason, all caps enumerated |
| `/position-size` | Size bounded by leverage cap, heat cap, account equity |
| `/regime/{symbol}` | One of {Trending, Mean-Reverting, Volatile, Quiet}, confidence in [0,1] |
| `/performance` | PnL, max DD, daily loss, trade count, by-symbol breakdown |
| `/journal` | Event list with timestamps and severity tags |

Mock data fallback behavior must also be contract-tested — if the live source is unreachable, the mock response must still satisfy the contract.

### Layer 3 — Replay scenarios ("replay days")

A replay is a frozen historical window the engine is run against. Each replay day is a stress-test for a specific failure class.

| Replay class | Example | What it catches |
|---|---|---|
| Regime flip | Mar 2024 BTC sudden Volatile → Quiet | Stale regime label persisting too long |
| Funding spike | Major funding cycle inversion | Signal logic that ignored sign flip |
| Liquidation cascade | Long cascade on alt | Position-sizer that didn't tighten in Volatile |
| Cross-symbol contagion | BTC dump pulling alts | Heat-cap aggregation across positions |
| Data gap | Exchange WS disconnect window | Reconnect logic + stale-data detection |

Corpus location: `tests/replays/<class>/<YYYY-MM-DD>_<symbol>_<class>.json` (frozen OHLCV + OI + funding + liquidations).

## Process

### Step 1 — Classify the change

Is this a unit-level change, a contract-level change, or a replay-class change? Each layer has a different cost. Don't write a replay for a one-line refactor.

### Step 2 — Write the failing test first

For bug fixes: a test that reproduces the bug and fails on `main` is mandatory before the fix.

### Step 3 — Run the full layer that contains the change

- Unit change → `pytest tests/unit/` for the affected module.
- Contract change → `pytest tests/contracts/`.
- Replay-class change → `pytest tests/replays/` (slow; run before merge, not on every save).

### Step 4 — Update the replay corpus if the incident produced a new failure class

If the issue is a new failure class (not just a new instance of an existing class), add a replay file. Document the date, symbol, and what the engine got wrong.

### Step 5 — Persist

Tests live next to code. Replays live in `tests/replays/`. Every new replay gets an entry in `tests/replays/INDEX.md` with one-line description and the failure class it exercises.

## Output contract

- New or updated test files under `tests/<layer>/`.
- For incidents: a replay file under `tests/replays/<class>/` and an `INDEX.md` row.
- A short note in the PR description: which layer changed, which replay class (if any) was added, and the test count delta.

## Anti-patterns

- Writing tests after the fix — they almost never fail, which means they aren't testing the bug.
- Replays without a failure class — becomes a museum of historical days with no regression value.
- Mocking the cap layer in unit tests — caps must be tested against real values from `coinscopeai-trading-rules`.
- Skipping contract tests because "the response looks fine" — the contract is the point.

## Cross-references

- Risk caps: `skills/coinscopeai-trading-rules`
- Engine endpoints: `skills/coinscopeai-engine-api`
- Signal source: `skills_src/signal-design-and-backtest`
- Incident SOP (planned): `commands/debug-suspect-signal.md`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)
