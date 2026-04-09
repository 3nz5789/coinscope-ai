# CoinScopeAI Memory System

The CoinScopeAI Memory System is a persistent decision-tracking and institutional memory layer built on top of [MemPalace](https://github.com/milla-jovovich/mempalace). It uses ChromaDB for vector storage and provides a temporal knowledge graph, L0-L3 layered context, and cross-agent memory sharing.

This system is designed for **post-trade analysis, risk auditing, and agent intelligence**—not just as a chatbot backend.

## Production-Readiness Features

This integration includes 5 critical production-readiness improvements:

1. **Non-blocking Async Write Queue**: Memory writes never block the trading engine. Events are enqueued to a background writer thread. If ChromaDB hangs or the queue fills up, events are dropped with a warning (best-effort memory guarantee).
2. **Idempotency & Deduplication**: Every drawer carries an `event_id`. The background writer silently skips duplicate events, making it safe for the engine to retry callbacks.
3. **Hall Strategy Enforcement**: Events are strictly routed to the correct MemPalace hall (e.g., `hall_events`, `hall_decisions`, `hall_facts`). The base store enforces this at write time.
4. **Batch & Flush Model**: Incoming events are buffered in memory and flushed to ChromaDB every 5 seconds (or 50 events), drastically reducing database overhead during high-frequency scanning.
5. **Retention & Pruning Policy**: Configurable retention periods prevent the disk from filling up silently. A `prune()` method and CLI command allow safe cleanup of old events while preserving permanent knowledge.

## Architecture: The Palace Taxonomy

MemPalace organizes data into a spatial hierarchy: `Wing → Hall → Room → Drawer`. CoinScopeAI maps its operational domains to this structure:

| Wing | Rooms | Halls | Purpose | Retention |
|------|-------|-------|---------|-----------|
| `wing_trading` | signals, entries, exits, analysis | `hall_events`, `hall_decisions`, `hall_discoveries` | Trade decisions, reasoning, and market context | 90 days |
| `wing_risk` | gate-checks, drawdowns, kills, rejections | `hall_events` | Risk events, margin incidents, circuit breakers | 90 days |
| `wing_scanner` | setups, performance, configs | `hall_events`, `hall_facts`, `hall_preferences` | Pattern scanner history and setup efficacy | 90 days |
| `wing_models` | snapshots, training, param-changes | `hall_events`, `hall_decisions`, `hall_facts` | ML model performance and parameter changes | 180 days |
| `wing_system` | regime-changes, lifecycle, config-changes | `hall_events`, `hall_decisions` | Engine starts/stops, config changes, market regimes | 180 days |
| `wing_dev` | architecture, bug-fixes, conventions | `hall_decisions`, `hall_preferences`, `hall_advice` | Project knowledge, ADRs, conventions | Indefinite |
| `wing_agent` | sessions, tasks, lessons, knowledge | `hall_events`, `hall_decisions`, `hall_advice`, `hall_facts` | Per-agent specialist memory and cross-agent sharing | 180 days* |

*\* Note: `lessons`, `architecture`, `conventions`, and `knowledge` rooms are exempt from pruning and kept indefinitely.*

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

# 1. Log a trade decision (non-blocking, fire-and-forget)
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

# 6. Retention Pruning
result = mm.prune(dry_run=True)

# 7. Graceful Shutdown (flushes buffered events)
mm.shutdown()
```

## Usage: Engine Integration

### Direct Engine Hooks

Wire directly into the paper trading engine callbacks. All writes are non-blocking.

```python
from memory.hooks import EngineMemoryHooks

hooks = EngineMemoryHooks()

# In your signal handler:
hooks.on_signal(symbol="BTCUSDT", signal="LONG", confidence=0.82, ...)

# On graceful shutdown (flushes remaining events):
hooks.shutdown()
```

## Usage: CLI

The memory system includes a powerful CLI for querying and maintaining the palace:

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

# Retention Pruning
python -m memory prune --dry-run    # Preview what would be deleted
python -m memory prune --execute    # Actually delete old drawers
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
