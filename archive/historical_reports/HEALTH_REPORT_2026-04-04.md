# CoinScopeAI — Daily Health Report
**Generated:** Saturday, April 4, 2026 — 20:07 UTC+3
**Environment:** Development / Testnet Mode
**Report Type:** Automated Daily Check

---

## Executive Summary

| Domain | Status | Notes |
|--------|--------|-------|
| Engine / Docker Services | ❌ OFFLINE | Containers not running |
| API Endpoint (port 8001) | ❌ OFFLINE | Not reachable |
| Redis | ❌ OFFLINE | Not responding to ping |
| Binance API Connectivity | ⚠️ UNKNOWN | Cannot verify — engine offline |
| Telegram Alert System | ⚠️ DEGRADED | Code-level issues remain (see below) |
| WebSocket Stability | ⚠️ UNKNOWN | Cannot verify — engine offline |
| Codebase Health | ⚠️ FAIR | 15/16 bugs resolved; 1 manual step pending |
| Security Posture | ✅ ACCEPTABLE | .env not committed; testnet mode active |

---

## 1. Error Logs — Past 24 Hours

❌ **No logs directory found** — The engine has not been running.

The `logs/` directory at the project root does not exist, which confirms no engine process has been active in the past 24 hours. This aligns with the Docker containers being offline.

**Action required:** Start the engine with `docker compose up --build` from the project root.

---

## 2. API Rate Limit Usage

### Binance Futures API
❌ **Cannot check live usage** — Engine is offline.

**Configured limits (from codebase review):**
- Engine auto-throttles at **85% of weight budget** via `X-MBX-USED-WEIGHT-1M` header monitoring
- Scan interval configurable via `SCAN_INTERVAL_SECONDS` in `.env`
- Default pairs: BTC, ETH, SOL, BNB, XRP, TAO (6 pairs per 4h cycle)
- Rate limit protection is implemented and functioning in code

**Recommendation:** Once started, monitor `/rate-limiter/stats` endpoint for live token bucket status.

### Telegram Bot API
⚠️ **Rate limiter configured but not verified live.**

Configured limits (from `rate_limiter.py`):
- Telegram: **20 messages / 60 seconds** (burst capacity: 20)
- Per-symbol: **3 signals / 5 minutes** (prevents single-pair spam)
- Webhook: **60 requests / 60 seconds**

Token-bucket implementation is correct and thread-safe. No live data available to check current consumption.

---

## 3. WebSocket Connection Stability

❌ **Cannot verify** — Engine not running.

**From codebase review:**
- Client connects to `wss://testnet.binancefuture.com/ws-fapi/v1` (testnet mode)
- Reconnection logic is implemented (`_ping_handler` + auto-reconnect on failure)
- Ping/pong handler runs as a separate asyncio task
- HMAC SHA256 signing is correctly implemented for authenticated streams

**Known risk:** The WebSocket client does not implement exponential backoff on reconnect — rapid reconnect loops could contribute to IP bans if Binance returns repeated errors.

---

## 4. Alert Volume & False Positive Rate

❌ **No data available** — No logs, no running engine.

**Architectural notes:**
- Signal thresholds are now correctly set at **≥8.0 for LONG** and **≤4.0 for SHORT** (BUG-2 fixed)
- Previously, overlapping thresholds (5.5/6.5) were causing all moderate-score bars to incorrectly emit SHORT signals — this has been corrected
- Multi-timeframe filter (`mtf_filter`) is now wired into `scan_pair()` (BUG-10 fixed)
- False positive rate should improve substantially with the new non-overlapping thresholds

**Recommendation:** After restart, monitor the first 2–3 scan cycles and compare LONG/SHORT/NEUTRAL distribution to verify balanced signal output.

---

## 5. Memory & Performance Metrics

❌ **No Prometheus/Grafana data available** — Services offline.

**Architecture:**
- Prometheus scrapes metrics from port `:9000` (MetricsExporter) and `:9090` (Prometheus UI)
- Grafana dashboard available at `:3000` (default password: `coinscopeai`)
- Celery ML worker is memory-capped at **2GB** (configured in docker-compose.yml)
- Redis is capped at **512MB** with `allkeys-lru` eviction policy

**Expected resource profile (per docker-compose):**
- Redis: ~50–100MB typical
- Engine: ~300–600MB (NumPy/Pandas arrays for 6 pairs × 300 bars)
- Celery ML worker: up to 2GB (HMM + RandomForest models)
- Total expected: ~1–2GB RAM across all containers

---

## 6. Security Assessment

✅ **`.env` file present locally** — API keys not committed to version control.

