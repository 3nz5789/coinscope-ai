"""
Memory Manager — Unified Interface to CoinScopeAI's MemPalace
================================================================
Ties together all stores, the L0-L3 memory stack, the knowledge graph,
and the palace graph into a single entry point.

Production-readiness features:
  - Non-blocking writes via background writer thread
  - Batch/flush model for reduced ChromaDB overhead
  - Idempotency/dedup via event_id fields
  - Hall strategy enforcement
  - Retention & pruning policy

Usage::

    from memory import MemoryManager

    mm = MemoryManager()

    # Trading memory
    mm.trading.log_signal(symbol="BTCUSDT", signal="LONG", ...)
    mm.risk.log_drawdown_event(drawdown_pct=0.05, ...)

    # Agent memory
    sid = mm.agents.start_session(agent_role="trading_agent", objective="...")
    mm.agents.write_diary("risk_agent", "SESSION:...|scanned.risk.gates|★★★")

    # L0-L3 layered context for agent wake-up (~170-800 tokens)
    context = mm.wake_up(wing="wing_trading")

    # Deep semantic search across all wings
    hits = mm.search("breakout signals on altcoins with funding flip")

    # Knowledge graph
    mm.kg_add("BTCUSDT", "regime_changed_to", "volatile", valid_from="2026-04-09")
    facts = mm.kg_query("BTCUSDT")

    # Palace graph traversal
    connected = mm.traverse("regime-changes", max_hops=2)

    # Retention pruning
    result = mm.prune(dry_run=True)   # preview
    result = mm.prune(dry_run=False)  # actually delete

    # Graceful shutdown (flush remaining events)
    mm.shutdown()
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import chromadb

from .config import (
    MemoryConfig,
    COLLECTION_NAME,
    DEFAULT_RETENTION_DAYS,
    RETENTION_EXEMPT_ROOMS,
)
from .stores.trade_decisions import TradeDecisionStore
from .stores.ml_models import MLModelStore
from .stores.risk_events import RiskEventStore
from .stores.system_events import SystemEventStore
from .stores.scanner import ScannerStore
from .stores.agent_sessions import AgentSessionStore
from .stores.project_knowledge import ProjectKnowledgeStore
from .stores.task_outcomes import TaskOutcomeStore

logger = logging.getLogger("coinscopeai.memory")


class MemoryManager:
    """
    Unified entry point for all CoinScopeAI memory operations.

    Provides:
      - Typed stores for each wing (trading, risk, scanner, models, system, dev, agent)
      - L0-L3 layered context via MemPalace MemoryStack
      - Knowledge graph for temporal fact tracking
      - Palace graph traversal for cross-wing discovery
      - Cross-wing semantic search
      - Retention pruning
      - Graceful shutdown with flush
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()

        # ----- Trading memory stores -----
        self.trading = TradeDecisionStore(self.config)
        self.risk = RiskEventStore(self.config)
        self.scanner = ScannerStore(self.config)
        self.models = MLModelStore(self.config)
        self.system = SystemEventStore(self.config)

        # ----- Agent memory stores -----
        self.agents = AgentSessionStore(self.config)
        self.knowledge = ProjectKnowledgeStore(self.config)
        self.tasks = TaskOutcomeStore(self.config)

        # ----- MemPalace native subsystems (lazy init) -----
        self._stack = None
        self._kg = None

    # ==================================================================
    # Lifecycle
    # ==================================================================

    def shutdown(self):
        """
        Graceful shutdown: flush all buffered memory events to ChromaDB.
        Call this before process exit to ensure no events are lost.
        """
        logger.info("[MemPalace] Shutting down — flushing remaining events...")
        # All stores share the same BackgroundWriter instance per palace_path,
        # so shutting down any store's writer shuts down the shared writer.
        try:
            self.trading._writer.shutdown()
        except Exception as e:
            logger.warning("[MemPalace] Shutdown flush error: %s", e)

    def flush(self):
        """Force flush all buffered events to ChromaDB immediately."""
        try:
            self.trading.flush()
        except Exception as e:
            logger.warning("[MemPalace] Flush error: %s", e)

    # ==================================================================
    # L0-L3 Memory Stack (MemPalace native)
    # ==================================================================

    def _get_stack(self):
        """Lazy-init the MemPalace MemoryStack."""
        if self._stack is None:
            try:
                from mempalace.layers import MemoryStack
                self._stack = MemoryStack(
                    palace_path=self.config.palace_path,
                    identity_path=self.config.identity_path,
                )
            except Exception as e:
                logger.warning("MemoryStack init failed: %s", e)
                self._stack = None
        return self._stack

    def wake_up(self, wing: str = None) -> str:
        """
        Generate wake-up context for an agent: L0 (identity) + L1 (essential story).
        Typically ~170-800 tokens.  Inject into system prompt or first message.

        Args:
            wing: Optional wing filter for project-specific wake-up.
                  e.g. "wing_trading" for the trading agent.
        """
        stack = self._get_stack()
        if stack is None:
            return self._fallback_wake_up(wing)
        try:
            return stack.wake_up(wing=wing)
        except Exception as e:
            logger.warning("MemoryStack wake_up failed: %s", e)
            return self._fallback_wake_up(wing)

    def recall(self, wing: str = None, room: str = None, n_results: int = 10) -> str:
        """On-demand L2 retrieval filtered by wing/room."""
        stack = self._get_stack()
        if stack is None:
            return ""
        try:
            return stack.recall(wing=wing, room=room, n_results=n_results)
        except Exception:
            return ""

    def deep_search(self, query: str, wing: str = None, room: str = None, n_results: int = 5) -> str:
        """Deep L3 semantic search — returns formatted text."""
        stack = self._get_stack()
        if stack is None:
            return ""
        try:
            return stack.search(query, wing=wing, room=room, n_results=n_results)
        except Exception:
            return ""

    def _fallback_wake_up(self, wing: str = None) -> str:
        """Fallback wake-up when MemoryStack is unavailable."""
        parts = [
            "CoinScopeAI Memory System — Wake-up Context",
            "=" * 50,
        ]
        for name, store in self._all_stores().items():
            try:
                st = store.status()
                total = st.get("total_drawers", 0)
                if total > 0:
                    parts.append(f"  {st['wing']}: {total} drawers")
            except Exception:
                pass
        return "\n".join(parts)

    # ==================================================================
    # Knowledge Graph (MemPalace native)
    # ==================================================================

    def _get_kg(self):
        """Lazy-init the MemPalace KnowledgeGraph."""
        if self._kg is None:
            try:
                from mempalace.knowledge_graph import KnowledgeGraph
                self._kg = KnowledgeGraph(db_path=self.config.kg_db)
            except Exception as e:
                logger.warning("KnowledgeGraph init failed: %s", e)
                self._kg = None
        return self._kg

    def kg_add(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: str = None,
        source_closet: str = None,
    ) -> Optional[int]:
        """Add a fact to the knowledge graph."""
        kg = self._get_kg()
        if kg is None:
            return None
        return kg.add_triple(subject, predicate, obj, valid_from=valid_from, source_closet=source_closet)

    def kg_query(self, entity: str, as_of: str = None, direction: str = "both") -> List[Dict]:
        """Query entity relationships from the knowledge graph."""
        kg = self._get_kg()
        if kg is None:
            return []
        return kg.query_entity(entity, as_of=as_of, direction=direction)

    def kg_invalidate(self, subject: str, predicate: str, obj: str, ended: str = None):
        """Mark a fact as no longer true."""
        kg = self._get_kg()
        if kg is None:
            return
        kg.invalidate(subject, predicate, obj, ended=ended)

    def kg_timeline(self, entity: str = None) -> List[Dict]:
        """Get chronological timeline of facts."""
        kg = self._get_kg()
        if kg is None:
            return []
        return kg.timeline(entity)

    def kg_stats(self) -> Dict[str, Any]:
        """Knowledge graph statistics."""
        kg = self._get_kg()
        if kg is None:
            return {"error": "KnowledgeGraph not available"}
        return kg.stats()

    # ==================================================================
    # Palace Graph Traversal
    # ==================================================================

    def traverse(self, start_room: str, max_hops: int = 2) -> Dict[str, Any]:
        """Walk the palace graph from a room. Find connected ideas across wings."""
        try:
            from mempalace.palace_graph import traverse as pg_traverse
            col = self._get_collection()
            return pg_traverse(start_room, col=col, max_hops=max_hops)
        except Exception as e:
            return {"error": str(e)}

    def find_tunnels(self, wing_a: str = None, wing_b: str = None) -> Dict[str, Any]:
        """Find rooms that bridge two wings."""
        try:
            from mempalace.palace_graph import find_tunnels as pg_tunnels
            col = self._get_collection()
            return pg_tunnels(wing_a, wing_b, col=col)
        except Exception as e:
            return {"error": str(e)}

    def graph_stats(self) -> Dict[str, Any]:
        """Palace graph overview."""
        try:
            from mempalace.palace_graph import graph_stats as pg_stats
            col = self._get_collection()
            return pg_stats(col=col)
        except Exception as e:
            return {"error": str(e)}

    # ==================================================================
    # Cross-wing semantic search
    # ==================================================================

    def search(
        self,
        query: str,
        wing: str = None,
        room: str = None,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across all wings (or filtered by wing/room).
        Uses MemPalace's native search_memories function.
        """
        try:
            from mempalace.searcher import search_memories
            result = search_memories(
                query,
                palace_path=self.config.palace_path,
                wing=wing,
                room=room,
                n_results=n_results,
            )
            return result.get("results", [])
        except Exception:
            return self._search_direct(query, wing=wing, room=room, n_results=n_results)

    def _search_direct(
        self, query: str, wing: str = None, room: str = None, n_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Direct ChromaDB search fallback."""
        col = self._get_collection()
        if col is None:
            return []

        where = {}
        if wing and room:
            where = {"$and": [{"wing": wing}, {"room": room}]}
        elif wing:
            where = {"wing": wing}
        elif room:
            where = {"room": room}

        kwargs = {
            "query_texts": [query],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = col.query(**kwargs)
        except Exception:
            return []

        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({
                "text": doc,
                "wing": meta.get("wing", ""),
                "room": meta.get("room", ""),
                "similarity": round(1 - dist, 4),
                "metadata": meta,
            })
        return hits

    # ==================================================================
    # Retention & Pruning
    # ==================================================================

    def prune(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Delete drawers older than the configured retention period per wing.

        Respects:
          - Per-wing retention days from config.retention_days
          - RETENTION_EXEMPT_ROOMS (lessons, architecture, conventions, knowledge)
          - Wings with retention = -1 are never pruned

        Args:
            dry_run: If True, only report what would be deleted without
                     actually deleting.  Default True for safety.

        Returns:
            Dict with summary: total_scanned, total_prunable, pruned_by_wing,
            and (if dry_run) the list of drawer IDs that would be deleted.
        """
        col = self._get_collection()
        if col is None:
            return {"error": "ChromaDB collection not available"}

        # Flush pending writes first so we have a complete picture
        self.flush()

        now = datetime.now(timezone.utc)
        retention_days = self.config.retention_days

        # Fetch all drawers
        try:
            all_results = col.get(
                include=["metadatas"],
                limit=100000,
            )
        except Exception as e:
            return {"error": f"Failed to fetch drawers: {e}"}

        ids = all_results.get("ids", [])
        metas = all_results.get("metadatas", [])

        total_scanned = len(ids)
        prunable_ids: List[str] = []
        pruned_by_wing: Dict[str, int] = {}

        for doc_id, meta in zip(ids, metas):
            wing = meta.get("wing", "")
            room = meta.get("room", "")
            filed_at_str = meta.get("filed_at", "")

            # Skip exempt rooms
            if room in RETENTION_EXEMPT_ROOMS:
                continue

            # Get retention for this wing
            ret_days = retention_days.get(wing, -1)
            if ret_days < 0:
                continue  # indefinite retention

            # Parse filed_at
            if not filed_at_str:
                continue
            try:
                filed_at = datetime.fromisoformat(filed_at_str)
                if filed_at.tzinfo is None:
                    filed_at = filed_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            cutoff = now - timedelta(days=ret_days)
            if filed_at < cutoff:
                prunable_ids.append(doc_id)
                pruned_by_wing[wing] = pruned_by_wing.get(wing, 0) + 1

        result: Dict[str, Any] = {
            "dry_run": dry_run,
            "total_scanned": total_scanned,
            "total_prunable": len(prunable_ids),
            "pruned_by_wing": pruned_by_wing,
            "retention_config": retention_days,
            "exempt_rooms": list(RETENTION_EXEMPT_ROOMS),
        }

        if dry_run:
            result["prunable_ids"] = prunable_ids[:100]  # cap preview
            if len(prunable_ids) > 100:
                result["note"] = f"Showing first 100 of {len(prunable_ids)} prunable IDs"
        else:
            # Actually delete
            if prunable_ids:
                try:
                    # ChromaDB delete supports batch
                    col.delete(ids=prunable_ids)
                    result["deleted"] = len(prunable_ids)
                    logger.info(
                        "[MemPalace] Pruned %d drawers across %d wings",
                        len(prunable_ids),
                        len(pruned_by_wing),
                    )
                except Exception as e:
                    result["error"] = f"Delete failed: {e}"
                    result["deleted"] = 0
            else:
                result["deleted"] = 0

        return result

    # ==================================================================
    # Status & Taxonomy
    # ==================================================================

    def status(self) -> Dict[str, Any]:
        """Full status across all wings."""
        result = {
            "palace_path": self.config.palace_path,
            "stores": {},
            "async_writer": {
                "pending_events": self.trading._writer.pending_count,
                "flush_interval_seconds": self.config.flush_interval_seconds,
                "flush_batch_size": self.config.flush_batch_size,
                "queue_size": self.config.write_queue_size,
            },
            "retention": {
                "retention_days": self.config.retention_days,
                "exempt_rooms": list(RETENTION_EXEMPT_ROOMS),
            },
        }
        for name, store in self._all_stores().items():
            try:
                result["stores"][name] = store.status()
            except Exception as e:
                result["stores"][name] = {"error": str(e)}

        try:
            result["knowledge_graph"] = self.kg_stats()
        except Exception:
            result["knowledge_graph"] = {"error": "unavailable"}

        try:
            col = self._get_collection()
            if col:
                result["total_drawers"] = col.count()
        except Exception:
            result["total_drawers"] = 0

        return result

    def taxonomy(self) -> Dict[str, Dict[str, int]]:
        """Full wing -> room -> count tree."""
        col = self._get_collection()
        if col is None:
            return {}
        try:
            all_meta = col.get(include=["metadatas"], limit=10000)["metadatas"]
            tree: Dict[str, Dict[str, int]] = {}
            for m in all_meta:
                w = m.get("wing", "unknown")
                r = m.get("room", "unknown")
                if w not in tree:
                    tree[w] = {}
                tree[w][r] = tree[w].get(r, 0) + 1
            return tree
        except Exception:
            return {}

    # ==================================================================
    # Internals
    # ==================================================================

    def _get_collection(self):
        """Get the shared mempalace_drawers collection."""
        try:
            client = chromadb.PersistentClient(path=self.config.palace_path)
            return client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            return None

    def _all_stores(self) -> Dict[str, Any]:
        return {
            "trading": self.trading,
            "risk": self.risk,
            "scanner": self.scanner,
            "models": self.models,
            "system": self.system,
            "agents": self.agents,
            "knowledge": self.knowledge,
            "tasks": self.tasks,
        }
