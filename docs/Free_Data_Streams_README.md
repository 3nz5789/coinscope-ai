# CoinScopeAI Market Data Streams

Free, zero-cost real-time and historical market data for CoinScopeAI — built entirely on public endpoints from **Binance**, **Bybit**, **OKX**, and **Hyperliquid**. No paid APIs, no API keys required.

---

## Architecture Overview

```
services/market_data/streams/
├── base.py          — Data models, EventBus, RateLimiter, symbol helpers
├── trades.py        — Unified tick trade stream (all 4 exchanges)
├── orderbook.py     — Unified L2 order book stream with local state management
├── funding.py       — Unified funding rate stream
├── liquidation.py   — Unified liquidation stream
├── recorder.py      — Historical data recorder (JSONL.gz output)
├── replay.py        — Replay engine (time-windowed, speed-controlled)
├── downloader.py    — Bulk historical data downloader
└── cli.py           — CLI for record / replay / download
```

---

## Stream 1: Tick Trades (`trades.py`)

| Exchange     | Protocol   | Endpoint                                          |
|--------------|------------|---------------------------------------------------|
| Binance      | WebSocket  | `wss://fstream.binance.com/ws/<symbol>@aggTrade`  |
| Bybit        | WebSocket  | `publicTrade.<symbol>`                            |
| OKX          | WebSocket  | `trades` channel                                  |
| Hyperliquid  | WebSocket  | `{"type":"trades","coin":"BTC"}`                  |

All messages are normalised to a unified `Trade` model and published to the `EventBus` as `EventType.TRADE`.

**Side convention:** `"buy"` = taker bought (aggressive buyer), `"sell"` = taker sold.

```python
from services.market_data.streams.trades import TradeStream
from services.market_data.streams.base import Exchange, EventType, get_event_bus

bus = get_event_bus()

async def on_trade(event_type, trade):
    print(f"{trade.exchange} {trade.symbol} {trade.side} {trade.price} x {trade.quantity}")

await bus.subscribe(EventType.TRADE, on_trade)

stream = TradeStream(
    symbols=["BTCUSDT", "ETHUSDT"],
    exchanges=[Exchange.BINANCE, Exchange.BYBIT, Exchange.OKX, Exchange.HYPERLIQUID],
)
await stream.start()
```

---

## Stream 2: L2 Order Book (`orderbook.py`)

| Exchange     | Protocol   | Endpoint / Method                                        |
|--------------|------------|----------------------------------------------------------|
| Binance      | WS + REST  | `@depth@100ms` + `/fapi/v1/depth` REST snapshot         |
| Bybit        | WebSocket  | `orderbook.50.<symbol>` (snapshot + delta)              |
| OKX          | WebSocket  | `books5` channel (snapshots)                            |
| Hyperliquid  | WebSocket  | `l2Book` subscription                                   |

Each exchange maintains a `LocalOrderBook` per symbol that:
- Applies snapshot and delta updates correctly
- Detects crossed books and triggers automatic re-snapshot
- Trims to configurable `max_depth` on every delta

Events published: `EventType.ORDERBOOK_SNAPSHOT` and `EventType.ORDERBOOK_UPDATE`.

```python
from services.market_data.streams.orderbook import OrderBookStream
from services.market_data.streams.base import Exchange, EventType, get_event_bus

bus = get_event_bus()

async def on_book(event_type, update):
    print(f"{'SNAP' if update.is_snapshot else 'DELTA'} {update.exchange} {update.symbol}")
    print(f"  Best bid: {update.bids[0].price if update.bids else 'N/A'}")
    print(f"  Best ask: {update.asks[0].price if update.asks else 'N/A'}")

await bus.subscribe(EventType.ORDERBOOK_SNAPSHOT, on_book)
await bus.subscribe(EventType.ORDERBOOK_UPDATE, on_book)

stream = OrderBookStream(
    symbols=["BTCUSDT"],
    exchanges=[Exchange.BINANCE, Exchange.BYBIT, Exchange.OKX, Exchange.HYPERLIQUID],
)
await stream.start()
```

---

## Stream 3: Funding Rates (`funding.py`)

