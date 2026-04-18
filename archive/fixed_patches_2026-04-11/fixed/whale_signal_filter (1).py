"""
Whale Signal Filter — Phase 9
Integrates Whale Alert API to detect large on-chain movements.
Exchange inflows  → BEARISH (whales preparing to sell)
Exchange outflows → BULLISH (whales accumulating)

This is a leading indicator that precedes price movement.
Reference: https://blog.amberdata.io/onchain-data-for-algorithmic-trading-strategy-development
"""

import aiohttp
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class WhaleDirection(Enum):
    """Whale signal direction"""
    BEARISH = "BEARISH"      # Exchange inflows (selling pressure)
    BULLISH = "BULLISH"      # Exchange outflows (accumulation)
    NEUTRAL = "NEUTRAL"      # No significant whale activity


@dataclass
class WhaleSignal:
    """Represents a whale transaction signal"""
    symbol: str
    direction: WhaleDirection
    confidence: float           # 0.0 - 1.0
    reason: str
    usd_volume: float
    timestamp: datetime
    transaction_hash: str
    from_address: str
    to_address: str


class WhaleSignalFilter:
    """
    Integrates Whale Alert API to detect large on-chain movements.
    
    Exchange inflows  → BEARISH (whales preparing to sell)
    Exchange outflows → BULLISH (whales accumulating / removing supply)
    
    API: https://whale-alert.io (free tier: 10 calls/min)
    """
    
    WHALE_THRESHOLD_USD = 10_000_000   # $10M+ transactions only
    
    EXCHANGE_WALLETS = {
        "binance", "coinbase", "kraken", "okx", "bybit", "huobi",
        "ftx", "kucoin", "bitfinex", "gemini", "bitstamp"
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.whale-alert.io/v1"
        self.cache = {}
        self.cache_ttl = 300  # 5 minute cache
    
    async def get_recent_signals(
        self,
        symbol: str = "bitcoin",
        lookback_mins: int = 60
    ) -> List[WhaleSignal]:
        """
        Get recent whale signals for a symbol.
        
        Args:
            symbol: "bitcoin", "ethereum", "solana"
            lookback_mins: How far back to look (default 60 min)
        
        Returns:
            List of WhaleSignal objects
        """
        
        if not self.api_key:
            logger.warning("⚠️  Whale Alert API key not configured")
            return []
        
        cache_key = f"{symbol}_{lookback_mins}"
        cached = self.cache.get(cache_key)
        if cached and (datetime.utcnow() - cached['ts']).seconds < self.cache_ttl:
            logger.debug(f"📊 Using cached whale signals for {symbol}")
            return cached['signals']
        
        since = int((datetime.utcnow() - timedelta(minutes=lookback_mins)).timestamp())
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/transactions",
                    params={
                        "api_key": self.api_key,
                        "min_value": self.WHALE_THRESHOLD_USD,
                        "since": since,
                        "currency": symbol.lower()[:3],  # btc, eth, sol
                    },
                    timeout=aiohttp.ClientTimeout(10)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"❌ Whale Alert API error: {resp.status}")
                        return []
                    
                    data = await resp.json()
                    txns = data.get("transactions", [])
        
        except Exception as e:
            logger.error(f"❌ Whale Alert fetch failed: {e}")
            return []
        
        signals = []
        for tx in txns:
            from_owner = (tx.get("from", {}).get("owner_type") or "").lower()
            to_owner = (tx.get("to", {}).get("owner_type") or "").lower()
            usd_val = tx.get("amount_usd", 0)
            
            # Large transfer TO exchange = selling pressure
            if to_owner == "exchange" and from_owner != "exchange":
                conf = min(usd_val / 100_000_000, 1.0)  # Scale with size
                signals.append(WhaleSignal(
                    symbol=symbol.upper(),
                    direction=WhaleDirection.BEARISH,
                    confidence=conf,
                    reason=f"${usd_val/1e6:.0f}M moved TO {tx.get('to',{}).get('owner','exchange')}",
                    usd_volume=usd_val,
                    timestamp=datetime.utcfromtimestamp(tx['timestamp']),
                    transaction_hash=tx.get('hash', ''),
                    from_address=tx.get('from', {}).get('address', ''),
                    to_address=tx.get('to', {}).get('address', '')
                ))
            
            # Large transfer FROM exchange = accumulation
            elif from_owner == "exchange" and to_owner != "exchange":
                conf = min(usd_val / 100_000_000, 1.0)
                signals.append(WhaleSignal(
                    symbol=symbol.upper(),
                    direction=WhaleDirection.BULLISH,
                    confidence=conf,
                    reason=f"${usd_val/1e6:.0f}M moved OFF {tx.get('from',{}).get('owner','exchange')}",
                    usd_volume=usd_val,
                    timestamp=datetime.utcfromtimestamp(tx['timestamp']),
                    transaction_hash=tx.get('hash', ''),
                    from_address=tx.get('from', {}).get('address', ''),
                    to_address=tx.get('to', {}).get('address', '')
                ))
        
        # Cache results
        self.cache[cache_key] = {
            'signals': signals,
            'ts': datetime.utcnow()
        }
        
        logger.info(f"📊 Found {len(signals)} whale signals for {symbol}")
        return signals
    
    async def get_aggregate_bias(self, symbol: str) -> dict:
        """
        Returns net whale bias for a symbol over last 4 hours.
        
        Returns:
            {
                'bias': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
                'confidence': 0.0 - 1.0,
                'signal_count': int,
                'bearish_vol': float,
                'bullish_vol': float,
                'net_ratio': float (-1.0 to +1.0)
            }
        """
        
        signals = await self.get_recent_signals(symbol, lookback_mins=240)
        
        if not signals:
            return {
                "bias": WhaleDirection.NEUTRAL.value,
                "confidence": 0,
                "signal_count": 0,
                "bearish_vol": 0,
                "bullish_vol": 0,
                "net_ratio": 0
            }
        
        bearish_vol = sum(
            s.usd_volume for s in signals
            if s.direction == WhaleDirection.BEARISH
        )
        bullish_vol = sum(
            s.usd_volume for s in signals
            if s.direction == WhaleDirection.BULLISH
        )
        total_vol = bearish_vol + bullish_vol
        
        if total_vol == 0:
            return {
                "bias": WhaleDirection.NEUTRAL.value,
                "confidence": 0,
                "signal_count": 0,
                "bearish_vol": 0,
                "bullish_vol": 0,
                "net_ratio": 0
            }
        
        net = (bullish_vol - bearish_vol) / total_vol  # -1.0 to +1.0
        
        if net > 0.2:
            bias = WhaleDirection.BULLISH.value
        elif net < -0.2:
            bias = WhaleDirection.BEARISH.value
        else:
            bias = WhaleDirection.NEUTRAL.value
        
        return {
            "bias": bias,
            "confidence": abs(net),
            "signal_count": len(signals),
            "bearish_vol": bearish_vol,
            "bullish_vol": bullish_vol,
            "net_ratio": net
        }
    
    async def should_block_trade(
        self,
        direction: str,
        symbol: str
    ) -> Tuple[bool, str]:
        """
        Block trade if whale flow strongly opposes signal direction.
        
        Args:
            direction: "BUY" or "SELL"
            symbol: "BTC", "ETH", "SOL"
        
        Returns:
            (should_block, reason)
        """
        
        bias = await self.get_aggregate_bias(symbol)
        
        if bias["confidence"] < 0.3:
            return False, "Whale signal too weak to block"
        
        if direction == "BUY" and bias["bias"] == WhaleDirection.BEARISH.value:
            return True, (
                f"Blocked BUY: whale exchange inflows "
                f"({bias['confidence']:.0%} confidence, "
                f"${bias['bearish_vol']/1e6:.0f}M inflow)"
            )
        
        if direction == "SELL" and bias["bias"] == WhaleDirection.BULLISH.value:
            return True, (
                f"Blocked SELL: whale exchange outflows "
                f"({bias['confidence']:.0%} confidence, "
                f"${bias['bullish_vol']/1e6:.0f}M outflow)"
            )
        
        return False, "Whale signal aligned with trade"
    
    async def get_whale_strength(self, symbol: str) -> float:
        """
        Get overall whale signal strength (-1.0 to +1.0).
        Useful for adjusting position size.
        
        Returns:
            -1.0 (strong bearish) to +1.0 (strong bullish)
        """
        bias = await self.get_aggregate_bias(symbol)
        net = bias['net_ratio']
        
        # Scale confidence into the signal
        if net > 0:
            return net * bias['confidence']
        else:
            return net * bias['confidence']


# Example usage
async def example():
    filter = WhaleSignalFilter(api_key="your_api_key_here")
    
    # Get recent signals
    signals = await filter.get_recent_signals("bitcoin", lookback_mins=60)
    print(f"Recent whale signals: {signals}")
    
    # Get aggregate bias
    bias = await filter.get_aggregate_bias("bitcoin")
    print(f"BTC whale bias: {bias}")
    
    # Check if trade should be blocked
    should_block, reason = await filter.should_block_trade("BUY", "BTC")
    print(f"Block BUY? {should_block} ({reason})")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example())
