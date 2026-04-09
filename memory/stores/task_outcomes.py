"""
Task Outcome Store — wing_agents
===================================
Tracks which agents exist, their roles and capabilities, what each agent
built, subtask outcomes, and what worked vs. what didn't.

Filed into ``wing_agents`` with rooms: facts, events, discoveries.

Hall strategy (from config.py HALL_STRATEGY):
  - facts       → hall_facts       (which agents exist, roles, capabilities)
  - events      → hall_events      (subtask outcomes, what each agent built)
  - discoveries → hall_discoveries (what worked, what didn't)

Helps agents avoid repeating mistakes and build on past successes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class TaskOutcomeStore(PalaceStore):
    """
    Agent-level outcome tracking in wing_agents.

    Rooms:
      - facts:       which agents exist, their roles and capabilities
      - events:      subtask outcomes, what each agent built
      - discoveries: what worked, what didn't, lessons learned
    """

    _wing = "wing_agents"
    _default_room = "events"
    _default_hall = "hall_events"

    # ------------------------------------------------------------------
    # Facts — agent registry
    # ------------------------------------------------------------------

    def log_agent_fact(
        self,
        agent_name: str,
        role: str,
        capabilities: str = "",
        notes: str = "",
        event_id: str = "",
    ) -> str:
        """Log an agent's existence, role, and capabilities."""
        text = f"[AGENT FACT] {agent_name} — role: {role}"
        if capabilities:
            text += f"\nCapabilities: {capabilities}"
        if notes:
            text += f"\nNotes: {notes}"

        meta: Dict[str, Any] = {
            "event_type": "agent_fact",
            "agent_name": agent_name,
            "role": role,
        }
        return self.file_drawer(
            content=text, room="facts", hall="hall_facts",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Events — task lifecycle
    # ------------------------------------------------------------------

    def log_task_started(
        self,
        task_id: str,
        title: str,
        description: str,
        agent_role: str = "",
        priority: str = "normal",
        event_id: str = "",
    ) -> str:
        """Log a task being started by an agent."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Task STARTED: {title} "
            f"| id={task_id} | agent={agent_role} | priority={priority}\n"
            f"Description: {description}"
        )
        meta: Dict[str, Any] = {
            "event_type": "task_started",
            "task_id": task_id,
            "title": title,
            "agent_role": agent_role,
            "priority": priority,
            "status": "in_progress",
        }
        return self.file_drawer(
            content=text, room="events", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_task_completed(
        self,
        task_id: str,
        title: str,
        summary: str,
        what_worked: str = "",
        lessons_learned: str = "",
        artifacts: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a task completion with summary and optional lessons."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Task COMPLETED: {title} "
            f"| id={task_id}\nSummary: {summary}"
        )
        if what_worked:
            text += f"\nWhat worked: {what_worked}"
        if lessons_learned:
            text += f"\nLessons learned: {lessons_learned}"
        if artifacts:
            text += f"\nArtifacts: {artifacts}"

        meta: Dict[str, Any] = {
            "event_type": "task_completed",
            "task_id": task_id,
            "title": title,
            "agent_role": agent_role,
            "status": "completed",
        }
        drawer_id = self.file_drawer(
            content=text, room="events", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

        # Auto-extract lesson if provided
        if lessons_learned:
            self.log_discovery(
                title=f"Lesson from: {title}",
                content=lessons_learned,
                category="lesson",
                agent_role=agent_role,
                related_task_id=task_id,
            )

        return drawer_id

    def log_task_failed(
        self,
        task_id: str,
        title: str,
        failure_reason: str,
        what_was_tried: str = "",
        root_cause: str = "",
        recommendations: str = "",
        agent_role: str = "",
        event_id: str = "",
    ) -> str:
        """Log a task failure with root cause analysis."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Task FAILED: {title} "
            f"| id={task_id}\nFailure: {failure_reason}"
        )
        if what_was_tried:
            text += f"\nWhat was tried: {what_was_tried}"
        if root_cause:
            text += f"\nRoot cause: {root_cause}"
        if recommendations:
            text += f"\nRecommendations: {recommendations}"

        meta: Dict[str, Any] = {
            "event_type": "task_failed",
            "task_id": task_id,
            "title": title,
            "agent_role": agent_role,
            "status": "failed",
            "failure_reason": failure_reason[:200],
        }
        drawer_id = self.file_drawer(
            content=text, room="events", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

        # Auto-extract lesson from failure
        if root_cause or recommendations:
            lesson = f"Failure: {failure_reason}"
            if root_cause:
                lesson += f"\nRoot cause: {root_cause}"
            if recommendations:
                lesson += f"\nRecommendation: {recommendations}"
            self.log_discovery(
                title=f"Failure lesson: {title}",
                content=lesson,
                category="failure_lesson",
                agent_role=agent_role,
                related_task_id=task_id,
            )

        return drawer_id

    # ------------------------------------------------------------------
    # Discoveries — lessons and insights
    # ------------------------------------------------------------------

    def log_discovery(
        self,
        title: str,
        content: str,
        category: str = "general",
        agent_role: str = "",
        related_task_id: str = "",
        event_id: str = "",
    ) -> str:
        """Log a discovery: what worked, what didn't, lessons learned."""
        text = f"[DISCOVERY] {title}\n{content}"

        meta: Dict[str, Any] = {
            "event_type": "discovery",
            "title": title,
            "category": category,
            "agent_role": agent_role,
            "related_task_id": related_task_id,
        }
        return self.file_drawer(
            content=text, room="discoveries", hall="hall_discoveries",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def completed_tasks(self, agent_role: str = "", n: int = 20) -> List[Dict]:
        """Retrieve completed task events."""
        conditions = [{"wing": self._wing}, {"room": "events"}, {"status": "completed"}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def failed_tasks(self, agent_role: str = "", n: int = 20) -> List[Dict]:
        """Retrieve failed task events."""
        conditions = [{"wing": self._wing}, {"room": "events"}, {"status": "failed"}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def agent_facts(self, agent_name: str = "", n: int = 20) -> List[Dict]:
        """Retrieve agent registry facts."""
        if agent_name:
            return self.get_drawers(
                where={"$and": [{"wing": self._wing}, {"room": "facts"}, {"agent_name": agent_name}]},
                limit=n,
            )
        return self.get_drawers(room="facts", limit=n)

    def discoveries(self, category: str = "", n: int = 20) -> List[Dict]:
        """Retrieve discoveries and lessons."""
        conditions = [{"wing": self._wing}, {"room": "discoveries"}]
        if category:
            conditions.append({"category": category})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def by_task(self, task_id: str, n: int = 10) -> List[Dict]:
        """Retrieve all drawers related to a specific task."""
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"task_id": task_id}]}, limit=n
        )
