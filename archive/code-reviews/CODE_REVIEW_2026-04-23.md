# CoinScopeAI — Daily Code Review
**Date:** 2026-04-23
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` (~9,865 LOC across 31 files)
**Reviewer:** Automated daily review (Claude, scheduled 09:00)
**Prime directive per CoinScopeAI trading rules:** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs`

---

## 0. Delta Since Last Review (2026-04-22)

- **No new commits** in scope. HEAD is still `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`. File mtimes across `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` are unchanged from the 18th. This is the fifth consecutive day without source changes in the reviewed modules.
- Three prior daily reviews (`CODE_REVIEW_2026-04-19.md`, `..._04-21.md`, `..._04-22.md`) are all still **untracked** in git. They have not been reviewed, prioritised, or converted into tickets.
- **Every P0 flagged on 2026-04-19, 2026-04-21, and 2026-04-22 is still present** (re-verified file-by-file, with line numbers, in §3).
- Today's report adds **two new P0s** and **three new P1s** the prior reviews missed, plus a refreshed carryover section and a concrete punch list.

---

## 1. Executive Summary

Four days of static code means the report reads more like a stalled-work escalation than a fresh review. The most important thing for this week is not the new findings — it is that the list of confirmed capital-at-risk issues has compounded without a single line of code changing. If the engine is being run at all against mainnet right now, several of these are directly inconsistent with the stated capital-preservation directive and should block the next trading session.

Two net-new P0s today:

- **`data/binance_rest.py` — signature/body ordering mismatch on every signed request.** The HMAC is computed over `urlencode(sorted(params.items()))` but the request body is sent as a dict (insertion-order urlencoded). On any signed endpoint (place order, cancel, positions, account, leverage change…), the signature Binance re-computes over the received payload will not match the one we sent. Either the code has never actually hit a live signed endpoint, or we have been getting `-1022 Signature for this request is not valid` and swallowing it. Details in §4.1.
- **`data/data_normalizer.py::liquidation_to_schema` — unusable against REST response format.** The method expects WebSocket short-code keys (`s`, `S`, `o`, `f`, `q`, `p`, `ap`, `X`, `T`) but the REST `/fapi/v1/allForceOrders` response uses long-form keys (`symbol`, `side`, `type`, `timeInForce`, `origQty`, `price`, `averagePrice`, `status`, `time`). Every normalise call on a REST liquidation raises `KeyError`, gets swallowed in the `try/except`, and returns `None`. `LiquidationScanner` is then effectively a no-op because `liq_orders` is always empty. Details in §4.2.

| Severity | Count | Trend vs yesterday |
|---|---|---|
| **P0 — fix before next live trading session** | **7** | 5 carryover + **2 new** |
| **P1 — fix this week** | **15** | 12 carryover + **3 new** |
| **P2 — hygiene** | 16 | 15 carryover + 1 new |

---

## 2. Code Quality Assessment

### 2.1 Security
API keys are read through `config.settings` with `SecretStr` and never logged in the reviewed files. The Redis URL is masked on log output (`_safe_url`). Three security-relevant issues remain open: webhook HMAC still does not cover `X-Timestamp` (§3.3), the signed-request signature computation is inconsistent with what is actually transmitted (§4.1), and the cache-manager subscribe helper opens a dedicated Redis connection per subscription with `socket_timeout=None` (blocking read) and relies on the context-manager exit for cleanup — an uncaught exception in the subscriber will leak the connection until process exit.

### 2.2 Performance
Scanners hit Redis first and fall back to REST on miss; TTLs are short (2–60 s) and appropriate. Three performance hazards remain: the signed-request retry loop can push cumulative backoff past `recvWindow` (§3.1 re-tagged under the broader signature issue), the per-symbol bucket map in `alerts/rate_limiter.py` is unbounded (§3.5), and the confluence scorer walks `scanner_results` with an O(R) filter for every symbol inside `score_all` (§5.3 optimisation).

### 2.3 Maintainability
Layering is still clean. The bigger maintainability smell today is **duplication of candle ↔ dict serialisation helpers** — `_candle_to_dict` / `_dict_to_candle` exist in both `scanner/volume_scanner.py` and are imported by `scanner/pattern_scanner.py` via `from scanner.volume_scanner import ...`. That cross-module private-helper import is a code smell that will break the day volume_scanner's private helpers change. This belongs in `data/data_normalizer.py` alongside the dataclasses.

