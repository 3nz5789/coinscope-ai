"""
CoinScopeAI Memory System — MemPalace Integration
=====================================================
AI-native memory layer for the CoinScopeAI trading engine.

Quick start::

    from memory import MemoryManager

    mm = MemoryManager()

    # Trading memory (non-blocking, fire-and-forget)
    mm.trading.log_signal(symbol="BTCUSDT", signal="LONG", confidence=0.82,
                          regime="trending", price=67000.0)

    # Risk memory
    mm.risk.log_drawdown_event(drawdown_pct=0.05, equity=9500, peak_equity=10000)

    # Agent diary
    mm.agents.write_diary("scanner_agent", "SESSION:...|scanned.BTC|★★★")

    # Semantic search across all wings
    hits = mm.search("breakout signals on altcoins")

    # Retention pruning
    result = mm.prune(dry_run=True)

    # Graceful shutdown (flush buffered events)
    mm.shutdown()

Production-readiness features:
  1. Non-blocking async write queue — writes never block trading
  2. Idempotency/dedup via event_id — retries are safe
  3. Hall strategy enforcement — events go to the right hall
  4. Batch/flush model — reduced ChromaDB overhead
  5. Retention & pruning — disk never fills up silently
"""

from .config import MemoryConfig
from .manager import MemoryManager

__all__ = ["MemoryConfig", "MemoryManager"]
__version__ = "0.2.0"
