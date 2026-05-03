# CoinScopeAI — Daily Code Review
**Date:** 2026-04-26
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` — ~9,865 LOC across 31 files
**Reviewer:** Automated daily review (Claude, scheduled 09:00)
**Prime directive per CoinScopeAI trading rules:** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`)

---

## 0. Delta Since Last Review (2026-04-24)

- **No new commits in scope.** HEAD remains `59416a2` from 2026-04-18. `git log --oneline -20` returns the same three commits as the last seven daily reviews.
- File mtimes across `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` are identical to the 2026-04-24 snapshot — every `.py` file last-touched at `2026-04-18 23:32:06`. **Eighth consecutive day with zero source changes in scope.**
- All **7 carried P0s** from 2026-04-24 are re-verified present at the same line numbers (see §3). Re-verification was done by re-grep, not from memory.
- The **P1 from 2026-04-24** on `risk/position_sizer.py` (`tick_size` default of `0.001` for all symbols, no per-symbol overrides at any caller) is also still present at `risk/position_sizer.py:93` with both call sites still passing no arguments (`api.py:105`, `main.py:140`).
- Six prior daily reviews (`CODE_REVIEW_2026-04-19.md` … `CODE_REVIEW_2026-04-24.md`) remain **untracked** in git. They have not been merged, triaged, or converted into Linear/GitHub issues. Today's review will be the seventh.
- Recommendation, repeated for the third day: **stop adding findings and start clearing them.** The signal here is the stall, not new material. If the engine is dormant by design (Tier-1 restructure is what HEAD says), say so explicitly in `README.md` so the daily review can switch to a "no-op verified" check instead of re-grepping the same defects.

---

## 1. Executive Summary

The code under review has been frozen for eight days. None of the seven capital-at-risk P0s identified in earlier reviews have been touched. Running the engine against mainnet today still means the following are all live on the production path:

1. Signed REST requests have HMAC/body order mismatch — every signed call can fail with `-1022` (§3.1).
2. Liquidation REST normalisation silently returns `None` because it uses WebSocket short-keys against REST long-key payloads — `LiquidationScanner` is effectively a no-op (§3.2).
3. Correlation gate fails **open** on insufficient history, violating the capital-preservation directive at engine start-up (§3.3).
4. Webhook HMAC still doesn't cover `X-Timestamp` — replayable (§3.4).
5. WebSocket reconnect counter is a no-op self-reference (`reconnects += 1 if reconnects else 0`) (§3.5).
6. Alert queue has a `full()` / `put()` race that can block producers under burst (§3.6).
7. Rate-limiter per-symbol bucket map is unbounded and refund path mutates `_tokens` outside the bucket lock (§3.7).

| Severity | Count | Trend vs. 2026-04-24 |
|---|---|---|
| **P0 — fix before next live trading session** | **7** | unchanged (8 days) |
| **P1 — fix this week** | **16** | unchanged |
| **P2 — hygiene** | **17** | +1 (`_ema` seed bias surfaced today, §5.1) |

No new P0 / P1 surfaced today. One **P2** is added — `_ema` in `signals/indicator_engine.py:324` seeds with `data[0]` instead of an SMA, which biases the first ~3·period samples enough to flip MACD cross detection on short windows. Documented because the daily review explicitly asks for "potential bugs or edge cases", not because it's urgent next to the live P0s.

---

## 2. Code Quality Assessment

### 2.1 Security
No regressions; no improvements. Still open:
- Webhook HMAC omits timestamp (§3.4) — replayable.
- Signed-request signature mismatch (§3.1) — all signed REST calls vulnerable to `-1022` and, on a server-side ordering quirk, signature acceptance with a different payload than the body sent.
- `data/cache_manager.py:108` Redis client `socket_timeout=5` is set on the main client but `_pubsub_client` is created elsewhere without an explicit timeout (verified at `data/cache_manager.py:91, 121`); a hung pub/sub call will not be cancelled by anything other than `close()`.
- No hardcoded secrets in `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` — `grep -rn "api_key\\s*=\\s*['\"]"` returns clean. (Good — preserve.)

