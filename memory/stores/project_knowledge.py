"""
Project Knowledge Store — wing_dev
=====================================
Stores architectural decisions, design choices, code patterns, conventions,
bug fixes, and dependency choices for the CoinScopeAI project.

Filed into ``wing_dev`` with rooms: architecture, conventions, bug-fixes, dependencies.

Hall strategy:
  - architecture  → hall_decisions   (ADRs, design decisions)
  - conventions   → hall_preferences (coding standards, patterns)
  - bug-fixes     → hall_advice      (bug fix records with lessons)
  - dependencies  → hall_facts       (library choices, version facts)

Agents query this to stay consistent with existing patterns.
Supports queries like:
  "What architecture decisions were made for the dashboard?"
  "What bugs were fixed last week and how?"
  "What's the current deployment setup?"
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore

VALID_CATEGORIES = {
    "architecture",
    "convention",
    "pattern",
    "deployment",
    "dependency",
    "api",
    "general",
}

# Map categories to rooms
_CATEGORY_ROOM = {
    "architecture": "architecture",
    "convention": "conventions",
    "pattern": "conventions",
    "deployment": "architecture",
    "dependency": "dependencies",
    "api": "architecture",
    "general": "architecture",
}


class ProjectKnowledgeStore(PalaceStore):
    _wing = "wing_dev"
    _default_room = "architecture"
    _default_hall = "hall_decisions"

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
        if category not in VALID_CATEGORIES:
            category = "general"

        room = _CATEGORY_ROOM.get(category, "architecture")
        now = datetime.now(timezone.utc)
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
            content=text, room=room, hall="hall_facts",
            metadata=meta, event_id=event_id,
        )

    def log_architecture_decision(
        self,
        title: str,
        decision: str,
        reasoning: str = "",
        alternatives: str = "",
        component: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log an Architecture Decision Record (ADR)."""
        now = datetime.now(timezone.utc)
        text = f"[ADR] {title}\nDecision: {decision}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"
        if alternatives:
            text += f"\nAlternatives considered: {alternatives}"

        meta: Dict[str, Any] = {
            "event_type": "adr",
            "title": title,
            "category": "architecture",
            "component": component,
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="architecture", hall="hall_decisions",
            metadata=meta, event_id=event_id,
        )

    def log_bug_fix(
        self,
        title: str,
        description: str,
        root_cause: str = "",
        fix: str = "",
        files_changed: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a bug fix with root cause analysis."""
        text = f"[BUG FIX] {title}\n{description}"
        if root_cause:
            text += f"\nRoot cause: {root_cause}"
        if fix:
            text += f"\nFix: {fix}"
        if files_changed:
            text += f"\nFiles changed: {files_changed}"

        meta: Dict[str, Any] = {
            "event_type": "bug_fix",
            "title": title,
            "category": "pattern",
            "files_changed": files_changed,
            "agent_role": agent_role,
        }
        return self.file_drawer(
            content=text, room="bug-fixes", hall="hall_advice",
            metadata=meta, event_id=event_id,
        )

    def log_convention(
        self,
        title: str,
        description: str,
        examples: str = "",
        component: str = "",
        event_id: str = "",
    ) -> str:
        """Log a coding convention or pattern."""
        text = f"[CONVENTION] {title}\n{description}"
        if examples:
            text += f"\nExamples: {examples}"

        meta: Dict[str, Any] = {
            "event_type": "convention",
            "title": title,
            "category": "convention",
            "component": component,
        }
        return self.file_drawer(
            content=text, room="conventions", hall="hall_preferences",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_category(self, category: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"category": category}]}, limit=n
        )

    def by_component(self, component: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"component": component}]}, limit=n
        )

    def architecture_decisions(self, n: int = 20) -> List[Dict]:
        return self.get_drawers(room="architecture", limit=n)

    def bug_fixes(self, n: int = 20) -> List[Dict]:
        return self.get_drawers(room="bug-fixes", limit=n)

    def conventions(self, n: int = 20) -> List[Dict]:
        return self.get_drawers(room="conventions", limit=n)
