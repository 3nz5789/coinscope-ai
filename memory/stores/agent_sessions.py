"""
Agent Session Store — wing_agent + per-agent specialist wings
===============================================================
Handles two layers of agent memory:

1. **Shared agent memory** (``wing_agent``) — cross-agent context,
   sessions, decisions, tasks, lessons, and shared knowledge.

2. **Per-agent specialist memory** (``wing_<agent_name>``) — each agent
   keeps its own diary using MemPalace's native diary pattern.
   The risk agent remembers liquidation events, the scanner agent
   remembers which setups worked, the devops agent remembers
   deployment configs and incident responses.

Agent roles:
  - risk_agent        — risk management specialist
  - scanner_agent     — pattern scanner specialist
  - trading_agent     — trade execution specialist
  - devops_agent      — infrastructure and deployment
  - research_agent    — market research and analysis
  - dashboard_agent   — frontend and visualization
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


def _new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M-") + uuid.uuid4().hex[:8]


class AgentSessionStore(PalaceStore):
    """
    Shared agent memory in wing_agent.
    For per-agent specialist diaries, use write_diary / read_diary.
    """
    _wing = "wing_agent"
    _default_room = "sessions"
    _default_hall = "hall_events"

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def start_session(
        self,
        agent_role: str,
        objective: str,
        context: str = "",
    ) -> str:
        session_id = _new_session_id()
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Session started | agent={agent_role} "
            f"| session={session_id}\nObjective: {objective}"
        )
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "session_start",
            "session_id": session_id,
            "agent_role": agent_role,
            "objective": objective,
        }
        self.file_drawer(content=text, room="sessions", hall="hall_events", metadata=meta)
        return session_id

    def log_event(
        self,
        session_id: str,
        agent_role: str,
        event: str,
        details: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] [{agent_role}] {event}"
        if details:
            text += f"\nDetails: {details}"

        meta: Dict[str, Any] = {
            "event_type": "session_event",
            "session_id": session_id,
            "agent_role": agent_role,
        }
        return self.file_drawer(content=text, room="sessions", hall="hall_events", metadata=meta)

    def log_decision(
        self,
        session_id: str,
        agent_role: str,
        decision: str,
        reasoning: str = "",
        alternatives: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] [{agent_role}] Decision: {decision}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"
        if alternatives:
            text += f"\nAlternatives considered: {alternatives}"

        meta: Dict[str, Any] = {
            "event_type": "decision",
            "session_id": session_id,
            "agent_role": agent_role,
        }
        return self.file_drawer(content=text, room="decisions", hall="hall_decisions", metadata=meta)

    def end_session(
        self,
        session_id: str,
        agent_role: str,
        summary: str,
        artifacts: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Session ended | agent={agent_role} "
            f"| session={session_id}\nSummary: {summary}"
        )
        if artifacts:
            text += f"\nArtifacts: {artifacts}"

        meta: Dict[str, Any] = {
            "event_type": "session_end",
            "session_id": session_id,
            "agent_role": agent_role,
            "summary": summary[:200],
        }
        return self.file_drawer(content=text, room="sessions", hall="hall_events", metadata=meta)

    # ------------------------------------------------------------------
    # Per-agent specialist diary (MemPalace native diary pattern)
    # ------------------------------------------------------------------

    def write_diary(
        self,
        agent_name: str,
        entry: str,
        topic: str = "general",
    ) -> str:
        """
        Write to an agent's personal diary.  Each agent gets its own wing
        (``wing_<agent_name>``) with a ``diary`` room — exactly matching
        MemPalace's native diary_write pattern.

        Use AAAK format for compression:
          "SESSION:2026-04-09|scanned.BTC.ETH.SOL|regime.flip.BTC.trending→volatile|★★★"
        """
        wing = f"wing_{agent_name.lower().replace(' ', '_')}"
        now = datetime.now(timezone.utc)
        entry_id = (
            f"diary_{wing}_{now.strftime('%Y%m%d_%H%M%S')}_"
            f"{hashlib.md5(entry[:50].encode()).hexdigest()[:8]}"
        )

        meta: Dict[str, Any] = {
            "wing": wing,
            "room": "diary",
            "hall": "hall_diary",
            "topic": topic,
            "type": "diary_entry",
            "agent": agent_name,
            "filed_at": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
        }

        self._col.upsert(
            ids=[entry_id],
            documents=[entry],
            metadatas=[meta],
        )
        return entry_id

    def read_diary(
        self,
        agent_name: str,
        last_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Read an agent's recent diary entries, newest first."""
        wing = f"wing_{agent_name.lower().replace(' ', '_')}"
        try:
            results = self._col.get(
                where={"$and": [{"wing": wing}, {"room": "diary"}]},
                include=["documents", "metadatas"],
                limit=10000,
            )
        except Exception:
            return []

        entries = []
        for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
            entries.append({
                "date": meta.get("date", ""),
                "timestamp": meta.get("filed_at", ""),
                "topic": meta.get("topic", ""),
                "content": doc,
            })
        entries.sort(key=lambda x: x["timestamp"], reverse=True)
        return entries[:last_n]

    # ------------------------------------------------------------------
    # Cross-agent context sharing
    # ------------------------------------------------------------------

    def share_context(
        self,
        from_agent: str,
        context: str,
        topic: str = "",
        importance: int = 3,
    ) -> str:
        """
        Share context that other agents should know about.
        Filed in wing_agent/knowledge for cross-agent visibility.
        """
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] [{from_agent}] {context}"

        meta: Dict[str, Any] = {
            "event_type": "shared_context",
            "from_agent": from_agent,
            "topic": topic,
            "importance": importance,
        }
        return self.file_drawer(content=text, room="knowledge", hall="hall_facts", metadata=meta)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_agent(self, agent_role: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"agent_role": agent_role}]}, limit=n
        )

    def by_session(self, session_id: str, n: int = 50) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"session_id": session_id}]}, limit=n
        )

    def recent_sessions(self, agent_role: str = "", n: int = 10) -> List[Dict]:
        conditions = [{"wing": self._wing}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        conditions.append({"event_type": "session_start"})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def decisions(self, agent_role: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "decisions"}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def shared_knowledge(self, topic: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "knowledge"}]
        if topic:
            conditions.append({"topic": topic})
        return self.get_drawers(where={"$and": conditions}, limit=n)
