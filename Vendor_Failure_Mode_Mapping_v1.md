# CoinScopeAI — Vendor Failure-Mode Mapping v1.0

**Date:** 2026-05-01
**Status:** Draft for Founder Review
**Resolves:** Production Candidate Criteria R4, Open Item O-6
**Owner:** Mohammed (Founder)

---

## 1. Purpose

Every external vendor is a single point of failure. This document maps each P1-tier vendor to (a) what fails when the vendor goes dark, (b) what the engine must do in degraded mode, (c) the recovery procedure, and (d) the stated risk-policy guarantee that **must not be violated** even during vendor failure.

**Core invariant:** vendor outages must not cause the engine to violate D1–D5 in the Production Candidate Criteria (max DD 10%, daily loss 5%, leverage 10x, max 5 positions, position heat ≤80%). If the engine cannot guarantee D1–D5 during a degraded mode, the correct response is **halt new entries**, not "best effort."

---

## 2. Vendor Inventory (P1 Stack)

| Vendor | Role | Criticality | Replaceable? |
|---|---|---|---|
| Binance Futures API (USDT-M) | Primary execution + market data | **CRITICAL** — no fallback for execution | No (mainnet); CCXT-abstracted later for multi-venue |
| CCXT (library, 4 exchanges) | Exchange abstraction | High — but a library, not a service | Yes (direct REST) |
| CoinGlass | Open interest, liquidations, funding rates | Medium — feeds confluence input | Partially (compute from exchange) |
| Tradefeeds | News + sentiment | Low — overlay only | Yes (skip overlay) |
| CoinGecko | Token reference data | Low — cacheable | Yes (cache + static mapping) |
| Anthropic Claude API | Minimal LLM use (non-hot-path per project rules) | Low — must NOT be in risk path | Yes (skip enrichment) |

---

## 3. Per-Vendor Failure Profiles

### 3.1 Binance Futures API

**Role.** Order placement, position management, account state, market data (klines, depth, funding, liquidations).

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| B-1 | Full API outage (REST + WS) | Low–Medium | Cannot place, modify, or close orders. Cannot read position state. |
| B-2 | REST degraded, WS healthy | Medium | Can stream data, cannot place orders reliably. |
| B-3 | WS disconnect, REST healthy | Medium–High | Stale market data; can still execute but on lagged signals. |
| B-4 | Rate-limit ban (HTTP 418/429) | Medium | Self-inflicted; usually correlates with reconnect storms. |
| B-5 | Geographic IP block | Low | Total outage from current VPS. |
| B-6 | Funding/liquidation feed dropout | Low | Confluence input quality drops. |
| B-7 | Testnet-mainnet config drift | Real (project-stage risk) | Wrong endpoint = catastrophic. |

**Engine guarantees during outage.**
- New entries: **HALT** on B-1, B-2, B-4, B-5.
- Open positions: stop-loss orders **must already be on-exchange** before any outage tolerance applies. No "we'll close it manually" — that violates the capital-preservation invariant.
- Reconciliation: on recovery, full state reconcile before any new entry.

**Degraded mode policy.**
- B-1 / B-2: Halt new entries; rely on on-exchange SL/TP for open positions. Founder receives a P0 alert.
- B-3: Halt new entries until WS reconnects and last-message gap is verified ≤ acceptable threshold.
- B-4: Halt new entries; back off; only resume after rate-limit window clears + 1 cycle of clean reads.
- B-7: Pre-flight check on every engine start verifies endpoint matches `BINANCE_NETWORK` env var. Mismatch = engine refuses to start.

**Recovery procedure.**
1. Confirm Binance status on `binance.com/status` (or `testnet.binancefuture.com` equivalent).
2. Run reconnect probe: 30s of clean REST + WS reads.
3. Reconcile: account state vs. engine view, 0 unexplained deltas.
4. Resume: re-enable new-entry flag.
5. Post-mortem if outage exceeded 30 minutes.

