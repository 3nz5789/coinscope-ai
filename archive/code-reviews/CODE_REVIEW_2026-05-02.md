# CoinScopeAI — Daily Code Review
**Date:** 2026-05-02
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}` — 9,865 LOC across 31 files
**Reviewer:** Automated daily review (Claude, scheduled 09:00, run unattended)
**Prime directive (per CoinScopeAI trading rules):** *capital preservation*
**Branch:** `restructure/2026-04-18-tier1-docs` (HEAD `59416a2`, unchanged)

---

## 0. Delta Since Last Review (2026-05-01)

- **No new commits.** `git log -1 --oneline` returns `59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)`. `git status` reports the same untracked-only state (CODE_REVIEW_*.md, business-plan/, legal/, strategy/, validation_analysis.py, etc.); no tracked-file modifications.
- **No file mutations in scope.** Every `.py` file under `scanner/`, `signals/`, `alerts/`, `data/`, `risk/` reports the identical mtime `2026-04-18 23:32:06` it had on the 2026-05-01 snapshot. Total LOC in scope: **9,865** — byte-for-byte identical. MD5 of the concatenated module hashes is `7c7e5c7…d9e4f59`, the same value computed yesterday.
- **Fourteenth consecutive day** with zero source changes in scope (Apr 19, 21, 22, 23, 24, 26, 30, May 1 reviews on the books; today is the ninth under the daily cadence).
- **All 7 P0s carry over** — re-verified at the same line numbers today (§3.1–§3.7, spot-check log in §6).
- **All 17 P1s carry over.** No new P1.
- **All 22 P2s carry over.** No new P2.
- **Nine untracked `CODE_REVIEW_*.md` files** (Apr 19 → May 1) remain in the repo root, still **not committed, not triaged, not converted into Linear/GitHub issues**. Today's becomes the tenth.
- **No new findings today.** Yesterday's review widened the spot-check into `signals/signal_generator.py` and surfaced one P1 plus three P2s. Today's deeper read of the same file at the same SHA produces no additional defects beyond what is already on the books.
- **Recommendation, repeated for the sixth day:** *stop adding findings and start clearing them.* If the engine is intentionally dormant pending the Tier-1 doc restructure, please add a one-line note to `README.md` ("engine code frozen on `59416a2` pending restructure — daily review will be a no-op verification") so this scheduled task can switch to a cheaper "still frozen, still defective" check instead of re-grepping the same defects every morning. Today's report is already that cheaper format; if you prefer the full carryover narrative, see CODE_REVIEW_2026-05-01.md §3–§5 — every line, line-number, and recommendation in that document is still current.

---

## 1. Executive Summary

The code under review has been frozen for fourteen days. None of the seven capital-at-risk P0s identified earlier have been touched. Running the engine against mainnet today still means the following are all live on the production path:

1. Signed REST requests have HMAC/body order mismatch and a stale-timestamp bug on retry — every signed call can fail with `-1022` or `-1021` (§3.1).
2. Liquidation REST normalisation silently returns `None` because it parses the WS short-key shape against REST long-key payloads — `LiquidationScanner` is effectively a no-op (§3.2).
3. Correlation gate fails **open** on insufficient history, violating capital preservation at engine start-up (§3.3).
4. Webhook HMAC still does not cover `X-Timestamp` — replayable (§3.4).
5. WebSocket reconnect counter on the connect-loop path is a no-op self-reference (§3.5).
6. Alert queue has a `full()`/`put()` check-then-act race that can block producers under burst (§3.6).
7. Rate-limiter per-symbol bucket map is unbounded *and* the refund path mutates `_tokens` outside the bucket lock (§3.7).

| Severity | Count | Δ vs. 2026-05-01 |
|---|---:|---:|
| **P0 — fix before next live trading session** | **7** | unchanged (14 days frozen) |
| **P1 — fix this week** | **17** | unchanged |
| **P2 — hygiene** | **22** | unchanged |

---

## 2. Code Quality Assessment

### 2.1 Security
No regressions; no improvements since 2026-04-19. Re-verified today (file paths and line numbers spot-checked, see §6):
- Webhook HMAC omits timestamp (§3.4) — replayable indefinitely. `_sign_payload(body, secret)` at `alerts/webhook_dispatcher.py:337` hashes `body.encode()` only; the `X-Timestamp` header set at line 239 is sent in clear and never bound into the MAC. Verified today at the same line numbers.
- Signed-request signature mismatch (§3.1) — every signed REST call is vulnerable to `-1022` rejection; on retries the stale `timestamp` (set once at `data/binance_rest.py:220`, before the `while attempt <= retries` loop at line 227) will trip `-1021` and burn the `recvWindow` budget. Verified today at the same line numbers.
- `data/cache_manager.py:91` — `_pubsub_client` field declared but never assigned. The `close()` path at line 122 simply skips the `if self._pubsub_client:` branch. Harmless today, but a placeholder to fix when wired up.
- No hardcoded secrets in scope: `grep -rn "api_key\s*=\s*['\"]"` returns clean.

### 2.2 Performance
No regressions; no improvements. Still open:
- `signals/confluence_scorer.py:311` — `score_all` filters `scanner_results` once per symbol inside `for symbol in symbols:`. O(R · S). With R ≈ 6 scanners × S ≈ 200 USDT-perps this is ~240k comparisons per cycle. Sub-second today, will dominate when the symbol universe expands. Fix: bucket once with `defaultdict(list)`. (Carryover, unchanged.)
- `alerts/rate_limiter.py:175` — `_symbol_buckets` is unbounded; never evicts buckets for delisted or never-traded symbols. Slow leak. Add an LRU cap and a daily prune on `reset_daily`. (Carryover, unchanged.)
- `signals/indicator_engine.py:324–331` — `_ema` is a Python `for` loop, called for SMA-20/50/200, MACD fast/slow/signal, and Stoch-K/D smoothing per symbol per cycle. Vectorise with `pandas.Series.ewm(adjust=False).mean()` or `scipy.signal.lfilter([k], [1, -(1-k)], data)`. (Carryover, unchanged.)
- `data/binance_websocket.py:325` — recv-loop reconnect path uses the *exponentially backed-off* `_reconnect_delay` even though the previous connect succeeded. After a long-tail disconnect the next reconnect can wait ≥ `MAX_RECONNECT_DELAY_S` (60s default) before re-attempting, even though connectivity is healthy. Fix: reset `_reconnect_delay` to `RECONNECT_DELAY_S` on a successful connect inside the *connect* path (already done at line 248) **and** on a clean recv-loop entry. (Carryover, unchanged.)

### 2.3 Maintainability
No regressions; no improvements. Still open:
- 31 files, no docstrings on 11 public methods (mostly `signals/backtester.py` and `data/data_normalizer.py`).
- Mixed naming: `scanner/funding_rate_scanner.py` uses `funding_rate` while `signals/indicator_engine.py` and `risk/position_sizer.py` use `funding`. Pick one.
- `alerts/telegram_notifier.py` (461 LOC) and `alerts/telegram_alerts.py` (76 LOC) have overlapping responsibilities. Merge or document the split.
- No `mypy.ini` or `pyproject.toml` type-check configuration in the engine package; mixed `Optional[X]` vs `X | None` across modules (Python 3.10+).

---

## 3. P0 — Capital-at-Risk Defects (Carryover, all re-verified)

> All seven re-verified at the same line numbers today. See §6 for the spot-check log. Full root-cause and fix narratives are in CODE_REVIEW_2026-04-19.md and have not changed since. Summarised below for the on-call reader.

### 3.1 Signed REST — HMAC/body order mismatch + stale timestamp on retry
**File:** `data/binance_rest.py:97`, `data/binance_rest.py:217–235`
**Bug:** `_sign(secret, params)` (line 97) sorts params alphabetically; the request then sends `params` (still a dict) as either query string (GET) or `data=` form body (POST). aiohttp may reorder dict iteration, breaking the alphabetical-sort assumption Binance verifies against. Separately, `req_params["timestamp"]` is set once at line 220 *before* the `while attempt <= retries` loop at line 227 — a retry can therefore arrive at Binance with a timestamp older than `recvWindow` and trip `-1021`.
**Fix:** build the canonical query string explicitly, sign it as a string, and send the same string in the body. Re-set `timestamp` on every retry attempt inside the loop.

### 3.2 LiquidationScanner REST normalisation is a no-op
**File:** `data/data_normalizer.py:421–443`, consumer `scanner/liquidation_scanner.py:153–164`
**Bug:** `liquidation_to_schema` reads short keys (`s`, `S`, `q`, `p`, `T`, `o`, `f`, `ap`, `X`) which are the WS `forceOrder` shape. Binance REST `allForceOrders` returns long keys (`symbol`, `side`, `origQty`, `price`, `time`, `type`, `timeInForce`, `averagePrice`, `status`). On the REST path `raw.get("o", raw)` returns `raw` (REST has no `o` key), then `order["s"]` raises `KeyError` → caught at line 442 → returns `None`. `_fetch_liquidations` filters out the `None`s at line 157, so `LiquidationScanner` runs on an empty list every cycle — it never fires. **Confirmed today by direct read of both files at the same line numbers.**
**Fix:** add a long-key branch in `liquidation_to_schema`. Add a unit test covering both shapes.

### 3.3 Correlation gate fails OPEN on insufficient history
**File:** `risk/correlation_analyzer.py:188–200`
**Bug:** at line 191, `pearson(...)` returns `None` if either symbol has fewer than `min_history` samples; the loop `continue`s. Comment on line 191 says "insufficient data — allow." If *every* candidate pair has insufficient data, the function returns `(True, "")` at line 200 — i.e. the correlation gate **passes** at engine cold-start when no symbol has a full price window. Capital-preservation directive requires the opposite default: fail closed until `min_history` is met. Verified today.
**Fix:** track `decided_count` and `gated_count`. If no pair was decideable, return `(False, "insufficient correlation history; gating closed")`.

### 3.4 Webhook HMAC does not cover `X-Timestamp`
**File:** `alerts/webhook_dispatcher.py:239`, `alerts/webhook_dispatcher.py:337–342`
**Bug:** `headers["X-Timestamp"]` is sent in clear and the signature only covers `body`. A captured payload can be re-played with a fresh timestamp under any tolerance window the receiver chooses, defeating the point of having a timestamp. Verified today at the same line numbers.
**Fix:** sign `f"{ts}.{body}"` and have the receiver verify the prefix.

### 3.5 WebSocket reconnect counter is a no-op self-reference
**File:** `data/binance_websocket.py:247`
**Bug:** `self.stats.reconnects += 1 if self.stats.reconnects else 0` only increments when the counter is already non-zero; on the first reconnect the field stays at `0` and never advances. The condition is inverted relative to intent. **Confirmed today at the same line.** The recv-loop path at line 321 (`self.stats.reconnects += 1`) is correct, so reconnects triggered after a successful connection do count — but a reconnect that comes from the connect-loop never does, which masks a class of failure in monitoring.
**Fix:** drop the conditional: `self.stats.reconnects += 1`. Or, better, only increment on the recv-loop path and have the connect-loop path increment a separate `connect_retries` counter so the two failure modes are distinguishable.

### 3.6 Alert queue has a check-then-act race
**File:** `alerts/alert_queue.py:84–112`
**Bug:** producer calls `if self._q.full(): drop` then `await self._q.put(...)`. Between the `full()` check and the `put()` another coroutine can drain the queue, causing the producer to drop spuriously; or vice-versa, two producers can both pass the `full()` check and one will block. Drop logic must be `put_nowait` inside `try/except QueueFull`.
**Fix:** replace with `try: q.put_nowait(item) except asyncio.QueueFull: log_drop(item)`.

### 3.7 Rate-limiter unbounded per-symbol map + lock-escape on refund
**File:** `alerts/rate_limiter.py:172–223`
**Bug:** `_symbol_buckets` (`defaultdict(_Bucket)`) grows indefinitely; the refund path at line 218 mutates `bucket._tokens` after releasing the per-bucket lock taken at line 209. Concurrent `consume`/`refund` calls can interleave and produce a negative or stale `_tokens` value.
**Fix:** add an LRU cap with daily prune, and keep the refund mutation inside the same `async with bucket._lock` block.

---

## 4. P1 — Fix This Week (Carryover, no new findings)

All 17 P1s identical to 2026-05-01. Spot-checked five today (positions in scope as of last review):

- §4.2 `signals/signal_generator.py:142` — `_aggregate_scores` divides by `len(active)` without a zero-guard. Verified today.
- §4.5 `risk/exposure_tracker.py:188` — `total_notional` does not account for cross-margin offsets when `position.side == "SHORT"` and a hedge leg exists. Verified today.
- §4.7 `data/binance_rest.py:412` — `klines` retry treats HTTP 418 (IP ban) the same as 429 (per-route limit). Verified today.
- §4.11 `signals/indicator_engine.py:188` — `vwap` rolling window resets on day boundary in exchange time, not symbol time; intraday VWAP can jump on cross-asset listings. Verified today.
- §4.16 `signals/signal_generator.py:201` — yesterday's new P1: HMM regime detector reuses the same `_hmm_state` dict across symbols, so a regime flip on BTC silently overrides ETH's last-known state until the next refresh tick. Verified today at the same line.

The remaining twelve P1s (rate-limiter, market-stream backpressure, scanner threshold loaders, etc.) are unchanged from prior reviews. Refer to CODE_REVIEW_2026-05-01.md §4 for the full set.

---

## 5. P2 — Hygiene (Carryover, no new findings)

All 22 P2s identical to 2026-05-01. No new P2 surfaced today. Refer to CODE_REVIEW_2026-05-01.md §5 for the full list.

The three P2s added yesterday (`signals/signal_generator.py` confidence calibration, `signals/entry_exit_calculator.py` rounding, `risk/circuit_breaker.py` log-spam on cooldown) are still present at the same line numbers — none touched.

---

## 6. Verification Log (today)

```
$ git log -1 --oneline
59416a2 docs: Tier-1 restructure + repo hygiene pass (2026-04-18)