### 2.2 Performance
No regressions; no improvements. Still open:
- `signals/confluence_scorer.py:312` — `score_all` filters `scanner_results` once per symbol inside a `for symbol in symbols:` loop. O(R · S). With R ≈ 6 scanners × S ≈ 200 USDT-perp symbols this is 240k comparisons each cycle — currently runs sub-second but will dominate when symbol universe expands. Fix: build `by_sym: dict[str, list[ScannerResult]] = defaultdict(list); for r in scanner_results: by_sym[r.symbol].append(r)` once, then iterate.
- `alerts/rate_limiter.py:175` — `_symbol_buckets` map grows unbounded; never evicts buckets for delisted or never-traded symbols. Capped only by symbol universe size today, but combined with churning testnet-style symbol lists this leaks slowly.
- `signals/indicator_engine.py:324–331` — `_ema` is a Python `for` loop over the whole array; called for SMA-20/50/200, MACD fast/slow/signal, and Stoch-K/D smoothing per symbol per cycle. Vectorise once with `scipy.signal.lfilter([k], [1, -(1-k)], data)` or precompute candles with pandas `ewm(adjust=False)`.

### 2.3 Maintainability
No regressions; no improvements. Still open:
- `scanner/pattern_scanner.py:232, 237` cross-imports `_candle_to_dict` / `_dict_to_candle` from `scanner.volume_scanner`. These should live in `data/data_normalizer.py`. Latent breakage risk if `volume_scanner` is ever moved or renamed.
- `alerts/*.py` mixes `datetime.utcnow()` (deprecation-warned in Python 3.12+) with the rest of the codebase's `time.monotonic()` / `time.time()`. See `alerts/alpha_decay_monitor.py:60,126,290`, `alerts/retrain_scheduler.py:60,152,195`, `alerts/telegram_alerts.py:51`. Replace with `datetime.now(timezone.utc)`.
- Six untracked `CODE_REVIEW_*.md` files in repo root accumulating without a triage destination. Either git-ignore them, sink them into `archive/`, or convert findings into issues. Right now they read as a to-do list nobody owns.

---

## 3. Carryover P0/P1 — re-verified at current line numbers

### 3.1 [P0] `data/binance_rest.py:97, 217–224` — signature over sorted payload, body sent unsorted
Verified by re-reading the file today:
```python
# data/binance_rest.py:97
def _sign(secret: str, params: dict[str, Any]) -> str:
    payload = urlencode(sorted(params.items()))
    return hmac.new(secret.encode("utf-8"),
                    payload.encode("utf-8"),
                    hashlib.sha256).hexdigest()

# data/binance_rest.py:217
req_params = dict(params or {})
if signed:
    req_params["timestamp"]  = int(time.time() * 1000)
    req_params["recvWindow"] = self._recv_window
    req_params["signature"]  = _sign(self._api_secret, req_params)
```
`req_params` is then passed straight to `aiohttp.ClientSession.request(... params=..., data=...)` which serialises in dict-insertion order, not sorted. Binance's HMAC check rebuilds from the on-wire query string, so signature verification fails with `-1022 Signature for this request is not valid`. Also: `timestamp` is set **once before** the `while attempt <= retries:` loop (line 222), so retries reuse a stale timestamp and will trip `-1021 Timestamp for this request is outside of the recvWindow`.

**Fix (unchanged from 2026-04-23):**
```python
async def _request(self, method, path, params=None, *, signed=False, retries=2):
    while attempt <= retries:
        req_params = dict(params or {})
        if signed:
            req_params["timestamp"]  = int(time.time() * 1000)
            req_params["recvWindow"] = self._recv_window
            qs = urlencode(req_params)                 # canonical, insertion-order
            req_params["signature"] = hmac.new(
                self._api_secret.encode(), qs.encode(), hashlib.sha256
            ).hexdigest()
            qs_signed = f"{qs}&signature={req_params['signature']}"
            kwargs = {"params": qs_signed} if method == "GET" else {"data": qs_signed}
        else:
            kwargs = {"params": req_params} if method == "GET" else {"data": req_params}
        async with self._session.request(method, url, **kwargs) as resp:
            ...
```
Building the query string once and signing the same string we send is the only way to make this robust to dict-ordering or any future param-name change.

