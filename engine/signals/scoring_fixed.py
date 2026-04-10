"""
Fixed Scoring Engine with Graduated Scoring (0-3 per sub-score)

Fixes the binary scoring bug where sub-scores were only 0 or 3.
Now implements graduated scoring (0, 1, 2, 3) for all sub-scores,
matching the original 0-12 rubric design.

Total score range: 0-12
Entry signals: score >= 5.5 (LONG) or score <= 6.5 (SHORT)
"""

import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class FixedScorer:
    """
    Vectorized scorer with graduated (0-3) sub-scores.
    
    Scoring rubric:
    - Momentum (0-3): RSI position
    - Trend (0-3): EMA alignment
    - Volatility (0-3): ATR-based regime
    - Volume (0-3): Volume confirmation
    - Entry (0-3): Pullback depth (GRADUATED - not binary)
    - Liquidity (0-3): Bid-ask spread (GRADUATED - not binary)
    
    Total: 0-12 (higher = stronger signal)
    """
    
    def __init__(self):
        self.rsi_period = 14
        self.ema_fast = 9
        self.ema_slow = 21
        self.atr_period = 14
        
    def calculate_rsi(self, closes: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        deltas = np.diff(closes)
        seed = deltas[:period+1]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = np.zeros_like(closes)
        rsi[:period] = 100. - 100. / (1. + rs)
        
        for i in range(period, len(closes)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta
            
            up = (up * (period - 1) + upval) / period
            down = (down * (period - 1) + downval) / period
            
            rs = up / down if down != 0 else 0
            rsi[i] = 100. - 100. / (1. + rs)
        
        return rsi
    
    def calculate_ema(self, closes: np.ndarray, period: int) -> np.ndarray:
        """Calculate EMA"""
        ema = np.zeros_like(closes)
        ema[0] = closes[0]
        multiplier = 2 / (period + 1)
        
        for i in range(1, len(closes)):
            ema[i] = closes[i] * multiplier + ema[i-1] * (1 - multiplier)
        
        return ema
    
    def calculate_atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate ATR"""
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - np.roll(close, 1)),
                np.abs(low - np.roll(close, 1))
            )
        )
        # BUG-12 FIX: np.roll wraps close[-1] to index 0, producing a spurious TR.
        # Override first bar with the simple high-low range.
        tr[0] = high[0] - low[0]
        atr = np.zeros_like(tr)
        atr[period-1] = np.mean(tr[:period])
        
        for i in range(period, len(tr)):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        
        return atr
    
    def score_momentum(self, rsi: np.ndarray) -> np.ndarray:
        """
        Score momentum (0-3) based on RSI position
        
        0: RSI < 30 (oversold, weak)
        1: RSI 30-45 (weak)
        2: RSI 45-55 (neutral)
        3: RSI 55-70 (strong)
        """
        scores = np.zeros_like(rsi)
        scores[rsi < 30] = 0
        scores[(rsi >= 30) & (rsi < 45)] = 1
        scores[(rsi >= 45) & (rsi < 55)] = 2
        scores[(rsi >= 55) & (rsi < 70)] = 3
        scores[rsi >= 70] = 2  # Overbought, reduce score
        
        return scores
    
    def score_trend(self, close: np.ndarray, ema_fast: np.ndarray, ema_slow: np.ndarray) -> np.ndarray:
        """
        Score trend (0-3) based on EMA alignment
        
        0: Price below both EMAs (downtrend)
        1: Price between EMAs (weak uptrend)
        2: Price above fast EMA, fast above slow (uptrend)
        3: Price above both EMAs, fast >> slow (strong uptrend)
        """
        scores = np.zeros_like(close)
        
        # Strong downtrend
        scores[close < np.minimum(ema_fast, ema_slow)] = 0
        
        # Weak uptrend
        scores[(close >= np.minimum(ema_fast, ema_slow)) & (close < np.maximum(ema_fast, ema_slow))] = 1
        
        # Uptrend
        scores[(close >= np.maximum(ema_fast, ema_slow)) & (ema_fast > ema_slow)] = 2
        
        # Strong uptrend (fast EMA > slow EMA by 2%)
        scores[(close >= np.maximum(ema_fast, ema_slow)) & (ema_fast > ema_slow * 1.02)] = 3
        
        return scores
    
    def score_volatility(self, atr: np.ndarray, close: np.ndarray) -> np.ndarray:
        """
        Score volatility (0-3) based on ATR regime
        
        0: Very low volatility (ATR < 0.5% of price)
        1: Low volatility (ATR 0.5-1% of price)
        2: Normal volatility (ATR 1-2% of price)
        3: High volatility (ATR > 2% of price)
        """
        atr_pct = (atr / close) * 100
        
        scores = np.zeros_like(atr_pct)
        scores[atr_pct < 0.5] = 0
        scores[(atr_pct >= 0.5) & (atr_pct < 1.0)] = 1
        scores[(atr_pct >= 1.0) & (atr_pct < 2.0)] = 2
        scores[atr_pct >= 2.0] = 3
        
        return scores
    
    def score_volume(self, volume: np.ndarray, volume_ma: np.ndarray) -> np.ndarray:
        """
        Score volume (0-3) based on volume confirmation
        
        0: Volume < 50% of MA (weak)
        1: Volume 50-75% of MA (below average)
        2: Volume 75-125% of MA (normal)
        3: Volume > 125% of MA (strong)
        """
        volume_ratio = volume / volume_ma
        
        scores = np.zeros_like(volume_ratio)
        scores[volume_ratio < 0.5] = 0
        scores[(volume_ratio >= 0.5) & (volume_ratio < 0.75)] = 1
        scores[(volume_ratio >= 0.75) & (volume_ratio <= 1.25)] = 2
        scores[volume_ratio > 1.25] = 3
        
        return scores
    
    def score_entry(self, close: np.ndarray, ema_fast: np.ndarray, atr: np.ndarray) -> np.ndarray:
        """
        Score entry timing (0-3) based on pullback depth
        GRADUATED scoring (not binary)
        
        0: No pullback (price at resistance)
        1: Shallow pullback (0-25% of ATR from EMA)
        2: Medium pullback (25-50% of ATR from EMA)
        3: Deep pullback (50%+ of ATR from EMA)
        """
        pullback_depth = np.abs(close - ema_fast) / atr
        
        scores = np.zeros_like(pullback_depth)
        scores[pullback_depth < 0.25] = 0
        scores[(pullback_depth >= 0.25) & (pullback_depth < 0.5)] = 1
        scores[(pullback_depth >= 0.5) & (pullback_depth < 1.0)] = 2
        scores[pullback_depth >= 1.0] = 3
        
        return scores
    
    def score_liquidity(self, bid_ask_spread: np.ndarray, close: np.ndarray) -> np.ndarray:
        """
        Score liquidity (0-3) based on bid-ask spread
        GRADUATED scoring (not binary)
        
        0: Very wide spread (> 0.1% of price)
        1: Wide spread (0.05-0.1% of price)
        2: Normal spread (0.01-0.05% of price)
        3: Tight spread (< 0.01% of price)
        """
        spread_pct = (bid_ask_spread / close) * 100
        
        scores = np.zeros_like(spread_pct)
        scores[spread_pct > 0.1] = 0
        scores[(spread_pct > 0.05) & (spread_pct <= 0.1)] = 1
        scores[(spread_pct > 0.01) & (spread_pct <= 0.05)] = 2
        scores[spread_pct <= 0.01] = 3
        
        return scores
    
    def calculate_total_score(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        bid_ask_spread: np.ndarray
    ) -> Tuple[np.ndarray, Dict]:
        """
        Calculate total score (0-12) with all graduated sub-scores
        
        Returns:
            (total_score, sub_scores_dict)
        """
        
        # Calculate indicators
        rsi = self.calculate_rsi(close, self.rsi_period)
        ema_fast = self.calculate_ema(close, self.ema_fast)
        ema_slow = self.calculate_ema(close, self.ema_slow)
        atr = self.calculate_atr(high, low, close, self.atr_period)
        volume_ma = np.convolve(volume, np.ones(20)/20, mode='same')
        
        # Calculate sub-scores (all graduated 0-3)
        momentum = self.score_momentum(rsi)
        trend = self.score_trend(close, ema_fast, ema_slow)
        volatility = self.score_volatility(atr, close)
        vol_score = self.score_volume(volume, volume_ma)
        entry = self.score_entry(close, ema_fast, atr)
        liquidity = self.score_liquidity(bid_ask_spread, close)
        
        # Total score (0-12)
        total_score = momentum + trend + volatility + vol_score + entry + liquidity
        
        return total_score, {
            'momentum': momentum,
            'trend': trend,
            'volatility': volatility,
            'volume': vol_score,
            'entry': entry,
            'liquidity': liquidity,
            'rsi': rsi,
            'ema_fast': ema_fast,
            'ema_slow': ema_slow,
            'atr': atr,
        }
    
    def generate_signals(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        bid_ask_spread: np.ndarray,
        long_threshold: float = 5.5,
        short_threshold: float = 6.5
    ) -> Tuple[np.ndarray, Dict]:
        """
        Generate BUY/SELL signals based on graduated scoring
        
        Args:
            long_threshold: Score >= threshold for LONG signal (default 5.5)
            short_threshold: Score <= threshold for SHORT signal (default 6.5)
        
        Returns:
            (signals, sub_scores_dict)
            signals: 1=LONG, -1=SHORT, 0=NEUTRAL
        """
        
        total_score, sub_scores = self.calculate_total_score(
            close, high, low, volume, bid_ask_spread
        )
        
        signals = np.zeros_like(close, dtype=int)
        signals[total_score >= long_threshold] = 1      # LONG
        signals[total_score <= short_threshold] = -1    # SHORT
        
        return signals, sub_scores


# Example usage
if __name__ == "__main__":
    import pandas as pd
    
    # Generate sample data
    np.random.seed(42)
    n = 1000
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    volume = np.random.uniform(1000, 5000, n)
    bid_ask_spread = np.random.uniform(0.001, 0.01, n)
    
    # Score
    scorer = FixedScorer()
    signals, sub_scores = scorer.generate_signals(close, high, low, volume, bid_ask_spread)
    
    # Results
    print(f"✅ Generated {np.sum(signals == 1)} LONG signals")
    print(f"✅ Generated {np.sum(signals == -1)} SHORT signals")
    print(f"✅ Neutral: {np.sum(signals == 0)} bars")
    print(f"\nScore range: {sub_scores['momentum'].min():.1f} to {sub_scores['momentum'].max():.1f}")