$ git status --porcelain | grep -v "^??" | wc -l
0                                  # zero tracked changes

$ wc -l scanner/*.py signals/*.py alerts/*.py data/*.py risk/*.py | tail -1
9865 total                         # unchanged

$ md5sum scanner/*.py signals/*.py alerts/*.py data/*.py risk/*.py | md5sum
7c7e5c704b6afca280c233639d9e4f59 -  # unchanged from 2026-05-01

$ stat -c "%y" scanner/liquidation_scanner.py
2026-04-18 23:32:06.086790293 +0000
```

Spot-checks (file:line confirms each P0 still at the location reported in §3):

| § | File | Line | Verified |
|---|---|---:|---|
| 3.1 | data/binance_rest.py | 97, 220, 227 | ✓ |
| 3.2 | data/data_normalizer.py | 421–443 | ✓ |
| 3.2 | scanner/liquidation_scanner.py | 153–164 | ✓ |
| 3.3 | risk/correlation_analyzer.py | 188–200 | ✓ |
| 3.4 | alerts/webhook_dispatcher.py | 239, 337–342 | ✓ |
| 3.5 | data/binance_websocket.py | 247 | ✓ |
| 3.6 | alerts/alert_queue.py | 84–112 | ✓ |
| 3.7 | alerts/rate_limiter.py | 172–223 | ✓ |

---

## 7. Specific Recommendations With Code Examples

These are the same fixes recommended in CODE_REVIEW_2026-04-19.md §6 and CODE_REVIEW_2026-05-01.md §7. Reproduced verbatim today because the source has not changed and the fixes have not landed. The two highest-leverage fixes — they would clear three P0s in roughly 60 lines of diff — are:

### 7.1 `data/binance_rest.py` — sign once, send the same string
Replace lines ~217–235 with:

```python
# Build a canonical query string ourselves so what we sign is bit-identical
# to what we send.
import time
from urllib.parse import urlencode

req_params = dict(params or {})

while attempt <= retries:
    if signed:
        # Re-stamp the timestamp on every retry, otherwise -1021.
        req_params["timestamp"]  = int(time.time() * 1000)
        req_params["recvWindow"] = self._recv_window
        # Drop any signature from a previous attempt before signing.
        req_params.pop("signature", None)
        qs = urlencode(sorted(req_params.items()))
        sig = hmac.new(
            self._api_secret.encode("utf-8"),
            qs.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        canonical = f"{qs}&signature={sig}"
    else:
        canonical = urlencode(sorted(req_params.items()))

    url = f"{self._base_url}{path}"
    t0 = time.monotonic()
    try:
        async with self._session.request(
            method,
            url if method != "GET" else f"{url}?{canonical}",
            data=canonical if method != "GET" else None,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
                if method != "GET" else None,
        ) as resp:
            ...
```

This collapses §3.1 (HMAC/body mismatch) and the §3.1 stale-timestamp bug into one fix, and removes the dependence on dict iteration order in the request layer.

### 7.2 `data/data_normalizer.py` — accept both REST and WS shapes
Replace `liquidation_to_schema` (lines 421–443) with:

```python
def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
    """
    Accept either:
      • REST allForceOrders (long keys: symbol, side, origQty, …)
      • WS forceOrder event (raw["o"] -> short keys: s, S, q, …)
    """
    try:
        if "o" in raw and isinstance(raw["o"], dict):
            o = raw["o"]                                    # WS shape
            return LiquidationOrder(
                symbol        = o["s"],
                side          = o["S"],
                order_type    = o["o"],
                time_in_force = o["f"],
                qty           = float(o["q"]),
                price         = float(o["p"]),
                avg_price     = float(o["ap"]),
                status        = o["X"],
                time          = _ms_to_dt(int(o["T"])),
            )
        # REST shape — long keys
        return LiquidationOrder(
            symbol        = raw["symbol"],
            side          = raw["side"],
            order_type    = raw.get("type", "LIMIT"),
            time_in_force = raw.get("timeInForce", "IOC"),
            qty           = float(raw.get("origQty", raw.get("executedQty", 0))),
            price         = float(raw["price"]),
            avg_price     = float(raw.get("averagePrice", raw["price"])),
            status        = raw.get("status", "FILLED"),
            time          = _ms_to_dt(int(raw["time"])),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
        return None
```

This single change makes `LiquidationScanner` fire — without it, today's "liquidation cascade" alpha source produces no alerts no matter how violent the move.

### 7.3 `risk/correlation_analyzer.py` — fail closed on insufficient history
Replace lines 188–200 with:

```python
decided_count = 0
gated_count   = 0

for sym, pos in open_positions.items():
    if sym == new_symbol or pos.direction != new_direction:
        continue
    r = self.pearson(new_symbol, sym)
    if r is None:
        continue                          # genuinely insufficient
    decided_count += 1
    if abs(r) >= self._threshold:
        gated_count += 1
        return (
            False,
            f"{new_symbol} highly correlated with open {sym} "
            f"(r={r:.2f} ≥ {self._threshold})",
        )

if decided_count == 0 and len(open_positions) > 0:
    return (False, "insufficient correlation history; gating closed (cold-start)")

return (True, "")
```

`open_positions` may legitimately be empty (cold start, no trades yet) — in that case there is nothing to be correlated *with*, and the gate should pass. The fix only flips the default when there *are* open positions but no pair could be decided.

---

## 8. What Should Happen Next

1. **Today:** triage `CODE_REVIEW_2026-04-19.md` § 3 into Linear (or GitHub Issues). The seven P0s are individual tickets; assign owners.
2. **Today:** add a one-line note to `README.md` declaring the engine code frozen. Without that, this scheduled task wakes up every morning, re-reads 9,865 LOC, finds the same defects, and writes another ~30 KB of markdown into the repo root that nobody reads.
3. **This week:** land §7.1 and §7.2 — they together clear three P0s and unblock any meaningful integration testing of the live engine. They are scoped to ~60 lines of diff.
4. **This week:** delete the ten `CODE_REVIEW_*.md` files from the repo root once their findings are in the issue tracker. Their continued presence is a `git status` noise source and confuses readers about which is canonical.
5. **Once unfrozen:** switch this scheduled task back to a real diff-aware review by feeding `git log --since=yesterday` into the prompt and only re-grepping files that actually changed.

---

*End of report. No new findings today; carryover only. If this is the sixth consecutive frozen-state report you have received, consider the README note in §0 — this task can be made cheaper.*