### 3.2 [P0] `data/data_normalizer.py:421` — `liquidation_to_schema` only handles WebSocket payloads
Verified at the same line. The implementation reads `d["s"], d["S"], d["o"], d["q"], d["p"], d["ap"], d["X"], d["T"]` — all WebSocket short-codes from `forceOrder@arr` events. `/fapi/v1/allForceOrders` returns long-form keys (`symbol`, `side`, `type`, `origQty`, `price`, `averagePrice`, `status`, `time`, `timeInForce`). Every REST liquidation raises `KeyError`, the caller in `scanner/liquidation_scanner.py:135` swallows it as a generic `Exception`, and the function returns `None`. Net effect: `LiquidationScanner` produces zero hits when fed REST data.

**Fix:** add a REST branch:
```python
def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
    # Detect payload shape — REST has "symbol", WS has "s"
    if "symbol" in raw:
        return LiquidationOrder(
            symbol=raw["symbol"],
            side=raw["side"],
            order_type=raw["type"],
            time_in_force=raw.get("timeInForce", "GTC"),
            qty=float(raw["origQty"]),
            price=float(raw["price"]),
            avg_price=float(raw.get("averagePrice", raw["price"])),
            status=raw.get("status", "FILLED"),
            ts_ms=int(raw["time"]),
        )
    # else WS short-code branch (existing code)
    ...
```

### 3.3 [P0] `risk/correlation_analyzer.py:190` — fail-open on missing history
Verified at line 190 today:
```python
r = self.pearson(new_symbol, sym)
if r is None:
    continue   # insufficient data — allow
```
A capital-preservation engine must **deny** when correlation cannot be evaluated. At engine cold start, `_returns_window` is empty for every symbol → every `pearson` call returns `None` → every concentration check is skipped → the engine is free to open arbitrary correlated positions for the first ~lookback minutes/hours of uptime.

**Fix:**
```python
r = self.pearson(new_symbol, sym)
if r is None:
    return (
        False,
        f"Insufficient correlation history for {new_symbol}/{sym} "
        f"(need ≥{self._min_samples}); refusing to add concentrated risk."
    )
```
And expose a metric/log so the operator can see how many trades are being refused on cold start (otherwise this fix will look like "the engine stopped trading" to anyone watching dashboards).

### 3.4 [P0] `alerts/webhook_dispatcher.py` — HMAC signs body only; `X-Timestamp` not covered
Verified by `grep -n "hmac\\|X-Timestamp\\|signature"`. The dispatcher signs `payload` only and emits `X-Signature` and `X-Timestamp` independently. Replay window is unbounded — an attacker who captures one signed body can resend it forever.

**Fix:**
```python
ts = str(int(time.time()))
to_sign = f"{ts}.{body}".encode()
sig = hmac.new(secret, to_sign, hashlib.sha256).hexdigest()
headers = {"X-Timestamp": ts, "X-Signature": f"v1={sig}", ...}

# consumer side:
if abs(int(headers["X-Timestamp"]) - now) > 300:   # 5-minute window
    raise InvalidSignature("stale timestamp")
expected = hmac.new(secret, f"{headers['X-Timestamp']}.{body}".encode(), hashlib.sha256).hexdigest()
hmac.compare_digest(headers["X-Signature"].split("=", 1)[1], expected)
```

