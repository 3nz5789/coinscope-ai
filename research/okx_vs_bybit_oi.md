# [RESEARCH] OKX vs Bybit — Open Interest Reliability (USDT-M Perpetuals)

**Author:** Scoopy (Claude)
**Date:** 2026-04-17
**Decision target:** Pick a primary Open Interest data source for CoinScopeAI v3 (post-validation). Secondary should remain available for cross-checks.
**Scope:** USDT-M linear perpetuals only. Spot, USDC-M, inverse, and options are out of scope.
**Depth:** Quick comparison (docs + community reports; no live API probing in this pass).
**Confidence:** Medium. Most primary specs were confirmed via OKX/Bybit docs through search snippets; the exchange doc domains themselves are not on the workspace network allowlist, so direct doc fetches were blocked. Any figure below marked (✱) should be re-confirmed against the live docs before production cutover.

---

## 1. TL;DR

Use **Bybit as the primary OI feed** and **OKX as the secondary / divergence monitor** for CoinScopeAI v3's post-validation iteration. The decision is close, but Bybit wins on four of the five things that actually matter for scanner signal quality: update cadence on the wire, symbol coverage, official SDK maturity, and existing integration depth in our codebase. OKX wins on channel separation (dedicated OI channel vs. bundled in ticker) and on the cleanliness of its public issue trail. Keeping OKX as a secondary gives us a free cross-exchange confirmation signal for OI-based setups, which is more valuable than picking one and discarding the other.

---

## 2. Endpoint map

### OKX — USDT-M perp OI

| Access pattern | Endpoint / channel | Cadence (✱) | Notes |
|---|---|---|---|
| REST current OI | `GET /api/v5/public/open-interest` with `instType=SWAP`, `instId=BTC-USDT-SWAP` | On-demand | Rate limit 20 req / 2 s per IP (✱) |
| REST historical OI | `GET /api/v5/rubik/stat/contracts/open-interest-volume` | Aggregated | "Trading statistics" endpoint; granularity parameter drives binning |
| WebSocket push | `open-interest` channel (public) | Push every ~3 s (✱) | Dedicated OI stream, separate from ticker |

### Bybit — USDT-M perp OI

| Access pattern | Endpoint / channel | Cadence (✱) | Notes |
|---|---|---|---|
| REST current OI | `GET /v5/market/tickers?category=linear` → `openInterest`, `openInterestValue` fields | On-demand | Ticker snapshot carries current OI |
| REST historical OI | `GET /v5/market/open-interest` | `intervalTime ∈ [5min, 15min, 30min, 1h, 4h, 1d]` | Binned. Default limit 50, max 200; `startTime` / `endTime` / `cursor` supported |
| WebSocket push | `tickers.{symbol}` on `wss://stream.bybit.com/v5/public/linear` | Derivatives push every **100 ms** (✱) | OI is a field inside the ticker delta, not a dedicated channel |

Rate limits: Bybit is per-second per-UID with `X-Bapi-Limit-*` response headers telling you exactly what's left. OKX is per-IP with fixed windows (20/2 s on the OI endpoint).

---

## 3. Head-to-head matrix

| Criterion | OKX | Bybit | Edge |
|---|---|---|---|
| Realtime push cadence | ~3 s (dedicated `open-interest` channel) | ~100 ms (via ticker) | **Bybit** — 30× faster on paper |
| Historical granularity (min) | 5-min binning via rubik stats | 5-min binning via dedicated endpoint | Tie |
| Dedicated OI channel | Yes — clean separation | No — bundled in ticker | **OKX** — lower coupling risk |
| USDT-M symbol coverage (approx) | ~200+ perp symbols | ~450+ perp symbols | **Bybit** — broader scanner universe |
| REST rate-limit headroom for validation scale | 20 req / 2 s / IP | Per-sec per-UID, headers returned | Tie for our scale |
| Official Python SDK | `python-okx` + third-party (`okx-sdk`) | `pybit` (officially maintained) | **Bybit** |
| Documented public OI issues (last 24 mo) | 1 (CCXT `openInterestValue` calc, Oct 2024) | 4+ (CCXT pagination, CCXT fetch failure, pybit options discrepancy, Atas indicator) | **OKX** — cleaner trail |
| Already integrated in CoinScopeAI | Yes (multi-exchange stream) | Yes (multi-exchange stream) | Tie; both present in repo |
| OI volume / liquidity depth (USDT-M) | ~$10.7B (2025 snapshot) | Historically larger in USDT-perps | **Bybit** |