---

## 3. Carryover Bugs (all still present today; re-verified at current line numbers)

### 3.1 [P0 — carryover] `risk/correlation_analyzer.py:140, 172` — fail-open on insufficient data
`pearson()` returns `None` if `min_len < 5`; `is_safe_to_add` treats `None` as "allow" and continues with `continue`. The prime directive is capital preservation — the correct failure mode here is **deny**, not allow. A freshly-started engine with no price history will let every correlated concentration through its only correlation gate. Fix:

```python
# risk/correlation_analyzer.py: is_safe_to_add
r = self.pearson(new_symbol, sym)
if r is None:
    return False, f"Insufficient correlation history for {new_symbol}/{sym} — refusing to add"
```

### 3.2 [P0 — carryover] `data/binance_websocket.py:247` — reconnect counter is a no-op
```python
self.stats.reconnects += 1 if self.stats.reconnects else 0
```
This is `reconnects += (1 if reconnects else 0)`. When reconnects is 0 it adds 0; when it is non-zero it adds 1. The counter will never advance past 0 in practice because it never gets incremented from 0 in the first place. Fix: `self.stats.reconnects += 1`.

### 3.3 [P0 — carryover] `alerts/webhook_dispatcher.py:239–243, 337` — HMAC does not cover timestamp
`X-Timestamp` is set alongside `X-Signature`, but `_sign_payload(body, self._secret)` hashes only the body. Replay attacks are trivial — capture one signed webhook, re-send at any time in the future. Fix:

```python
# sign "{timestamp}.{body}" instead of body
ts = str(int(time.time()))
headers["X-Timestamp"] = ts
headers["X-Signature"] = _sign_payload(f"{ts}.{body}", self._secret)
```
…and on the consumer side, reject requests whose `X-Timestamp` is more than ~5 minutes old.

### 3.4 [P0 — carryover] `alerts/alert_queue.py:244` — full-check / put race
```python
async def _enqueue(self, item):
    if self._queue.full():      # check
        ...
    await self._queue.put(item)  # put — not atomic with the check
```
Between the `full()` check and the `put()`, the worker may drain and another producer may fill. Under burst conditions the queue can block on the `put` despite the `full()` branch having been "not taken". Fix: use `put_nowait()` inside a `try/except asyncio.QueueFull`.

### 3.5 [P0 — carryover, originally P1 on 2026-04-22] `alerts/rate_limiter.py:307, 261–265` — symbol bucket map grows unbounded + race on token refund
Two distinct bugs in the same file, upgraded to P0 because together they leak memory on long-running engines and corrupt bucket state under the `allow_signal` refund path.

1. **Unbounded map.** `_get_symbol_bucket` creates a `_TokenBucket` per never-seen symbol and never evicts. Every new symbol from `settings.scan_pairs` or anywhere else stays in `_symbol_buckets` forever, as does `_symbol_limited[symbol]`. Over a week-long run this is small, but over months it is a real leak and makes `stats()` responses linear in symbols-ever-seen.
2. **Unlocked refund.** `allow_signal` hand-mutates `_tokens` outside the bucket's `Lock`:
   ```python
   self._get_symbol_bucket(symbol)._tokens = min(
       self._symbol_capacity,
       self._get_symbol_bucket(symbol)._tokens + 1,
   )
   ```
   This can interleave with `_refill()` (inside `try_consume`) and leak or duplicate tokens. Add a `_TokenBucket.refund(n)` method that performs `_refill(); self._tokens = min(capacity, self._tokens + n)` under `self._lock`, and call that instead.

### 3.6 [P1 — carryover] `signals/indicator_engine.py:334` — `_rsi` has no length guard
Callsite gates on `n >= 15`, so `_rsi` currently gets enough data. But the function itself accepts any array; a refactor that removes the callsite guard silently returns garbage because `np.mean(gains[:14])` succeeds even on very short arrays. Add `if len(closes) < period + 1: return 50.0` at the top of `_rsi` as a defensive guard — the signal will default to "neutral" rather than "100 or 0 depending on the last couple of bars".

