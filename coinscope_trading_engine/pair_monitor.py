"""
Pair-Level Performance Monitor

Tracks per-pair statistics to identify:
- Volatility characteristics (high-vol pairs like ADA/DOGE need slippage modeling)
- Win rate by pair (to detect regime transfer issues)
- Slippage patterns (especially important for less-liquid pairs)
- Regime accuracy per pair (HMM was trained on BTC/ETH/SOL)
"""

import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List


@dataclass
class PairStats:
    """Per-pair statistics"""
    symbol: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    win_rate: float = 0.0
    avg_slippage: float = 0.0
    regime_accuracy: float = 0.0   # % of directional trades where regime matched signal
    regime_directional_trades: int = 0  # count of bull/bear trades (chop excluded)
    last_updated: str = ""


# Pair characteristics for Week 1 monitoring
PAIR_CHARACTERISTICS = {
    "BTC/USDT": {
        "volatility": "low",
        "liquidity": "very_high",
        "hmm_trained": True,
        "slippage_risk": "minimal",
        "notes": "Baseline pair - HMM trained on BTC data"
    },
    "ETH/USDT": {
        "volatility": "low",
        "liquidity": "very_high",
        "hmm_trained": True,
        "slippage_risk": "minimal",
        "notes": "Baseline pair - HMM trained on ETH data"
    },
    "SOL/USDT": {
        "volatility": "medium",
        "liquidity": "high",
        "hmm_trained": True,
        "slippage_risk": "minimal",
        "notes": "Baseline pair - HMM trained on SOL data"
    },
    "BNB/USDT": {
        "volatility": "low",
        "liquidity": "high",
        "hmm_trained": False,
        "slippage_risk": "low",
        "notes": "Good liquidity, regime transfer may need validation"
    },
    "XRP/USDT": {
        "volatility": "medium",
        "liquidity": "high",
        "hmm_trained": False,
        "slippage_risk": "low",
        "notes": "Good liquidity, regime transfer may need validation"
    },
    "TAO/USDT": {
        "volatility": "high",
        "liquidity": "medium",
        "hmm_trained": False,
        "slippage_risk": "medium",
        "notes": "Higher volatility - monitor slippage closely"
    },
    # Alternative pairs (if swapped in)
    "ADA/USDT": {
        "volatility": "high",
        "liquidity": "medium",
        "hmm_trained": False,
        "slippage_risk": "medium",
        "notes": "Higher volatility than BNB - slippage modeling required"
    },
    "DOGE/USDT": {
        "volatility": "very_high",
        "liquidity": "medium",
        "hmm_trained": False,
        "slippage_risk": "high",
        "notes": "Very high volatility - slippage modeling critical"
    },
}


class PairMonitor:
    """Track per-pair performance and characteristics"""
    
    def __init__(self, path: str = "logs/pair_monitor.json"):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.stats: Dict[str, PairStats] = self._load()
    
    def _load(self) -> Dict[str, PairStats]:
        """Load existing pair stats"""
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    data = json.load(f)
                return {symbol: PairStats(**s) for symbol, s in data.items()}
            except Exception:
                return {}
        return {}
    
    def _save(self):
        """Save pair stats to file"""
        with open(self.path, "w") as f:
            json.dump(
                {symbol: asdict(stats) for symbol, stats in self.stats.items()},
                f,
                indent=2
            )
    
    def record_trade(self, symbol: str, pnl_pct: float, regime: str, signal_direction: str):
        """Record a trade for per-pair tracking"""
        if symbol not in self.stats:
            self.stats[symbol] = PairStats(symbol=symbol)
        
        stats = self.stats[symbol]
        stats.trades += 1
        stats.total_pnl += pnl_pct
        
        if pnl_pct > 0:
            stats.wins += 1
            stats.avg_win = (stats.avg_win * (stats.wins - 1) + pnl_pct) / stats.wins
            stats.max_win = max(stats.max_win, pnl_pct)
        else:
            stats.losses += 1
            stats.avg_loss = (stats.avg_loss * (stats.losses - 1) + pnl_pct) / stats.losses
            stats.max_loss = min(stats.max_loss, pnl_pct)
        
        stats.win_rate = stats.wins / stats.trades if stats.trades > 0 else 0
        stats.last_updated = datetime.utcnow().isoformat()
        
        # Track regime accuracy (did regime match signal direction?)
        # CHOP FIX: exclude chop-regime trades from the accuracy denominator.
        # Regime accuracy is only meaningful for directional regimes (bull/bear).
        # In a chop regime the HMM is deliberately agnostic about direction, so
        # including chop trades would deflate accuracy for pairs that trade more
        # often in choppy conditions.
        if regime in ("bull", "bear"):
            stats.regime_directional_trades += 1
            is_hit = (regime == "bull" and signal_direction == "LONG") or \
                     (regime == "bear" and signal_direction == "SHORT")
            n = stats.regime_directional_trades
            stats.regime_accuracy = (stats.regime_accuracy * (n - 1) + (1 if is_hit else 0)) / n
        
        self._save()
    
    def get_pair_report(self) -> str:
        """Generate per-pair performance report"""
        report = "\n" + "=" * 70
        report += "\n PAIR-LEVEL PERFORMANCE REPORT\n"
        report += "=" * 70 + "\n"
        
        for symbol in sorted(self.stats.keys()):
            stats = self.stats[symbol]
            chars = PAIR_CHARACTERISTICS.get(symbol, {})
            
            report += f"\n{symbol}\n"
            report += f"  Volatility: {chars.get('volatility', 'unknown')} | "
            report += f"Liquidity: {chars.get('liquidity', 'unknown')} | "
            report += f"Slippage Risk: {chars.get('slippage_risk', 'unknown')}\n"
            report += f"  Trades: {stats.trades} | Win Rate: {stats.win_rate:.1%} | "
            report += f"Total PnL: {stats.total_pnl:+.2%}\n"
            report += f"  Avg Win: {stats.avg_win:+.2%} | Avg Loss: {stats.avg_loss:+.2%} | "
            report += f"Regime Accuracy: {stats.regime_accuracy:.1%}\n"
            
            # Highlight concerns
            if stats.trades >= 10:
                if stats.win_rate < 0.30:
                    report += f"  ⚠️  LOW WIN RATE: {stats.win_rate:.1%} (target: 40%+)\n"
                if stats.regime_accuracy < 0.60 and stats.trades >= 5:
                    report += f"  ⚠️  LOW REGIME ACCURACY: {stats.regime_accuracy:.1%} - regime transfer may need adjustment\n"
                if chars.get('slippage_risk') in ['medium', 'high'] and stats.avg_loss < -0.03:
                    report += f"  ⚠️  HIGH SLIPPAGE: Avg loss {stats.avg_loss:.2%} - consider modeling slippage\n"
        
        report += "\n" + "=" * 70 + "\n"
        return report
    
    def print_report(self):
        """Print pair report to console"""
        print(self.get_pair_report())


if __name__ == "__main__":
    monitor = PairMonitor()
    
    # Example: Record some trades
    monitor.record_trade("BTC/USDT", 0.015, "bull", "LONG")
    monitor.record_trade("BTC/USDT", -0.008, "bull", "SHORT")
    monitor.record_trade("ETH/USDT", 0.012, "bull", "LONG")
    monitor.record_trade("SOL/USDT", 0.020, "bull", "LONG")
    monitor.record_trade("TAO/USDT", -0.025, "bear", "LONG")  # Regime mismatch
    
    monitor.print_report()
