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
from typing import Dict

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
    "project":  "wing_project",
    "user":     "wing_user",
    "agents":   "wing_agents",
    "assets":   "wing_assets",
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
        "facts",         # code conventions, file locations, API endpoints
        "events",        # PRs merged, features built, bugs fixed
        "discoveries",   # technical insights, performance findings
    ],
    "wing_agent": [
        "sessions",      # agent session start/end
        "decisions",     # cross-agent decisions
        "tasks",         # task outcomes
        "lessons",       # lessons learned
        "knowledge",     # shared project knowledge
    ],
    "wing_project": [
        "facts",         # confirmed decisions (pricing, tech stack)
        "events",        # milestones, deployments, releases
        "discoveries",   # lessons learned, post-mortems
    ],
    "wing_user": [
        "facts",         # user name, timezone, communication style
        "events",        # user requests, feedback
        "discoveries",   # patterns in user preferences
    ],
    "wing_agents": [
        "facts",         # which agents exist, roles, capabilities
        "events",        # subtask outcomes, what each agent built
        "discoveries",   # what worked, what didn't
    ],
    "wing_assets": [
        "facts",         # dashboard URLs, GitHub repos, API keys, Stripe config
        "events",        # deployments, URL changes
        "discoveries",   # infrastructure insights
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

# ---------------------------------------------------------------------------
# Hall Strategy — which hall types are used in each wing/room
# ---------------------------------------------------------------------------
# This mapping is the authoritative reference for hall assignments.
# Stores MUST use these halls; the base_store enforces this at write time.

HALL_STRATEGY: Dict[str, Dict[str, str]] = {
    # wing_trading
    "wing_trading/signals":        "hall_events",
    "wing_trading/entries":        "hall_decisions",
    "wing_trading/exits":          "hall_events",
    "wing_trading/analysis":       "hall_discoveries",
    # wing_risk
    "wing_risk/gate-checks":       "hall_events",
    "wing_risk/drawdowns":         "hall_events",
    "wing_risk/kill-switch":       "hall_events",
    "wing_risk/rejections":        "hall_events",
    "wing_risk/circuit-breaker":   "hall_events",
    # wing_scanner
    "wing_scanner/setups":         "hall_events",
    "wing_scanner/performance":    "hall_facts",
    "wing_scanner/configs":        "hall_preferences",
    # wing_models
    "wing_models/training-runs":   "hall_events",
    "wing_models/param-changes":   "hall_decisions",
    "wing_models/snapshots":       "hall_facts",
    # wing_system
    "wing_system/lifecycle":       "hall_events",
    "wing_system/config-changes":  "hall_decisions",
    "wing_system/deployments":     "hall_events",
    "wing_system/regime-changes":  "hall_events",
    # wing_dev
    "wing_dev/architecture":       "hall_decisions",
    "wing_dev/conventions":        "hall_preferences",
    "wing_dev/bug-fixes":          "hall_advice",
    "wing_dev/dependencies":       "hall_facts",
    # wing_agent (shared)
    "wing_agent/sessions":         "hall_events",
    "wing_agent/decisions":        "hall_decisions",
    "wing_agent/tasks":            "hall_events",
    "wing_agent/lessons":          "hall_advice",
    "wing_agent/knowledge":        "hall_facts",
    # wing_project
    "wing_project/facts":          "hall_facts",
    "wing_project/events":         "hall_events",
    "wing_project/discoveries":    "hall_discoveries",
    # wing_dev (Scoopy additions)
    "wing_dev/facts":              "hall_facts",
    "wing_dev/events":             "hall_events",
    "wing_dev/discoveries":        "hall_discoveries",
    # wing_user
    "wing_user/facts":             "hall_facts",
    "wing_user/events":            "hall_events",
    "wing_user/discoveries":       "hall_discoveries",
    # wing_agents
    "wing_agents/facts":           "hall_facts",
    "wing_agents/events":          "hall_events",
    "wing_agents/discoveries":     "hall_discoveries",
    # wing_assets
    "wing_assets/facts":           "hall_facts",
    "wing_assets/events":          "hall_events",
    "wing_assets/discoveries":     "hall_discoveries",
}

# ---------------------------------------------------------------------------
# Default retention periods (days) per wing.
# -1 means indefinite (never pruned).
# Summaries and lessons are kept indefinitely.
# ---------------------------------------------------------------------------

DEFAULT_RETENTION_DAYS: Dict[str, int] = {
    "wing_trading":  90,
    "wing_risk":     90,
    "wing_scanner":  90,
    "wing_models":   180,
    "wing_system":   180,
    "wing_dev":      -1,   # architecture knowledge is permanent
    "wing_agent":    180,
    "wing_project":  -1,   # project knowledge is permanent
    "wing_user":     -1,   # user knowledge is permanent
    "wing_agents":   -1,   # agent knowledge is permanent
    "wing_assets":   -1,   # asset knowledge is permanent
}

# Rooms that are never pruned regardless of wing retention
RETENTION_EXEMPT_ROOMS = {
    "lessons",        # lessons learned are permanent
    "architecture",   # ADRs are permanent
    "conventions",    # coding standards are permanent
    "knowledge",      # shared knowledge is permanent
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

    # --- Async write queue settings ---
    # Max items in the write queue before dropping (fire-and-forget)
    write_queue_size: int = field(
        default_factory=lambda: int(os.environ.get("CSAI_MEMORY_QUEUE_SIZE", "10000"))
    )

    # --- Batch/flush settings ---
    # Flush to ChromaDB every N seconds
    flush_interval_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CSAI_MEMORY_FLUSH_INTERVAL", "5.0"))
    )

    # Flush when buffer reaches this many events
    flush_batch_size: int = field(
        default_factory=lambda: int(os.environ.get("CSAI_MEMORY_FLUSH_BATCH_SIZE", "50"))
    )

    # --- Retention settings ---
    # Per-wing retention in days (-1 = indefinite)
    retention_days: Dict[str, int] = field(
        default_factory=lambda: dict(DEFAULT_RETENTION_DAYS)
    )

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
