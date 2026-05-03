# CoinScopeAI — Daily Code Review
**Date:** 2026-04-24
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` — ~9,865 LOC across 31 files
**Reviewer:** Automated daily review (Claude, scheduled 09:00)
**Prime directive per CoinScopeAI trading rules:** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`)

---

## 0. Delta Since Last Review (2026-04-23)

- **No new commits in scope.** HEAD is still `59416a2` from 2026-04-18. File mtimes across `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` are identical to yesterday's review. This is the **sixth consecutive day** with zero source changes in the reviewed modules.
- All **7 carried P0s** from 2026-04-23 are re-verified present at the same line numbers (see §3).
- Four prior daily reviews (`CODE_REVIEW_2026-04-19.md` → `..._04-23.md`) remain **untracked** in git and have not been merged, triaged, or converted into issues.
- One **new P1** surfaced this pass — `risk/position_sizer.py` uses a misnamed and under-specified `tick_size` field to round order quantities (§4.1). This is not a new regression; it was simply not called out in prior reviews.
- Recommendation for the ops owner: **stop adding findings and start clearing them.** Today's report is deliberately shorter than yesterday's — the signal is in the stall, not in the new material.

---

## 1. Executive Summary

The code under review has not changed in a week, yet the set of documented capital-at-risk bugs continues to grow through re-reading. Running the engine against mainnet today means the following are all still live on the production path:

1. Signed REST requests have HMAC/body order mismatch — every signed call can fail with `-1022` (§3.1 / originally 4.1 on 2026-04-23).
2. Liquidation REST normalisation silently returns `None` because it uses WebSocket short-keys against REST long-key payloads — `LiquidationScanner` is effectively a no-op (§3.2).
3. Correlation gate fails **open** on insufficient history, violating the capital-preservation directive at engine start-up (§3.3).
4. Webhook HMAC still doesn't cover `X-Timestamp` — replayable (§3.4).
5. WebSocket reconnect counter is a no-op self-reference (`reconnects += 1 if reconnects else 0`) (§3.5).
6. Alert queue has a `full()`/`put()` race that can block producers under burst (§3.6).
7. Rate-limiter per-symbol bucket map is unbounded and refund path mutates `_tokens` outside the bucket lock (§3.7).

**New today:** `PositionSizer` rounds quantities using a field called `tick_size` with a single default of `0.001`. That default is only correct for a minority of Binance Futures symbols (e.g. XRPUSDT needs step 1, DOGEUSDT step 1, SHIBUSDT step 1,000,000). No caller in the repo (`api.py:105`, `main.py:140`) overrides it. Under the current default, sizes computed for most symbols will be rejected by Binance's `LOT_SIZE` filter or — worse — silently rounded in ways that change risk vs. the calculated `risk_usdt`.

| Severity | Count | Trend |
|---|---|---|
| **P0 — fix before next live trading session** | **7** | unchanged vs. 2026-04-23 |
| **P1 — fix this week** | **16** | 15 carryover + **1 new** |
| **P2 — hygiene** | 16 | unchanged |

---

## 2. Code Quality Assessment

### 2.1 Security
No regressions. Still open: webhook HMAC omits timestamp (§3.4); signed-request signature mismatch (§3.1); cache-manager Redis subscriber still uses `socket_timeout=None` (blocking) and relies on context-manager exit for cleanup.

### 2.2 Performance
No regressions. Still open: confluence scorer O(R) filter per symbol inside `score_all`; unbounded symbol bucket map (§3.7).

### 2.3 Maintainability
Cross-module private-helper import (`pattern_scanner` imports `_candle_to_dict` / `_dict_to_candle` from `scanner.volume_scanner`) is still a latent breakage. These helpers belong in `data/data_normalizer.py`.

---

## 3. Carryover P0/P1 — re-verified at current line numbers

### 3.1 [P0] `data/binance_rest.py:98, 221–224` — signature over sorted payload, body sent unsorted
Verified. `_sign` still uses `urlencode(sorted(params.items()))`; `_request` still passes `req_params` directly to aiohttp, which serialises in insertion order. Binance HMAC check will fail. Fix as proposed 2026-04-23: build the query string **once**, sign it, and send the exact same string as the body / query so signature and transmitted payload are identical. Also move timestamp into the retry loop so it refreshes each attempt.

### 3.2 [P0] `data/data_normalizer.py::liquidation_to_schema` — REST keys not supported
Verified. The method reads `d["s"]`, `d["S"]`, `d["o"]`, `d["f"]`, `d["q"]`, `d["p"]`, `d["ap"]`, `d["X"]`, `d["T"]` (WebSocket short-codes). `/fapi/v1/allForceOrders` returns `symbol/side/type/timeInForce/origQty/price/averagePrice/status/time`. Every REST liquidation raises `KeyError`, is swallowed, returns `None`. Fix: add a REST branch that maps the long-form keys, or keep short-codes and normalise the REST payload upstream.

