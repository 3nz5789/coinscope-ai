# CoinScopeAI — Troubleshooting Guide

## Quick-Reference Checklist

Before debugging, run the smoke test first:
```bash
cd coinscope_trading_engine
python testnet_check.py
```
It checks all 7 prerequisites and prints exact fix instructions for each failure.

---

## 1. Installation Issues

### `pip install -r requirements.txt` fails

**Symptom:** `ERROR: Could not find a version that satisfies the requirement…`

**Fix A — proxy / firewall:**
```bash
pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

**Fix B — Python version:**
```bash
python --version   # must be 3.11+
# If not, install via pyenv:
pyenv install 3.11.9
pyenv local 3.11.9
```

**Fix C — use a virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Fix D — torch is slow to install:**
```bash
# Install everything except torch first, then torch separately
pip install -r requirements.txt --no-deps
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

---

## 2. Binance Connectivity

### `Binance REST ping failed`

**Causes and fixes:**

| Cause | Fix |
|-------|-----|
| No internet | Check connection |
| IP banned by Binance | Wait 24h or use a different IP / VPN |
| Wrong API key for testnet | Keys from binance.com don't work on testnet — create keys at testnet.binancefuture.com |
| TESTNET_MODE=false but using testnet keys | Set `TESTNET_MODE=true` in `.env` |

### `AuthenticationError: -1022 Signature`

Timestamp in request is too far from server time. Causes: system clock drift.
```bash
# Sync system clock (Linux/macOS)
sudo ntpdate pool.ntp.org
# or
sudo timedatectl set-ntp true
```

### `BinanceAPIError: -2015 Invalid API-key`

- Keys must have **Futures** permission enabled (not just spot)
- Keys from `testnet.binancefuture.com` — **not** from `testnet.binance.vision`
- Check for leading/trailing whitespace in `.env` values

### Rate limit errors (`-1003`)

The engine auto-detects throttling at 85% weight usage via `X-MBX-USED-WEIGHT-1M`.
If you're still hitting limits, reduce scan frequency:
```bash
# In .env
SCAN_INTERVAL_SECONDS=60   # scan once per minute instead of every 5s
SCAN_PAIRS=BTCUSDT,ETHUSDT  # fewer pairs
```

---

## 3. Redis Issues

### `Redis connection refused`

```bash
# Check if Redis is running
redis-cli ping   # should return PONG

# Start Redis (macOS with Homebrew)
brew services start redis

# Start Redis (Linux)
sudo systemctl start redis

# Start Redis with Docker (quickest)
docker run -d -p 6379:6379 redis:7-alpine
```

### `aioredis.exceptions.ResponseError: WRONGTYPE`

Key collision — a key exists with a different type than expected.
```bash
redis-cli FLUSHDB   # clear the database (dev only — data loss!)
```

### High Redis memory usage

The cache manager uses TTL on all keys (default 60s). Check for runaway keys:
```bash
redis-cli INFO memory
redis-cli DBSIZE
redis-cli --scan --pattern "coinscopeai:*" | wc -l
```

---

## 4. WebSocket Issues

### WebSocket keeps disconnecting

Binance closes connections after 24 hours — the engine auto-reconnects.
For frequent drops (< 1 hour), check:

```bash
# Test raw WS connection (requires websocat)
websocat wss://stream.binancefuture.com/ws/btcusdt@kline_1m

# Check for firewall blocking WSS
curl -I https://stream.binancefuture.com
```

**Fix:** Switch to `python-binance` backend which has built-in keepalive:
```bash
# .env
WS_BACKEND=python-binance
```

### `ssl.SSLCertVerificationError`

```bash
pip install certifi
python -m certifi   # shows path to cert bundle
# Set SSL_CERT_FILE env var to that path
```

### No messages received for > 60 seconds

```bash
# Verify the stream is active:
curl "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=1"
# Should return data. If not, Binance may be in maintenance.
```

---

## 5. Signal / Scanner Issues

### No signals generated

**Diagnostic steps:**
```bash
# Lower the confluence threshold temporarily
# In .env:
MIN_CONFLUENCE_SCORE=30   # default is 65

# Run a manual scan via API
curl "http://localhost:8001/scan" -X POST \
  -H "Content-Type: application/json" \
  -d '{"pairs": ["BTCUSDT"], "timeframe": "1h", "limit": 100}'
```

Check the logs for scanner-level hits:
```bash
# Set debug logging
LOG_LEVEL=DEBUG
# Look for lines like:
# DEBUG VolumeScanner BTCUSDT: no hit (volume=1.2× baseline, threshold=3×)
```

### Signals generated but not alerted

