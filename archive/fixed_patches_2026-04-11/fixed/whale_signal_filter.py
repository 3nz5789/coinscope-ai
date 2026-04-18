"""
Whale Signal Filter for On-Chain Leading Indicators

Uses Whale Alert API to detect large exchange flows.
Blocks LONG when whales are selling (inflows), SHORT when buying (outflows).
"""

import requests
from datetime import datetime, timedelta


class WhaleSignalFilter:
    """On-chain whale signal detection"""
    
    THRESHOLD_USD = 10_000_000  # $10M+ only

    def __init__(self, api_key: str = ""):
        self.api_key  = api_key
        self.base_url = "https://api.whale-alert.io/v1"

    def get_bias(self, symbol: str = "bitcoin", lookback_mins: int = 240) -> dict:
        """
        Get whale flow bias
        
        Returns:
            {
                "bias": "BULLISH" | "BEARISH" | "NEUTRAL",
                "confidence": 0.0-1.0,
                "source": "whale_alert" | "no_key" | "api_error" | "no_data"
            }
        """
        if not self.api_key:
            return {"bias": "NEUTRAL", "confidence": 0.0, "source": "no_key"}

        since = int((datetime.utcnow() - timedelta(minutes=lookback_mins)).timestamp())
        
        try:
            r = requests.get(
                f"{self.base_url}/transactions",
                params={
                    "api_key": self.api_key,
                    "min_value": self.THRESHOLD_USD,
                    "since": since,
                    "currency": symbol[:3].lower()
                },
                timeout=8
            )
            txns = r.json().get("transactions", [])
        except Exception:
            return {"bias": "NEUTRAL", "confidence": 0.0, "source": "api_error"}

        # Calculate bull vs bear volume
        bull_vol, bear_vol = 0, 0
        
        for tx in txns:
            usd = tx.get("amount_usd", 0)
            to_type   = (tx.get("to", {}).get("owner_type") or "").lower()
            from_type = (tx.get("from", {}).get("owner_type") or "").lower()
            
            # Inflow to exchange = bearish (selling)
            if to_type == "exchange" and from_type != "exchange":
                bear_vol += usd
            # Outflow from exchange = bullish (buying)
            elif from_type == "exchange" and to_type != "exchange":
                bull_vol += usd

        total = bull_vol + bear_vol
        if total == 0:
            return {"bias": "NEUTRAL", "confidence": 0.0, "source": "no_data"}

        # Calculate net bias
        net = (bull_vol - bear_vol) / total
        bias = "BULLISH" if net > 0.2 else "BEARISH" if net < -0.2 else "NEUTRAL"
        
        return {
            "bias": bias,
            "confidence": round(abs(net), 3),
            "source": "whale_alert"
        }

    def should_block(self, direction: str, symbol: str) -> tuple:
        """
        Determine if trade should be blocked by whale signals
        
        Args:
            direction: "LONG" or "SHORT"
            symbol: "bitcoin", "ethereum", etc.
        
        Returns:
            (should_block, reason_string)
        """
        bias = self.get_bias(symbol)
        
        # Weak signal — don't block
        if bias["confidence"] < 0.3:
            return False, "Whale signal too weak"
        
        # Block LONG if whales are bearish
        if direction == "LONG" and bias["bias"] == "BEARISH":
            return True, f"Whale block LONG: {bias['confidence']:.0%} bearish flow"
        
        # Block SHORT if whales are bullish
        if direction == "SHORT" and bias["bias"] == "BULLISH":
            return True, f"Whale block SHORT: {bias['confidence']:.0%} bullish flow"
        
        return False, f"Whale aligned: {bias['bias']}"


# Example usage
if __name__ == "__main__":
    whale = WhaleSignalFilter(api_key="")
    
    # Check bias (will return neutral without API key)
    bias = whale.get_bias("bitcoin")
    print(f"Whale bias: {bias}")
    
    # Check if trade should be blocked
    blocked, reason = whale.should_block("LONG", "bitcoin")
    print(f"Blocked: {blocked}, Reason: {reason}")
