# ⬡ CoinScopeAI

> **AI-powered Binance Futures scanner and autonomous trading assistant**
> Built on FastAPI · FixedScorer · HMM Regime Detection · Kelly Position Sizing

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg)](https://fastapi.tiangolo.com)
[![Testnet Only](https://img.shields.io/badge/trading-testnet%20only-orange.svg)]()
[![License: Private](https://img.shields.io/badge/license-private-red.svg)]()

---

## What It Does

CoinScopeAI continuously scans Binance Futures perpetual pairs and scores each one using a 6-component signal model. When a setup scores above the threshold, the system sizes the position using the Kelly Criterion, validates it against live risk limits, and logs every decision to a Notion trade journal.

```
Market Data → FixedScorer (0–12) → HMM Regime Filter → Risk Gate → Kelly Sizer → Order / Journal
```

---

## Signal Scoring — FixedScorer

Each pair receives a score from **0 to 12** across 6 sub-components:

| Sub-Score | Range | What It Measures |
|-----------|-------|-----------------|
| Momentum | 0–2 | RSI divergence, price velocity vs ATR |
| Trend | 0–2 | EMA 20/50/200 stack alignment, MACD |
| Volatility | 0–2 | ATR % in optimal range |
| Volume | 0–2 | Volume spike vs 20-period average |
| Entry Timing | 0–2 | S/R proximity, candle pattern quality |
| Liquidity | 0–2 | Spread, order book depth, funding rate |

| Score | Strength | Action |
|-------|----------|--------|
| 9.0–12.0 | Very Strong | Full Kelly position |
| 7.0–8.9 | Strong | Standard position |
| 5.5–6.9 | Moderate | Reduced position |
| < 5.5 | Weak | Skip |

---

## Architecture

```
coinscope_trading_engine/
├── api.py                        # FastAPI app — all HTTP endpoints
├── scoring_fixed.py              # FixedScorer: 6 sub-scores → 0–12
├── hmm_regime_detector.py        # HMM: Bull / Bear / Chop classifier
├── risk_gate.py                  # Circuit breakers & daily limits
├── kelly_position_sizer.py       # Fractional Kelly position sizing
├── master_orchestrator.py        # Async scan loop coordinator
├── orchestrator_with_notion.py   # Orchestrator + live Notion sync
├── binance_futures_testnet_client.py  # Futures testnet REST client
├── binance_rest_testnet_client.py     # Spot testnet REST client
├── binance_websocket_client.py        # Futures testnet WebSocket
├── binance_testnet_executor.py        # Order placement layer
├── trade_journal.py              # Local trade journal store
├── trade_logger.py               # Trade event logger
├── notion_simple_integration.py  # Notion API — log trades & signals
├── notion_sync_config.py         # Notion DB IDs and field maps
├── telegram_alerts.py            # Telegram signal notifications
├── funding_rate_filter.py        # Funding rate risk filter
├── multi_timeframe_filter.py     # Multi-TF signal confirmation
├── whale_signal_filter.py        # Large-order flow filter
├── alpha_decay_monitor.py        # Signal freshness tracker
├── pair_monitor.py               # Per-pair health monitor
├── portfolio_sync.py             # Portfolio state sync
├── realtime_dashboard.py         # Terminal dashboard
├── metrics_exporter.py           # Prometheus-compatible metrics
├── retrain_scheduler.py          # Scheduled HMM retraining
└── scale_up_manager.py           # Scale-up position manager

market_scanner_skill/
├── SKILL.md                      # Manus agent skill definition
├── market_scanner.py             # CLI scanner runner
└── skill_config.json             # Manus trigger & parameter config

tests/
└── ...                           # Test suite
```

---

## API Endpoints

The engine runs at `http://localhost:8001` by default.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Engine health + module status |
| `GET` | `/scan` | Score all pairs, return signals |
| `GET` | `/regime/{symbol}` | HMM regime for a symbol |
| `GET` | `/performance` | Trade performance metrics |
| `GET` | `/journal` | Recent trade journal entries |
| `POST` | `/scale` | Kelly position sizing |
| `POST` | `/validate` | Risk gate trade validation |

**Scan example:**
```bash
curl "http://localhost:8001/scan?min_score=5.5&signal=LONG&limit=10"
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/coinscope-ai.git
cd coinscope-ai
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — add your Binance testnet keys and Notion token
```

### 3. Start the engine

```bash
python coinscope_trading_engine/api.py
# Engine runs at http://localhost:8001
```

### 4. Run the scanner

```bash
python market_scanner_skill/market_scanner.py --top 10 --min-score 5.5
```

---

## Environment Variables

Copy `.env.example` to `.env` and populate:

```env
# Binance Futures Testnet
BINANCE_FUTURES_TESTNET_API_KEY=your_key_here
BINANCE_FUTURES_TESTNET_API_SECRET=your_secret_here
BINANCE_FUTURES_TESTNET_BASE_URL=https://testnet.binancefuture.com

# Notion Integration
NOTION_TOKEN=your_notion_token_here

# Telegram Alerts (optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Engine Config
ENGINE_PORT=8001
TESTNET_MODE=true
```

> ⚠️ **Never commit `.env`** — it is listed in `.gitignore`

---

## Notion Integration

CoinScopeAI syncs to two Notion databases:

| Database | Purpose |
|----------|---------|
| Trade Journal | Every trade — entry, exit, score, P&L, regime |
| Signal Log | Every scanner signal — acted on and skipped |

Set `NOTION_TOKEN` in `.env` and ensure your integration is invited to both databases.

---

## Supported Pairs

`BTCUSDT` · `ETHUSDT` · `SOLUSDT` · `BNBUSDT` · `XRPUSDT` · `DOGEUSDT` · `AVAXUSDT` · `LINKUSDT`

---

## Risk Management

The Risk Gate blocks new trades when any threshold is breached:

| Breaker | Default | Env Variable |
|---------|---------|-------------|
| Daily loss | 3% | `MAX_DAILY_LOSS_PCT` |
| Consecutive losses | 5 | `MAX_CONSECUTIVE_LOSSES` |
| Total drawdown | 10% | `MAX_DRAWDOWN_PCT` |
| Open positions | 3 | `MAX_OPEN_POSITIONS` |

---

## Testnet Only

This system is configured for **Binance Futures Testnet** by default (`TESTNET_MODE=true`). Do not connect real API keys until you have completed at least 30 days of paper trading and are satisfied with system performance.

---

## Testing

```bash
pytest tests/ -v
```

---

## Manus Agent Skills

The `market_scanner_skill/` folder contains skill definitions for the Manus AI agent platform. Trigger phrases include:

- *"Scan top movers"*
- *"Find setups"*
- *"What's setting up now?"*

See `market_scanner_skill/SKILL.md` for the full skill specification.

---

## Roadmap

- [ ] Live mainnet support (post paper-trading validation)
- [ ] FinBERT sentiment filter integration
- [ ] Multi-exchange support (OKX, Bybit)
- [ ] Web dashboard (React frontend for `realtime_dashboard.py`)
- [ ] Automated weekly performance reports → Google Drive

---

*CoinScopeAI is a research and paper-trading tool. It does not constitute financial advice. All trading involves risk.*
