"""
Scanner Store — wing_scanner
==============================
Logs pattern scanner history: which setups were detected, which worked
on which pairs/timeframes, and scanner configuration changes.
Filed into ``wing_scanner`` with rooms: setups, performance, configs.

Supports queries like:
  "Which scanner configs under-performed in prior market regimes?"
  "What breakout setups worked on ETHUSDT in volatile regimes?"
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class ScannerStore(PalaceStore):
    _wing = "wing_scanner"
    _default_room = "setups"
    _default_hall = "hall_events"

    def log_setup(
        self,
        symbol: str,
        timeframe: str,
        setup_type: str,
        regime: str,
        confidence: float,
        price: float = 0.0,
        details: str = "",
    ) -> str:
        """Log a pattern setup detection."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Setup: {setup_type} on {symbol}/{timeframe} "
            f"| regime={regime} | confidence={confidence:.3f}"
        )
        if price:
            text += f" | price={price:.2f}"
        if details:
            text += f"\nDetails: {details}"

        meta: Dict[str, Any] = {
            "event_type": "setup_detected",
            "symbol": symbol,
            "timeframe": timeframe,
            "setup_type": setup_type,
            "regime": regime,
            "confidence": confidence,
            "price": price,
        }
        return self.file_drawer(content=text, room="setups", hall="hall_events", metadata=meta)

    def log_setup_outcome(
        self,
        symbol: str,
        timeframe: str,
        setup_type: str,
        regime: str,
        outcome: str,
        pnl_pct: float = 0.0,
        hold_time_hours: float = 0.0,
        notes: str = "",
    ) -> str:
        """Log the outcome of a previously detected setup."""
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Setup outcome: {setup_type} on {symbol}/{timeframe} "
            f"| regime={regime} | outcome={outcome} | pnl={pnl_pct:+.2%}"
        )
        if hold_time_hours:
            text += f" | hold={hold_time_hours:.1f}h"
        if notes:
            text += f"\nNotes: {notes}"

        meta: Dict[str, Any] = {
            "event_type": "setup_outcome",
            "symbol": symbol,
            "timeframe": timeframe,
            "setup_type": setup_type,
            "regime": regime,
            "outcome": outcome,
            "pnl_pct": pnl_pct,
            "hold_time_hours": hold_time_hours,
        }
        return self.file_drawer(content=text, room="performance", hall="hall_facts", metadata=meta)

    def log_config(
        self,
        config_name: str,
        params: str,
        reasoning: str = "",
    ) -> str:
        """Log a scanner configuration change."""
        now = datetime.now(timezone.utc)
        text = f"[{now:%Y-%m-%d %H:%M UTC}] Scanner config: {config_name}\nParams: {params}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "scanner_config",
            "config_name": config_name,
        }
        return self.file_drawer(content=text, room="configs", hall="hall_preferences", metadata=meta)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_setup_type(self, setup_type: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"setup_type": setup_type}]}, limit=n
        )

    def by_symbol_timeframe(self, symbol: str, timeframe: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"symbol": symbol}]
        if timeframe:
            conditions.append({"timeframe": timeframe})
        return self.get_drawers(where={"$and": conditions}, limit=n)

    def outcomes(self, regime: str = "", n: int = 20) -> List[Dict]:
        conditions = [{"wing": self._wing}, {"room": "performance"}]
        if regime:
            conditions.append({"regime": regime})
        return self.get_drawers(where={"$and": conditions}, limit=n)
