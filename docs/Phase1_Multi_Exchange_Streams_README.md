# CoinScopeAI — Phase 1: Live Scanner & Execution Backbone

Multi-exchange WebSocket price stream infrastructure that feeds all scanners, signals, and execution logic for CoinScopeAI.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Aggregator                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Binance  │ │  Bybit   │ │   OKX    │ │  Hyperliquid     │   │
│  │ Futures  │ │  Linear  │ │  Swap    │ │  Perp            │   │
│  │  Client  │ │  Client  │ │  Client  │ │  Client          │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────────────┘   │
│       │             │            │             │                 │
│       └─────────────┴────────────┴─────────────┘                │
│                          │                                      │
│                    ┌─────▼─────┐                                │
│                    │ Event Bus │                                 │
│                    └─────┬─────┘                                │
│                          │                                      │
│       ┌──────────────────┼──────────────────┐                   │
│       │                  │                  │                   │
│  ┌────▼────┐  ┌──────────▼──────┐  ┌───────▼───────┐           │
│  │Breakout │  │Funding Extreme  │  │  Spread       │           │
│  │+ OI     │  │Scanner          │  │  Divergence   │           │
│  │Scanner  │  │                 │  │  Scanner      │           │
│  └─────────┘  └─────────────────┘  └───────────────┘           │
│                                     ┌───────────────┐           │
│                                     │  Liquidity    │           │
│                                     │  Deterioration│           │
│                                     │  Scanner      │           │
│                                     └───────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
coinscopeai/
├── pyproject.toml
├── README.md
├── services/
│   ├── __init__.py
│   └── market_data/
│       ├── __init__.py
│       ├── models.py              # Unified data models
│       ├── base.py                # Abstract base client, EventBus, RateLimiter
│       ├── aggregator.py          # Multi-exchange orchestrator
│       ├── cli.py                 # CLI entry point
│       ├── binance/
│       │   ├── __init__.py
│       │   └── client.py          # Binance Futures WS + REST
│       ├── bybit/
│       │   ├── __init__.py
│       │   └── client.py          # Bybit V5 Linear WS + REST
│       ├── okx/
│       │   ├── __init__.py
│       │   └── client.py          # OKX Swap WS streams
│       ├── hyperliquid/
│       │   ├── __init__.py
│       │   └── client.py          # Hyperliquid native WS + REST
│       └── scanner/
│           ├── __init__.py
│           ├── base_scanner.py    # Abstract scanner base
│           ├── breakout_oi.py     # Breakout + OI expansion
│           ├── funding_extreme.py # Funding rate extremes
│           ├── spread_divergence.py # Mark/mid & cross-exchange divergence
│           └── liquidity_deterioration.py # Liquidity warnings
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_base.py
    ├── test_binance.py
    ├── test_bybit.py
    ├── test_okx.py
    ├── test_hyperliquid.py
    ├── test_scanners.py
    └── test_aggregator.py