### 3.7 [P1 — carryover] `risk/position_sizer.py:133` — Kelly falsy-guard drops valid inputs
```python
if self._method == "KELLY" and win_rate and avg_rr:
```
`win_rate=0.0` (a legitimately bad strategy state) and `avg_rr=0.0` (undefined — though ideally we would not trade) are treated as "missing". Prefer `win_rate is not None and avg_rr is not None` so the validation happens inside `_kelly_fraction` (which already clamps to `max(0.0, ...)`).

### 3.8 [P1 — carryover] `risk/circuit_breaker.py::reset` (line 227) — rapid-loss log not cleared
`reset()` re-closes the breaker but leaves `self._rapid_log` populated. An operator who resets after a rapid-loss trip can have the breaker re-trip immediately on the next trade, because the historical losses in `_rapid_log` are still inside the window. `reset()` should `self._rapid_log.clear()` too; `reset_daily()` already does.

### 3.9 [P1 — carryover] `alerts/telegram_notifier.py::_is_duplicate` — O(N) eviction
Still present. Not urgent but worth swapping to an `OrderedDict` or `deque` + set.

### 3.10 [P1 — carryover] `signals/confluence_scorer.py:66` — `MAX_RAW_SCORE = 300.0` mismatches docs
The scoring comment implies 0–100 normalisation against a theoretical sum, but with 5 scanners each emitting WEAK/MEDIUM/STRONG weights 1/2/3 and scores up to ~60, the real maximum is far larger than 300. The net effect is that `long_norm` hits the 70-point cap very early, compressing the confluence score into an effectively-narrow range. Either document the cap explicitly or raise `MAX_RAW_SCORE` to ~600 and re-tune bonus weights.

### 3.11 [P1 — carryover] `alerts/webhook_dispatcher.py:257` — redundant exception tuple
`except (httpx.HTTPError, Exception)` — `Exception` already includes `HTTPError`. Trim to `except Exception` or, better, to a narrow whitelist (`httpx.HTTPError, asyncio.TimeoutError`) so programming errors surface instead of being swallowed as "request failed".

### 3.12 [P2 — carryover and carryover-of-carryover] Other hygiene
- `binance_rest.py:222–225` still logs `"backing off %ds"` but raises instead of sleeping (log-lie).
- `rate_limiter.py` mixes `threading.Lock` (inside `_TokenBucket`) and `asyncio.Lock` (in `AlertRateLimiter._lock`) and the latter is never actually awaited anywhere.
- `entry_exit_calculator.py`'s 0.2 % "very tight SL" threshold and 3.0 % "high volatility" threshold are still hard-coded; lift to config.
- `signals/backtester.py` has a commented-out `numba` path and two TODOs that have sat for >2 weeks.

---

## 4. New Findings (not in prior daily reviews)

### 4.1 [P0 — NEW] `data/binance_rest.py::_request` — signature is over sorted payload but body is sent unsorted
Severity is high because this affects every signed endpoint — accounts, positions, leverage, margin type, **and order placement**.

```python
# binance_rest.py:98 — signature helper
def _sign(secret, params):
    payload = urlencode(sorted(params.items()))     # ← sorted
    return hmac.new(...).hexdigest()

# binance_rest.py:210–214 — _request
if signed:
    req_params["timestamp"]  = int(time.time() * 1000)
    req_params["recvWindow"] = self._recv_window
    req_params["signature"]  = _sign(self._api_secret, req_params)

# binance_rest.py:221–224 — actual send (aiohttp)
async with self._session.request(
    method, url,
    params=req_params if method == "GET" else None,
    data=req_params  if method != "GET" else None,
):
```

`_sign` hashes the sorted payload. `aiohttp` then serialises `req_params` in the order keys were inserted (timestamp, recvWindow, signature, *caller-supplied keys*). Binance re-computes HMAC over the payload **as it arrives over the wire** — i.e. in the sent order, which is not sorted. The two HMACs disagree and Binance returns `-1022 Signature for this request is not valid`.

This is inconsistent with `binance_rest_testnet_client.py:43–49` in the same repo, which does it correctly — signs `urlencode(params)` (unsorted) and sends in that same order. That the two files disagree suggests `data/binance_rest.py` was never exercised against a real signed endpoint.

