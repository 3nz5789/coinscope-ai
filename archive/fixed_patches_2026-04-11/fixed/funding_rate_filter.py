"""
Funding Rate Arbitrage Filter — Phase 9
Uses Binance perpetual funding rates as a contrarian filter.

High positive funding → market is overlong → fade LONG signals
High negative funding → market is overshort → fade SHORT signals

Extreme funding: |rate| > 0.05% per 8h = 54% annualized
This is free alpha from market structure.

BUG-9 FIX: All methods converted from async → synchronous to match
the synchronous ccxt.binance() exchange used internally.
Previously all methods were `async def` while calling blocking
`self.exchange.fetch_funding_rate()` — this would have blocked the
event loop. Now the API is fully synchronous and consistent.

Reference: https://www.talos.com/insights/understanding-market-impact-in-crypto-trading-the-talos-model-for-estimating-execution-costs
"""

import ccxt
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import numpy as np

logger = logging.getLogger(__name__)


class FundingRateFilter:
    """
    Uses Binance perpetual funding rates as a contrarian filter.

    Funding rates are paid every 8 hours between longs and shorts.
    When funding is extremely positive, longs are overcrowded.
    When funding is extremely negative, shorts are overcrowded.

    This creates exploitable imbalances.
    """

    # Funding rate thresholds (per 8-hour period)
    EXTREME_POSITIVE_FUNDING = 0.0005   # 0.05% = 54% annualized
    EXTREME_NEGATIVE_FUNDING = -0.0005

    # Moderate thresholds
    MODERATE_POSITIVE_FUNDING = 0.0002  # 0.02%
    MODERATE_NEGATIVE_FUNDING = -0.0002

    def __init__(self):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {"defaultType": "future"}
        })
        self.cache = {}
        self.cache_ttl = 300  # 5 minute cache

    def get_funding_rate(self, symbol: str) -> Optional[float]:
        """
        Get current funding rate for a perpetual pair.

        Args:
            symbol: "BTC/USDT", "ETH/USDT", etc.

        Returns:
            Current funding rate (e.g., 0.0001 = 0.01%)
        """
        cache_key = f"funding_{symbol}"
        cached = self.cache.get(cache_key)
        if cached and (datetime.utcnow() - cached['ts']).seconds < self.cache_ttl:
            return cached['rate']

        try:
            funding = self.exchange.fetch_funding_rate(symbol)
            rate = funding.get('fundingRate', 0)

            self.cache[cache_key] = {
                'rate': rate,
                'ts': datetime.utcnow()
            }

            logger.debug(f"📊 {symbol} funding rate: {rate:+.4%}")
            return rate

        except Exception as e:
            logger.error(f"❌ Failed to fetch funding rate for {symbol}: {e}")
            return None

    def get_funding_history(
        self,
        symbol: str,
        limit: int = 8  # Last 8 periods = 64 hours
    ) -> list:
        """
        Get historical funding rates.

        Args:
            symbol: "BTC/USDT", "ETH/USDT", etc.
            limit: Number of periods to fetch

        Returns:
            List of funding rate records
        """
        try:
            history = self.exchange.fetch_funding_rate_history(symbol, limit=limit)
            return history
        except Exception as e:
            logger.error(f"❌ Failed to fetch funding history for {symbol}: {e}")
            return []

    def get_funding_statistics(self, symbol: str) -> Dict:
        """
        Get funding rate statistics for a symbol.

        Returns:
            {
                'current': float,
                'mean_8h': float,
                'mean_24h': float,
                'max_8h': float,
                'min_8h': float,
                'std_dev': float,
            }
        """
        current = self.get_funding_rate(symbol)
        history = self.get_funding_history(symbol, limit=24)

        if not history:
            return {
                'current': current or 0,
                'mean_8h': 0,
                'mean_24h': 0,
                'max_8h': 0,
                'min_8h': 0,
                'std_dev': 0,
            }

        rates = [h.get('fundingRate', 0) for h in history]
        rates_8h = rates[-8:] if len(rates) >= 8 else rates

        return {
            'current': current or 0,
            'mean_8h': np.mean(rates_8h),
            'mean_24h': np.mean(rates),
            'max_8h': np.max(rates_8h),
            'min_8h': np.min(rates_8h),
            'std_dev': np.std(rates),
        }

    def should_fade_trade(
        self,
        direction: str,
        symbol: str
    ) -> Tuple[bool, str, float]:
        """
        Determine if trade should be faded based on funding rates.

        Args:
            direction: "BUY" or "SELL"
            symbol: "BTC/USDT", "ETH/USDT", etc.

        Returns:
            (should_fade, reason, funding_rate)
        """
        rate = self.get_funding_rate(symbol)
        if rate is None:
            return False, "Unable to fetch funding rate", 0

        # LONG signals faded when funding is extremely positive
        if direction == "BUY":
            if rate > self.EXTREME_POSITIVE_FUNDING:
                return True, (
                    f"Fade LONG: extreme positive funding "
                    f"({rate:+.4%} — longs overcrowded)"
                ), rate
            elif rate > self.MODERATE_POSITIVE_FUNDING:
                return False, (
                    f"Moderate positive funding ({rate:+.4%}) — "
                    f"proceed with caution, reduce size"
                ), rate

        # SHORT signals faded when funding is extremely negative
        elif direction == "SELL":
            if rate < self.EXTREME_NEGATIVE_FUNDING:
                return True, (
                    f"Fade SHORT: extreme negative funding "
                    f"({rate:+.4%} — shorts overcrowded)"
                ), rate
            elif rate < self.MODERATE_NEGATIVE_FUNDING:
                return False, (
                    f"Moderate negative funding ({rate:+.4%}) — "
                    f"proceed with caution, reduce size"
                ), rate

        return False, f"Funding rate normal ({rate:+.4%})", rate

    def get_position_size_multiplier(self, symbol: str) -> float:
        """
        Get position size multiplier based on funding rate extremeness.

        Returns:
            1.0 (normal) to 0.5 (extreme funding, reduce size)
        """
        stats = self.get_funding_statistics(symbol)
        rate = stats['current']

        if abs(rate) > self.EXTREME_POSITIVE_FUNDING:
            return 0.5
        elif abs(rate) > self.MODERATE_POSITIVE_FUNDING:
            return 0.75
        else:
            return 1.0

    def get_funding_sentiment(self, symbol: str) -> Dict:
        """
        Get overall funding rate sentiment.

        Returns:
            {
                'sentiment': 'EXTREME_LONG' | 'LONG' | 'NEUTRAL' | 'SHORT' | 'EXTREME_SHORT',
                'funding_rate': float,
                'annualized': float,
                'action': 'FADE_LONGS' | 'FADE_SHORTS' | 'NEUTRAL',
            }
        """
        rate = self.get_funding_rate(symbol)
        if rate is None:
            return {
                'sentiment': 'UNKNOWN',
                'funding_rate': 0,
                'annualized': 0,
                'action': 'NEUTRAL',
            }

        # Annualize (3 periods per day × 365 days)
        annualized = rate * 3 * 365

        if rate > self.EXTREME_POSITIVE_FUNDING:
            sentiment = 'EXTREME_LONG'
            action = 'FADE_LONGS'
        elif rate > self.MODERATE_POSITIVE_FUNDING:
            sentiment = 'LONG'
            action = 'NEUTRAL'
        elif rate < self.EXTREME_NEGATIVE_FUNDING:
            sentiment = 'EXTREME_SHORT'
            action = 'FADE_SHORTS'
        elif rate < self.MODERATE_NEGATIVE_FUNDING:
            sentiment = 'SHORT'
            action = 'NEUTRAL'
        else:
            sentiment = 'NEUTRAL'
            action = 'NEUTRAL'

        return {
            'sentiment': sentiment,
            'funding_rate': rate,
            'annualized': annualized,
            'action': action,
        }

    def get_market_structure(self, symbols: list) -> Dict:
        """
        Get overall market structure across multiple symbols.

        Returns:
            {
                'avg_funding': float,
                'extreme_long_count': int,
                'extreme_short_count': int,
                'overall_bias': 'LONG' | 'SHORT' | 'NEUTRAL',
            }
        """
        rates = []
        extreme_long = 0
        extreme_short = 0

        for symbol in symbols:
            rate = self.get_funding_rate(symbol)
            if rate is not None:
                rates.append(rate)

                if rate > self.EXTREME_POSITIVE_FUNDING:
                    extreme_long += 1
                elif rate < self.EXTREME_NEGATIVE_FUNDING:
                    extreme_short += 1

        if not rates:
            return {
                'avg_funding': 0,
                'extreme_long_count': 0,
                'extreme_short_count': 0,
                'overall_bias': 'UNKNOWN',
            }

        avg_funding = np.mean(rates)

        if avg_funding > self.MODERATE_POSITIVE_FUNDING:
            bias = 'LONG'
        elif avg_funding < self.MODERATE_NEGATIVE_FUNDING:
            bias = 'SHORT'
        else:
            bias = 'NEUTRAL'

        return {
            'avg_funding': avg_funding,
            'extreme_long_count': extreme_long,
            'extreme_short_count': extreme_short,
            'overall_bias': bias,
        }


# Example usage (now synchronous — no asyncio.run needed)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    frf = FundingRateFilter()

    rate = frf.get_funding_rate("BTC/USDT")
    print(f"BTC funding rate: {rate:+.4%}" if rate else "BTC funding rate: unavailable")

    stats = frf.get_funding_statistics("BTC/USDT")
    print(f"BTC funding stats: {stats}")

    should_fade, reason, rate = frf.should_fade_trade("BUY", "BTC/USDT")
    print(f"Fade BUY? {should_fade} ({reason})")

    sentiment = frf.get_funding_sentiment("BTC/USDT")
    print(f"BTC funding sentiment: {sentiment}")

    structure = frf.get_market_structure(["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    print(f"Market structure: {structure}")