### 3.3 [P0] `risk/correlation_analyzer.py:188–190` — fail-open on missing history
Verified at line 190: `if r is None: continue`. The correct failure mode for a capital-preservation engine is **deny**, not allow. Fix: `return (False, f"Insufficient correlation history for {new_symbol}/{sym} — refusing to add")`.

### 3.4 [P0] `alerts/webhook_dispatcher.py` — HMAC does not cover `X-Timestamp`
Verified. Still signs the body only. Replayable. Sign `"{timestamp}.{body}"` and reject stale timestamps on the consumer.

### 3.5 [P0] `data/binance_websocket.py:247` — reconnect counter is a no-op
Verified:
```python
self.stats.reconnects  += 1 if self.stats.reconnects else 0
```
`+= (1 if x else 0)` where `x` starts at 0 → never advances. Fix: `self.stats.reconnects += 1`.

### 3.6 [P0] `alerts/alert_queue.py:244–252` — `full()` / `put()` race
Verified. Fix:
```python
try:
    self._queue.put_nowait(item)
except asyncio.QueueFull:
    self._dropped += 1
    logger.warning("AlertQueue full (%d). Dropping %s alert (total dropped=%d).",
                   self._queue.maxsize, item.alert_type, self._dropped)
    return False
return True
```

### 3.7 [P0] `alerts/rate_limiter.py:261–265, 305–312` — unbounded bucket map + unlocked token refund
Verified. `_get_symbol_bucket` still has no eviction; `allow_signal` still mutates `._tokens` outside the bucket's lock. Fix: add a `_TokenBucket.refund(n)` method that runs under the lock, and evict buckets idle for > N minutes from `_symbol_buckets` / `_symbol_limited` on `stats()` calls or via a periodic sweep.

### 3.8 [P1] `signals/indicator_engine.py:334` — `_rsi` no internal length guard (carryover).
### 3.9 [P1] `risk/position_sizer.py:133` — Kelly falsy-guard (carryover). Use `is not None`.
### 3.10 [P1] `risk/circuit_breaker.py::reset` — `_rapid_log` not cleared (carryover).
### 3.11 [P1] `alerts/telegram_notifier.py::_is_duplicate` — O(N) eviction (carryover).
### 3.12 [P1] `signals/confluence_scorer.py:66` — `MAX_RAW_SCORE=300.0` mismatches docs (carryover).
### 3.13 [P1] `alerts/webhook_dispatcher.py:257` — `except (HTTPError, Exception)` redundancy (carryover).

P2 hygiene (unchanged):
- `binance_rest.py:222–225` logs `"backing off %ds"` but raises instead of sleeping.
- `rate_limiter.py` mixes `threading.Lock` and an unused `asyncio.Lock`.
- Hard-coded 0.2 % / 3.0 % thresholds in `entry_exit_calculator.py`.
- `signals/backtester.py` commented-out `numba` path and 2-week-stale TODOs.

---

## 4. New Findings

### 4.1 [P1 — NEW] `risk/position_sizer.py:84–99, 144, 157` — `tick_size` is a misnomer **and** under-specified
The field is introduced as "quantity rounding step (default 0.001)" and is used as the step for `round_step(qty, self._tick_size)`. Two problems:

1. **Naming.** On Binance Futures, `tickSize` is the **price** increment (PRICE_FILTER), and `stepSize` is the **quantity** increment (LOT_SIZE). Using `tick_size` for quantity rounding is actively misleading — the next developer who passes a real Binance symbol's `tickSize` will silently produce wrong-sized orders. Rename to `step_size` and source it from `exchangeInfo.symbols[*].filters[LOT_SIZE].stepSize`.
2. **Default is wrong for most symbols.** `0.001` is the LOT_SIZE step for e.g. BTCUSDT, ETHUSDT, but XRPUSDT and DOGEUSDT have step `1`, SHIBUSDT has step `1000000`. The two instantiations in the repo (`api.py:105`, `main.py:140`) both use the default, so every non-0.001-step symbol will either be rejected by Binance at order placement (`-4024 LOT_SIZE`) or — if the caller wraps exchangeInfo rounding elsewhere — have `risk_usdt` internally computed against a qty that differs from what is actually sent.

Minimum fix:

