"""
Trade Decision Store — wing_trading
=====================================
Logs every trade signal, entry/exit decision, and the reasoning behind it.
Filed into ``wing_trading`` with rooms: signals, entries, exits, analysis.

Searchable by symbol, date, strategy, outcome, regime.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..base_store import PalaceStore


class TradeDecisionStore(PalaceStore):
    _wing = "wing_trading"
    _default_room = "signals"
    _default_hall = "hall_events"

    # ------------------------------------------------------------------
    # Signal logging
    # ------------------------------------------------------------------

    def log_signal(
        self,
        symbol: str,
        signal: str,
        confidence: float,
        regime: str,
        price: float,
        strategy: str = "",
        reasoning: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] Signal: {signal} {symbol} "
            f"| confidence={confidence:.3f} | regime={regime} | price={price:.2f}"
        )
        if strategy:
            text += f" | strategy={strategy}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "signal",
            "symbol": symbol,
            "signal": signal,
            "confidence": confidence,
            "regime": regime,
            "price": price,
            "strategy": strategy,
        }
        if extra:
            for k, v in extra.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

        return self.file_drawer(content=text, room="signals", hall="hall_events", metadata=meta)

    # ------------------------------------------------------------------
    # Entry logging
    # ------------------------------------------------------------------

    def log_entry(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        regime: str,
        confidence: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        kelly_usd: float = 0.0,
        reasoning: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] ENTRY: {side} {symbol} "
            f"@ {entry_price:.2f} | qty={quantity} | regime={regime} "
            f"| confidence={confidence:.3f}"
        )
        if stop_loss:
            text += f" | SL={stop_loss:.2f}"
        if take_profit:
            text += f" | TP={take_profit:.2f}"
        if kelly_usd:
            text += f" | kelly=${kelly_usd:.2f}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "entry",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "quantity": quantity,
            "regime": regime,
            "confidence": confidence,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "kelly_usd": kelly_usd,
        }
        return self.file_drawer(content=text, room="entries", hall="hall_decisions", metadata=meta)

    # ------------------------------------------------------------------
    # Exit logging
    # ------------------------------------------------------------------

    def log_exit(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        reason: str = "",
        regime: str = "",
        reasoning: str = "",
    ) -> str:
        now = datetime.now(timezone.utc)
        outcome = "WIN" if pnl_usd >= 0 else "LOSS"
        text = (
            f"[{now:%Y-%m-%d %H:%M UTC}] EXIT: {side} {symbol} "
            f"| entry={entry_price:.2f} → exit={exit_price:.2f} "
            f"| pnl={pnl_pct:+.2%} (${pnl_usd:+.2f}) | {outcome}"
        )
        if reason:
            text += f" | reason={reason}"
        if regime:
            text += f" | regime={regime}"
        if reasoning:
            text += f"\nReasoning: {reasoning}"

        meta: Dict[str, Any] = {
            "event_type": "exit",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "outcome": outcome,
            "exit_reason": reason,
            "regime": regime,
        }
        return self.file_drawer(content=text, room="exits", hall="hall_events", metadata=meta)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def by_symbol(self, symbol: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(where={"$and": [{"wing": self._wing}, {"symbol": symbol}]}, limit=n)

    def by_outcome(self, outcome: str, n: int = 20) -> List[Dict]:
        return self.get_drawers(
            where={"$and": [{"wing": self._wing}, {"room": "exits"}, {"outcome": outcome}]},
            limit=n,
        )

    def by_date(self, date: str, n: int = 50) -> List[Dict]:
        return self.get_drawers(where={"$and": [{"wing": self._wing}, {"date": date}]}, limit=n)

    def signals_only(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "signals"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "signals"}]}
        return self.get_drawers(where=where, limit=n)

    def entries_only(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "entries"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "entries"}]}
        return self.get_drawers(where=where, limit=n)

    def exits_only(self, symbol: str = "", n: int = 20) -> List[Dict]:
        if symbol:
            where = {"$and": [{"wing": self._wing}, {"room": "exits"}, {"symbol": symbol}]}
        else:
            where = {"$and": [{"wing": self._wing}, {"room": "exits"}]}
        return self.get_drawers(where=where, limit=n)