### 3.5 [P0] `data/binance_websocket.py:247` — reconnect counter is a no-op
Verified:
```python
self.stats.reconnects += 1 if self.stats.reconnects else 0
```
Operator precedence here is `+= (1 if x else 0)` and `x` starts at `0`, so the increment is always `0`. The counter at line 321 in the retry loop is correct (`self.stats.reconnects += 1`), so the bug at 247 produces undercounting on first reconnect only — but it does mean the "first reconnect" event is invisible in metrics.

**Fix:**
```python
self.stats.reconnects += 1
```

### 3.6 [P0] `alerts/alert_queue.py:244–252` — `full()` / `put()` race
Verified. `_enqueue` checks `self._queue.full()` and then `await self._queue.put(item)`. Between the check and the await, the worker can drain enough items for the queue to become non-full *or* a concurrent producer can fill it; in the latter case `put()` will block, defeating the "drop on full" guarantee.

**Fix:** use `put_nowait` and let it raise:
```python
async def _enqueue(self, item: AlertItem) -> bool:
    try:
        self._queue.put_nowait(item)
        return True
    except asyncio.QueueFull:
        self._dropped += 1
        logger.warning(
            "AlertQueue full (%d). Dropped %s (total dropped=%d).",
            self._queue.maxsize, item.alert_type, self._dropped,
        )
        return False
```

### 3.7 [P0] `alerts/rate_limiter.py:175, 261–264` — unbounded symbol-bucket map; refund mutates `_tokens` outside the bucket lock
Verified. `_symbol_buckets` (line 175) grows by one entry per unique symbol seen; never evicted. The refund path in `allow_signal` (lines 261–264) does:
```python
self._get_symbol_bucket(symbol)._tokens = min(
    self._symbol_capacity,
    self._get_symbol_bucket(symbol)._tokens + 1,
)
```
This reads-then-writes `_tokens` without holding `_TokenBucket._lock`, racing with `_refill` and `try_consume` on the dispatcher worker thread.

**Fix:**
```python
class _TokenBucket:
    def refund(self, tokens: float = 1.0) -> None:
        with self._lock:
            self._tokens = min(self.capacity, self._tokens + tokens)

# composite limiter:
def allow_signal(self, symbol: str) -> bool:
    bucket = self._get_symbol_bucket(symbol)
    if not bucket.try_consume():
        return False
    if not self._telegram.try_consume():
        bucket.refund()              # atomic, lock-held
        return False
    return True
```
Add an LRU/TTL eviction on `_symbol_buckets` (e.g. `cachetools.TTLCache(maxsize=2_000, ttl=86_400)`) to bound memory.

### 3.8 [P1, carried 2026-04-24] `risk/position_sizer.py:93, 144, 157` — single `tick_size=0.001` default applied to every symbol
Verified:
```python
def __init__(self, ..., tick_size: float = 0.001, ...) -> None:
    self._tick_size = tick_size
...
qty = round_step(qty, self._tick_size)
...
qty = round_step(safe_divide(notional, setup.entry), self._tick_size)
```
Both call sites (`api.py:105`, `main.py:140`) instantiate `PositionSizer()` with no argument. The default of `0.001` is wrong for every symbol whose Binance Futures `LOT_SIZE.stepSize` is 1 (e.g. XRPUSDT, DOGEUSDT) or 1,000,000 (SHIBUSDT). For those, the engine will either submit quantities the exchange rejects, or — worse — the post-rounding qty silently changes effective `risk_usdt` because `risk = qty × sl_distance` is computed on the unrounded value.

**Fix:** plumb a `symbol_info_cache: dict[str, SymbolFilters]` from `data/binance_rest.py` (or persist via `cache_manager`) and look up `step_size` per symbol:
```python
class PositionSizer:
    def __init__(self, symbol_filters: Mapping[str, SymbolFilters], ...):
        self._filters = symbol_filters
    def calculate(self, setup, balance, ...):
        step = self._filters[setup.symbol].step_size
        qty  = round_step(safe_divide(risk_usdt, setup.sl_distance), step)
        ...
        # always re-derive risk_usdt after rounding
        risk_usdt = qty * setup.sl_distance
```
The post-rounding `risk_usdt` recompute matters: yesterday's review noted that today's `notional > max_notional` branch (line 157) recomputes risk after rounding, but the primary path at line 144 does not. So under the default the engine reports a `risk_usdt` that is up to one `tick_size` × `sl_distance` worse than what was sized for.