Check the alert queue and rate limiter:
```bash
curl http://localhost:8001/rate-limiter/stats
# Look for "times_limited" > 0
```

Per-symbol rate limit: 3 signals per 5 minutes by default.
To relax during testing:
```bash
# In .env
SIGNAL_COOLDOWN_SECONDS=30
```

---

## 6. Circuit Breaker Tripped

### Trading halted unexpectedly

```bash
# Check circuit breaker state
curl http://localhost:8001/circuit-breaker

# Reset via API
curl -X POST http://localhost:8001/circuit-breaker/reset
```

**Common causes:**
| Trigger | Default threshold | Fix |
|---------|------------------|-----|
| Daily loss | 2% of balance | Wait for daily reset at 00:00 UTC, or increase `MAX_DAILY_LOSS_PCT` |
| Rapid loss | 1.5% in 5 min | Normal during volatile periods — reset and monitor |
| Manual trip | n/a | Check logs for who/what triggered it |

---

## 7. Celery Issues

### Worker not picking up tasks

```bash
# Check worker is running
celery -A celery_app inspect active

# Check broker connectivity
celery -A celery_app inspect ping

# Check queue lengths
celery -A celery_app inspect reserved
```

### Tasks stuck in `PENDING`

```bash
# Check Redis queues directly
redis-cli LLEN coinscopeai:default
redis-cli LLEN coinscopeai:ml_tasks

# Restart workers
celery -A celery_app control shutdown
celery -A celery_app worker --loglevel=info &
```

### Dead Letter Queue growing

```bash
redis-cli LLEN coinscopeai:dlq
redis-cli LRANGE coinscopeai:dlq 0 -1   # inspect failed tasks
```

---

## 8. Prometheus / Metrics Issues

### Metrics endpoint not accessible

```bash
curl http://localhost:9090/metrics   # should return text/plain Prometheus format

# If port 9090 is in use:
# In main.py, change: start_metrics_server(port=9091)
```

### `prometheus_client not installed`

```bash
pip install prometheus-client
```

This is optional — the engine runs fine without it, metrics just become no-ops.

---

## 9. Docker Issues

### Container fails to start

```bash
docker compose logs engine   # check engine logs
docker compose logs redis    # check Redis logs

# Common fix — rebuild after code changes:
docker compose up --build
```

### Port already in use

```bash
# Find what's using port 8001
lsof -i :8001   # macOS/Linux
netstat -ano | findstr :8001   # Windows

# Change port in docker-compose.yml:
ports:
  - "8002:8001"   # map host 8002 → container 8001
```

### Volume permission errors

```bash
docker compose down -v   # remove volumes
docker compose up --build
```

---

## 10. Performance Issues

### Scan cycle taking > 10 seconds

Run the benchmark to find the bottleneck:
```bash
python benchmark.py --test scanner --iterations 50
```

**Common causes:**

| Cause | Fix |
|-------|-----|
| Too many pairs | Reduce `SCAN_PAIRS` to top 10 |
| Slow REST calls | Use WebSocket candle cache — enable `WS_BACKEND` |
| ML models on every cycle | Move `run_regime_detection` to Celery beat (every 10 min) |
| Redis round-trip > 5ms | Check Redis is on localhost, not remote |

### High memory usage (> 1 GB)

```bash
# Check candle cache size
curl http://localhost:8001/status | python -m json.tool | grep candle

# Reduce cache limit in main.py:
CANDLE_CACHE_LIMIT = 100   # default 200
```

### CPU at 100%

```bash
# Profile with py-spy (install separately):
pip install py-spy
py-spy top --pid $(pgrep -f "python main.py")
```

---

## 11. Log Reference

Key log patterns and what they mean:

```
✅ Signal | BTCUSDT LONG score=72.1 | entry=65000 sl=64000 tp2=67000 | QUEUED
   → Normal signal dispatched

🛑 CIRCUIT BREAKER TRIPPED | Daily loss -2.3% ≤ -2.0% limit
   → Trading halted. Check /circuit-breaker API, reset when ready.

⚠️  Telegram disabled — alerts will be logged only
   → Normal when TELEGRAM_BOT_TOKEN is blank

WebSocket disconnected: … — reconnecting in 2s
   → Normal, auto-recovers

Redis unavailable (…) — running without cache
   → Redis is down. Scanner still works but slower (no caching).

Correlation gate blocked ETHUSDT: … highly correlated with BTCUSDT (r=0.94)
   → Risk management working correctly. Not an error.
```

---

## Getting Help

1. Check logs first: `tail -f logs/coinscope.log`
2. Run `python testnet_check.py` for a self-diagnostic
3. Run `python benchmark.py` to rule out performance issues
4. Check `/docs` at `http://localhost:8001/docs` for API introspection
