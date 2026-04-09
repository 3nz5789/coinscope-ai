"""
CoinScopeAI Memory Module — MemPalace Integration
====================================================
Persistent decision-tracking and institutional memory for the CoinScopeAI
trading system, built on MemPalace (ChromaDB + knowledge graph).

Wing structure::

    wing_trading  — trade signals, entries, exits
    wing_risk     — risk gate checks, drawdowns, kill switch events
    wing_scanner  — pattern scanner history, setup performance
    wing_models   — ML training runs, performance snapshots
    wing_system   — engine lifecycle, regime changes, config changes
    wing_dev      — architecture decisions, conventions, bug fixes
    wing_agent    — per-agent sessions, diaries, tasks, lessons

Usage::

    from memory import MemoryManager

    mm = MemoryManager()
    mm.trading.log_signal(symbol="BTCUSDT", signal="LONG", ...)
    mm.risk.log_drawdown_event(drawdown_pct=0.05, ...)
    mm.agents.start_session(agent_role="trading_agent", ...)

    hits = mm.search("breakout signals on altcoins")
    context = mm.wake_up(wing="wing_trading")
"""

from .config import MemoryConfig
from .manager import MemoryManager

__all__ = ["MemoryConfig", "MemoryManager"]