Recommended fix — sign and send the same string, and do it **inside the retry loop** so the timestamp is fresh on every attempt (which also closes yesterday's P0 4.1):

```python
async def _request(self, method, path, params=None, signed=False, retries=MAX_RETRIES):
    if self._session is None:
        await self._open_session()

    base_params = dict(params or {})

    url = f"{self._base_url}{path}"
    attempt = 0
    while attempt <= retries:
        req_params = dict(base_params)
        if signed:
            req_params["timestamp"]  = int(time.time() * 1000)
            req_params["recvWindow"] = self._recv_window
            # Build the exact query string once, then reuse it as both the
            # signature payload AND the body — guaranteeing they match.
            qs = urlencode(req_params)
            sig = hmac.new(
                self._api_secret.encode(), qs.encode(), hashlib.sha256
            ).hexdigest()
            qs_full = f"{qs}&signature={sig}"
            send_kwargs = (
                {"params": qs_full} if method == "GET"
                else {"data": qs_full, "headers": {"Content-Type": "application/x-www-form-urlencoded"}}
            )
        else:
            send_kwargs = (
                {"params": req_params} if method == "GET" else {"data": req_params}
            )
        # … rest of the retry loop uses send_kwargs
```

Also verify on a disposable testnet key before re-enabling any mainnet signed call.

### 4.2 [P0 — NEW] `data/data_normalizer.py::liquidation_to_schema` — REST shape not handled
```python
def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
    try:
        order = raw.get("o", raw)              # WS wraps payload under "o"
        return LiquidationOrder(
            symbol        = order["s"],         # REST uses "symbol"
            side          = order["S"],         # REST uses "side"
            order_type    = order["o"],         # REST uses "type"
            time_in_force = order["f"],         # REST uses "timeInForce"
            qty           = float(order["q"]),  # REST uses "origQty"
            price         = float(order["p"]),  # REST uses "price"
            avg_price     = float(order["ap"]), # REST uses "averagePrice"
            status        = order["X"],         # REST uses "status"
            time          = _ms_to_dt(int(order["T"])),  # REST uses "time"
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
        return None
```

`LiquidationScanner._fetch_liquidations()` calls `self.rest.get_liquidation_orders(...)` which returns REST-shaped dicts, pipes each through `liquidation_to_schema`, and filters `None`:
```python
orders = [o for r in raw if (o := self._normalizer.liquidation_to_schema(r)) is not None]
```

Because every REST item raises `KeyError("s")`, `orders` is always empty. `total = 0 < threshold`, the scanner returns no hits, and the downstream confluence score never sees a liquidation signal. Whatever the tests say about the scanner, the live pipeline returns no liquidation input.

Fix — branch on the shape:

```python
def liquidation_to_schema(self, raw):
    try:
        if "o" in raw and isinstance(raw["o"], dict):   # WS forceOrder event
            o = raw["o"]
            return LiquidationOrder(
                symbol=o["s"], side=o["S"], order_type=o["o"],
                time_in_force=o["f"], qty=float(o["q"]), price=float(o["p"]),
                avg_price=float(o["ap"]), status=o["X"],
                time=_ms_to_dt(int(o["T"])),
            )
        # REST /fapi/v1/allForceOrders item
        return LiquidationOrder(
            symbol=raw["symbol"], side=raw["side"], order_type=raw["type"],
            time_in_force=raw["timeInForce"],
            qty=float(raw["origQty"]), price=float(raw["price"]),
            avg_price=float(raw["averagePrice"]),
            status=raw["status"], time=_ms_to_dt(int(raw["time"])),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
        return None
```

Also worth pointing out: Binance has been tightening access to `/fapi/v1/allForceOrders` — even after this fix, the right primary source is the `!forceOrder@arr` WebSocket stream. The REST path should stay as a backfill.

### 4.3 [P1 — NEW] `signals/confluence_scorer.py::_apply_indicator_bonuses` — MACD "cross" bonus fires whenever MACD is same-sign, not on actual crosses
```python
@property
def macd_bullish_cross(self) -> bool:
    return (self.macd is not None and self.macd_signal is not None
            and self.macd > self.macd_signal and self.macd_hist is not None
            and self.macd_hist > 0)
```
This describes the **state** of MACD being above signal, not the **event** of MACD crossing. Every LONG signal taken in an uptrend collects the full `+7 MACD cross` bonus every scan cycle — even 40 bars after the actual crossover. The bonus is no longer additional evidence; it is a trend re-tag.

Fix — a cross requires "prev bar: MACD < signal, this bar: MACD > signal":

```python
# compute MACD across the last 2+ closed bars and check the sign flip
# Keep the property name but implement it on a two-value history:
prev_hist = compute_macd_hist(candles[:-1])[-1]
curr_hist = indicators.macd_hist
macd_bullish_cross = prev_hist is not None and prev_hist <= 0 < curr_hist
```
The simplest path: add `macd_hist_prev: Optional[float]` to `Indicators` and set it during `compute()` so the scorer can detect the zero-crossing.

### 4.4 [P1 — NEW] `scanner/volume_scanner.py:78` uses `candles[-1]` as "current"; Binance REST `/klines` returns the still-forming candle as the last element
The scanner treats `current = candles[-1]` as a closed bar, compares its volume to the rolling mean, and fires strong signals when the ratio crosses the threshold. But `/fapi/v1/klines` returns the currently-open bar as the last element (`is_closed=False` in raw form, though `klines_to_candles` hard-codes `is_closed=True` — see also §4.5). Early in a 5-minute bar, volume is a tiny fraction of what it will be at close, so the ratio starts low and grows through the bar. Signals then fire as soon as accumulated volume crosses threshold, sometimes multiple times per bar, and the "bullish/bearish" label from `is_bullish` flips while the candle is still being painted.

Fix — drop the forming candle. `pattern_scanner` has the same bug; it calls `candles[-1]` the "most recent closed" but does not enforce closure:

```python
# scanner/volume_scanner.py
if candles and not candles[-1].is_closed:
    candles = candles[:-1]
if len(candles) < self._baseline_period + 1:
    return self._make_result(...)
current  = candles[-1]
baseline = candles[-(self._baseline_period + 1):-1]
```

And make `klines_to_candles` respect the bar's actual closure state rather than hard-coding `is_closed=True`. Binance signals closure by `close_time <= now_ms()` — the normalizer can stamp it correctly.

### 4.5 [P1 — NEW] `data/data_normalizer.py:281` — `klines_to_candles` hard-codes `is_closed=True`
Directly related to §4.4. The REST response includes the currently-forming candle; the normalizer should stamp it `is_closed=False` so downstream scanners can filter. Fix:

```python
now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
is_closed = int(k[6]) <= now_ms      # close_time already past
candles.append(Candle(..., is_closed=is_closed))
```

### 4.6 [P2 — NEW] `scanner/pattern_scanner.py:154` — `max(p.low, 0.001)` is a meaningless floor on crypto prices
```python
if (p.is_bearish and c.is_bullish and
        abs(p.low - c.low) / max(p.low, 0.001) < 0.001):
```
`max(..., 0.001)` guards against a zero denominator, but real crypto lows are never near 0.001. The guard is effectively a no-op except on a completely broken price feed, and it makes the intent harder to read. Prefer `safe_divide(abs(p.low - c.low), p.low, default=float("inf")) < 0.001` so the bad-data case fails the check instead of passing it.

---

## 5. Optimisation Opportunities (refreshed)

### 5.1 Cross-module private imports
`scanner/pattern_scanner.py` imports `_candle_to_dict` / `_dict_to_candle` from `scanner/volume_scanner.py`. These are `_`-prefixed — underscore means private by convention. Lift them to `data/data_normalizer.py` (or expose a public `serialize_candle` / `deserialize_candle`) so the two scanners share a properly-public helper.

### 5.2 Exchange info fetched per call in `get_min_notional`
`binance_rest.py:835` calls `get_exchange_info()` on every `get_min_notional(symbol)`. `/fapi/v1/exchangeInfo` has weight 1 but returns every symbol's metadata — it is a heavy response. Cache it in the REST client for ~60 minutes; symbol filters change only on exchange config updates.

### 5.3 `ConfluenceScorer.score_all` — O(R × S)
```python
for symbol in symbols:
    sym_results = [r for r in scanner_results if r.symbol == symbol]
```
Group once: `by_symbol = defaultdict(list); [by_symbol[r.symbol].append(r) for r in scanner_results if not r.error]`, then iterate. Scanner-result lists grow with every new scanner; the quadratic cost shows up as LA spikes once we run 5+ scanners on 20+ symbols.

### 5.4 `CorrelationAnalyzer.correlation_matrix` recomputes pearson twice per pair
`matrix[sym_a][sym_b]` and `matrix[sym_b][sym_a]` both get a full `pearson` call. Pearson is symmetric — compute once and fill both entries.

### 5.5 `alerts/alert_queue.py::_worker` busy-polls on empty queue
```python
try:   item = self._queue.get_nowait()
except asyncio.QueueEmpty:
    await asyncio.sleep(WORKER_SLEEP_S)   # 0.05s
    continue
```
50 ms is fine; but prefer `await self._queue.get()` (blocks until an item arrives) and use `self._running` inside the loop as the stop signal via a cancellation task. Lower CPU, lower latency on first item.

---

## 6. Best-Practice Violations (summary)

- **Fail-open on ambiguous data** in `correlation_analyzer` (§3.1) and `liquidation_to_schema` (§4.2). Both should fail-safe per the capital-preservation prime directive.
- **Signature generation decoupled from wire format** in `binance_rest.py` (§4.1). Sign-what-you-send is a cross-cutting rule for every HMAC'd request path in the system.
- **Replay-unsafe webhook** (§3.3). Timestamp must be in the signed material.
- **Race-and-drop patterns** (§3.4, §3.5) — anywhere a check-then-act touches a shared queue or bucket, use `_nowait` with `try/except`.
- **State-not-event naming** (§4.3) — `macd_bullish_cross` should describe a cross, not a regime. Same pattern worth auditing for `golden_cross` / `death_cross` if they appear anywhere in `intelligence/`.
- **Currently-forming candle treated as closed** (§4.4, §4.5). Signals on open candles lead to flip-flop hits and false confluence.
- **Tests cannot catch any of these** unless they cover the WS-vs-REST shape and a real signed roundtrip. Of the 7 P0s listed above, only §3.2 is easy to exercise with a purely in-process test.

---

## 7. Recommended Priority Order (this week)

Ship in this order; each row is independently verifiable:

1. **§4.1 — binance_rest signed-request fix.** Do NOT ship the engine to mainnet with signed calls until this is patched and verified against a testnet roundtrip. This also subsumes the 2026-04-22 P0 about `timestamp` not being refreshed on retry.
2. **§4.2 — liquidation_to_schema REST shape.** Restore LiquidationScanner as a real input.
3. **§3.1 — correlation_analyzer fail-closed.** One-liner change, massive safety win.
4. **§3.2 — reconnects counter.** One-character fix that restores a real observability signal.
5. **§3.3 — webhook HMAC over ts|body.** Needs a consumer-side change too; coordinate.
6. **§3.4 — alert queue race.** Swap to `put_nowait` inside try/except.
7. **§3.5 — rate limiter leak + refund race.** Introduce `_TokenBucket.refund()` and an LRU cap on `_symbol_buckets`.
8. **§4.3, §4.4, §4.5 — signal correctness (MACD cross; forming candle).** These affect signal quality, not capital safety, but they also account for a lot of noise in the confluence log.

Tracking suggestion: convert each numbered item into a Linear ticket in `CSCAI` with the section reference in the body. The three untracked `CODE_REVIEW_*.md` files at the repo root should also be either committed or archived — the `.gitignore` should stay consistent with the review workflow.

---

## 8. Verification Notes for This Run

- All P0 claims re-verified against the working tree under `restructure/2026-04-18-tier1-docs`:
  - `data/binance_rest.py` signed path inspected at L210–225 and signature helper at L98–104; testnet comparator at `binance_rest_testnet_client.py:43–49`.
  - `data/binance_websocket.py:247` reconnect counter.
  - `alerts/webhook_dispatcher.py:226–243, 337–342` HMAC scope.
  - `alerts/alert_queue.py:244–254` enqueue race.
  - `risk/correlation_analyzer.py:140–172, 178–180` fail-open.
  - `alerts/rate_limiter.py:257–266, 307–316` refund race + unbounded map.
- File-modification times across the reviewed modules are all `1776555126` (2026-04-18). No code movement since the Tier-1 docs restructure commit (`59416a2`).
- No runtime verification was performed — this review is static-only. A testnet signed-request roundtrip is the minimum gate before any of the §4.1 fix is deployed.

---

*End of CODE_REVIEW_2026-04-23.md*
