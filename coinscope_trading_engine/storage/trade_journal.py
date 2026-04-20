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
    """Full provenance record for a single trade.

    Fields are grouped into:
      * Identity       — id, symbol, side, leverage
      * Signal origin  — source, regime, confidence, signal_score, scanner_hits, indicators_at_entry, reasons
      * Entry order    — entry_client_id, entry_order_id, entry_submit_ms, entry_fill_ms, entry_price, quantity, kelly_usd
      * Bracket        — sl_price, tp_price, sl_algo_id, tp_algo_id
      * Exit           — exit_trigger, exit_order_id, exit_price, closed_at, pnl_pct, pnl_usd
      * Status         — status ("OPEN" | "CLOSED")
    """
    # ── Identity ──────────────────────────────────────────────────
    id: str
    symbol: str
    side: str                         # "BUY" / "SELL"
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

    # ── Signal origin ─────────────────────────────────────────────
    signal_score:     float = 0.0
    sentiment_score:  float = 0.0
    strength:         str   = ""       # "STRONG" / "MODERATE" etc
    htf_trend:        str   = ""       # "bull"/"bear"/"neutral" at entry
    leverage:         int   = 0
    source:           str   = ""       # "manual" / "auto" / "api"
    reasons:          list  = None     # scanner reason strings (e.g. "Bid wall @ …")
    scanner_hits:     list  = None     # full per-scanner breakdown
    indicators_at_entry: dict = None   # {rsi, adx, macd, atr_pct, trend, momentum, volatility}

    # ── Entry order details ──────────────────────────────────────
    entry_client_id:  str = ""         # our idempotency token (cs-… / auto-…)
    entry_order_id:   int = 0          # Binance orderId
    entry_submit_ms:  int = 0          # when we sent the order to Binance
    entry_fill_ms:    int = 0          # when Binance reported fill
    slippage_bps:     float = 0.0      # entry_price vs setup.entry

    # ── Protective bracket (algo orders) ─────────────────────────
    sl_price:         float = 0.0
    tp_price:         float = 0.0
    sl_algo_id:       int   = 0
    tp_algo_id:       int   = 0

    # ── Exit details ──────────────────────────────────────────────
    exit_trigger:     str = ""         # "manual" / "killswitch" / "sl_hit" / "tp_hit" / "reconcile" / ""
    exit_order_id:    int = 0          # Binance orderId of the closing order
    closed_by:        str = ""         # who/what called close (user id / "engine")


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
        signal_score: float = 0.0,
        leverage: int = 0,
        source: str = "",
        reasons: list = None,
        strength: str = "",
        htf_trend: str = "",
        scanner_hits: list = None,
        indicators_at_entry: dict = None,
        entry_client_id: str = "",
        entry_order_id:  int = 0,
        entry_submit_ms: int = 0,
        entry_fill_ms:   int = 0,
        slippage_bps:    float = 0.0,
        sl_price: float = 0.0,
        tp_price: float = 0.0,
        sl_algo_id: int = 0,
        tp_algo_id: int = 0,
    ):
        """Log a trade open with full provenance."""
        entry = JournalEntry(
            id=f"{symbol}_{datetime.utcnow():%Y%m%d%H%M%S}",
            symbol=symbol,
            side=side,
            regime=regime or "UNKNOWN",
            confidence=confidence,
            entry_price=entry_price,
            exit_price=0.0,
            quantity=quantity,
            kelly_usd=kelly_usd,
            pnl_pct=0.0,
            pnl_usd=0.0,
            status="OPEN",
            opened_at=datetime.utcnow().isoformat(),
            signal_score=signal_score,
            strength=strength or "",
            htf_trend=htf_trend or "",
            leverage=int(leverage or 0),
            source=source or "",
            reasons=list(reasons or []),
            scanner_hits=list(scanner_hits or []),
            indicators_at_entry=dict(indicators_at_entry or {}),
            entry_client_id=entry_client_id or "",
            entry_order_id=int(entry_order_id or 0),
            entry_submit_ms=int(entry_submit_ms or 0),
            entry_fill_ms=int(entry_fill_ms or 0),
            slippage_bps=float(slippage_bps or 0.0),
            sl_price=float(sl_price or 0.0),
            tp_price=float(tp_price or 0.0),
            sl_algo_id=int(sl_algo_id or 0),
            tp_algo_id=int(tp_algo_id or 0),
        )
        self.entries.append(entry)
        self._save()
        return entry

    def update_bracket(self, entry_id: str, sl_algo_id: int = 0, tp_algo_id: int = 0) -> bool:
        """Attach algo-order IDs to an existing OPEN entry after the bracket
        is confirmed live on Binance."""
        for e in self.entries:
            if e.id == entry_id and e.status == "OPEN":
                if sl_algo_id: e.sl_algo_id = int(sl_algo_id)
                if tp_algo_id: e.tp_algo_id = int(tp_algo_id)
                self._save()
                return True
        return False

    def log_close(
        self,
        entry_id: str,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        exit_trigger: str = "",
        exit_order_id: int = 0,
        closed_by: str = "",
    ):
        """Log trade close with the reason + exit order reference."""
        for e in self.entries:
            if e.id == entry_id and e.status == "OPEN":
                e.exit_price = exit_price
                e.pnl_pct = round(pnl_pct, 5)
                e.pnl_usd = round(pnl_usd, 2)
                e.status = "CLOSED"
                e.closed_at = datetime.utcnow().isoformat()
                e.exit_trigger = exit_trigger or e.exit_trigger or ""
                e.exit_order_id = int(exit_order_id or e.exit_order_id or 0)
                e.closed_by = closed_by or e.closed_by or ""
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
