---
name: futures-market-researcher
description: Encode and apply crypto-futures microstructure knowledge — funding rates, open interest, liquidations, basis, contango/backwardation, and perpetual mechanics — to validate signals, filters, and examples against how USDT perpetuals actually behave on Binance (and later Bybit at P2). Use when designing or critiquing any signal that references futures-only features, when explaining why a regime label was assigned, when a trade idea relies on funding/OI/liquidation behavior, or when a generic TA pattern needs a futures-specific sanity check. Triggers on "funding rate", "open interest", "OI", "liquidation cluster", "basis", "contango", "backwardation", "perpetual", "futures microstructure", "is this a real futures signal", "would this work on perps".
---

# Futures Market Researcher

Domain-knowledge skill. Translates "looks like a setup" into "respects how perpetuals actually behave."

## When to use

- Designing or critiquing a signal that references futures-only features (funding, OI, liquidations, basis).
- Explaining a `regime/{symbol}` label when the user asks why Trending vs Mean-Reverting vs Volatile vs Quiet.
- Validating that a generic TA pattern (e.g., "RSI + EMA cross") still makes sense once funding and OI are layered in.
- Sanity-checking historical anomalies before treating them as edges (funding flips, liquidation cascades, expiry effects on dated futures).
- Reviewing P1-P5 phase-map decisions that depend on venue-specific microstructure.

## When NOT to use

- Pure spot-market analysis — no funding, no OI, no liquidation feed; this skill's machinery doesn't add value.
- Code-level fixes to the engine — engine is frozen during the 30-day validation phase; route to `bug-hunter-and-debugger` only if a documented incident exists.
- Risk-cap enforcement — that's `coinscopeai-trading-rules` / `risk-and-position-manager`.

## Domain primitives

| Primitive | Source today | Notes |
|---|---|---|
| Funding rate | Binance `/fapi/v1/fundingRate`, CoinGlass | 8h cycle on Binance USDT-M; sign and magnitude both matter |
| Open interest | Binance `/fapi/v1/openInterest`, CoinGlass | Track 1h Δ; absolute vs relative-to-30d-MA both useful |
| Liquidations | Binance forced-orders WS, CoinGlass | Cluster size + side — long-side cascade ≠ short-side cascade |
| Basis / mark-index | `/fapi/v1/premiumIndex` | Persistent positive basis = leveraged-long bias; confirms regime |
| Aggregated CVD | Trade stream, derived | Already used in `market-scanner` confluence score |

## Process

### Step 1 — State the assumption explicitly

Before any claim: name the venue (Binance USDT-M during P0/P1), the timeframe (5m default for `market-scanner`), and the lookback window. Anti-overclaim rule applies — never assert a microstructure effect without naming the data source.

### Step 2 — Map the signal to microstructure

For each feature in the candidate signal, answer:
- Does this feature only exist on perps? (funding, OI, liquidations, basis → yes; price, volume → also exists on spot)
- Is the threshold the user is proposing within the empirical range for the symbol over the chosen window?
- What microstructure effect would invalidate it? (e.g., a funding flip during a Volatile regime can flip the entire premise.)

### Step 3 — Cross-check against regime label

| Regime | Expected microstructure profile |
|---|---|
| Trending (mint #00FFB8) | Persistent funding skew, OI rising with price, liquidations one-sided |
| Mean-Reverting (neutral #A3ADBD) | Funding oscillates around zero, OI flat, liquidations symmetric |
| Volatile (amber #F5A623) | Funding spikes, OI volatile, liquidation cascades on both sides |
| Quiet (muted #5B6472) | Funding near zero, OI flat-low, liquidation feed sparse |

If the proposed signal contradicts the regime's profile (e.g., a breakout long in Quiet with no OI build-up), flag it before sizing.

### Step 4 — Phase awareness

- P0 / P1 (May–Jul 2026): Binance only. Do not propose Bybit-specific microstructure as a primary feature.
- P2 (Aug-Sep 2026): Vendor expansion. Bybit, multi-venue basis, cross-exchange OI become available.
- Anything proposed earlier is speculative and must be labeled "P2-deferred."

### Step 5 — Output contract

Always include:
- `Venue` — Binance USDT-M (or explicitly "P2-deferred").
- `Microstructure features used` — bullet list with data source per feature.
- `Regime fit` — one of the 4 labels with a one-line justification.
- `Failure modes` — 2-4 microstructure events that would invalidate the setup.
- `Confidence` — Low / Medium / High; never "production-ready."

## Anti-patterns

- Quoting funding/OI numbers without naming the venue or the timestamp.
- Treating spot patterns as proof a perp signal will work.
- Assuming Bybit behaves identically to Binance during P0/P1 — venue pairity is a P2 concern.
- Calling a signal "edge" before it has been backtested via `signal-design-and-backtest`.

## Cross-references

- Risk caps: `skills/coinscopeai-trading-rules` (10x leverage, 5% daily loss, 10% DD, 5 max positions, 80% heat)
- Engine endpoints: `skills/coinscopeai-engine-api` (`/regime/{symbol}` for regime labels)
- Backtest pairing: `skills_src/signal-design-and-backtest` (this skill informs, that skill formalizes)
- Phase map: `business-plan/14-launch-roadmap.md`
- Source pattern: Scoopy v3 master prompt §"Claude Skills (internal)" (proposed 2026-05-04)
