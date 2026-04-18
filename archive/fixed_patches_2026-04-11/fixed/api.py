"""
FastAPI Bridge - Connect Python Trading Engine to React Frontend

Run: uvicorn api:app --reload --port 8001

Exposes REST endpoints for:
- Live market scans
- Performance metrics
- Trade journal
- Regime detection
- Scaling status
- Walk-forward validation
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from storage.trade_journal import TradeJournal
from alerts.scale_up_manager import ScaleUpManager

app = FastAPI(title="CoinScopeAI Engine API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

journal = TradeJournal()
scaler = ScaleUpManager()


# ── Health ────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": time.time(), "version": "1.0.0"}


# ── Market Scan ───────────────────────────────────────────────────
@app.get("/scan")
async def scan(
    pairs: str = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,TAO/USDT"
):
    """Trigger live market scan. Returns signals for all requested pairs."""
    try:
        from live.master_orchestrator import CoinScopeOrchestrator

        pair_list = [p.strip() for p in pairs.split(",")]
        # BUG-3 FIX: pass pairs via constructor so run_scan() uses self.pairs
        orch = CoinScopeOrchestrator(pairs=pair_list)
        results = orch.run_scan()
        active = [r for r in results if r.get("signal") in ("LONG", "SHORT")]
        return {
            "signals": results,
            "active_count": len(active),
            "total_scanned": len(results),
            "timestamp": time.time(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Performance ───────────────────────────────────────────────────
@app.get("/performance")
async def performance():
    """Full performance stats from trade journal."""
    stats = journal.performance_stats()
    scale = scaler.status()
    return {**stats, "scale_profile": scale}


@app.get("/performance/daily")
async def daily_summary():
    """Today's P&L summary."""
    return journal.daily_summary()


# ── Trade Journal ─────────────────────────────────────────────────
@app.get("/journal")
async def get_journal(days: int = 7):
    """Get recent trades from journal."""
    trades = journal.get_recent_trades(days=days)
    return {"trades": trades, "count": len(trades), "days": days}


# ── Regime ────────────────────────────────────────────────────────
@app.get("/regime/{symbol}")
async def get_regime(symbol: str):
    """Get current regime for a symbol."""
    try:
        import ccxt
        import pandas as pd
        import numpy as np

        from intelligence.hmm_regime_detector import EnsembleRegimeDetector

        exchange = ccxt.binance({"enableRateLimit": True})
        sym = symbol.upper().replace("-", "/")
        ohlcv = exchange.fetch_ohlcv(sym, "4h", limit=200)
        df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
        returns = df["close"].pct_change().dropna().values
        vol = pd.Series(returns).rolling(20).std().dropna().values
        det = EnsembleRegimeDetector()
        min_len = min(len(returns), len(vol))
        det.fit(returns[-min_len:], vol)
        result = det.predict_regime(returns[-min_len:][-50:], vol[-50:])
        return {
            "symbol": sym,
            "regime": result["regime"],
            "confidence": result["confidence"],
            "price": float(df["close"].iloc[-1]),
            "timestamp": time.time(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Scale Profile ─────────────────────────────────────────────────
@app.get("/scale")
async def scale_status():
    """Get current scaling profile status."""
    return scaler.status()


@app.post("/scale/check")
async def check_promotion(trades: int, sharpe: float):
    """Check if current stats qualify for scale-up."""
    promoted = scaler.check_promotion(trades, sharpe)
    return {
        "promoted": promoted is not None,
        "new_profile": promoted.name if promoted else None,
        "current": scaler.status(),
    }


# ── Validation ────────────────────────────────────────────────────
@app.get("/validate")
async def run_validation(symbol: str = "BTC/USDT", limit: int = 1000):
    """Run walk-forward validation and return results."""
    try:
        import pandas as pd

        from validation.walk_forward_validation import (
            WalkForwardValidator,
            fetch_data,
        )

        df = fetch_data(symbol, "4h", limit)
        validator = WalkForwardValidator(df)
        passed = validator.run_all()
        return {
            "passed": passed,
            "results": validator.results,
            "symbol": symbol,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
