"""
Trade Journal - File-based trade logging

Saves all trades to logs/journal.json for audit trail and performance analysis.
Can be swapped for PostgreSQL in production.
"""

import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


@dataclass
class JournalEntry:
    """Single trade journal entry"""
    id: str
    symbol: str
    side: str
    regime: str
    confidence: float
    entry_price: float
    exit_price: float
    quantity: float
    kelly_usd: float
    pnl_pct: float
    pnl_usd: float
    status: str
    opened_at: str
    closed_at: str = ""
    signal_score: float = 0.0
    sentiment_score: float = 0.0


class TradeJournal:
    """File-based trade journal (no DB required)"""

    def __init__(self, path: str = "logs/journal.json", initial_capital: float = 10_000):
        self.path = path
        self.initial_capital = initial_capital  # BUG-13 FIX: parameterize capital
        os.makedirs("logs", exist_ok=True)
        self.entries = self._load()

    def _load(self):
        """Load existing entries from file"""
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                return [JournalEntry(**d) for d in data]
            except Exception:
                return []
        return []

    def _save(self):
        """Save entries to file"""
        with open(self.path, "w") as f:
            json.dump([asdict(e) for e in self.entries], f, indent=2)

    def log_open(
        self,
        symbol,
        side,
        regime,
        confidence,
        entry_price,
        quantity,
        kelly_usd,
        signal_score=0.0
    ):
        """Log trade open"""
        entry = JournalEntry(
            id=f"{symbol}_{datetime.utcnow():%Y%m%d%H%M%S}",
            symbol=symbol,
            side=side,
            regime=regime,
            confidence=confidence,
            entry_price=entry_price,
            exit_price=0.0,
            quantity=quantity,
            kelly_usd=kelly_usd,
            pnl_pct=0.0,
            pnl_usd=0.0,
            status="OPEN",
            opened_at=datetime.utcnow().isoformat(),
            signal_score=signal_score
        )
        self.entries.append(entry)
        self._save()
        return entry

    def log_close(self, entry_id: str, exit_price: float, pnl_pct: float, pnl_usd: float):
        """Log trade close"""
        for e in self.entries:
            if e.id == entry_id and e.status == "OPEN":
                e.exit_price = exit_price
                e.pnl_pct = round(pnl_pct, 5)
                e.pnl_usd = round(pnl_usd, 2)
                e.status = "CLOSED"
                e.closed_at = datetime.utcnow().isoformat()
                self._save()
                return True
        return False

    def get_recent_trades(self, days: int = 30):
        """Get recent closed trades"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [
            asdict(e)
            for e in self.entries
            if e.status == "CLOSED" and datetime.fromisoformat(e.closed_at) > cutoff
        ]

    def daily_summary(self):
        """Get today's summary"""
        today = datetime.utcnow().date().isoformat()
        today_trades = [
            e
            for e in self.entries
            if e.status == "CLOSED" and e.closed_at.startswith(today)
        ]
        if not today_trades:
            return {"date": today, "trades": 0}
        pnls = [e.pnl_pct for e in today_trades]
        wins = [p for p in pnls if p > 0]
        return {
            "date": today,
            "trades": len(today_trades),
            "win_rate": round(len(wins) / len(pnls), 3),
            "total_pnl": round(sum(pnls), 4),
            "best_trade": round(max(pnls), 4),
            "worst_trade": round(min(pnls), 4),
        }

    def performance_stats(self):
        """Get overall performance statistics including timestamped equity curve."""
        closed = [e for e in self.entries if e.status == "CLOSED"]
        if not closed:
            return {
                "total_trades": 0,
                "equity_curve": [],
                "initial_capital": self.initial_capital,
            }

        # Sort chronologically so the equity curve is in time order
        closed = sorted(closed, key=lambda e: e.closed_at)

        pnls_pct = [e.pnl_pct for e in closed]
        pnls_usd = [e.pnl_usd for e in closed]
        wins = [p for p in pnls_pct if p > 0]
        losses = [p for p in pnls_pct if p < 0]

        import numpy as np

        # Equity curve: USD-based, timestamped — was missing, causing the chart to go dark
        usd_arr = np.array(pnls_usd, dtype=float)
        equity_values = np.cumsum(usd_arr) + self.initial_capital

        equity_curve = [
            {"ts": e.closed_at, "equity": round(float(eq), 2)}
            for e, eq in zip(closed, equity_values)
        ]

        # Drawdown (USD-based)
        peak = np.maximum.accumulate(equity_values)
        dd = float(((equity_values - peak) / peak).min()) if peak.max() > 0 else 0.0

        # Sharpe (pct-based, annualised to 8h bars)
        pnl_arr = np.array(pnls_pct, dtype=float)
        sharpe = (
            float(np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(2190 / 24))
            if np.std(pnl_arr) > 0
            else 0.0
        )

        return {
            "total_trades":    len(closed),
            "win_rate":        round(len(wins) / len(pnls_pct), 3),
            "profit_factor":   round(sum(wins) / abs(sum(losses)), 2) if losses else 0,
            "sharpe":          round(sharpe, 3),
            "max_drawdown":    round(dd, 4),
            "avg_win":         round(sum(wins) / len(wins), 4) if wins else 0,
            "avg_loss":        round(sum(losses) / len(losses), 4) if losses else 0,
            "total_pnl":       round(sum(pnls_pct), 4),
            "total_pnl_usd":   round(sum(pnls_usd), 2),
            "current_equity":  round(float(equity_values[-1]), 2) if len(equity_values) else self.initial_capital,
            "initial_capital":  self.initial_capital,
            "equity_curve":    equity_curve,
        }
