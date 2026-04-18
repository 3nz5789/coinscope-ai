"""
Risk Gate Orchestrator

Manages:
1. Hard stop-loss (ATR-based with 2% cap)
2. Take-profit at 2:1 risk-reward ratio
3. Position sizing (Kelly fraction)
4. Regime-aware multipliers
5. Circuit breakers (daily loss, max DD, consecutive losses)
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    direction: int  # 1=LONG, -1=SHORT
    entry_price: float
    entry_time: int
    position_size: float
    stop_loss: float
    take_profit: float
    kelly_fraction: float
    regime: str  # 'bull', 'bear', 'chop'


class RiskGate:
    """
    Risk management orchestrator
    """
    
    def __init__(
        self,
        initial_capital: float = 10000,
        max_daily_loss_pct: float = 0.10,  # 10%
        max_drawdown_pct: float = 0.20,     # 20%
        max_consecutive_losses: int = 5,
        kelly_fraction: float = 0.25,       # Conservative 25% Kelly
        min_signal_score: float = 0.65      # 65/100
    ):
        self.initial_capital = initial_capital
        self.current_equity = initial_capital
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.kelly_fraction = kelly_fraction
        self.min_signal_score = min_signal_score
        
        # Tracking
        self.positions: Dict[str, Position] = {}
        self.daily_pnl = 0
        self.peak_equity = initial_capital
        self.consecutive_losses = 0
        self.trades_history = []
        
        # Circuit breaker status
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        atr: float,
        direction: int
    ) -> float:
        """
        Calculate hard stop-loss (ATR-based with 2% cap)
        
        Args:
            entry_price: Entry price
            atr: Average True Range
            direction: 1=LONG, -1=SHORT
        
        Returns:
            Stop-loss price
        """
        
        # ATR-based stop (typically 1-1.5x ATR)
        atr_stop = atr * 1.5
        
        # Cap at 2% of entry price
        max_stop = entry_price * 0.02
        
        # Use the smaller of the two
        stop_distance = min(atr_stop, max_stop)
        
        if direction == 1:  # LONG
            stop_loss = entry_price - stop_distance
        else:  # SHORT
            stop_loss = entry_price + stop_distance
        
        return stop_loss
    
    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        direction: int
    ) -> float:
        """
        Calculate take-profit at 2:1 risk-reward ratio
        
        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            direction: 1=LONG, -1=SHORT
        
        Returns:
            Take-profit price
        """
        
        risk = abs(entry_price - stop_loss)
        reward = risk * 2  # 2:1 ratio
        
        if direction == 1:  # LONG
            take_profit = entry_price + reward
        else:  # SHORT
            take_profit = entry_price - reward
        
        return take_profit
    
    def calculate_position_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        regime: str = 'bull'
    ) -> float:
        """
        Calculate position size using Kelly criterion with regime multipliers
        
        Kelly formula: f = (bp - q) / b
        where:
            b = ratio of win to loss (avg_win / avg_loss)
            p = win probability
            q = loss probability (1 - p)
        
        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average win size (%)
            avg_loss: Average loss size (%)
            regime: Current market regime
        
        Returns:
            Position size as fraction of capital (0-1)
        """
        
        if win_rate <= 0 or avg_loss <= 0:
            return 0
        
        # Kelly formula
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        
        kelly = (b * p - q) / b
        
        # Apply fractional Kelly (conservative)
        kelly_fraction = kelly * self.kelly_fraction
        
        # Regime multipliers
        regime_multipliers = {
            'bull': 1.0,
            'neutral': 0.75,
            'bear': 0.5,
            'chop': 0.5,
        }
        
        regime_mult = regime_multipliers.get(regime, 0.75)
        
        # Final position size
        position_size = kelly_fraction * regime_mult
        
        # Cap at 5% per trade
        position_size = min(position_size, 0.05)
        
        return max(position_size, 0)
    
    def check_circuit_breakers(self) -> Tuple[bool, str]:
        """
        Check if any circuit breaker should be triggered
        
        Returns:
            (should_halt, reason)
        """
        
        # Daily loss limit
        if self.daily_pnl < -self.initial_capital * self.max_daily_loss_pct:
            return True, f"Daily loss limit hit: {self.daily_pnl:.2f}"
        
        # Max drawdown limit
        current_dd = (self.peak_equity - self.current_equity) / self.peak_equity
        if current_dd > self.max_drawdown_pct:
            return True, f"Max drawdown limit hit: {current_dd:.1%}"
        
        # Consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            return True, f"Consecutive loss limit hit: {self.consecutive_losses}"
        
        return False, ""
    
    def open_position(
        self,
        symbol: str,
        direction: int,
        entry_price: float,
        entry_time: int,
        atr: float,
        regime: str,
        signal_score: float,
        win_rate: float = 0.42,
        avg_win: float = 2.1,
        avg_loss: float = 1.0
    ) -> Optional[Position]:
        """
        Open a new position with risk management
        
        Returns:
            Position object if opened, None if blocked
        """
        
        # Check circuit breakers
        halted, reason = self.check_circuit_breakers()
        if halted:
            logger.warning(f"🔴 Position blocked: {reason}")
            self.circuit_breaker_active = True
            self.circuit_breaker_reason = reason
            return None
        
        # Check signal score
        if signal_score < self.min_signal_score:
            logger.warning(f"🔴 Signal score too low: {signal_score:.2f} < {self.min_signal_score}")
            return None
        
        # Calculate risk management
        stop_loss = self.calculate_stop_loss(entry_price, atr, direction)
        take_profit = self.calculate_take_profit(entry_price, stop_loss, direction)
        position_size = self.calculate_position_size(win_rate, avg_win, avg_loss, regime)
        
        if position_size <= 0:
            logger.warning(f"🔴 Position size too small: {position_size:.4f}")
            return None
        
        # Create position
        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            kelly_fraction=self.kelly_fraction,
            regime=regime
        )
        
        self.positions[symbol] = position
        
        logger.info(
            f"✅ Position opened: {symbol} {direction:+d} @ {entry_price:.2f} "
            f"| SL: {stop_loss:.2f} | TP: {take_profit:.2f} | Size: {position_size:.4f}"
        )
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_time: int,
        reason: str = "manual"
    ) -> Optional[Dict]:
        """
        Close a position and record P&L
        
        Returns:
            Trade record dict
        """
        
        if symbol not in self.positions:
            logger.warning(f"⚠️ No position to close: {symbol}")
            return None
        
        pos = self.positions[symbol]
        
        # Calculate P&L
        if pos.direction == 1:  # LONG
            pnl_pct = (exit_price - pos.entry_price) / pos.entry_price
        else:  # SHORT
            pnl_pct = (pos.entry_price - exit_price) / pos.entry_price
        
        pnl_dollars = self.current_equity * pos.position_size * pnl_pct
        
        # Update equity
        self.current_equity += pnl_dollars
        self.daily_pnl += pnl_dollars
        
        # BUG-5 FIX: base consecutive loss counter on individual trade outcome, not equity peak
        if pnl_pct > 0:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
        # Update peak equity separately
        self.peak_equity = max(self.peak_equity, self.current_equity)
        
        # Record trade
        trade = {
            'symbol': symbol,
            'direction': pos.direction,
            'entry_price': pos.entry_price,
            'exit_price': exit_price,
            'entry_time': pos.entry_time,
            'exit_time': exit_time,
            'position_size': pos.position_size,
            'pnl_pct': pnl_pct,
            'pnl_dollars': pnl_dollars,
            'stop_loss': pos.stop_loss,
            'take_profit': pos.take_profit,
            'reason': reason,
            'regime': pos.regime,
        }
        
        self.trades_history.append(trade)
        del self.positions[symbol]
        
        win_loss = "✅ WIN" if pnl_pct > 0 else "❌ LOSS"
        logger.info(
            f"{win_loss}: {symbol} closed @ {exit_price:.2f} | "
            f"P&L: {pnl_pct:+.2%} ({pnl_dollars:+.2f}) | Reason: {reason}"
        )
        
        return trade
    
    def get_status(self) -> Dict:
        """Get current risk status"""
        
        current_dd = (self.peak_equity - self.current_equity) / self.peak_equity if self.peak_equity > 0 else 0
        
        return {
            'equity': self.current_equity,
            'daily_pnl': self.daily_pnl,
            'peak_equity': self.peak_equity,
            'drawdown': current_dd,
            'open_positions': len(self.positions),
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker_active': self.circuit_breaker_active,
            'circuit_breaker_reason': self.circuit_breaker_reason,
            'total_trades': len(self.trades_history),
            'win_rate': sum(1 for t in self.trades_history if t['pnl_pct'] > 0) / len(self.trades_history) if self.trades_history else 0,
        }


# Example usage
if __name__ == "__main__":
    gate = RiskGate(initial_capital=10000)
    
    # Open a LONG position
    pos = gate.open_position(
        symbol="BTC/USDT",
        direction=1,
        entry_price=45000,
        entry_time=0,
        atr=500,
        regime="bull",
        signal_score=0.75,
        win_rate=0.42,
        avg_win=2.1,
        avg_loss=1.0
    )
    
    print(f"Position: {pos}")
    
    # Close with profit
    trade = gate.close_position(
        symbol="BTC/USDT",
        exit_price=45900,
        exit_time=1,
        reason="take_profit"
    )
    
    print(f"Trade: {trade}")
    print(f"Status: {gate.get_status()}")
