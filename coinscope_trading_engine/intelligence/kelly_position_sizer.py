"""
Kelly Criterion Position Sizing with Regime Multipliers

Implements fractional Kelly formula with:
- Regime-aware multipliers (bull 1.0x, chop 0.5x, bear 0.3x)
- Drawdown-based position adjustment
- Hard cap at 2% per trade
"""

import numpy as np


class KellyRiskController:
    """Kelly criterion position sizing controller"""
    
    def __init__(self, fraction: float = 0.25, hard_cap_pct: float = 0.02):
        self.fraction    = fraction       # fractional Kelly (conservative)
        self.hard_cap    = hard_cap_pct   # never exceed 2% per trade
        self.REGIME_MULT = {
            "bull": 1.0,
            "chop": 0.5,
            "bear": 0.3
        }
        self.peak_equity = None

    def calculate_position_size(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        regime: str,
        account_balance: float
    ) -> float:
        """
        Calculate position size using Kelly criterion
        
        Kelly formula: f = (bp - q) / b
        where:
            b = ratio of win to loss (avg_win / avg_loss)
            p = win probability
            q = loss probability (1 - p)
        
        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average win size (%)
            avg_loss: Average loss size (%)
            regime: Current market regime ('bull', 'chop', 'bear')
            account_balance: Current account balance
        
        Returns:
            Position size in USD
        """
        
        if avg_loss == 0 or win_rate <= 0:
            return 0.0

        # Kelly formula
        b = avg_win / avg_loss
        p = win_rate
        q = 1.0 - p

        kelly_full = (b * p - q) / b
        if kelly_full <= 0:
            return 0.0

        # Regime multiplier
        regime_mult = self.REGIME_MULT.get(regime, 0.5)

        # Drawdown adjustment
        dd_mult = self._drawdown_multiplier(account_balance)

        # Calculate raw percentage
        raw_pct = kelly_full * self.fraction * regime_mult * dd_mult
        
        # Apply hard cap
        final_pct = min(raw_pct, self.hard_cap)

        return round(account_balance * final_pct, 2)

    def _drawdown_multiplier(self, equity: float) -> float:
        """Calculate drawdown-based position multiplier"""
        if self.peak_equity is None:
            self.peak_equity = equity
        
        self.peak_equity = max(self.peak_equity, equity)
        dd = (equity - self.peak_equity) / self.peak_equity
        
        if dd > -0.05:
            return 1.0
        elif dd > -0.10:
            return 0.75
        elif dd > -0.15:
            return 0.50
        else:
            return 0.25  # severe drawdown

    def size_summary(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        regime: str,
        balance: float
    ) -> dict:
        """Get detailed sizing summary"""
        
        size = self.calculate_position_size(
            win_rate, avg_win, avg_loss, regime, balance
        )
        
        b = avg_win / avg_loss if avg_loss > 0 else 0
        p = win_rate
        q = 1 - p
        kelly_full = (b * p - q) / b if b > 0 else 0
        
        return {
            "kelly_full_pct": round(kelly_full * 100, 2),
            "kelly_fraction_pct": round(kelly_full * self.fraction * 100, 2),
            "regime_mult": self.REGIME_MULT.get(regime, 0.5),
            "final_size_usd": size,
            "final_pct": round(size / balance * 100, 3) if balance > 0 else 0,
        }


# Example usage
if __name__ == "__main__":
    kelly = KellyRiskController(fraction=0.25)
    
    # Example: 44% win rate, 2.1% avg win, 1.0% avg loss
    size = kelly.calculate_position_size(
        win_rate=0.44,
        avg_win=0.021,
        avg_loss=0.010,
        regime="bull",
        account_balance=10000
    )
    
    print(f"Position size: ${size:.2f}")
    
    # Get summary
    summary = kelly.size_summary(0.44, 0.021, 0.010, "bull", 10000)
    print(f"Summary: {summary}")
