# CoinScopeAI Memory System

The CoinScopeAI Memory System is a persistent decision-tracking and institutional memory layer built on top of [MemPalace](https://github.com/milla-jovovich/mempalace). It uses ChromaDB for vector storage and provides a temporal knowledge graph, L0-L3 layered context, and cross-agent memory sharing.

This system is designed for **post-trade analysis, risk auditing, and agent intelligence**—not just as a chatbot backend.

## Architecture: The Palace Taxonomy

MemPalace organizes data into a spatial hierarchy: `Wing → Hall → Room → Drawer`. CoinScopeAI maps its operational domains to this structure:

| Wing | Rooms | Purpose |
|------|-------|---------|
| `wing_trading` | signals, entries, exits | Trade decisions, reasoning, and market context |
| `wing_risk` | gate-checks, drawdowns, kills | Risk events, margin incidents, circuit breakers |
| `wing_scanner` | setups, performance | Pattern scanner history and setup efficacy |
| `wing_models` | snapshots, training | ML model performance and parameter changes |
| `wing_system` | regime-changes, lifecycle | Engine starts/stops, config changes, market regimes |
| `wing_dev` | architecture, bug-fixes | Project knowledge, ADRs, conventions |
| `wing_agent` | sessions, tasks, lessons | Per-agent specialist memory and cross-agent sharing |

## Features

1. **Automatic Engine Capture**: Middleware and hooks automatically capture signals, risk checks, and regime changes from the trading engine without adding latency.
2. **Temporal Knowledge Graph**: Tracks facts over time (e.g., "BTCUSDT regime changed to volatile on 2026-04-09").
3. **L0-L3 Memory Stack**: Generates highly compressed "wake-up" context (~170-800 tokens) for AI agents using AAAK summaries, reducing API costs and latency.
4. **Palace Graph Traversal**: Discovers connected ideas across different wings (e.g., linking a risk event to a specific architecture decision).

## Installation

The memory system requires MemPalace and ChromaDB:

```bash
pip install mempalace chromadb
```

## Usage: Python API

The `MemoryManager` is the unified entry point for all memory operations.

```python
from memory import MemoryManager

mm = MemoryManager()

# 1. Log a trade decision
mm.trading.log_signal(
    symbol="BTCUSDT",
    signal="LONG",
    confidence=0.85,
    regime="trending_up",
    price=65000.0,
    reasoning="Breakout with funding flip"
)

# 2. Log a risk event
mm.risk.log_drawdown_event(drawdown_pct=0.05, equity=9500.0, peak_equity=10000.0)

# 3. Agent Wake-up (L0-L1 Context)
context = mm.wake_up(wing="wing_trading")
print(context)

# 4. Semantic Search (L3 Deep Retrieval)
hits = mm.search("breakout signals on altcoins with funding flip")

# 5. Knowledge Graph
mm.kg_add("ETHUSDT", "in_regime", "volatile")
facts = mm.kg_query("ETHUSDT")
```

## Usage: Engine Integration

### FastAPI Middleware

Automatically capture data from the engine's REST API:

```python
from fastapi import FastAPI
from memory.hooks import MemoryMiddleware

app = FastAPI()
memory_mw = MemoryMiddleware(app)
# /scan, /risk-gate, /regime/{symbol}, and /performance are now captured
```

### Direct Engine Hooks

Wire directly into the paper trading engine callbacks:

```python
from memory.hooks import EngineMemoryHooks

hooks = EngineMemoryHooks()
engine._signal_engine.on_signal(hooks.on_signal)
engine._order_manager.on_position_close(hooks.on_position_close)
```

## Usage: CLI

The memory system includes a powerful CLI for querying the palace:

```bash
# Semantic search across all wings
python -m memory search "Why did we enter a long on BTCUSDT last Tuesday?"

# Filter search by wing
python -m memory search "risk gate readings before drawdown" --wing wing_risk

# View recent signals
python -m memory signals --symbol BTCUSDT

# View regime changes
python -m memory regimes --symbol ETHUSDT

# View risk events
python -m memory risks

# Query the knowledge graph
python -m memory kg-query BTCUSDT
python -m memory kg-timeline BTCUSDT

# View the palace taxonomy (wing -> room -> count)
python -m memory taxonomy

# Generate agent wake-up context
python -m memory wake-up --wing wing_trading
```

## Usage: REST API

You can run the memory system as a standalone REST API:

```bash
uvicorn memory.api:app --port 8002
```

Endpoints:
- `GET /memory/search?q=...`
- `GET /memory/wake-up?wing=wing_trading`
- `GET /memory/signals?symbol=BTCUSDT`
- `GET /memory/kg/query?entity=BTCUSDT`
- `GET /memory/taxonomy`