✅ **Testnet mode active** (`TESTNET_MODE=true`, `ENV=development`) — No real funds at risk.

✅ **HMAC signing** implemented correctly in `BinanceWebSocketClient._sign_request()`.

⚠️ **CORS policy is permissive** — `api.py` currently allows `allow_origins=["*"]`. This is acceptable for local development but must be restricted before any network-exposed deployment.

⚠️ **Grafana default password** (`coinscopeai`) should be changed if the service is ever exposed beyond localhost.

✅ **No hardcoded secrets detected** in any Python source files reviewed — all credentials loaded from environment variables via `pydantic-settings`.

---

## 7. Codebase Health: Bug Tracker

From the comprehensive audit (last reviewed 2026-04-02):

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| BUG-1 | 🔴 Critical | Missing `finbert_sentiment_filter.py` | ✅ Fixed |
| BUG-2 | 🔴 Critical | Signal threshold overlap (LONG/SHORT inverted) | ✅ Fixed |
| BUG-3 | 🔴 Critical | `/scan?pairs=` query param silently ignored | ✅ Fixed |
| BUG-4 | 🔴 Critical | `logs/` dir not created before FileHandler | ✅ Fixed |
| BUG-5 | 🔴 Critical | Consecutive loss counter increments on wins | ✅ Fixed |
| BUG-6 | 🔴 Critical | `alpha_decay_monitor` calls non-existent Telegram methods | ✅ Fixed |
| BUG-7 | 🔴 Critical | `retrain_scheduler` calls non-existent Telegram methods | ✅ Fixed |
| BUG-8 | 🔴 Critical | `journal.get_trades()` method doesn't exist | ✅ Fixed |
| BUG-9 | 🔴 Critical | async/sync mismatch in `funding_rate_filter.py` | ✅ Fixed |
| BUG-10 | 🔴 Critical | `mtf_filter` and `risk_gate` never called in `scan_pair()` | ✅ Fixed |
| BUG-11 | 🟡 Medium | Spread calculation wrong scale (liquidity score saturated) | ✅ Fixed |
| BUG-12 | 🟡 Medium | `np.roll` wraps first ATR bar | ✅ Fixed |
| BUG-13 | 🟡 Medium | Hardcoded `10000` initial capital in trade journal | ✅ Fixed |
| BUG-14 | 🟡 Medium | Sharpe annualization factor wrong (`√365` vs `√1460`) | ✅ Fixed |
| BUG-15 | 🟡 Medium | `ScaleUpManager` state resets on restart | ✅ Fixed |
| BUG-16 | ⚠️ Pending | Two conflicting `whale_signal_filter` files | ⚠️ **Manual step needed** |

**15/16 bugs resolved.** One manual cleanup step remains.

---

## 8. Actionable Recommendations

### 🔴 Immediate (Today)

1. **Start the engine** — All services are offline. Run from project root:
   ```bash
   docker compose up --build
   ```
   Then verify: `curl http://localhost:8001/health`

2. **Complete BUG-16 cleanup** — Delete the duplicate whale filter file:
   ```bash
   rm "coinscope_trading_engine/intelligence/whale signal filter (1).py"
   ```
   *(note the space in the filename — use quotes or tab-completion)*

### 🟡 This Week

3. **Run the full test suite** after startup to confirm all 16 fixes are stable:
   ```bash
   cd coinscope_trading_engine
   pytest tests/ -v
   ```

4. **Restrict CORS** in `api.py` — Replace `"*"` with `["http://localhost:5173", "http://localhost:3000"]` before any non-local deployment.

5. **Change Grafana default password** (`coinscopeai`) via the Grafana admin UI at `http://localhost:3000`.

6. **Implement exponential backoff** in `BinanceWebSocketClient` reconnect logic to avoid rapid reconnection loops triggering Binance IP bans.

### 🟢 Nice to Have

7. **Replace `MockSentimentFilter`** with a real or configurable sentiment source — currently all sentiment checks return `False` (no blocking), making the sentiment layer inactive.

8. **Wire `FundingRateFilter`** into the main orchestrator pipeline — it is initialized but never called (minor gap noted in M5 of audit).

9. **Set up log rotation** — once the engine is running, `logs/` will grow unbounded. Configure logrotate or a max file size in the logging config.

---

## System Architecture Reference

```
Redis (port 6379) ←─ All Celery workers
Engine (main.py) ─→ Prometheus (:9000) ─→ Grafana (:3000)
API (uvicorn :8001) ─→ frontend / scan requests
Celery Workers: default, ml, alerts, beat
Flower (Celery monitor :5555)
Prometheus (:9090)
```

---

*Report generated automatically by CoinScopeAI health-check task. No write actions were taken.*
