# CoinScopeAI — Daily Code Review
**Date:** 2026-04-21
**Scope:** `coinscope_trading_engine/{scanner, signals, alerts, data, risk}`
**Reviewer:** Automated daily review (Claude)
**Prime directive per CoinScopeAI trading rules:** capital preservation

---

## 0. Delta Since Last Review

- Last engine commit: `59416a2` on **2026-04-18** (Tier-1 docs restructure + repo hygiene). **No code commits have landed in the past 3 days.**
- A prior automated review exists at `CODE_REVIEW_2026-04-19.md` (untracked). The findings below carry most of it forward but **correct two claims that were wrong on re-inspection** (see §6).
- Branch: `restructure/2026-04-18-tier1-docs` — still ahead of `main`. No uncommitted source changes.

Because no source changes have shipped, this report is a verification pass: I re-read the in-scope files, confirmed which prior P0/P1 claims are actually present in the code, corrected mischaracterizations, and flagged new items not called out previously.

---

## 1. Executive Summary

The engine has solid bones — clean async layering, dataclasses, type hints, a well-structured risk package. The persistent risk is a pattern of **fail-open behavior on ambiguous data**, which directly contradicts the stated prime directive (capital preservation). The single most important action for this week remains **converting silent-missing-data paths from "allow" to "block"** in `risk/correlation_analyzer.py` and `risk/exposure_tracker.py`.

| Severity | Count | Notes |
|---|---|---|
| **P0 — fix before next trading session** | 4 | correlation fail-open, reconnect counter no-op, webhook replay vector, alert-queue full-check race |
| **P1 — fix this week** | 11 | RSI on thin data, Kelly falsy-guard, naive exception swallow in webhook, cache-manager URL redaction, indicator recompute, etc. |
| **P2 — hygiene** | 14 | magic numbers, duplicate telegram modules, deprecated `datetime.utcnow()`, inconsistent return types, doc mismatch (`MAX_RAW_SCORE`) |

---

## 2. Code Quality Assessment

### 2.1 Security

**HMAC on REST (Binance):** correct. `data/binance_rest.py` builds the signed query with `timestamp` + `recvWindow` before HMAC-SHA256. No issues.

**Secrets:** keys come from `settings` and are never logged. `data/cache_manager.py::_safe_url()` masks the password in Redis URLs, but not the username — minor. Nothing else leaks.

**Webhook replay vector (carryover, still present):** `alerts/webhook_dispatcher.py` sends `X-Timestamp` and `X-Signature` as separate headers, but `_sign_payload(body, secret)` only hashes the body — not the timestamp. A captured webhook can be replayed indefinitely by any downstream consumer that trusts the signature. See `webhook_dispatcher.py:239-243` and `_sign_payload` at line 337.

**Over-broad exception catches:** the `alerts/webhook_dispatcher.py::_post_to_endpoint` block uses `except (httpx.HTTPError, Exception) as exc:` (line ~257). The `Exception` branch makes the `httpx.HTTPError` branch redundant and masks bugs. `scanner/base_scanner.py` has a similar bare `except Exception` in the run-loop merge path.

### 2.2 Performance

- `signals/indicator_engine.py` recomputes full EMA/RSI/ATR/ADX on every tick. Each `_adx` call iterates `O(len(closes))` per symbol × 5 timeframes. Add a per-symbol cache keyed on `last_closed_candle_ts`.
- `alerts/telegram_notifier.py::_is_duplicate` (line 131) rebuilds its eviction set on every call (`expired = [k for k, ts in self._dedup_cache.items() if now - ts > ttl]`). At steady state N is small; under a burst this is quadratic. Prefer `cachetools.TTLCache`.
- `data/cache_manager.py::subscribe` opens a new Redis pub/sub per call.
- `data/binance_websocket.py::_pending` dict is written by both send and receive paths. In single-loop asyncio this is functionally safe, but the `stats.reconnects` counter shows that the file *assumes* multi-producer mutation elsewhere (see §3.2).