Net: Bybit on 4, OKX on 2, 3 ties. The OKX "wins" are real (channel separation and a cleaner public-issue trail) but they matter less than Bybit's cadence and coverage for our use case.

---

## 4. Why this matches CoinScopeAI's actual use case

The scanner uses OI mainly as an **enrichment feature** — specifically `oi_change_1h` (1-hour delta) in the signal confluence score, plus a stretch goal to evaluate shorter-window OI deltas (5m / 15m) for entry-timing confirmation.

For that shape of consumption:

1. **1-hour OI delta is cadence-insensitive** down to 5-min granularity, so both exchanges satisfy the baseline. Neither wins on the headline signal.
2. **Shorter-window OI deltas** would benefit from sub-second OI updates. Bybit's 100 ms ticker stream gives us room to experiment with `oi_change_5m`, `oi_change_15m`, and even tick-level OI momentum without needing a second data provider. OKX's 3 s channel is still usable for 5-min+ deltas but caps what we can build later.
3. **Symbol coverage** directly scales the scanner's watchlist. Bybit listing more USDT-perps means more candidate setups from the same feed — lower per-symbol plumbing overhead.
4. **Cross-exchange confirmation** is where OKX earns its keep. If both Bybit and OKX show OI rising into a breakout, the signal is stronger than if only one does. That's the post-validation enhancement the secondary feed unlocks.

---

## 5. Documented issues worth tracking

### OKX
- **ccxt/ccxt #23969** (Oct 2024): `openInterestValue` computed incorrectly in CCXT because OKX returns `oiUsd` directly; fixed on the CCXT side. Not an exchange-side data problem.

### Bybit
- **ccxt/ccxt #17854**: `fetchOpenInterestHistory` pagination bug — requesting "from Jan" returns data "from April" because of cursor handling. Client-side, but affects anyone pulling historical OI through CCXT.
- **ccxt/ccxt #12105**: historical failure-to-fetch OI on Bybit. Older issue.
- **bybit-exchange/pybit #267**: options OI discrepancy between API and the Bybit UI. **Options only** — not applicable to our USDT-M perp scope, but shows Bybit's API ↔ UI reconciliation isn't always airtight.
- **AtasPlatform/Indicators #2**: third-party indicator reporting Bybit OI oddities.

Both exchanges' issue trails are dominated by *client-side library bugs*, not exchange-side data integrity problems. The bybit-exchange/pybit #267 options discrepancy is the only documented case where the exchange itself returned values that didn't match its own UI — and it's in a contract category we don't touch.

---

## 6. Recommendation

**Primary:** Bybit V5 — use `tickers.{symbol}` on `wss://stream.bybit.com/v5/public/linear` for live OI, and `GET /v5/market/open-interest` with `intervalTime=5min` for historical backfill.

**Secondary / cross-check:** OKX V5 — subscribe to the `open-interest` WebSocket channel for a second opinion, and reconcile against `GET /api/v5/public/open-interest` on any divergence.

**Cross-exchange divergence signal:** if Bybit and OKX OI deltas disagree on direction over a 15-min window, down-weight the OI component of the confluence score for that symbol on that bar. That's a free risk control we only get by running both feeds.

---

## 7. Open questions / what needs a live-data pass before production cutover

These are the things the quick comparison can't answer — they need actual probing during validation:

