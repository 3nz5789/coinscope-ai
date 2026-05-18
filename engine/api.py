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

import logging
import time
from datetime import timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from engine.core.scale_up_manager import ScaleUpManager
from engine.integrations.trade_journal import TradeJournal
from risk_management.regime_predictor import HMMRegimePredictor

logger = logging.getLogger(__name__)

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
regime_predictor = HMMRegimePredictor()

# Mapping legacy 3-state ensemble labels onto the 4-state v1 taxonomy.
# Used only by the hmm_fallback path; the primary path uses the trained
# regime_map persisted in the pickle.
_FALLBACK_LABEL_MAP = {"bull": "Trending", "bear": "Volatile", "chop": "Mean-Reverting"}
_V1_STATE_LABELS = ["Trending", "Mean-Reverting", "Volatile", "Quiet"]


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
        from engine.core.master_orchestrator import CoinScopeOrchestrator

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
def _normalise_symbols(symbol: str) -> tuple[str, str]:
    """Return (registry_symbol, ccxt_symbol). e.g. 'btc-usdt' → ('BTCUSDT','BTC/USDT')."""
    raw = symbol.upper().replace("-", "").replace("/", "")
    if raw.endswith("USDT") and len(raw) > 4:
        base, quote = raw[:-4], "USDT"
    elif raw.endswith("USD") and len(raw) > 3:
        base, quote = raw[:-3], "USD"
    else:
        base, quote = raw, ""
    return (raw, f"{base}/{quote}" if quote else raw)


def _hmm_fallback(symbol: str, registry_symbol: str) -> dict:
    """Named fallback used when model_registry has no active row or the pickle is missing.

    Runs the legacy 3-state ensemble (fit on demand against 4h bars), maps its
    label onto the v1 4-state taxonomy, and synthesises a soft 4-element
    state_probs so the response contract stays uniform.
    """
    import ccxt
    import pandas as pd

    from risk_management.hmm_regime_detector import EnsembleRegimeDetector

    exchange = ccxt.binance({"enableRateLimit": True})
    ohlcv = exchange.fetch_ohlcv(symbol, "4h", limit=200)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
    returns = df["close"].pct_change().dropna().values
    vol = pd.Series(returns).rolling(20).std().dropna().values
    det = EnsembleRegimeDetector()
    min_len = min(len(returns), len(vol))
    det.fit(returns[-min_len:], vol)
    result = det.predict_regime(returns[-min_len:][-50:], vol[-50:])

    legacy_label = result["regime"]
    raw_confidence = float(result["confidence"])
    # Clamp the fallback confidence to [0.40, 0.85] for two reasons:
    #  - 0.85 ceiling: guarantees the residual 0.15 splits across the other
    #    three buckets at >0 each, so we never emit the [0, 0, 1, 0] anti-pattern.
    #  - 0.40 floor: legacy ensemble's "confidence" is a heuristic blend; values
    #    below 0.40 are noise, and pegging the peak below 0.40 would invert
    #    argmax. 0.40 lets the mapped label remain dominant by construction.
    confidence = max(0.40, min(0.85, raw_confidence))
    mapped = _FALLBACK_LABEL_MAP.get(legacy_label, "Mean-Reverting")
    others = (1.0 - confidence) / 3.0
    probs = [confidence if lab == mapped else others for lab in _V1_STATE_LABELS]

    return {
        "symbol": registry_symbol,
        "label": mapped,
        "confidence": round(confidence, 4),
        "state_probs": [round(p, 4) for p in probs],
        "state_labels": _V1_STATE_LABELS,
        "source": "hmm_fallback",
        "legacy_label": legacy_label,
        "price": float(df["close"].iloc[-1]),
        "timestamp": time.time(),
    }


@app.get("/regime/{symbol}")
async def get_regime(symbol: str):
    """Get current regime for a symbol.

    Path 1 (primary): load active HMM v1 model from `model_registry`, predict
    state distribution from 1h bars, return label + 4-element state_probs.

    Path 2 (fallback): legacy 3-state on-the-fly ensemble, mapped to the v1
    4-state taxonomy. Triggered when no active registry row exists for the
    symbol, the pickle is missing, or feature computation fails.
    """
    registry_symbol, ccxt_symbol = _normalise_symbols(symbol)

    try:
        import ccxt
        import pandas as pd

        # Try the persisted model first. Even instantiating the predictor is
        # cheap — the DB query happens inside .predict().
        exchange = ccxt.binance({"enableRateLimit": True})
        raw = exchange.fetch_ohlcv(ccxt_symbol, "1h", limit=500)
        df = pd.DataFrame(
            raw,
            columns=["ts", "open", "high", "low", "close", "volume"],
        )
        df["open_time"] = pd.to_datetime(df["ts"], unit="ms", utc=True)

        prediction = regime_predictor.predict(registry_symbol, df)
        if prediction is not None:
            return {
                "symbol": prediction.symbol,
                "label": prediction.label,
                "confidence": round(prediction.confidence, 6),
                "state_probs": [round(p, 6) for p in prediction.state_probs],
                "state_labels": prediction.state_labels,
                "source": "hmm_regime_v1",
                "model_version": prediction.model_version,
                "trained_at": prediction.trained_at.astimezone(timezone.utc).isoformat(),
                "val_accuracy": prediction.val_accuracy,
                "price": float(df["close"].iloc[-1]),
                "timestamp": time.time(),
            }

        logger.warning(
            "regime %s: no active model_registry row or pickle missing; using hmm_fallback",
            registry_symbol,
        )
        return _hmm_fallback(ccxt_symbol, registry_symbol)
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
