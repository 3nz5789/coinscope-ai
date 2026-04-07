# CoinScopeAI Phase 2 — Alpha and Regime Enrichment

Extends the Phase 1 multi-exchange WebSocket infrastructure with deeper data sources for alpha generation and market regime detection.

## Architecture Overview

```
services/market_data/
├── models.py                          # Unified data models (Phase 1 + Phase 2)
├── hyperliquid/
│   ├── __init__.py
│   └── deep_client.py                 # Extended Hyperliquid REST + WebSocket client
├── coinglass/
│   ├── __init__.py
│   └── client.py                      # CoinGlass REST client + free exchange fallback
├── alpha/
│   ├── __init__.py
│   ├── base.py                        # Abstract base generator + statistical utilities
│   ├── funding.py                     # Funding rate alpha signals
│   ├── liquidation.py                 # Liquidation alpha signals
│   ├── open_interest.py               # Open interest alpha signals
│   ├── basis.py                       # Futures basis alpha signals
│   └── orderbook.py                   # Order book depth alpha signals
└── regime/
    ├── __init__.py
    └── enricher.py                    # Market regime classification engine
```

## Components

### 1. Hyperliquid Deep Client (`hyperliquid/deep_client.py`)

Extended REST and WebSocket client for the Hyperliquid Info API:

- **`HyperliquidDeepClient`** (REST) — asset contexts, predicted fundings, funding history, L2 order book snapshots, all mids
- **`HyperliquidDeepWs`** (WebSocket) — real-time L2 book updates, active asset context updates, trades, all mids

All requests target `https://api.hyperliquid.xyz/info` (POST, no auth required).

### 2. CoinGlass Client (`coinglass/client.py`)

Cross-exchange aggregated data via CoinGlass API v4:

- **`CoinGlassClient`** — liquidation history, OI by exchange, funding rates, basis history, funding arbitrage
- **`ExchangeFallbackClient`** — free alternative that aggregates data from Binance, Bybit, and OKX public APIs

The CoinGlass API key is **optional** — set `COINGLASS_API_KEY` env var to enable, otherwise the system uses the free exchange fallback automatically.

### 3. Alpha Feature Generators (`alpha/`)

Five stateless, composable generators that produce standardised `AlphaSignal` objects:

| Generator | Key Signals |
|---|---|
| `FundingAlphaGenerator` | Cross-exchange divergence, mean reversion, predicted extremes |
| `LiquidationAlphaGenerator` | Cascade detection, cluster analysis, long/short ratio |
| `OIAlphaGenerator` | Cross-exchange divergence, expansion/contraction rate, OI vs price divergence |
| `BasisAlphaGenerator` | Premium/discount extremes, convergence/divergence, history z-score |
| `OrderBookAlphaGenerator` | Book imbalance, depth-weighted mid, liquidity cliff detection, spread dynamics |

### 4. Regime Enricher (`regime/enricher.py`)

Combines multiple data sources and alpha signals to classify market regime:

| Regime | Characteristics |
|---|---|
| **Trending** | Strong directional move + expanding OI + normal funding |
| **Mean-reverting** | Range-bound + declining OI + extreme funding |
| **Volatile** | High liquidations + wide spreads + rapid OI changes |
| **Low-liquidity** | Thin books + wide spreads + low volume |

Handles missing data gracefully — each data source is scored independently and the enricher degrades proportionally.

## Data Models (`models.py`)

All data flows through the unified model layer:

- `L2OrderBook`, `OrderBookLevel` — order book depth
- `FundingRate`, `FundingSnapshot`, `PredictedFunding` — funding data
- `AssetContext` — Hyperliquid per-asset enriched context
- `OpenInterest`, `AggregatedOI` — open interest
- `Liquidation`, `LiquidationSnapshot` — liquidation events
- `BasisData`, `AggregatedBasis` — futures premium/discount
- `AlphaSignal` — standardised output from all generators
- `RegimeState` — regime classification result with confidence scores

## Quick Start

```python
import asyncio
from services.market_data.hyperliquid.deep_client import HyperliquidDeepClient
from services.market_data.coinglass.client import CoinGlassClient
from services.market_data.alpha.funding import FundingAlphaGenerator
from services.market_data.alpha.orderbook import OrderBookAlphaGenerator
from services.market_data.regime.enricher import RegimeEnricher

async def main():
    # Fetch data
    hl = HyperliquidDeepClient()
    meta, contexts = await hl.get_meta_and_asset_contexts()
    book = await hl.get_l2_book("BTC")
    predicted = await hl.get_predicted_fundings()
    await hl.close()

    # Generate alpha signals
    funding_gen = FundingAlphaGenerator()
    book_gen = OrderBookAlphaGenerator()
    signals = funding_gen.generate("BTC", predicted=predicted.get("BTC", []))
    signals += book_gen.generate("BTC", book=book)

    # Classify regime
    enricher = RegimeEnricher()
    btc_ctx = next((c for c in contexts if c.symbol == "BTC"), None)
    regime = enricher.classify("BTC", asset_context=btc_ctx, book=book, alpha_signals=signals)
    print(f"Regime: {regime.regime.value} (confidence: {regime.confidence:.2f})")

asyncio.run(main())
```

## Testing

```bash
pip install aiohttp pytest pytest-asyncio
python -m pytest tests/ -v
```

**110 tests** covering models, Hyperliquid client, CoinGlass client, all alpha generators, regime enricher, and full integration pipeline.

## Design Principles

1. **Unified data model** — all data flows through `models.py`, compatible with Phase 1
2. **Stateless generators** — alpha generators receive data and return signals with no internal state
3. **Composable** — generators can be mixed and matched; regime enricher accepts any combination
4. **Graceful degradation** — missing data sources are simply omitted from scoring
5. **Optional CoinGlass** — system works without API key using free exchange data
6. **Prototype-tier** — optimised for correctness and clarity, not production throughput