**Tolerance threshold.** 30-minute total outage → degraded operation OK. >30 min → mandatory halt + post-mortem.

---

### 3.2 CCXT

**Role.** Library abstracting REST+WS APIs across Binance/Bybit/OKX/Hyperliquid (P1 = 4 exchanges).

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| C-1 | Library bug introduced in a version bump | Medium | Silent data corruption or order misformat. |
| C-2 | Endpoint schema drift not yet patched in CCXT | Medium | Specific calls fail until version update. |
| C-3 | Maintainer abandons or pauses | Low | Long-term sustainability risk. |

**Engine guarantees.**
- Pin CCXT to a specific version. No floating-version installs.
- Direct-REST fallback path exists for **Binance only** (the critical path).
- Smoke test on every deployment validates: order placement, position read, balance read.

**Degraded mode policy.**
- C-1 / C-2: revert to pinned prior version; if not viable, switch to direct-REST fallback for Binance.

**Recovery procedure.**
1. Detect via smoke test failure or order error.
2. Roll back to last known-good CCXT version (version pin in `requirements.txt`).
3. If roll-back fails: switch Binance to direct REST.
4. Re-run smoke test.

**Tolerance threshold.** Any silent data corruption = immediate halt + investigation.

---

### 3.3 CoinGlass

**Role.** Open interest, liquidation feed, funding-rate aggregation. Feeds the confluence layer.

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| G-1 | Full API outage | Medium | Confluence missing OI/liq/funding components. |
| G-2 | Rate-limit hit on tier | Medium | Throttled data. |
| G-3 | Pricing tier change / contract change | Low–Medium | Cost or access surprise. |
| G-4 | Data quality degradation (stale, incomplete) | Medium | Signal noise. |

**Engine guarantees.**
- Confluence weights must be **configurable** so the engine can downweight CoinGlass-sourced inputs to zero without breaking signal generation.
- CoinGlass is **never** the sole input for a risk-gate decision.

**Degraded mode policy.**
- G-1: Re-weight confluence to drop CoinGlass-sourced components. Engine continues to operate with degraded signal precision; minimum-confluence threshold is automatically raised by 1 to compensate.
- G-2: Reduce poll frequency; rely on cached values up to documented TTL.
- G-4: If staleness >5 minutes, treat as G-1.

**Fallback.** Compute open interest from exchange APIs directly (Binance Futures provides per-symbol OI). Funding rates similarly. Liquidation feed cannot be cleanly reconstructed without CoinGlass or paid alternatives — accept temporary loss.

**Recovery procedure.**
1. Verify CoinGlass status.
2. Reset confluence weights to documented default.
3. Resume normal poll cadence.

**Tolerance threshold.** Up to 24h degraded operation acceptable; >24h → review whether to add a backup vendor.

---

### 3.4 Tradefeeds

**Role.** News + sentiment overlay.

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| T-1 | API outage | Medium | No sentiment overlay. |
| T-2 | Latency spike | Medium | Stale sentiment. |
| T-3 | Pricing/access change | Low | Operational. |

**Engine guarantees.**
- Sentiment is **never** in the risk-gate hot path.
- Engine must operate fully without Tradefeeds (signal generation does not depend on sentiment for validity).

**Degraded mode policy.**
- T-1 / T-2: Skip sentiment enrichment; signals tagged `sentiment_unavailable=true` for journal traceability.

**Fallback.** None required at P1; sentiment is enrichment, not input.

**Recovery procedure.** Re-enable sentiment poll after API health restored.

**Tolerance threshold.** Indefinite (operationally non-critical).

---

### 3.5 CoinGecko

**Role.** Token reference data — symbol metadata, market caps, basic listings.

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| K-1 | API outage | Low | Cannot refresh symbol metadata. |
| K-2 | Free-tier limit | High | Already mitigated with cache. |
| K-3 | Schema change | Low | Parse failures. |