---

## 4. Edge cases and bugs surfaced today

### 4.1 [P2] `risk/exposure_tracker.py:220–227` — `daily_pnl` / `daily_loss_pct` read across the lock boundary
`update_mark_price` and `close_position` mutate `_positions` and `_realised_pnl` under `self._lock`, but the `daily_pnl` and `daily_loss_pct` properties read `self._realised_pnl + self.unrealised_pnl` with no lock. `unrealised_pnl` iterates `self._positions.values()` — a `dict`-mutated-during-iteration `RuntimeError` is possible if the circuit breaker reads `daily_loss_pct` while a position is closing.

**Fix:** snapshot under lock:
```python
async def daily_loss_pct(self) -> float:
    async with self._lock:
        return safe_divide(
            self._realised_pnl + sum(p.unrealised_pnl for p in self._positions.values()),
            self._balance,
        ) * 100
```
Callers (the circuit breaker in `risk/circuit_breaker.py`) need to be made async. Severity is P2 because the race is short and the worst case is a one-cycle bad reading, not corrupt state — but it's the kind of intermittent bug that becomes a P0 only when the engine is heavily loaded.

---

## 5. Optimisation opportunities (no behavioural change)

### 5.1 [P2 — new] `signals/indicator_engine.py:324–331` — `_ema` seeds with first sample
```python
def _ema(data, period):
    k   = 2.0 / (period + 1)
    out = np.zeros(len(data))
    out[0] = data[0]                  # ← seed bias
    for i in range(1, len(data)):
        out[i] = data[i] * k + out[i - 1] * (1 - k)
    return out
```
Seeding with `data[0]` rather than `SMA(data[:period])` means the first ~3·period samples carry a bias that decays exponentially. For a 200-period EMA on 250 candles, only the last ~50 samples are stable — fine for the indicator engine's "needs ≥200 candles" precondition, but for the 50-period EMA the convention matters less. Bigger issue: the same function is reused for MACD signal smoothing on a short window; the seed bias can flip a marginal `macd_bullish_cross` at the very beginning of the series.

**Fix (and vectorise, addresses §2.2):**
```python
def _ema(data, period):
    k   = 2.0 / (period + 1)
    out = np.empty_like(data, dtype=float)
    out[:period] = np.nan
    seed = data[:period].mean()
    # vectorised EMA via scipy.signal.lfilter
    from scipy.signal import lfilter
    out[period - 1:] = lfilter([k], [1, -(1 - k)], data[period - 1:], zi=[(1 - k) * seed])[0]
    return out
```
Caller code already gates on `n >= period`, so returning NaN for the warm-up region is safe.

### 5.2 [P2] `signals/confluence_scorer.py:291–323` — pre-bucket scanner results
See §2.2 — single-line fix.

### 5.3 [P2] `signals/indicator_engine.py:184–188` — five list-comprehensions over the same `candles` list
```python
closes  = np.array([c.close  for c in candles], dtype=float)
highs   = np.array([c.high   for c in candles], dtype=float)
lows    = np.array([c.low    for c in candles], dtype=float)
volumes = np.array([c.volume for c in candles], dtype=float)
opens   = np.array([c.open   for c in candles], dtype=float)
```
Five passes over `candles` each cycle. Replace with one structured-array build:
```python
arr = np.fromiter(
    ((c.open, c.high, c.low, c.close, c.volume) for c in candles),
    dtype=np.dtype([("o", "f8"), ("h", "f8"), ("l", "f8"), ("c", "f8"), ("v", "f8")]),
    count=len(candles),
)
opens, highs, lows, closes, volumes = arr["o"], arr["h"], arr["l"], arr["c"], arr["v"]
```
~5× less iteration per indicator cycle. Minor (microseconds per symbol), but free.