### 2.3 Maintainability

- **Duplicate module pair**: `coinscope_trading_engine/scanner/` **and** `coinscope_trading_engine/scanners/` *both exist* at the top level. `signal_generator.py` imports from `scanners.*`, but `orchestrator` and most other callers import from `scanner.*`. This is a latent import-path trap and one of the two will eventually be deleted in the wrong order. Pick one canonical name and remove the other. (**Correction to prior review**: the `signals/signal_generator.py` imports are *not* orphaned — the modules exist in `core/`, `intelligence/`, and `scanners/`. The real problem is the `scanner/` vs `scanners/` duplication, not missing files.)
- Two Telegram modules: `alerts/telegram_alerts.py` (sync, `requests.post`, no dedup) and `alerts/telegram_notifier.py` (async, httpx, dedup). `retrain_scheduler.py` and `alpha_decay_monitor.py` still import the former. Consolidate or have the sync module delegate.
- `MAX_RAW_SCORE = 300.0` in `signals/confluence_scorer.py:67` — documentation claims a 0–12 confluence bucket, code normalizes against 300 then caps at 70. Either the docs or the code is stale.
- Deprecated `datetime.utcnow()` used in `alerts/alpha_decay_monitor.py`, `alerts/telegram_alerts.py`. Python 3.12 deprecation; use `datetime.now(timezone.utc)`.

---

## 3. Bugs & Edge Cases (severity-ordered)

### 3.1 [P0] `risk/correlation_analyzer.py` — fail-open on missing data

Two linked defects in the correlation path:

```python
# correlation_matrix() — line ~140
matrix[sym_a][sym_b] = round(r, 4) if r is not None else 0.0
```

Callers cannot distinguish "insufficient price history" (None → 0.0) from "genuinely uncorrelated" (r ≈ 0.0). Then in the position gate:

```python
# is_safe_to_add() — line ~189
r = self.pearson(new_symbol, sym)
if r is None:
    continue   # insufficient data — allow
```

This is **explicitly fail-open**. If the price feed hiccups or a new symbol has <5 points of history, the engine will approve correlated exposure it would otherwise reject. This directly contradicts capital preservation.

**Recommended fix:**
```python
# correlation_matrix: propagate None, do not coerce
matrix[sym_a][sym_b] = round(r, 4) if r is not None else None

# is_safe_to_add: fail CLOSED on insufficient data
if r is None:
    logger.warning(
        "corr(%s, %s) insufficient data — blocking add as a precaution",
        new_symbol, sym,
    )
    return False, f"Insufficient price history for {new_symbol} vs {sym}"
```

*(Prior review described this as a swallowed try/except returning 0.0. There is no try/except in `pearson()`; the real hole is the `None → 0.0` coercion in `correlation_matrix` plus the `continue` in `is_safe_to_add`.)*

### 3.2 [P0] `data/binance_websocket.py` — reconnect counter is a no-op on first use

```python
# line 247
self.stats.reconnects += 1 if self.stats.reconnects else 0
```

Precedence makes this `self.stats.reconnects += (1 if self.stats.reconnects else 0)`. When `reconnects == 0` (always, on first reconnect), the RHS is `0` — the counter never increments at this callsite. Line 321 has the correct form (`+= 1`); 247 is dead code, but also a logging lie: operators will see "reconnect attempts = 0" even after repeated reconnects through that path.

**Fix:**
```python
self.stats.reconnects += 1
```

### 3.3 [P0] `alerts/webhook_dispatcher.py` — HMAC does not cover timestamp

See §2.1. A replay attacker can re-POST a captured alert and the signature still verifies. Downstream consumers (Slack relays, auto-trader bots, journaling) have no way to reject a replay.

**Fix:**
```python
def _sign_payload(body: str, secret: str, ts: str) -> str:
    return hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()

# caller:
ts = str(int(time.time()))
headers["X-Timestamp"] = ts
headers["X-Signature"] = _sign_payload(body, self._secret, ts)
```