**Engine guarantees.**
- Symbol mapping cached locally; engine boots with last-known-good cache.
- Static fallback: a frozen JSON of the supported-symbol set ships with the engine.

**Degraded mode policy.**
- K-1: Use cache; refresh deferred.
- K-3: Use cache + static mapping until parser updated.

**Fallback.** Static `supported_symbols.json` shipped with the engine.

**Recovery procedure.** Refresh cache once API health restored.

**Tolerance threshold.** Indefinite (operationally non-critical for live trading).

---

### 3.6 Anthropic Claude API

**Role.** Minimal LLM use per project rules. **MUST NOT be in any signal-generation hot path** that can change risk behavior.

**Failure modes.**
| # | Mode | Likelihood | Impact |
|---|---|---|---|
| A-1 | API outage | Low | Loss of LLM-enriched output (e.g., natural-language explanations on dashboard). |
| A-2 | Latency spike | Medium | UI delay only. |
| A-3 | Output drift / format change | Low | UI parsing failures. |

**Engine guarantees.**
- A pre-merge audit confirms no LLM call sits in the signal-generation hot path.
- A failed LLM call **cannot** delay or alter an order decision.
- LLM output is enrichment-only.

**Degraded mode policy.** Skip enrichment; UI shows raw signal data.

**Fallback.** None required.

**Tolerance threshold.** Indefinite.

**Audit obligation.** A standing requirement (S0 hard rule in Production Candidate Criteria) is to verify no LLM call is in the risk path. This must be re-verified on every engine release.

---

## 4. Cross-Vendor Failure Scenarios

| Scenario | Engine response |
|---|---|
| Binance + CoinGlass simultaneously down | Halt new entries (Binance hard-stops it anyway); manage open positions via on-exchange SL/TP. |
| Binance WS down + CCXT REST stale | Halt new entries until both healthy. |
| All three "soft" vendors (CoinGlass + Tradefeeds + CoinGecko) down | Engine continues with raised confluence threshold; founder alerted. |
| Full internet loss at VPS | On-exchange SL/TP saves the open positions; engine restarts on connectivity restore; reconcile before resuming. |
| Time-skew on VPS (NTP failure) | Halt — exchange APIs reject signed requests with bad timestamps. |

---

## 5. Standing Operational Requirements

These are not vendor-specific but apply to all of them:

- **On-exchange SL/TP for every open position.** No exception. This is the single most important defense against vendor outages. (Mapped to Production Candidate Criteria X3.)
- **Pre-flight check on engine start.** Verifies network env var, API connectivity to all P1 vendors, time sync, log-store reachable.
- **Vendor health panel.** All P1 vendor statuses visible on a single dashboard panel. (Mapped to M3.)
- **Vendor outage alerts.** Each vendor has a P0/P1 alert wired to the founder, distinguishing "degraded" from "down."
- **Quarterly fire drill.** Simulate each vendor's outage in staging once per quarter; verify degraded mode behavior matches this document.

---

## 6. Open Items

| # | Item | Owner |
|---|---|---|
| V-1 | Confirm pinned CCXT version + roll-back procedure documented | Founder |
| V-2 | Build the on-exchange SL/TP attachment audit (resolves X3) | Founder |
| V-3 | Build the vendor health panel (resolves M3) | Founder |
| V-4 | Build the LLM-not-in-hot-path audit (resolves S0 hard rule) | Founder |
| V-5 | Schedule first quarterly fire drill | Founder |
| V-6 | Decide whether to add a backup OI/liquidation vendor (resolves CoinGlass single-point-of-failure) | Founder |

---

## 7. Acceptance for v1

- [ ] Every P1 vendor has a documented degraded-mode policy.
- [ ] Every degraded-mode policy has been tested in staging at least once.
- [ ] Founder has signed off on tolerance thresholds.
- [ ] Document committed to repo at `docs/vendor_failure_mapping.md`.