```python
# risk/position_sizer.py
def __init__(
    self,
    *,
    risk_per_trade_pct: float | None = None,
    max_position_pct:   float        = 10.0,
    max_leverage:       int          = 10,
    step_size:          float        = 0.001,   # LOT_SIZE.stepSize — caller MUST pass per-symbol value
    method:             str          = "FIXED",
):
    ...
    self._step_size = step_size

def size(self, setup, balance, *, step_size: float | None = None, ...):
    step = step_size if step_size is not None else self._step_size
    qty = round_step(qty, step)
    ...
```

And at call-sites: fetch `LOT_SIZE.stepSize` from `binance_rest.get_exchange_info` and pass it per trade.

### 4.2 [P1 — NEW] `risk/position_sizer.py:153–157` — max-notional cap skips MIN_QTY re-check
After the cap reduces `qty` and re-rounds:
```python
if notional > max_notional:
    notional = max_notional
    qty      = round_step(safe_divide(notional, setup.entry), self._tick_size)
    risk_usdt = qty * setup.sl_distance
```
…there is no second `qty < MIN_QTY` check. If the max-position cap pushes a previously-valid qty below `MIN_QTY`, the function will happily return a `valid=True` result with a sub-minimum quantity. Add a post-cap check that returns `_invalid("Computed qty below minimum after max-position cap")`.

---

## 5. Optimisation Opportunities (unchanged — still worth doing)

1. `signals/confluence_scorer.py::score_all` — pre-group scanner results by symbol once (O(R)), not per symbol (O(S·R)).
2. `signals/indicator_engine.py` — cache EMA/ATR under a per-(symbol, timeframe) LRU keyed by the latest candle's close_time; most callers recompute them from scratch on every tick.
3. `data/binance_rest.py` — batch `/fapi/v1/premiumIndex` and `/fapi/v1/openInterest` per symbol list where supported rather than per-symbol GETs.
4. `alerts/alert_queue.py::_worker` — replace `get_nowait()` + `asyncio.sleep(WORKER_SLEEP_S)` polling with `await self._queue.get()`; saves wall time and CPU on idle.
5. `risk/correlation_analyzer.py::matrix` is O(N²) with two `pearson` calls per pair (once from each side via symmetry). Exploit the symmetry: iterate `for j > i`, mirror.

---

## 6. Punch List for the Code Owner (suggested ticket breakdown)

P0 — block next live session:

1. Fix `_sign` / `_request` payload ordering and move timestamp inside retry loop (`data/binance_rest.py`).
2. Add REST-keys branch to `liquidation_to_schema` (`data/data_normalizer.py`).
3. Flip correlation gate to fail-closed (`risk/correlation_analyzer.py:188–190`).
4. Sign `ts.body` for webhooks and enforce server-side freshness (`alerts/webhook_dispatcher.py`).
5. Replace `reconnects += 1 if reconnects else 0` with `+= 1` (`data/binance_websocket.py:247`).
6. Convert `AlertQueue._enqueue` to `put_nowait` + `QueueFull` (`alerts/alert_queue.py`).
7. Move rate-limiter token refund under `_TokenBucket` lock and add idle-bucket eviction (`alerts/rate_limiter.py`).

P1 — this week:

8. Rename `tick_size` → `step_size` in `PositionSizer`, make it per-symbol, source from exchangeInfo.
9. Add `qty < MIN_QTY` recheck after max-notional cap in `PositionSizer`.
10. `_rsi` internal length guard.
11. Kelly guard `is not None`.
12. `CircuitBreaker.reset()` clears `_rapid_log`.
13. Telegram dedupe via `deque` + set (or OrderedDict).
14. Decide `MAX_RAW_SCORE` semantics and document.
15. Trim overbroad `except (HTTPError, Exception)` in `webhook_dispatcher`.
16. Promote `scanner/volume_scanner._candle_to_dict` / `_dict_to_candle` into `data/data_normalizer.py` and drop the cross-module private import from `pattern_scanner`.

P2 — rolling hygiene: lift magic thresholds to config, clean up backtester numba TODOs, fix `binance_rest.py` "backing off" log-lie, prune unused `asyncio.Lock` in `rate_limiter.py`.

---

## 7. Process Note (non-code)

Five consecutive daily reviews with zero actioned changes is itself a risk signal. Recommend:

- Converting §6 items 1–7 into GitHub issues on `main` with `P0 / capital-at-risk` labels **today**.
- Committing the five daily review files into `docs/reviews/` so future reviewers can diff against them rather than re-deriving findings from the code each day.
- If the engine is running in any live capacity this week, consider pausing until §6/1–4 land. The §6/1 signature bug alone would cause every signed request — including order placement and leverage change — to 400 out.

*— end of report*
