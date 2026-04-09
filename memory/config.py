"""
Memory Configuration
====================
Central configuration for CoinScopeAI's MemPalace integration.

Key design: MemPalace uses a **single** ChromaDB collection
(``mempalace_drawers``) with wing/room/hall metadata on every drawer.
We do NOT create separate collections per store — that would bypass
MemPalace's native graph, search, and layer system.

Wing taxonomy for CoinScopeAI:
  - wing_trading   — trade signals, entries, exits, outcomes
  - wing_risk      — risk gate checks, drawdowns, kill switch, rejections
  - wing_scanner   — pattern scanner history, setup performance
  - wing_models    — ML training runs, param changes, performance snapshots
  - wing_system    — engine lifecycle, config changes, deployments, regimes
  - wing_dev       — architecture decisions, conventions, bug fixes, patterns
  - wing_agent     — cross-agent shared context, task outcomes, lessons
  - wing_<name>    — per-agent specialist diary (e.g. wing_risk_agent)
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_PALACE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)

# MemPalace native collection name — single collection, all drawers
COLLECTION_NAME = "mempalace_drawers"

# CoinScopeAI wing taxonomy
WINGS = {
    "trading":  "wing_trading",
    "risk":     "wing_risk",
    "scanner":  "wing_scanner",
    "models":   "wing_models",
    "system":   "wing_system",
    "dev":      "wing_dev",
    "agent":    "wing_agent",
}

# Room taxonomy per wing
ROOMS = {
    "wing_trading": [
        "signals",       # raw signal generation events
        "entries",       # position open events
        "exits",         # position close events
        "analysis",      # post-trade analysis
    ],
    "wing_risk": [
        "gate-checks",   # risk gate pass/fail
        "drawdowns",     # drawdown events
        "kill-switch",   # kill switch activations
        "rejections",    # order rejections
        "circuit-breaker",
    ],
    "wing_scanner": [
        "setups",        # pattern setups detected
        "performance",   # which setups worked on which pairs/timeframes
        "configs",       # scanner configuration history
    ],
    "wing_models": [
        "training-runs", # model training events
        "param-changes", # hyperparameter changes
        "snapshots",     # periodic performance snapshots
    ],
    "wing_system": [
        "lifecycle",     # engine start/stop
        "config-changes",# configuration changes
        "deployments",   # deployment events
        "regime-changes",# market regime transitions
    ],
    "wing_dev": [
        "architecture",  # ADRs, design decisions
        "conventions",   # coding standards, patterns
        "bug-fixes",     # bug fix records
        "dependencies",  # library choices
    ],
    "wing_agent": [
        "sessions",      # agent session start/end
        "decisions",     # cross-agent decisions
        "tasks",         # task outcomes
        "lessons",       # lessons learned
        "knowledge",     # shared project knowledge
    ],
}

# Hall taxonomy (cross-cutting categories within rooms)
HALLS = {
    "hall_facts":        "Verified factual data",
    "hall_events":       "Timestamped events",
    "hall_decisions":    "Decisions with reasoning",
    "hall_discoveries":  "New findings and insights",
    "hall_preferences":  "Configuration preferences and settings",
    "hall_advice":       "Lessons learned and recommendations",
    "hall_diary":        "Agent diary entries",
}


@dataclass
class MemoryConfig:
    """Configuration for the CoinScopeAI MemPalace integration."""

    # Root directory for ChromaDB persistent storage
    palace_dir: str = field(
        default_factory=lambda: os.environ.get(
            "CSAI_MEMORY_PALACE_DIR", _DEFAULT_PALACE_DIR
        )
    )

    # Default max results for searches
    default_n_results: int = 10

    # Whether to log verbose output
    verbose: bool = field(
        default_factory=lambda: os.environ.get("CSAI_MEMORY_VERBOSE", "0") == "1"
    )

    # Knowledge graph database path (SQLite, inside palace dir)
    kg_db: str = ""

    def __post_init__(self):
        Path(self.palace_dir).mkdir(parents=True, exist_ok=True)
        if not self.kg_db:
            self.kg_db = os.path.join(self.palace_dir, "knowledge_graph.sqlite3")

    @property
    def palace_path(self) -> str:
        """Alias used by MemPalace APIs."""
        return self.palace_dir

    @property
    def collection_name(self) -> str:
        """The single MemPalace collection name."""
        return COLLECTION_NAME

    @property
    def identity_path(self) -> str:
        """Path to the L0 identity file."""
        return os.path.join(self.palace_dir, "identity.txt")
