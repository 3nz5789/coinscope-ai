"""
Task Outcome Store — wing_agent (tasks + lessons rooms)
=========================================================
Logs what tasks were completed, what worked, what failed, and lessons
learned.  Filed into ``wing_agent`` rooms: tasks, lessons.

Helps agents avoid repeating mistakes and build on past successes.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class TaskOutcomeStore(PalaceStore):
    _wing = "wing_agent"
    _default_room = "tasks"
    _default_hall = "hall_events"

    def log_task_started(
        self,
        task_id: str,
        title: str,
        description: str,
        agent_role: str = "",
        priority: str = "normal",
    ) -> str:
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
        return self.file_drawer(content=text, room="tasks", hall="hall_events", metadata=meta)

    def log_task_completed(
        self,
        task_id: str,
        title: str,
        summary: str,
        what_worked: str = "",
        lessons_learned: str = "",
        artifacts: str = "",
        agent_role: str = "",
    ) -> str:
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
        drawer_id = self.file_drawer(content=text, room="tasks", hall="hall_events", metadata=meta)

        # Auto-extract lesson if provided
        if lessons_learned:
            self.log_lesson(
                title=f"Lesson from: {title}",
                lesson=lessons_learned,
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
    ) -> str:
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
        drawer_id = self.file_drawer(content=text, room="tasks", hall="hall_events", metadata=meta)

        # Auto-extract lesson from failure
        if root_cause or recommendations:
            lesson = f"Failure: {failure_reason}"
            if root_cause:
                lesson += f"\nRoot cause: {root_cause}"
            if recommendations:
                lesson += f"\nRecommendation: {recommendations}"
            self.log_lesson(
                title=f"Failure lesson: {title}",
                lesson=lesson,
                category="failure",
                agent_role=agent_role,
                related_task_id=task_id,
            )

        return drawer_id

    def log_lesson(
        self,
        title: str,
        lesson: str,
        category: str = "general",
        agent_role: str = "",
        related_task_id: str = "",
    ) -> str:
        text = f"[LESSON] {title}\n{lesson}"

        meta: Dict[str, Any] = {
            "event_type": "lesson",
            "title": title,
            "category": category,
            "agent_role": agent_role,
            "related_task_id": related_task_id,
        }
        return self.file_drawer(content=text, room="lessons", hall="hall_advice", metadata=meta)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def completed_tasks(self, agent_role: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "tasks"}, {"status": "completed"}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def failed_tasks(self, agent_role: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "tasks"}, {"status": "failed"}]
        if agent_role:
            conditions.append({"agent_role": agent_role})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def lessons(self, category: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "lessons"}]
        if category:
            conditions.append({"category": category})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def by_task(self, task_id: str, n: int = 10) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"task_id": task_id}]}, limit=n
        )
