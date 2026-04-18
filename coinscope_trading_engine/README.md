# CoinScopeAI Trading Engine

An automated crypto trading engine for Binance USD-M Futures — real-time market scanning, multi-signal confluence scoring, ML-powered regime detection, risk management, and multi-channel alerts.

---

## Quick Start

```bash
# 1. Clone / enter the project
cd coinscope_trading_engine

# 2. Set up your environment
cp .env.template .env          # copy the template
nano .env                      # fill in API keys, Telegram token, etc.

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the engine
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000/docs` for the interactive API documentation.

---

## Project Structure

```
coinscope_trading_engine/
│
├── api.py                     # FastAPI app — all HTTP routes
├── config.py                  # Pydantic Settings — loads & validates .env
├── master_orchestrator.py     # Central coordinator — wires every module
├── requirements.txt           # Python dependencies
├── .env.template              # Environment variable reference
│
├── data/                      # Exchange connectivity & data ingestion
│   ├── binance_websocket.py   # Persistent WS connection (ws-fapi/v1)
│   ├── binance_rest.py        # Async REST client (fapi/v1, fapi/v2)
│   ├── data_normalizer.py     # Standardises raw exchange payloads
│   └── cache_manager.py       # Redis caching layer with TTL management
│
├── scanner/                   # Real-time market scanners
│   ├── base_scanner.py        # Abstract base class all scanners inherit
│   ├── volume_scanner.py      # Volume spike detection
│   ├── liquidation_scanner.py # Liquidation cascade tracking
│   ├── funding_rate_scanner.py# Funding rate anomaly detection
│   ├── pattern_scanner.py     # Candlestick & chart pattern recognition
│   └── orderbook_scanner.py   # Order book imbalance detection
│
├── signals/                   # Signal generation & scoring
│   ├── indicator_engine.py    # RSI, MACD, Bollinger Bands, ATR, etc.
│   ├── confluence_scorer.py   # Weighted aggregation of scanner outputs
│   ├── entry_exit_calculator.py # Entry / Take-Profit / Stop-Loss levels
│   └── backtester.py          # Historical strategy performance simulation
│
├── alerts/                    # Notification & alerting system
│   ├── telegram_notifier.py   # Telegram Bot API integration
│   ├── webhook_dispatcher.py  # External webhook POST delivery
│   ├── alert_queue.py         # Priority-based async alert queue
│   └── rate_limiter.py        # Token-bucket spam prevention
│
├── risk/                      # Risk management engine
│   ├── position_sizer.py      # ATR/Kelly-based position sizing
│   ├── exposure_tracker.py    # Real-time portfolio exposure monitoring
│   ├── correlation_analyzer.py# Asset correlation concentration checks
│   └── circuit_breaker.py     # Emergency halt on drawdown breach
│
├── models/                    # ML / AI models
│   ├── regime_detector.py     # HMM market regime classification
│   ├── sentiment_analyzer.py  # FinBERT NLP sentiment scoring
│   ├── price_predictor.py     # LSTM short-horizon price forecasting
│   └── anomaly_detector.py    # Statistical anomaly flagging
│
├── utils/                     # Shared utilities
│   ├── logger.py              # Rotating file + console logging setup
│   ├── validators.py          # Symbol, price, and input validation
│   └── helpers.py             # Time, formatting, and math helpers
│
└── tests/                     # Pytest test suite
    ├── test_api.py
    ├── test_scanners.py
    ├── test_signals.py
    └── test_risk.py
```

---

## Architecture

```
Binance Exchange
      │
      ├── WebSocket (ws-fapi/v1)          ← binance_websocket.py
      └── REST API  (fapi/v1, fapi/v2)    ← binance_rest.py
                │
                ▼
         data_normalizer.py  ──►  cache_manager.py (Redis)
                │
                ▼
    ┌───────────────────────┐
    │      scanner/         │   volume, liquidation, funding rate,
    │  (runs every N secs)  │   pattern, orderbook
    └───────────┬───────────┘
                │ raw scanner hits
                ▼
    ┌───────────────────────┐
    │      signals/         │   indicators → confluence score
    │  indicator_engine     │   → entry / TP / SL levels
    └───────────┬───────────┘
                │ scored signal
                ▼
    ┌───────────────────────┐        ┌──────────────┐
    │       risk/           │◄───────│   models/    │
    │  position_sizer       │        │ regime + NLP │
    │  circuit_breaker      │        └──────────────┘
    └───────────┬───────────┘
                │ approved signal
                ▼
    ┌───────────────────────┐
    │      alerts/          │   Telegram, webhooks, queue
    └───────────────────────┘
```

---

## Configuration

All settings live in `.env`. Copy `.env.template` to get started:

| Variable | Required | Description |
|---|---|---|
| `BINANCE_TESTNET_API_KEY` | ✅ | Testnet API key |
| `BINANCE_TESTNET_API_SECRET` | ✅ | Testnet API secret |
| `TELEGRAM_BOT_TOKEN` | ✅ | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | Chat/channel ID for alerts |
| `SECRET_KEY` | ✅ | JWT signing key (32-byte hex) |
| `TESTNET_MODE` | optional | `true` (default) — switch to `false` for live trading |
| `SCAN_PAIRS` | optional | Comma-separated futures pairs to scan |
| `MAX_LEVERAGE` | optional | Hard leverage cap (default `10`) |
| `MAX_DAILY_LOSS_PCT` | optional | Daily loss halt threshold (default `2.0`) |

See `.env.template` for the full list with inline documentation.

---

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run a specific module
pytest tests/test_scanners.py -v
```

---

## API Endpoints

Once running, visit `http://localhost:8000/docs` for full Swagger UI.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Engine health check |
| `GET` | `/signals` | Latest signals for all scanned pairs |
| `GET` | `/signals/{symbol}` | Signal for a specific pair |
| `GET` | `/positions` | Current open positions |
| `GET` | `/risk/status` | Risk engine status & exposure |
| `POST` | `/scanner/start` | Start the scanning loop |
| `POST` | `/scanner/stop` | Stop the scanning loop |
| `GET` | `/metrics` | Prometheus metrics |

---

## Safety Notes

- **Always test on Testnet first.** `TESTNET_MODE=true` is the default. Set it to `false` only when you are ready to trade real funds.
- **Never commit `.env`** to version control. It contains your API secrets.
- **API key permissions.** On Binance, grant only `Read` + `Futures Trading` — never `Withdrawal`.
- **Circuit breaker.** The engine halts all trading for the day when `MAX_DAILY_LOSS_PCT` is breached.
- **Rate limits.** The REST client tracks `X-MBX-USED-WEIGHT-1M` and backs off at 85% usage.

---

## Requirements

- Python 3.11+
- Redis (for caching — `brew install redis` / `apt install redis-server`)
- A Binance Futures account with API access ([testnet](https://testnet.binancefuture.com) recommended to start)
- A Telegram bot ([create one via @BotFather](https://t.me/BotFather))