| Exchange     | Protocol   | Endpoint                                                |
|--------------|------------|---------------------------------------------------------|
| Binance      | REST poll  | `GET /fapi/v1/premiumIndex` (every 30 s)               |
| Bybit        | REST poll  | `GET /v5/market/funding/history` (every 60 s)          |
| OKX          | WebSocket  | `funding-rate` channel                                  |
| Hyperliquid  | REST poll  | `POST /info` `{"type":"metaAndAssetCtxs"}` (every 60 s)|

Events published: `EventType.FUNDING_RATE`.

```python
from services.market_data.streams.funding import FundingStream
from services.market_data.streams.base import Exchange, EventType, get_event_bus

bus = get_event_bus()

async def on_funding(event_type, fr):
    print(f"{fr.exchange} {fr.symbol} rate={fr.funding_rate:.6f} mark={fr.mark_price}")

await bus.subscribe(EventType.FUNDING_RATE, on_funding)

stream = FundingStream(
    symbols=["BTCUSDT"],
    exchanges=[Exchange.BINANCE, Exchange.BYBIT, Exchange.OKX, Exchange.HYPERLIQUID],
)
await stream.start()
```

---

## Stream 4: Liquidations (`liquidation.py`)

| Exchange     | Protocol   | Endpoint                                                     |
|--------------|------------|--------------------------------------------------------------|
| Binance      | WebSocket  | `wss://fstream.binance.com/ws/!forceOrder@arr`              |
| Bybit        | WebSocket  | `liquidation.<symbol>`                                       |
| OKX          | REST poll  | `GET /api/v5/public/liquidation-orders` (every 5 s)         |
| Hyperliquid  | REST poll  | `POST /info` `{"type":"liquidations"}` (every 5 s)          |

**Side convention:** `"buy"` = long position was liquidated, `"sell"` = short position was liquidated.

Events published: `EventType.LIQUIDATION`.

---

## Stream 5: Recorder, Replay & Downloader

### StreamRecorder (`recorder.py`)

Records all EventBus events to compressed JSONL.gz files, partitioned by event type and date.

```python
from services.market_data.streams.recorder import StreamRecorder
from services.market_data.streams.base import get_event_bus

recorder = StreamRecorder(
    output_dir="./data/recordings",
    event_bus=get_event_bus(),
    flush_interval=60.0,   # flush every 60 seconds
    buffer_size=1000,      # or when buffer hits 1000 events
)
await recorder.start()
# ... run streams ...
await recorder.stop()  # flushes all buffers on shutdown
```

Output structure:
```
data/recordings/
└── trades/
    └── 2025-01-15_binance_BTCUSDT_trades.jsonl.gz
└── orderbook_snapshot/
    └── 2025-01-15_bybit_BTCUSDT_orderbook_snapshot.jsonl.gz
└── funding_rate/
    └── 2025-01-15_binance_BTCUSDT_funding_rate.jsonl.gz
```

### ReplayEngine (`replay.py`)

Reads recordings and re-emits events through the EventBus at controlled speed. Scanners and alpha generators work identically on live and replayed data.

```python
from services.market_data.streams.replay import ReplayEngine
from services.market_data.streams.base import get_event_bus

engine = ReplayEngine(
    data_dir="./data/recordings",
    event_bus=get_event_bus(),
    speed=10.0,            # 10x real-time (0 = as fast as possible)
    start_time_ms=1736899200000,   # optional: 2025-01-15 00:00 UTC
    end_time_ms=1736985600000,     # optional: 2025-01-16 00:00 UTC
)
await engine.start()
engine.pause()   # pause mid-replay
engine.resume()  # resume
await engine.wait()
print(engine.stats)
```

### HistoricalDownloader (`downloader.py`)

Bulk downloads historical data from all free public sources.

```python
from services.market_data.streams.downloader import HistoricalDownloader
from datetime import date

dl = HistoricalDownloader(output_dir="./data/historical")

# Bybit history-data portal: 500-level L2 order book (free, back to 2023)
await dl.download_bybit_orderbook(
    symbol="BTCUSDT",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
    market_type="linear",
)

# Bybit public trades (CSV.gz from public.bybit.com)
await dl.download_bybit_trades(
    symbol="BTCUSDT",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
)

# Binance historical klines / aggTrades
await dl.download_binance_aggrades(
    symbol="BTCUSDT",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
)

# Bybit funding rate history
await dl.download_bybit_funding(
    symbol="BTCUSDT",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 1, 31),
)
```

