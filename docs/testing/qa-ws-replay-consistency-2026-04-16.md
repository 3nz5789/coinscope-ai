# QA Report — WebSocket Replay Consistency Test
**Date:** 2026-04-16  
**Module:** `data/` pipeline (DataNormalizer, BinanceFuturesStreamClient, BinanceStreamAdapter)  
**Test file:** `coinscope_trading_engine/tests/test_ws_replay_consistency.py`  
**Result:** ✅ **45 / 45 PASSED** — 0 failures, 0 errors  
**Runtime:** 0.34 s  

---

## Summary

The WebSocket replay consistency test validates that CoinScopeAI's data ingestion pipeline is fully deterministic and internally consistent — meaning the same market event always produces the same internal `Candle` object regardless of how many times it is replayed, which path it travels (REST vs WS), or what the queue state is.

All 8 test categories passed without issue.

---

## Test Matrix

| # | Category | Tests | Result | Notes |
|---|---|---|---|---|
| TC-01 | DataNormalizer Determinism | 3 | ✅ PASS | 50-replay stress, deep-copy safety, no mutation |
| TC-02 | REST vs WS Parity | 7 | ✅ PASS | Exact field equality; 4 symbols parametrized |
| TC-03 | Combined-Stream Envelope Unwrapping | 4 | ✅ PASS | Wrapped, unwrapped, batch, and malformed JSON |
| TC-04 | Closed-Candle Gating | 3 | ✅ PASS | Open candles correctly discarded at adapter layer |
| TC-05 | Float Precision Consistency | 12 | ✅ PASS | 6 price strings × 2 paths; includes 0.1 IEEE-754 case |
| TC-06 | Multi-Candle Sequence Ordering | 3 | ✅ PASS | 100-candle sequence, monotonic timestamps, REST/WS match |
| TC-07 | Queue Delivery Integrity | 4 | ✅ PASS | 50-event FIFO, open-event gate, queue-full safety |
| TC-08 | Malformed / Missing Field Handling | 9 | ✅ PASS | 8 failure modes, all return None with no crash |

---

## Key Findings

### ✅ DataNormalizer is fully deterministic
Replaying the same `ws_kline_event` dict 50 times produces byte-identical `Candle` objects on every pass. The normalizer has no mutable state, no `datetime.now()` contamination, and does not modify the input dict.

### ✅ REST and WS paths are exactly equivalent
`klines_to_candles()` (REST path) and `ws_kline_to_candle()` (WS path) produce identical `open`, `high`, `low`, `close`, `volume`, `quote_volume`, `taker_buy_base_volume`, `taker_buy_quote_volume`, `trades`, `open_time`, and `close_time` values when given the same underlying bar data. No precision drift between paths.

### ✅ Combined-stream envelope stripping is transparent
`BinanceFuturesStreamClient._dispatch()` correctly unwraps `{"stream": "...", "data": {...}}` envelopes before calling `on_message`. The callback always receives the raw event payload, regardless of whether it arrives wrapped or unwrapped. 10-event batch delivery confirmed in-order.

### ✅ Closed-candle gating is correct
The `_NativeAdapter.on_kline` callback correctly discards in-progress (open) candles where `k.x == False`. Only closed candles (`k.x == True`) enter the downstream queue. 20 open events → 0 queue entries.

### ✅ IEEE-754 float parsing is stable
Including the notoriously non-exact binary representation of `0.1`, all price strings parse to identical float values across 100 repetitions and between the REST and WS paths. Python's `float()` is deterministic for these inputs.

### ✅ 100-candle sequence ordering preserved end-to-end
Replaying 100 sequential kline events (ascending open_time, monotonically increasing close price) produces a candle list in the exact same order via both WS and REST paths. No reordering at any layer.

### ✅ asyncio.Queue bridge is FIFO and loss-free under normal load
50 closed-candle events → exactly 50 queue entries, dequeued in correct chronological order. Queue-full condition (5-item queue, 50 pushes) handled gracefully — first 5 accepted, remaining silently dropped with no exception.

### ✅ Malformed input is handled safely
All 8 tested failure modes (missing `k` key, missing `close` field, non-numeric price, empty dict, `None` input, malformed REST rows, extra unknown fields, extreme integer values) return `None` or skip the row without raising an unhandled exception.

---

## Side-finding: conftest.py field name mismatch (low severity)

The shared `conftest.py` fixture uses `taker_buy_volume` and `taker_buy_quote` as field names when constructing `Candle` objects. The actual `Candle` dataclass in `data/data_normalizer.py` defines these fields as `taker_buy_base_volume` and `taker_buy_quote_volume`.

**Impact:** The conftest fixtures (`btc_candles`, `eth_candles`) will fail if any test tries to use them. Tests that construct their own `Candle` objects directly (like `test_signals.py`) use a local `make_candle()` helper that also uses the old names.

**Recommendation:** Update `conftest.py` lines 53–54 and 73–74, and `test_signals.py` `make_candle()` helper:
```python
# OLD (broken)
taker_buy_volume = 600.0,
taker_buy_quote  = close * 600,

# CORRECT
taker_buy_base_volume  = 600.0,
taker_buy_quote_volume = close * 600,
```

This does not affect the replay consistency tests (which use their own fixtures) but would cause failures in any test that calls `btc_candles` or `eth_candles` fixtures.

---

## Validation Phase Coverage

This test suite covers the data ingestion layer end-to-end for COI-41 (30-Day Testnet Validation Phase). Specifically it validates:

- No silent data corruption between exchange wire format and internal `Candle` schema
- No float drift that could cause signal miscalculations
- No race condition risk from open-candle leakage into signal computation
- No crash risk from malformed exchange data (e.g. during Binance maintenance windows)

---

## Next QA Targets (recommended)

| Priority | Target | Why |
|---|---|---|
| High | `signals/indicator_engine.py` | RSI/EMA/ATR correctness with known reference values |
| High | `core/risk_gate.py` | Drawdown thresholds, kill switch trigger logic |
| Medium | `data/binance_rest.py` (mocked) | REST client retry/backoff behaviour |
| Medium | `execution/order_manager.py` (testnet mock) | Order lifecycle state machine |
| Low | `billing/stripe_gateway.py` | Webhook signature verification |
