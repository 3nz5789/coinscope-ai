"""
Project Knowledge Store — wing_project
=========================================
Stores confirmed project decisions, milestones, deployments, releases,
lessons learned, and post-mortem insights for the CoinScopeAI project.

Filed into ``wing_project`` with rooms: facts, events, discoveries.

Hall strategy (from config.py HALL_STRATEGY):
  - facts       → hall_facts       (confirmed decisions: pricing, tech stack, etc.)
  - events      → hall_events      (milestones, deployments, releases)
  - discoveries → hall_discoveries (lessons learned, post-mortems)

Agents query this to stay aligned with project-level knowledge.
Supports queries like:
  "What pricing model was decided?"
  "When was the last deployment?"
  "What post-mortem lessons came from the testnet phase?"
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


VALID_CATEGORIES = {
    "decision",
    "pricing",
    "tech_stack",
    "deployment",
    "milestone",
    "release",
    "postmortem",
    "lesson",
    "general",
}

# Map categories to rooms
_CATEGORY_ROOM = {
    "decision":   "facts",
    "pricing":    "facts",
    "tech_stack": "facts",
    "deployment": "events",
    "milestone":  "events",
    "release":    "events",
    "postmortem": "discoveries",
    "lesson":     "discoveries",
    "general":    "facts",
}


class ProjectKnowledgeStore(PalaceStore):
    """
    Project-level knowledge in wing_project.

    Rooms:
      - facts:       confirmed decisions (pricing, tech stack, architecture)
      - events:      milestones, deployments, releases
      - discoveries: lessons learned, post-mortems, insights
    """

    _wing = "wing_project"
    _default_room = "facts"
    _default_hall = "hall_facts"

    # ------------------------------------------------------------------
    # Generic logging
    # ------------------------------------------------------------------

    def log(
        self,
        title: str,
        content: str,
        category: str = "general",
        component: str = "",
        agent_role: str = "",
        supersedes: str = "",
        event_id: str = "",
    ) -> str:
        """
        Log a project knowledge entry.

        The ``category`` determines which room the drawer is filed into:
          - decision, pricing, tech_stack, general → facts
          - deployment, milestone, release         → events
          - postmortem, lesson                     → discoveries
        """
        if category not in VALID_CATEGORIES:
            category = "general"

        room = _CATEGORY_ROOM.get(category, "facts")
        hall = {
            "facts": "hall_facts",
            "events": "hall_events",
            "discoveries": "hall_discoveries",
        }.get(room, "hall_facts")

        text = f"[{category.upper()}] {title}\n{content}"

        meta: Dict[str, Any] = {
            "event_type": "knowledge",
            "title": title,
            "category": category,
            "component": component,
            "agent_role": agent_role,
        }
        if supersedes:
            meta["supersedes"] = supersedes

        return self.file_drawer(
            content=text, room=room, hall=hall,
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Fact logging
    # ------------------------------------------------------------------

    def log_fact(
        self,
        title: str,
        content: str,
        category: str = "decision",
        component: str = "",
        agent_role: str = "",
        supersedes: str = "",
        event_id: str = "",
    ) -> str:
        """Log a confirmed project fact (pricing, tech stack, architecture decision)."""
        text = f"[FACT] {title}\n{content}"

        meta: Dict[str, Any] = {
            "event_type": "fact",
            "title": title,
            "category": category,
            "component": component,
            "agent_role": agent_role,
        }
        if supersedes:
            meta["supersedes"] = supersedes

        return self.file_drawer(
            content=text, room="facts", hall="hall_facts",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------

    def log_event(
        self,
        title: str,
        description: str,
        event_type: str = "milestone",
        component: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a project event (milestone, deployment, release)."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] {event_type.upper()}: {title}\n"
            f"{description}"
        )

        meta: Dict[str, Any] = {
            "event_type": event_type,
            "title": title,
            "component": component,
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="events", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_deployment(
        self,
        title: str,
        description: str,
        version: str = "",
        environment: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a deployment event."""
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] DEPLOYMENT: {title}\n{description}"
        if version:
            text += f"\nVersion: {version}"
        if environment:
            text += f"\nEnvironment: {environment}"

        meta: Dict[str, Any] = {
            "event_type": "deployment",
            "title": title,
            "version": version,
            "environment": environment,
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="events", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Discovery logging
    # ------------------------------------------------------------------

    def log_discovery(
        self,
        title: str,
        content: str,
        category: str = "lesson",
        component: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a discovery, lesson learned, or post-mortem insight."""
        text = f"[DISCOVERY] {title}\n{content}"

        meta: Dict[str, Any] = {
            "event_type": "discovery",
            "title": title,
            "category": category,
            "component": component,
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="discoveries", hall="hall_discoveries",
            metadata=meta, event_id=event_id,
        )

    def log_postmortem(
        self,
        title: str,
        description: str,
        root_cause: str = "",
        lessons: str = "",
        action_items: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a post-mortem analysis."""
        text = f"[POSTMORTEM] {title}\n{description}"
        if root_cause:
            text += f"\nRoot cause: {root_cause}"
        if lessons:
            text += f"\nLessons: {lessons}"
        if action_items:
            text += f"\nAction items: {action_items}"

        meta: Dict[str, Any] = {
            "event_type": "postmortem",
            "title": title,
            "category": "postmortem",
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="discoveries", hall="hall_discoveries",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_category(self, category: str, n: int = 20) -> List[Dict]:
        """Retrieve drawers by category."""
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"category": category}]}, limit=n
        )

    def by_component(self, component: str, n: int = 20) -> List[Dict]:
        """Retrieve drawers by component."""
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"component": component}]}, limit=n
        )

    def facts(self, n: int = 20) -> List[Dict]:
        """Retrieve all confirmed project facts."""
        return self.get_drawers(room="facts", limit=n)

    def events(self, n: int = 20) -> List[Dict]:
        """Retrieve all project events."""
        return self.get_drawers(room="events", limit=n)

    def discoveries(self, n: int = 20) -> List[Dict]:
        """Retrieve all project discoveries and lessons."""
        return self.get_drawers(room="discoveries", limit=n)