Also publish the signature scheme (e.g., `v1=…`) so consumers can rotate.

### 3.4 [P0] `alerts/alert_queue.py::_enqueue` — full-check/put race

```python
async def _enqueue(self, item):
    if self._queue.full():
        self._dropped += 1
        logger.warning("AlertQueue full … Dropping")
        return False
    await self._queue.put(item)
    return True
```

Between the sync `full()` probe and the `await put()`, another coroutine can fill the queue. `put()` then **blocks** instead of dropping, defeating the stated contract ("dropped=%d") and stalling the producer. During a market-event burst this can back-pressure the scan loop.

**Fix:**
```python
try:
    self._queue.put_nowait(item)
    return True
except asyncio.QueueFull:
    self._dropped += 1
    logger.warning("AlertQueue full (%d). Dropping %s alert (total dropped=%d).",
                   self._queue.maxsize, item.alert_type, self._dropped)
    return False
```

### 3.5 [P1] `signals/indicator_engine.py::_rsi` — no length guard

```python
avg_gain = np.mean(gains[:period])
avg_loss = np.mean(losses[:period])
...
if avg_loss == 0:
    return 100.0
```

Two issues:
1. If `len(closes) <= period`, `gains[:period]` silently averages fewer than `period` deltas and returns a misleading RSI; the caller cannot tell this happened.
2. `avg_loss == 0 → 100.0` is formula-correct but will routinely occur on thin pre-warmup data, triggering `rsi_overbought` and feeding a false-positive score into `confluence_scorer`.

**Fix:** return `None` when `len(deltas) < period` (or when `avg_gain + avg_loss == 0`), and make the caller treat `None` as "not enough history — skip the symbol this tick." The `IndicatorSet.rsi` field is already `Optional[float]`.

### 3.6 [P1] `risk/position_sizer.py::calculate` — Kelly falsy-guard

```python
if self._method == "KELLY" and win_rate and avg_rr:
    risk_fraction = self._kelly_fraction(win_rate, avg_rr)
```

`win_rate = 0.0` and `avg_rr = 0.0` are legitimate values (new strategy, no history) that should *explicitly* fall back to fixed-fraction, but the `and` guard treats them as "Kelly not configured" silently. An operator reading logs won't see why Kelly was bypassed.

**Fix:** use `is not None` checks and log when the Kelly math is skipped.

### 3.7 [P1] `risk/circuit_breaker.py` — rapid-loss log not cleared on reset

`record_trade_result` prunes entries older than `_rapid_window_s` but `reset()` / `reset_daily()` do not clear `_rapid_log` (only `reset_daily` does). After a manual `reset()`, a new loss within the previous rapid window can re-trip instantly. This is arguably safe-by-default, but inconsistent with operator intent.

**Fix:** clear `_rapid_log` inside `reset()`, or keep the behavior and document it explicitly.

### 3.8 [P1] `alerts/telegram_notifier.py::_is_duplicate` — O(N) eviction on every call

Already noted in §2.2. Real correctness issue only under sustained bursts, but easy to fix.

### 3.9 [P1] `signals/confluence_scorer.py` — `MAX_RAW_SCORE` mismatches docs

Docs describe a 0–12 confluence bucket; code normalizes raw against `300.0` then caps normalized scores at `70.0`. Either docs or code is wrong. At minimum, add a test that `max_possible_raw_score()` equals `MAX_RAW_SCORE`.

### 3.10 [P1] `alerts/webhook_dispatcher.py` — `except (httpx.HTTPError, Exception)`

`httpx.HTTPError` is a subclass of `Exception`. The tuple is redundant, and the effect is "catch everything" — hides programmer errors (AttributeError, TypeError) as transient network failures. Narrow to `(httpx.HTTPError, asyncio.TimeoutError)`.

