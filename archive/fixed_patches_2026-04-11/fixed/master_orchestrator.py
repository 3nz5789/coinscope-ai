"""
Master Orchestrator - Main Trading Loop

Coordinates:
1. HMM regime detection
2. Signal generation
3. Multi-timeframe filtering
4. Sentiment & whale blocking
5. Kelly position sizing
6. Order execution
"""

import os
import sys
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# Adjust sys.path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scoring_fixed import FixedScorer
from core.risk_gate import RiskGate
from core.multi_timeframe_filter import MultiTimeframeFilter
from intelligence.hmm_regime_detector import EnsembleRegimeDetector
from intelligence.kelly_position_sizer import KellyRiskController
from intelligence.finbert_sentiment_filter import MockSentimentFilter
from intelligence.whale_signal_filter import WhaleSignalFilter

# Binance Futures requires BTCUSDT format — no slash separator
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "TAOUSDT"]

# REST base URLs — klines are public, no auth required
_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"
_FUTURES_MAINNET_URL = "https://fapi.binance.com"
TIMEFRAME = "4h"
ACCOUNT_SIZE = 10_000


class CoinScopeOrchestrator:
    """Main trading orchestrator"""

    def __init__(self, testnet: bool = True, pairs: list = None):
        # Use the Binance Futures REST API directly via requests (public klines endpoint).
        # testnet=True → testnet.binancefuture.com
        # testnet=False → fapi.binance.com (live)
        self._base_url = _FUTURES_TESTNET_URL if testnet else _FUTURES_MAINNET_URL
        self.regime = EnsembleRegimeDetector()
        self.kelly = KellyRiskController(fraction=0.25)
        self.sentiment = MockSentimentFilter()
        self.whale = WhaleSignalFilter(api_key=os.getenv("WHALE_ALERT_KEY", ""))
        self.scorer = FixedScorer()
        self.risk_gate = RiskGate()
        self.mtf_filter = MultiTimeframeFilter()
        self.testnet = testnet
        self.pairs = pairs or PAIRS  # BUG-3 FIX: use instance attribute, not module constant
        self.regime_fitted = {}
        self.last_regime = {}

    def fetch_bars(self, symbol: str, timeframe: str = "4h", limit: int = 300) -> pd.DataFrame:
        """
        Fetch OHLCV bars from Binance Futures REST API.

        symbol must be BTCUSDT format (no slash separator).
        Klines are a public endpoint — no API key required.
        """
        try:
            resp = requests.get(
                f"{self._base_url}/fapi/v1/klines",
                params={"symbol": symbol, "interval": timeframe, "limit": limit},
                timeout=10,
            )
            resp.raise_for_status()
            raw = resp.json()
            # Kline format: [open_time, open, high, low, close, volume, ...]
            df = pd.DataFrame(raw, columns=[
                "ts", "open", "high", "low", "close", "vol",
                "close_time", "quote_vol", "trades",
                "taker_buy_base", "taker_buy_quote", "ignore",
            ])
            df = df[["ts", "open", "high", "low", "close", "vol"]].copy()
            df[["open", "high", "low", "close", "vol"]] = df[
                ["open", "high", "low", "close", "vol"]
            ].astype(float)
            df.index = pd.to_datetime(df["ts"], unit="ms")
            return df
        except Exception as e:
            print(f"  [!] Fetch error {symbol}: {e}")
            return pd.DataFrame()

    def get_regime(self, symbol: str, df: pd.DataFrame) -> dict:
        """Detect market regime using HMM"""
        returns = df["close"].pct_change().dropna().values
        vol = pd.Series(returns).rolling(20).std().dropna().values
        
        if len(returns) < 50:
            return {"regime": "chop", "confidence": 0.5}

        min_len = min(len(returns), len(vol))
        r, v = returns[-min_len:], vol

        # Fit once per symbol per session
        if symbol not in self.regime_fitted:
            print(f"  [*] Fitting HMM for {symbol}...")
            self.regime.fit(r, v)
            self.regime_fitted[symbol] = True

        return self.regime.predict_regime(r[-50:], v[-50:])

    def scan_pair(self, symbol: str) -> dict:
        """Scan single pair for trading signals"""
        print(f"\n[SCAN] {symbol}")
        df_4h = self.fetch_bars(symbol, "4h", 300)
        
        if df_4h.empty or len(df_4h) < 100:
            return {"symbol": symbol, "signal": "NO_DATA"}

        # 1 — Regime
        reg = self.get_regime(symbol, df_4h)
        regime, confidence = reg["regime"], reg["confidence"]
        print(f"  Regime: {regime.upper()} ({confidence:.0%})")

        if confidence < 0.5:
            return {"symbol": symbol, "signal": "LOW_CONFIDENCE", "regime": regime}

        # 2 — Signal from scorer
        c = df_4h["close"].values
        h = df_4h["high"].values
        lo = df_4h["low"].values
        v = df_4h["vol"].values
        # BUG-11 FIX: use absolute USD spread (high - low), not a scaled ratio
        spread = h - lo

        signals, sub_scores = self.scorer.generate_signals(c, h, lo, v, spread)
        latest_signal = signals[-1]
        direction = "LONG" if latest_signal == 1 else "SHORT" if latest_signal == -1 else "NEUTRAL"
        print(f"  Signal: {direction}")

        # BUG-10 FIX: apply multi-timeframe filter
        if direction in ("LONG", "SHORT"):
            trend_4h = self.mtf_filter.get_4h_trend(c)
            mtf_signal = 1 if direction == "LONG" else -1
            filtered, mtf_reason = self.mtf_filter.filter_signal(mtf_signal, trend_4h)
            if filtered == 0:
                print(f"  BLOCKED by MTF: {mtf_reason}")
                return {"symbol": symbol, "signal": "BLOCKED_MTF", "regime": regime}
            print(f"  MTF: {mtf_reason}")

        # BUG-10 FIX: check risk gate circuit breakers
        cb_active, cb_reason = self.risk_gate.check_circuit_breakers()
        if cb_active:
            print(f"  BLOCKED by risk gate: {cb_reason}")
            return {"symbol": symbol, "signal": "BLOCKED_RISKGATE", "regime": regime}

        if direction == "NEUTRAL":
            return {"symbol": symbol, "signal": "NEUTRAL", "regime": regime}

        # 3 — Sentiment block
        blocked, reason = self.sentiment.should_block(direction, [])
        if blocked:
            print(f"  BLOCKED by sentiment: {reason}")
            return {"symbol": symbol, "signal": "BLOCKED_SENTIMENT", "regime": regime}

        # 4 — Whale block
        # Symbols are BTCUSDT format — strip the USDT suffix to get base asset
        sym_base = symbol.replace("USDT", "").lower()
        whale_blocked, whale_reason = self.whale.should_block(direction, sym_base)
        if whale_blocked:
            print(f"  BLOCKED by whale: {whale_reason}")
            return {"symbol": symbol, "signal": "BLOCKED_WHALE", "regime": regime}

        # 5 — Kelly size
        kelly_size = self.kelly.calculate_position_size(
            win_rate=0.44,
            avg_win=0.018,
            avg_loss=0.012,
            regime=regime,
            account_balance=ACCOUNT_SIZE
        )

        result = {
            "symbol": symbol,
            "signal": direction,
            "regime": regime,
            "confidence": confidence,
            "price": float(df_4h["close"].iloc[-1]),
            "kelly_usd": kelly_size,
            "timestamp": datetime.utcnow().isoformat(),
        }
        print(f"  ✅ SIGNAL: {direction} | Kelly: ${kelly_size:.2f} | Regime: {regime}")
        return result

    def run_scan(self) -> list:
        """Run full market scan"""
        print(f"\n{'='*55}")
        print(f" CoinScopeAI Full Scan | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'='*55}")
        
        results = []
        for pair in self.pairs:  # BUG-3 FIX: use instance attribute
            result = self.scan_pair(pair)
            results.append(result)
            time.sleep(0.5)  # rate limit
        
        self._print_summary(results)
        return results

    def _print_summary(self, results: list):
        """Print scan summary"""
        print(f"\n{'─'*55}")
        print(f" SCAN SUMMARY")
        print(f"{'─'*55}")
        
        active = [r for r in results if r.get("signal") in ("LONG", "SHORT")]
        for r in active:
            print(f" ✅ {r['symbol']:12s} {r['signal']:6s} | "
                  f"Regime: {r['regime']:4s} | "
                  f"Kelly: ${r.get('kelly_usd', 0):.2f} | "
                  f"Price: ${r.get('price', 0):.4f}")
        
        if not active:
            print(" No active signals — market in consolidation")
        
        blocked = [r for r in results if "BLOCKED" in r.get("signal", "")]
        if blocked:
            print(f"\n Blocked signals: {len(blocked)}")
        
        print(f"{'─'*55}\n")

    def run_loop(self, interval_seconds: int = 14400):
        """Main 4-hour polling loop"""
        print("CoinScopeAI Engine started. Press Ctrl+C to stop.")
        while True:
            try:
                self.run_scan()
                print(f"Next scan in {interval_seconds//3600}h...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("\nEngine stopped.")
                break
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(60)


if __name__ == "__main__":
    orch = CoinScopeOrchestrator(testnet=True)
    orch.run_scan()  # single scan, or use run_loop() for continuous
