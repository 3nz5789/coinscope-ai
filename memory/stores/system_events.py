"""
System Event Store — wing_system
==================================
Logs engine lifecycle, configuration changes, deployment events,
and market regime transitions.
Filed into ``wing_system`` with rooms: lifecycle, config-changes, deployments, regime-changes.

Hall strategy:
  - lifecycle       → hall_events    (engine start/stop events)
  - config-changes  → hall_decisions (configuration change decisions)
  - deployments     → hall_events    (deployment events)
  - regime-changes  → hall_events    (market regime transition events)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class SystemEventStore(PalaceStore):
    _wing = "wing_system"
    _default_room = "lifecycle"
    _default_hall = "hall_events"

    def log_engine_start(
        self,
        engine_version: str = "",
        config_summary: str = "",
        symbols: str = "",
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Engine STARTED"
        if engine_version:
            text += f" | version={engine_version}"
        if symbols:
            text += f" | symbols={symbols}"
        if config_summary:
            text += f"\nConfig: {config_summary}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "engine_start",
            "engine_version": engine_version,
            "symbols": symbols,
        }
        return self.file_drawer(
            content=text, room="lifecycle", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_engine_stop(
        self,
        reason: str = "",
        uptime_seconds: float = 0.0,
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Engine STOPPED"
        if reason:
            text += f" | reason={reason}"
        if uptime_seconds:
            text += f" | uptime={uptime_seconds / 3600:.1f}h"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "engine_stop",
            "reason": reason,
            "uptime_seconds": uptime_seconds,
        }
        return self.file_drawer(
            content=text, room="lifecycle", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_config_change(
        self,
        component: str,
        param_name: str,
        old_value: str,
        new_value: str,
        reasoning: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Config change: {component}.{param_name} "
            f"| {old_value} → {new_value}"
        )
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "config_change",
            "component": component,
            "param_name": param_name,
            "old_value": old_value,
            "new_value": new_value,
        }
        return self.file_drawer(
            content=text, room="config-changes", hall="hall_decisions",
            metadata=meta, event_id=event_id,
        )

    def log_deployment(
        self,
        action: str,
        environment: str = "",
        version: str = "",
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Deployment: {action}"
        if environment:
            text += f" | env={environment}"
        if version:
            text += f" | version={version}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "deployment",
            "action": action,
            "environment": environment,
            "version": version,
        }
        return self.file_drawer(
            content=text, room="deployments", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_regime_change(
        self,
        symbol: str,
        old_regime: str,
        new_regime: str,
        confidence: float = 0.0,
        price: float = 0.0,
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Regime change: {symbol} "
            f"| {old_regime} → {new_regime} | confidence={confidence:.3f}"
        )
        if price:
            text += f" | price={price:.2f}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "regime_change",
            "symbol": symbol,
            "old_regime": old_regime,
            "new_regime": new_regime,
            "confidence": confidence,
            "price": price,
            "importance": 4,
        }
        return self.file_drawer(
            content=text, room="regime-changes", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def regime_changes(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "regime-changes"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "regime-changes"}]}
        return self.get_drawers(where=where, limit=n)

    def config_changes(self, component: str = "", n: int = 20) -> List[Dict]:
        if component:
            where = {"$and": [{"wing": self._wing}, {"room": "config-changes"}, {"component": component}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "config-changes"}]}
        return self.get_drawers(where=where, limit=n)

    def deployments(self, n: int = 10) -> List[Dict]:
        return self.get_drawers(room="deployments", limit=n)
