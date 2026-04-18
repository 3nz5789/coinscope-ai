"""
Binance Testnet Executor

Simulates live trading on Binance Testnet with:
- Order placement and tracking
- Circuit breakers
- P&L calculation
- Trade logging
"""

import os
import json
import logging
from datetime import datetime, date
from dataclasses import dataclass, asdict, field


@dataclass
class TradeRecord:
    """Single trade record"""
    symbol: str
    side: str
    quantity: float
    entry_price: float
    regime: str
    kelly_usd: float
    order_id: str
    timestamp: str
    status: str = "OPEN"
    exit_price: float = 0.0
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0


class TestnetExecutor:
    """Testnet order executor with circuit breakers"""

    def __init__(self):
        self.testnet = True
        self.trade_log: list = []
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.peak_equity = 10_000.0
        self.current_equity = 10_000.0
        self._reset_date = date.today()
        self._setup_logging()

    def _setup_logging(self):
        """Setup logging to file and console"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(message)s",
            handlers=[
                logging.FileHandler(f"logs/testnet_{datetime.now():%Y%m%d}.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TestnetExecutor")

    def _reset_daily(self):
        """Reset daily counters"""
        if date.today() != self._reset_date:
            self.daily_pnl = 0.0
            self.consecutive_losses = 0
            self._reset_date = date.today()

    def _circuit_breakers(self) -> tuple:
        """Check circuit breaker conditions"""
        self._reset_daily()
        dd = (self.current_equity - self.peak_equity) / self.peak_equity
        
        if self.daily_pnl < -0.03:
            return False, f"Daily loss limit: {self.daily_pnl:.2%}"
        if self.consecutive_losses >= 5:
            return False, f"Consecutive losses: {self.consecutive_losses}"
        if dd < -0.10:
            return False, f"Max drawdown: {dd:.2%}"
        
        return True, "OK"

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        regime: str,
        kelly_usd: float,
    ) -> str:
        """Place order (testnet simulation).

        Signature updated: caller pre-computes quantity and price so the
        executor is exchange-agnostic. Returns order_id string (empty on block).
        """
        ok, reason = self._circuit_breakers()
        if not ok:
            self.logger.warning(f"⛔ BLOCKED — {reason}")
            return ""

        order_id = f"TEST_{datetime.utcnow():%Y%m%d%H%M%S}_{symbol[:3]}"

        record = TradeRecord(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            regime=regime,
            kelly_usd=kelly_usd,
            order_id=order_id,
            timestamp=datetime.utcnow().isoformat()
        )

        self.trade_log.append(record)
        self.logger.info(
            f"✅ {side} {symbol} qty={quantity:.6f} @ ${price:.4f} "
            f"| regime={regime} | kelly=${kelly_usd:.2f}"
        )
        return order_id

    def _get_mock_price(self, symbol: str) -> float:
        """Get mock price for testnet"""
        prices = {
            "BTC/USDT": 68500,
            "ETH/USDT": 2130,
            "SOL/USDT": 83,
            "BNB/USDT": 960,
            "XRP/USDT": 1.34,
            "TAO/USDT": 311,
        }
        return prices.get(symbol, 100.0)

    def close_position(self, record: TradeRecord, exit_price: float) -> float:
        """Close position and calculate P&L"""
        direction = 1 if record.side == "BUY" else -1
        pnl_pct = direction * (exit_price - record.entry_price) / record.entry_price
        pnl_usd = pnl_pct * record.kelly_usd

        record.exit_price = exit_price
        record.pnl_pct = round(pnl_pct, 5)
        record.pnl_usd = round(pnl_usd, 2)
        record.status = "CLOSED"

        self.current_equity += pnl_usd
        self.peak_equity = max(self.peak_equity, self.current_equity)
        self.daily_pnl += pnl_pct

        if pnl_pct < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        self.logger.info(
            f"🔒 CLOSED {record.symbol} @ ${exit_price:.4f} | "
            f"PnL: {pnl_pct:+.2%} (${pnl_usd:+.2f}) | "
            f"Equity: ${self.current_equity:,.2f}"
        )
        return pnl_pct

    def _anomaly_detected(self, closed: list) -> bool:
        """Detect suspiciously high win rate in early trades (data-leakage signal)."""
        if len(closed) < 5:
            return False
        pnls = [t.pnl_pct for t in closed]
        wins = [p for p in pnls if p > 0]
        win_rate = len(wins) / len(pnls)
        # Alert if >60% win rate within first 30 trades — likely data leakage
        return len(closed) <= 30 and win_rate > 0.60

    def get_summary(self) -> dict:
        """Get trading summary"""
        closed = [t for t in self.trade_log if t.status == "CLOSED"]
        if not closed:
            return {"trades": 0, "equity": self.current_equity, "anomaly_detected": False}

        pnls = [t.pnl_pct for t in closed]
        wins = [p for p in pnls if p > 0]

        return {
            "trades": len(closed),
            "win_rate": round(len(wins) / len(pnls), 3),
            "total_pnl": round(sum(pnls), 4),
            "avg_win": round(sum(wins) / len(wins), 4) if wins else 0,
            "equity": round(self.current_equity, 2),
            "peak_equity": round(self.peak_equity, 2),
            "daily_pnl": round(self.daily_pnl, 4),
            "anomaly_detected": self._anomaly_detected(closed),
        }

    def export_log(self, path: str = "logs/testnet_trades.json"):
        """Export trade log to JSON"""
        os.makedirs("logs", exist_ok=True)
        with open(path, "w") as f:
            json.dump([asdict(t) for t in self.trade_log], f, indent=2)
        print(f"Trade log saved → {path}")


# Example usage
if __name__ == "__main__":
    executor = TestnetExecutor()
    
    # Place order — new signature: quantity and price are pre-computed by caller
    order_id = executor.place_order(
        symbol="BTC/USDT",
        side="BUY",
        quantity=0.00292,   # 200 / 68500
        price=68500.0,
        regime="bull",
        kelly_usd=200,
    )

    print(f"Order ID: {order_id}")

    # Fetch trade record from log and close position
    rec = executor.trade_log[-1] if executor.trade_log else None
    if rec:
        pnl = executor.close_position(rec, 69000)
        print(f"P&L: {pnl:+.2%}")
    
    # Summary
    print(f"Summary: {executor.get_summary()}")