### 3.11 [P2] Other hygiene
- `data/cache_manager.py::_safe_url` redacts password but not username.
- Magic numbers (`0.001` tweezer tolerance in `pattern_scanner.py`, `1.5` volume multiplier, dedup TTL) should live in `config/settings`.
- `datetime.utcnow()` appears in `alerts/alpha_decay_monitor.py` and `alerts/telegram_alerts.py`.
- `scanner/` vs `scanners/` duplication (see §2.3).

---

## 4. Optimization Opportunities

1. **Per-symbol indicator cache.** `IndicatorEngine` is the single hottest path under a 50-symbol × 5-timeframe scan. Gate recompute on `last_closed_candle_ts`; incremental Wilder smoothing only needs the latest bar.
2. **Reuse a single Redis pub/sub.** `data/cache_manager.py::subscribe` currently opens a fresh connection per caller; switch to a shared pub/sub managed by `CacheManager.start`.
3. **Bulk-fetch ticker snapshots.** `data/binance_rest.py` issues per-symbol REST calls in a few places. `/fapi/v1/ticker/24hr` accepts a batched response — use it and cache for `ticker_refresh_s`.
4. **Move the rapid-loss prune to a monotonic deque.** `circuit_breaker._rapid_log` list-comp is O(N) per trade; `collections.deque` with left-pop amortizes to O(1).
5. **Indicator engine: vectorize `_adx`.** The inner Python loops in `_adx` / `_wilder` become hot on 5m-1h streams; `pandas.ewm` or `ta-lib` drops most of this cost.

---

## 5. Best-Practice Violations (summary)

- Fail-open error handling in risk gates (§3.1).
- Separate auth artifacts (timestamp not under HMAC) (§3.3).
- Race between non-atomic check-then-act in async code (§3.4).
- Magic numbers in trading-critical logic (§2.3, §3.11).
- Duplicated modules and mixed import conventions (§2.3, `scanner/` vs `scanners/`).
- Deprecated datetime API (§2.3).
- Over-broad exception catches (§2.1, §3.10).

---

## 6. Corrections to the 2026-04-19 Automated Review

These are for future-review drift-tracking, not accusations — the prior run was still net-useful, but two of its P0 claims do not hold up on re-inspection.

1. **"Orphaned imports in `signals/signal_generator.py` — module fails to import."**
   All four modules (`core.scoring_fixed`, `core.multi_timeframe_filter`, `intelligence.hmm_regime_detector`, `scanners.volume_scanner`, `scanners.liquidation_scanner`) exist in the tree today. The real hazard is the `scanner/` vs `scanners/` top-level duplication, which the prior review did not mention.
2. **"`risk/correlation_analyzer.py` silently returns 0.0 via a try/except."**
   No try/except is present in `pearson()`. The fail-open happens via `correlation_matrix`'s `None → 0.0` coercion and `is_safe_to_add`'s `continue` on missing data (§3.1). Same capital-preservation impact, different mechanism.
3. **"Race on circuit-breaker state."** In the current code, all mutators are synchronous and — in a single-loop asyncio context — execute atomically between awaits. It is not a correctness bug at present, though it *would* become one if any mutator migrated to `async def` with an `await` mid-update. Reclassified from P0 → P2 (defensive lock recommended before any future `async` refactor).

---

## 7. Recommended Priority Order (this week)

1. Flip `risk/correlation_analyzer` to fail-closed (§3.1).
2. Patch the reconnect counter one-liner (§3.2).
3. Include timestamp in webhook HMAC and bump scheme to `v1=` (§3.3).
4. Replace `full()`+`put()` with `put_nowait` (§3.4).
5. Add `None` return from `_rsi` on thin data and propagate (§3.5).
6. Consolidate `scanner/` vs `scanners/` into one canonical package.
7. Retire `alerts/telegram_alerts.py` or route it through `telegram_notifier`.

---

*Next scheduled run: 2026-04-22 09:00. If no commits land by then, this report will largely repeat — at which point the correct action is to work the punch list rather than run another review.*