1. **Bybit ticker OI field refresh cadence.** The ticker stream updates at 100 ms, but the `openInterest` field specifically may be snapshotted at a slower internal cadence. Need to measure actual delta frequency on the wire for a busy symbol (BTCUSDT) and a thin symbol.
2. **OKX dedicated channel vs. REST drift.** Check whether the 3 s WebSocket value ever disagrees with the REST `open-interest` response at the same instant.
3. **Symbol-overlap reconciliation.** For the ~150+ symbols listed on both exchanges, compare absolute OI values and 1h deltas over 48 h. Large systematic offsets are fine (different contract sizes / liquidity pools). Large *random* divergences aren't.
4. **Binance as ground truth.** Binance's `GET /fapi/v1/openInterest` is our de facto benchmark for OI quality. Where symbols overlap across all three, we should pick whichever of Bybit/OKX tracks Binance more tightly on the same symbol.
5. **Historical backfill depth.** How far back does Bybit's `intervalTime=5min` go? OKX's rubik stats? Need this for any OI-based backtesting extensions.
6. **Rate-limit behavior under scanner load.** Scanner scans ~100-200 symbols; confirm neither exchange's rate limits bite under the actual call pattern (which is bursty at scan-tick boundaries).

---

## 8. Decision log

- **2026-04-17** — Initial research pass. Recommendation: Bybit primary, OKX secondary. Subject to live-data validation during COI-41 (30-day testnet validation phase). No engine code changes triggered by this doc — it's input to the v3 post-validation iteration.

---

## 9. Sources

### OKX
- [OKX API guide — V5 overview](https://www.okx.com/docs-v5/en/)
- [OKX V5 API upcoming changes](https://www.okx.com/docs-v5/log_en/)
- [OKX — A complete guide to API v5 (US)](https://www.okx.com/en-us/learn/complete-guide-to-okex-api-v5-upgrade)
- [OKX Open interest limits help article](https://www.okx.com/en-us/help/position-limits-of-contracts)
- [OKX — How do I use the Open interest indicator?](https://www.okx.com/en-us/help/how-do-i-use-the-open-interest-indicator)
- [tiagosiebler/okx-api — endpoint function list](https://github.com/tiagosiebler/okx-api/blob/master/docs/endpointFunctionList.md)
- [ccxt/ccxt #23969 — OKX openInterestValue issue](https://github.com/ccxt/ccxt/issues/23969)
- [Tardis.dev — OKX Futures data details](https://docs.tardis.dev/historical-data-details/okex-futures)

### Bybit
- [Bybit V5 API — Get Open Interest](https://bybit-exchange.github.io/docs/v5/market/open-interest)
- [Bybit V5 API — Rate Limit Rules](https://bybit-exchange.github.io/docs/v5/rate-limit)
- [Bybit V5 API — Public Ticker WebSocket](https://bybit-exchange.github.io/docs/v5/websocket/public/ticker)
- [Bybit V5 API — Get Tickers](https://bybit-exchange.github.io/docs/v5/market/tickers)
- [Bybit V5 API — Enums (intervalTime values)](https://bybit-exchange.github.io/docs/v5/enum)
- [pybit — _v5_market.py](https://github.com/bybit-exchange/pybit/blob/master/pybit/_v5_market.py)
- [ccxt/ccxt #17854 — Bybit fetchOpenInterestHistory pagination bug](https://github.com/ccxt/ccxt/issues/17854)
- [ccxt/ccxt #12105 — Bybit fail to fetch open-interest](https://github.com/ccxt/ccxt/issues/12105)
- [bybit-exchange/pybit #267 — Options OI discrepancy](https://github.com/bybit-exchange/pybit/issues/267)

### Context / cross-references
- [CoinGlass — OKX futures data](https://www.coinglass.com/exchanges/OKX)
- [CoinAPI — Open interest data overview](https://www.coinapi.io/blog/open-interest-data-api)