```

## Exchange Coverage

| Exchange | WebSocket Streams | REST Polling |
|----------|-------------------|--------------|
| **Binance Futures** | markPrice@1s, bookTicker, aggTrade | Open Interest, Funding Rate (premiumIndex) |
| **Bybit** | orderbook.{1,50}, publicTrade | Open Interest, Funding History |
| **OKX** | books5, tickers, mark-price, funding-rate, open-interest | — (all via WS) |
| **Hyperliquid** | allMids, l2Book, trades | metaAndAssetCtxs (funding + OI) |

## Unified Data Models

All exchange data is normalized into common schemas while preserving the raw payload:

| Model | Key Fields |
|-------|------------|
| `MarkPrice` | exchange, symbol, mark_price, index_price, timestamp, raw |
| `OrderBook` | exchange, symbol, bids[], asks[], spread, mid_price, spread_bps |
| `Trade` | exchange, symbol, trade_id, price, quantity, side, timestamp |
| `FundingRate` | exchange, symbol, funding_rate, predicted_rate, annualized_rate |
| `OpenInterest` | exchange, symbol, open_interest, open_interest_value |
| `Ticker` | exchange, symbol, last_price, bid/ask, high/low_24h, volume |

## Scan Engines

### 1. Breakout + OI Expansion (`breakout_oi`)
Detects price breakouts above rolling highs (or below lows) confirmed by rising open interest — genuine directional conviction rather than stop-hunts.

**Configurable thresholds:** `price_breakout_pct`, `oi_expansion_pct`, `min_data_points`

### 2. Funding Extreme (`funding_extreme`)
Flags abnormally high/low funding rates and cross-exchange funding divergence — overcrowded positioning and sentiment extremes.

**Configurable thresholds:** `high_funding_pct`, `low_funding_pct`, `cross_exchange_spread_pct`

### 3. Spread / Mark-Price Divergence (`spread_divergence`)
Detects intra-exchange mark-vs-mid divergence and cross-exchange mark price divergence — arbitrage opportunities and liquidation cascade precursors.

**Configurable thresholds:** `mark_mid_divergence_bps`, `cross_exchange_divergence_bps`

### 4. Liquidity Deterioration (`liquidity_deterioration`)
Monitors spread widening, depth thinning, and trade imbalance — early warnings before flash crashes or large moves.

**Configurable thresholds:** `spread_multiplier`, `depth_thin_pct`, `trade_imbalance_ratio`

## Connection Management

- **Auto-reconnect** with exponential backoff (1s → 60s max)
- **Heartbeat monitoring** via WebSocket ping/pong (30s interval, 10s timeout)
- **Connection health tracking** per exchange: state, uptime, messages/sec, reconnect count, errors
- **Rate limiting** for REST endpoints via token-bucket algorithm
- **Graceful shutdown** with task cancellation and session cleanup

## Quick Start

### Install Dependencies

```bash
pip install websockets aiohttp pydantic
pip install pytest pytest-asyncio  # for tests
```

### Run All Feeds + Scanners

```bash
cd coinscopeai
python -m services.market_data.cli \
    --symbols BTCUSDT,ETHUSDT,SOLUSDT \
    --exchanges all \
    --scanners all \
    --scan-interval 5 \
    --window 300 \
    --log-level INFO
```

### Run Specific Exchanges / Scanners

```bash
python -m services.market_data.cli \
    --symbols BTCUSDT \
    --exchanges binance,bybit \
    --scanners breakout_oi,funding_extreme \
    --duration 3600
```

### Programmatic Usage

```python
import asyncio
from services.market_data.aggregator import Aggregator
from services.market_data.binance import BinanceFuturesClient
from services.market_data.bybit import BybitClient
from services.market_data.scanner import BreakoutOIScanner, ScannerConfig
from services.market_data.models import Exchange, ScanSignal

async def main():
    agg = Aggregator()

    # Add exchange clients
    agg.add_client(BinanceFuturesClient(symbols=["BTCUSDT", "ETHUSDT"]))
    agg.add_client(BybitClient(symbols=["BTCUSDT", "ETHUSDT"]))

    # Add scanners
    config = ScannerConfig(
        symbols=["BTCUSDT", "ETHUSDT"],
        exchanges=[Exchange.BINANCE, Exchange.BYBIT],
        window_seconds=300,
        scan_interval=5.0,
        thresholds={"price_breakout_pct": 0.3, "oi_expansion_pct": 1.5},
    )
    agg.add_scanner(BreakoutOIScanner(config, agg.event_bus))

    # Register signal callback
    async def on_signal(sig: ScanSignal):
        print(f"SIGNAL: {sig.signal_type} {sig.exchange.value}:{sig.symbol} "
              f"strength={sig.strength:.2f}")

    agg.on_signal(on_signal)

    await agg.start()
    await asyncio.sleep(3600)
    await agg.stop()

asyncio.run(main())
```

### Run Tests

```bash
cd coinscopeai
python -m pytest tests/ -v
```

## Metrics

The aggregator exposes per-exchange metrics:

```python
metrics = aggregator.get_metrics()
# {
#   "binance": {"state": "connected", "messages_received": 12345, "messages_per_second": 42.3, ...},
#   "bybit":   {"state": "connected", "messages_received": 8901, ...},
#   ...
# }
```

## Environment Tier

**Prototype** — designed for rapid iteration. Production hardening (persistent storage, alerting integrations, horizontal scaling) planned for Phase 2.

## License

Proprietary — CoinScopeAI