#### Bybit History-Data Portal

The Bybit history-data portal (`quote-saver.bycsi.com`) provides **500-level L2 order book** data for derivatives going back to 2023. Each daily file is a ZIP containing NDJSON in the same snapshot+delta format as the live WebSocket feed.

Direct CDN URL pattern:
```
https://quote-saver.bycsi.com/orderbook/linear/{SYMBOL}/{DATE}_{SYMBOL}_ob500.data.zip
```

The downloader handles:
- Streaming ZIP decompression (no full-file buffering)
- NDJSON → JSONL.gz conversion with unified `OrderBookUpdate` schema
- Automatic skipping of already-downloaded dates
- Concurrent downloads with configurable parallelism

---

## CLI (`cli.py`)

```bash
# Record all streams for BTCUSDT and ETHUSDT
python -m services.market_data.streams.cli record \
    --symbols BTCUSDT ETHUSDT \
    --exchanges binance bybit okx hyperliquid \
    --streams trades orderbook funding liquidation \
    --output-dir ./data/recordings

# Replay a recording at 5x speed
python -m services.market_data.streams.cli replay \
    --data-dir ./data/recordings \
    --speed 5.0 \
    --start 2025-01-15 \
    --end 2025-01-16

# Download historical data
python -m services.market_data.streams.cli download \
    --symbol BTCUSDT \
    --start 2025-01-01 \
    --end 2025-01-31 \
    --output-dir ./data/historical \
    --sources bybit-portal bybit-trades binance-agg bybit-funding
```

---

## Data Models

All streams emit unified models defined in `base.py`:

| Model            | Key Fields                                                              |
|------------------|-------------------------------------------------------------------------|
| `Trade`          | `exchange`, `symbol`, `trade_id`, `price`, `quantity`, `side`, `timestamp_ms` |
| `OrderBookUpdate`| `exchange`, `symbol`, `bids`, `asks`, `is_snapshot`, `sequence`, `timestamp_ms` |
| `OrderBookLevel` | `price`, `quantity`                                                     |
| `FundingRate`    | `exchange`, `symbol`, `funding_rate`, `predicted_rate`, `mark_price`, `funding_time_ms` |
| `Liquidation`    | `exchange`, `symbol`, `side`, `price`, `quantity`, `usd_value`, `is_derived` |
| `StreamStatus`   | `exchange`, `stream_type`, `symbol`, `connected`, `message`            |

---

## EventBus

The `EventBus` is a singleton pub/sub system. All streams publish to it; scanners and alpha generators subscribe from it. This makes live and replayed data completely interchangeable.

```python
from services.market_data.streams.base import EventBus, EventType, get_event_bus

bus = get_event_bus()  # singleton

# Subscribe to a specific event type
await bus.subscribe(EventType.TRADE, my_handler)

# Subscribe to all event types
await bus.subscribe_all(my_catch_all_handler)

# Publish (done internally by streams)
await bus.publish(EventType.TRADE, trade_object)
```

**EventType values:** `TRADE`, `ORDERBOOK_SNAPSHOT`, `ORDERBOOK_UPDATE`, `FUNDING_RATE`, `LIQUIDATION`, `STREAM_STATUS`

---

## Installation

```bash
pip install websockets aiohttp orjson sortedcontainers
```

---

## Running Tests

```bash
cd coinscopeai
pytest tests/test_streams.py -v
# 95 passed in ~1s (all offline, no network calls)
```

---

## Design Principles

- **Zero paid APIs** — all endpoints are free and public, no authentication required
- **Unified data models** — one schema across all 4 exchanges
- **EventBus decoupling** — streams, scanners, and alpha generators are fully decoupled
- **Live/replay parity** — scanners work identically on live WebSocket data and historical recordings
- **Auto-reconnect** — all WebSocket connections reconnect with exponential backoff
- **Rate limiting** — token-bucket rate limiter on all REST endpoints
- **Graceful shutdown** — recorder flushes all buffers on SIGINT/SIGTERM
- **Desync detection** — order book stream detects crossed books and triggers re-snapshot