---

## 6. Best-practice violations

| # | File / line | Violation | Suggested fix |
|---|---|---|---|
| 1 | `alerts/*.py` (multiple, see §2.3) | `datetime.utcnow()` is deprecation-warned in Py 3.12 | `datetime.now(timezone.utc)` |
| 2 | `scanner/pattern_scanner.py:232, 237` | Function-local imports of `_candle_to_dict` / `_dict_to_candle` from a sibling scanner module | Move to `data/data_normalizer.py`; import at top |
| 3 | `scanner/*`, `data/*`, `risk/*` (20+ matches) | `except Exception as exc:` without re-raise of `(asyncio.CancelledError, KeyboardInterrupt)` | Use `except (asyncio.CancelledError, KeyboardInterrupt): raise` first, then a narrow `except Exception` |
| 4 | `alerts/rate_limiter.py:261–264` | Mutates `_tokens` from outside `_TokenBucket._lock` (see §3.7) | Add `_TokenBucket.refund()` |
| 5 | `risk/exposure_tracker.py:220–227` | Reads shared state outside the asyncio.Lock (see §4.1) | Snapshot under lock |
| 6 | `risk/position_sizer.py:144` | Recomputes `notional` from rounded qty but **does not** recompute `risk_usdt`; second branch (line 157) does | Recompute on both paths (see §3.8) |
| 7 | Repo root | Six untracked `CODE_REVIEW_*.md` files | Triage into Linear/GitHub issues; archive the markdown |
| 8 | `data/cache_manager.py:91, 121` | `_pubsub_client` instantiated without explicit `socket_timeout` | Pass `socket_timeout=5` to match the main client |

---

## 7. Recommendations (ranked)

1. **Pick a P0 a day and clear it.** All seven are independently small. The signature/body fix (§3.1) and the reconnect counter (§3.5) are each one-commit changes; the queue race (§3.6) is a 5-line change. None of these need a sprint — they need an owner and an hour.
2. **Document the freeze.** If `restructure/2026-04-18-tier1-docs` is intentionally dormant, add a one-line note to `README.md` and have the daily review skill detect that and emit a "no-op verified" report instead of re-grepping the same file every day. Right now the report is honest but increasingly stale.
3. **Triage the six untracked review docs.** Either delete (if findings are duplicated in some other tracker) or convert to issues. Carrying them in repo root indefinitely is the worst of both worlds.
4. **Land the `tick_size`-per-symbol fix (§3.8) before any live trade.** Capital preservation is the prime directive; submitting orders that get silently re-rounded changes effective risk vs. configured risk.
5. **Validate the next live-trade run on testnet first** with a smoke test that exercises (a) a signed REST call (would catch §3.1), (b) one liquidation REST poll (would catch §3.2), (c) a deliberate cold-start trade attempt with no correlation history (would catch §3.3). Each test is ≤ 30 lines and would have caught these issues before this review series existed.

---

## 8. Appendix — verification commands used today

```
git -C coinscope_trading_engine/.. log --oneline -5
find scanner signals alerts risk data -name "*.py" -printf '%T+ %p\n' | sort -r | head
sed -n '95,105p' data/binance_rest.py
sed -n '215,235p' data/binance_rest.py
sed -n '180,205p' risk/correlation_analyzer.py
grep -n "reconnects" data/binance_websocket.py
sed -n '240,260p' alerts/alert_queue.py
sed -n '180,275p' alerts/rate_limiter.py
sed -n '85,165p' risk/position_sizer.py
sed -n '320,360p' signals/indicator_engine.py
sed -n '215,260p' risk/exposure_tracker.py
grep -rn "datetime.utcnow" alerts/
grep -rn "api_key\s*=\s*['\"]" scanner/ signals/ alerts/ data/ risk/
```
All findings reproducible with the above against `HEAD = 59416a2`.
