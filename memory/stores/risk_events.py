"""
Risk Event Store — wing_risk
==============================
Logs risk gate triggers, drawdown events, kill switch activations,
circuit breaker trips, and safety rejections.
Filed into ``wing_risk`` with rooms: gate-checks, drawdowns, kill-switch, rejections.

Hall strategy:
  - gate-checks     → hall_events  (timestamped risk gate pass/fail)
  - drawdowns       → hall_events  (drawdown threshold events)
  - kill-switch     → hall_events  (kill switch activations)
  - rejections      → hall_events  (order rejection events)
  - circuit-breaker → hall_events  (circuit breaker trips)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class RiskEventStore(PalaceStore):
    _wing = "wing_risk"
    _default_room = "gate-checks"
    _default_hall = "hall_events"

    def log_risk_gate_check(
        self,
        symbol: str,
        passed: bool,
        equity: float,
        daily_pnl: float,
        drawdown: float,
        consecutive_losses: int,
        open_positions: int,
        circuit_breaker_active: bool = False,
        circuit_breaker_reason: str = "",
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        status = "PASSED" if passed else "BLOCKED"
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Risk gate {status} for {symbol} | "
            f"equity=${equity:.2f} | daily_pnl=${daily_pnl:.2f} | "
            f"drawdown={drawdown:.2%} | consec_losses={consecutive_losses} | "
            f"open_positions={open_positions}"
        )
        if circuit_breaker_active:
            text += f"\nCircuit breaker ACTIVE: {circuit_breaker_reason}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "risk_gate_check",
            "symbol": symbol,
            "passed": passed,
            "equity": equity,
            "daily_pnl": daily_pnl,
            "drawdown": drawdown,
            "consecutive_losses": consecutive_losses,
            "open_positions": open_positions,
            "circuit_breaker_active": circuit_breaker_active,
        }
        if circuit_breaker_reason:
            meta["circuit_breaker_reason"] = circuit_breaker_reason

        return self.file_drawer(
            content=text, room="gate-checks", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_drawdown_event(
        self,
        drawdown_pct: float,
        equity: float,
        peak_equity: float,
        trigger: str = "",
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] DRAWDOWN: {drawdown_pct:.2%} "
            f"| equity=${equity:.2f} | peak=${peak_equity:.2f}"
        )
        if trigger:
            text += f" | trigger={trigger}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "drawdown",
            "drawdown_pct": drawdown_pct,
            "equity": equity,
            "peak_equity": peak_equity,
            "trigger": trigger,
            "importance": 5,
        }
        return self.file_drawer(
            content=text, room="drawdowns", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_kill_switch(
        self,
        activated: bool,
        reason: str = "",
        equity: float = 0.0,
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        action = "ACTIVATED" if activated else "DEACTIVATED"
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Kill switch {action}"
        if reason:
            text += f" | reason={reason}"
        if equity:
            text += f" | equity=${equity:.2f}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "kill_switch",
            "activated": activated,
            "reason": reason,
            "equity": equity,
            "importance": 5,
        }
        return self.file_drawer(
            content=text, room="kill-switch", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    def log_rejection(
        self,
        symbol: str,
        reason: str,
        order_details: str = "",
        context: str = "",
        event_id: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Order REJECTED for {symbol} | reason={reason}"
        if order_details:
            text += f"\nOrder: {order_details}"
        if context:
            text += f"\nContext: {context}"

        meta: Dict[str, Any] = {
            "event_type": "rejection",
            "symbol": symbol,
            "reason": reason,
        }
        return self.file_drawer(
            content=text, room="rejections", hall="hall_events",
            metadata=meta, event_id=event_id,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def drawdowns(self, n: int = 20) -> List[Dict]:
        return self.get_drawers(room="drawdowns", limit=n)

    def kill_switch_events(self, n: int = 10) -> List[Dict]:
        return self.get_drawers(room="kill-switch", limit=n)

    def rejections(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "rejections"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "rejections"}]}
        return self.get_drawers(where=where, limit=n)

    def failed_checks(self, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"room": "gate-checks"}, {"passed": False}]},
            limit=n,
        )
