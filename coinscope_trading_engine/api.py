"""
api.py — CoinScopeAI FastAPI HTTP Layer
========================================
Provides a REST API for monitoring and controlling the running engine.

Start alongside the engine (two terminals):
    python main.py              # starts engine
    uvicorn api:app --port 8001 # starts API server

Or combined via Docker Compose.

Endpoints
---------
  GET  /health                   — liveness probe
  GET  /status                   — full engine status snapshot
  GET  /signals                  — most recent scored signals (cached)
  GET  /positions                — open positions + PnL
  GET  /exposure                 — portfolio exposure metrics
  GET  /regime                   — current market regime per symbol
  GET  /sentiment                — latest sentiment score
  POST /scan                     — trigger an immediate scan cycle
  POST /circuit-breaker/reset    — manually reset a tripped breaker
  POST /circuit-breaker/trip     — manually halt trading
  GET  /rate-limiter/stats       — token bucket stats
  GET  /config                   — safe (non-secret) config values
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from data.binance_rest import BinanceRESTClient
from data.data_normalizer import DataNormalizer
from scanner.volume_scanner import VolumeScanner
from scanner.pattern_scanner import PatternScanner
from scanner.funding_rate_scanner import FundingRateScanner
from scanner.orderbook_scanner import OrderBookScanner
from scanner.liquidation_scanner import LiquidationScanner
from signals.confluence_scorer import ConfluenceScorer, Signal
from signals.entry_exit_calculator import EntryExitCalculator
from signals.indicator_engine import IndicatorEngine
from risk.circuit_breaker import CircuitBreaker, BreakerState
from risk.exposure_tracker import ExposureTracker
from risk.position_sizer import PositionSizer
from risk.correlation_analyzer import CorrelationAnalyzer
from models.sentiment_analyzer import SentimentAnalyzer, SentimentScore
from models.regime_detector import RegimeDetector, MarketRegime
try:
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from ml.regime_classifier_v3 import RegimeClassifierV3 as _RCV3
    _MODEL_PATH = _os.path.join(_os.path.dirname(__file__), "..", "ml", "models", "regime_classifier_v3.pkl")
    _regime_v3 = _RCV3.load(_MODEL_PATH) if _os.path.exists(_MODEL_PATH) else None
except Exception as _e:
    _regime_v3 = None
from models.anomaly_detector import AnomalyDetector
from storage.trade_journal import TradeJournal
from alerts.scale_up_manager import ScaleUpManager
from utils.logger import get_logger

from billing.stripe_gateway import router as billing_router

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title       = "CoinScopeAI Engine API",
    description = "REST control and monitoring layer for the CoinScopeAI futures scanner.",
    version     = "2.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["http://localhost:5173", "http://localhost:3000", "*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# ---------------------------------------------------------------------------
# Shared singletons (lightweight — no persistent state between requests)
# ---------------------------------------------------------------------------

_rest         = BinanceRESTClient(
    api_key    = settings.active_api_key.get_secret_value(),
    api_secret = settings.active_api_secret.get_secret_value(),
    testnet    = settings.testnet_mode,
)
_norm         = DataNormalizer()
_indicator    = IndicatorEngine()
_scorer       = ConfluenceScorer(min_score=settings.min_confluence_score)
_calc         = EntryExitCalculator()
_sizer        = PositionSizer()
_sentiment    = SentimentAnalyzer()
_regime       = RegimeDetector()
_anomaly      = AnomalyDetector()
_correlation  = CorrelationAnalyzer()
_exposure     = ExposureTracker(balance=10_000.0)
_circuit      = CircuitBreaker()
_journal      = TradeJournal()
_scaler       = ScaleUpManager()
_scanners     = [
    VolumeScanner(rest_client=_rest, cache=None),
    PatternScanner(),
    FundingRateScanner(rest_client=_rest, cache=None),
    OrderBookScanner(),
    LiquidationScanner(),
]

# In-memory signal cache: {symbol: dict}
_signal_cache:   dict[str, dict] = {}
_last_scan_ts:   float = 0.0


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CircuitBreakerTripRequest(BaseModel):
    reason: str = "Manual halt via API"


class ScanRequest(BaseModel):
    pairs:      Optional[list[str]] = None   # defaults to settings.scan_pairs
    timeframe:  str = "1h"
    limit:      int = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _scan_symbol(symbol: str, timeframe: str, limit: int) -> Optional[dict]:
    """
    Fetch candles, run all scanners, score, and return a signal dict or None.
    """
    try:
        raw     = await _rest.get_klines(symbol, timeframe, limit=limit)
        candles = _norm.klines_to_candles(symbol, timeframe, raw)
        if len(candles) < 30:
            return None

        results = []
        for scanner in _scanners:
            try:
                r = await scanner.scan(symbol)
                results.append(r)
            except Exception:
                pass

        signal = _scorer.score(symbol, results, candles)
        if not signal:
            return None

        setup     = _calc.calculate(signal, candles)
        anomaly   = _anomaly.check(candles)
        regime    = _regime.detect(candles)
        indicators = _indicator.compute(candles)

        return {
            "symbol":      symbol,
            "direction":   signal.direction.value,
            "score":       round(signal.score, 2),
            "strength":    signal.strength,
            "scanners":    signal.scanner_names,
            "reasons":     signal.reasons[:5],
            "actionable":  signal.is_actionable,
            "setup": {
                "entry":      round(setup.entry, 8)    if setup.valid else None,
                "stop_loss":  round(setup.stop_loss, 8) if setup.valid else None,
                "tp1":        round(setup.tp1, 8)       if setup.valid else None,
                "tp2":        round(setup.tp2, 8)       if setup.valid else None,
                "tp3":        round(setup.tp3, 8)       if setup.valid else None,
                "rr_ratio":   round(setup.rr_ratio_tp2, 3) if setup.valid else None,
                "valid":      setup.valid,
                "reason":     setup.invalid_reason if not setup.valid else None,
            },
            "regime":  regime.regime.value,
            "anomaly": {
                "detected": anomaly.is_anomaly,
                "severity": anomaly.severity,
                "types":    anomaly.anomaly_types,
            },
            "indicators": {
                "rsi":        round(indicators.rsi, 2)  if indicators.rsi else None,
                "adx":        round(indicators.adx, 2)  if indicators.adx else None,
                "trend":      indicators.trend_direction,
                "momentum":   indicators.momentum_bias,
                "volatility": indicators.volatility_state,
            },
            "scanned_at": time.time(),
        }
    except Exception as exc:
        logger.warning("API scan error for %s: %s", symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------
app.include_router(billing_router)

@app.get("/health", tags=["System"])
async def health():
    """Liveness probe."""
    return {
        "status":    "ok",
        "version":   "2.0.0",
        "testnet":   settings.testnet_mode,
        "timestamp": time.time(),
    }


@app.get("/config", tags=["System"])
async def get_config():
    """Return safe (non-secret) configuration values."""
    return {
        "testnet_mode":           settings.testnet_mode,
        "environment":            settings.environment.value,
        "scan_pairs":             settings.scan_pairs,
        "scan_interval_s":        settings.scan_interval_seconds,
        "min_confluence_score":   settings.min_confluence_score,
        "risk_per_trade_pct":     settings.risk_per_trade_pct,
        "max_leverage":           settings.max_leverage,
        "max_open_positions":     settings.max_open_positions,
        "max_position_size_pct":  settings.max_position_size_pct,
        "max_total_exposure_pct": settings.max_total_exposure_pct,
        "max_daily_loss_pct":     settings.max_daily_loss_pct,
    }


# ── Signals ──────────────────────────────────────────────────────────────────

@app.get("/signals", tags=["Signals"])
async def get_signals():
    """Return the most recently cached signals from the last scan."""
    return {
        "signals":      list(_signal_cache.values()),
        "count":        len(_signal_cache),
        "actionable":   sum(1 for s in _signal_cache.values() if s.get("actionable")),
        "last_scan_at": _last_scan_ts,
        "age_s":        round(time.time() - _last_scan_ts, 1) if _last_scan_ts else None,
    }


@app.post("/scan", tags=["Signals"])
async def run_scan(body: ScanRequest, background_tasks: BackgroundTasks):
    """
    Trigger an immediate scan of the requested pairs.

    Results are returned directly and also cached for GET /signals.
    """
    global _last_scan_ts

    pairs     = body.pairs or settings.scan_pairs
    timeframe = body.timeframe
    limit     = min(max(body.limit, 30), 500)

    tasks = [_scan_symbol(sym, timeframe, limit) for sym in pairs]
    raw   = await asyncio.gather(*tasks, return_exceptions=True)

    results = []
    for sym, result in zip(pairs, raw):
        if isinstance(result, dict):
            _signal_cache[sym] = result
            results.append(result)

    _last_scan_ts = time.time()
    actionable    = [r for r in results if r.get("actionable")]

    return {
        "scanned":     len(results),
        "actionable":  len(actionable),
        "signals":     results,
        "timestamp":   _last_scan_ts,
    }


# ── Positions & Exposure ──────────────────────────────────────────────────────

@app.get("/positions", tags=["Risk"])
async def get_positions():
    """Return all open positions with unrealised PnL."""
    snap = _exposure.snapshot()
    return snap


@app.get("/exposure", tags=["Risk"])
async def get_exposure():
    """Portfolio exposure summary."""
    return {
        "balance":              round(_exposure._balance, 2),
        "position_count":       _exposure.position_count,
        "total_notional":       round(_exposure.total_notional, 2),
        "total_exposure_pct":   round(_exposure.total_exposure_pct, 2),
        "unrealised_pnl":       round(_exposure.unrealised_pnl, 2),
        "realised_pnl":         round(_exposure.realised_pnl, 2),
        "daily_pnl":            round(_exposure.daily_pnl, 2),
        "daily_loss_pct":       round(_exposure.daily_loss_pct, 4),
        "is_over_exposed":      _exposure.is_over_exposed,
        "max_total_exposure_pct": settings.max_total_exposure_pct,
    }


# ── Circuit Breaker ───────────────────────────────────────────────────────────

@app.get("/circuit-breaker", tags=["Risk"])
async def get_circuit_breaker():
    """Current circuit breaker state."""
    return {
        **_circuit.status(),
        "timestamp": time.time(),
    }


@app.post("/circuit-breaker/reset", tags=["Risk"])
async def reset_circuit_breaker():
    """Manually reset a tripped circuit breaker."""
    if _circuit.state == BreakerState.CLOSED:
        return {"message": "Circuit breaker is already closed.", "state": "CLOSED"}
    _circuit.reset()
    return {"message": "Circuit breaker reset.", "state": _circuit.state.value}


@app.post("/circuit-breaker/trip", tags=["Risk"])
async def trip_circuit_breaker(body: CircuitBreakerTripRequest):
    """Manually halt trading by tripping the circuit breaker."""
    _circuit.trip(body.reason)
    return {
        "message": "Circuit breaker tripped.",
        "reason":  body.reason,
        "state":   _circuit.state.value,
    }


# ── Market Intelligence ───────────────────────────────────────────────────────

@app.get("/regime", tags=["Intelligence"])
async def get_regime(
    symbol:    str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1h"),
    limit:     int = Query(default=150, ge=60, le=500),
):
    """Detect the current market regime for a symbol (v3 ML + HMM fallback)."""
    try:
        raw     = await _rest.get_klines(symbol, timeframe, limit=limit)
        candles = _norm.klines_to_candles(symbol, timeframe, raw)

        # ── v3 ML classifier (primary) ────────────────────────────────
        if _regime_v3 is not None:
            from signals.indicator_engine import IndicatorEngine as _IE
            _ie  = _IE()
            ind  = _ie.compute(candles)
            feat = {
                "log_ret":          float(getattr(ind, "roc",  0) or 0) / 100,
                "abs_ret":          abs(float(getattr(ind, "roc", 0) or 0) / 100),
                "roc_10":           float(getattr(ind, "roc",  0) or 0),
                "rsi":              float(ind.rsi or 50),
                "stoch_k":          float(ind.stoch_k or 50),
                "macd_hist":        float(ind.macd_hist or 0),
                "adx":              float(ind.adx or 0),
                "di_split":         abs(float((ind.di_pos or 0) - (ind.di_neg or 0))),
                "ema_align":        int(
                    (1 if (ind.ema_9 or 0) > (ind.ema_21 or 0) else 0) +
                    (1 if (ind.ema_21 or 0) > (ind.ema_50 or 0) else 0) +
                    (1 if (ind.ema_50 or 0) > (ind.ema_200 or 0) else 0)
                ),
                "price_vs_ema50":   float(((candles[-1].close - (ind.ema_50 or candles[-1].close)) / (ind.ema_50 or candles[-1].close)) * 100) if ind.ema_50 else 0,
                "price_vs_ema200":  float(((candles[-1].close - (ind.ema_200 or candles[-1].close)) / (ind.ema_200 or candles[-1].close)) * 100) if ind.ema_200 else 0,
                "atr_pct":          float(ind.atr_pct or 0),
                "atr_pct_zscore":   0.0,   # runtime z-score requires rolling history; use 0 as neutral
                "bb_width":         float(ind.bb_bandwidth or 0) if hasattr(ind, "bb_bandwidth") else 0,
                "bb_width_zscore":  0.0,
                "bb_pct_b":         float(ind.bb_pct_b or 0.5),
                "vol_of_vol":       0.0,   # requires rolling ATR history
                "vol_zscore":       0.0,
            }
            v3_result = _regime_v3.predict(feat)
            return {
                "symbol":      symbol,
                "timeframe":   timeframe,
                "regime":      v3_result["regime"],
                "confidence":  v3_result["confidence"],
                "probabilities": v3_result["probabilities"],
                "model":       "v3_ensemble_rf_xgb",
                "candles_used": len(candles),
                "timestamp":   time.time(),
            }

        # ── HMM fallback ──────────────────────────────────────────────
        result = _regime.detect(candles)
        return {
            "symbol":      symbol,
            "timeframe":   timeframe,
            "regime":      result.regime.value,
            "confidence":  result.confidence,
            "state_probs": result.state_probs,
            "model":       "hmm_fallback",
            "candles_used": len(candles),
            "timestamp":   time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/sentiment", tags=["Intelligence"])
async def get_sentiment(
    symbol: str = Query(default="BTCUSDT"),
):
    """
    Calculate composite market sentiment for a symbol using
    funding rate, open interest, and liquidation data.
    """
    try:
        funding_data = await _rest.get_funding_rate(symbol)
        oi_data      = await _rest.get_open_interest(symbol)

        funding_rate = float(funding_data.get("lastFundingRate", 0))
        oi_change    = 0.0   # would need historical OI for Δ

        result = _sentiment.analyze(
            funding_rate     = funding_rate,
            oi_change_pct    = oi_change,
        )
        return {
            "symbol":       symbol,
            "score":        result.score,
            "label":        result.label.value,
            "components":   result.components,
            "funding_rate": funding_rate,
            "timestamp":    time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/anomaly", tags=["Intelligence"])
async def get_anomaly(
    symbol:    str = Query(default="BTCUSDT"),
    timeframe: str = Query(default="1h"),
    limit:     int = Query(default=60, ge=20, le=200),
):
    """Run anomaly detection on recent candles for a symbol."""
    try:
        raw     = await _rest.get_klines(symbol, timeframe, limit=limit)
        candles = _norm.klines_to_candles(symbol, timeframe, raw)
        report  = _anomaly.check(candles)
        return {
            "symbol":        symbol,
            "is_anomaly":    report.is_anomaly,
            "severity":      report.severity,
            "anomaly_types": report.anomaly_types,
            "z_score":       report.z_score,
            "volume_z":      report.volume_z,
            "details":       report.details,
            "timestamp":     time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Position Sizing ───────────────────────────────────────────────────────────

@app.get("/position-size", tags=["Risk"])
async def get_position_size(
    symbol:          str   = Query(default="BTCUSDT"),
    entry:           float = Query(default=65000.0, gt=0),
    stop_loss:       float = Query(default=64000.0, gt=0),
    account_balance: float = Query(default=10_000.0, gt=0),
    win_rate:        Optional[float] = Query(default=None, ge=0.0, le=1.0),
    avg_rr:          Optional[float] = Query(default=None, gt=0.0),
):
    """
    Calculate recommended position size given entry/SL levels and balance.
    Optionally uses Kelly criterion if win_rate and avg_rr are provided.
    """
    from signals.entry_exit_calculator import TradeSetup
    from scanner.base_scanner import SignalDirection

    direction = SignalDirection.LONG if entry > stop_loss else SignalDirection.SHORT
    sl_dist   = abs(entry - stop_loss)
    setup     = TradeSetup(
        symbol       = symbol,
        direction    = direction,
        signal_score = 70.0,
        entry        = entry,
        stop_loss    = stop_loss,
        tp1          = entry + sl_dist       if direction == SignalDirection.LONG else entry - sl_dist,
        tp2          = entry + sl_dist * 2   if direction == SignalDirection.LONG else entry - sl_dist * 2,
        tp3          = entry + sl_dist * 3   if direction == SignalDirection.LONG else entry - sl_dist * 3,
        risk_pct     = sl_dist / entry * 100,
        rr_ratio_tp2 = 2.0,
        rr_ratio_tp3 = 3.0,
        atr          = sl_dist / 1.5,
        atr_pct      = (sl_dist / 1.5) / entry * 100,
    )
    _exposure.update_balance(account_balance)
    pos = _sizer.calculate(setup, account_balance, win_rate=win_rate, avg_rr=avg_rr)

    return {
        "symbol":       symbol,
        "direction":    direction.value,
        "qty":          pos.qty,
        "notional":     pos.notional,
        "risk_usdt":    pos.risk_usdt,
        "margin_usdt":  pos.margin_usdt,
        "risk_pct":     pos.risk_pct,
        "leverage":     pos.leverage_used,
        "method":       pos.method,
        "valid":        pos.valid,
        "reason":       pos.reason if not pos.valid else None,
        "timestamp":    time.time(),
    }


# ── Correlation ───────────────────────────────────────────────────────────────

@app.get("/correlation", tags=["Risk"])
async def get_correlation(
    symbols:   str = Query(default="BTCUSDT,ETHUSDT,SOLUSDT"),
    timeframe: str = Query(default="1h"),
    limit:     int = Query(default=60, ge=20, le=200),
):
    """Compute pairwise Pearson correlation matrix for the given symbols."""
    pair_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    tasks     = [_rest.get_klines(s, timeframe, limit=limit) for s in pair_list]
    raw_list  = await asyncio.gather(*tasks, return_exceptions=True)

    for sym, raw in zip(pair_list, raw_list):
        if isinstance(raw, list) and raw:
            candles = _norm.klines_to_candles(sym, timeframe, raw)
            _correlation.update_prices(sym, [c.close for c in candles])

    matrix = _correlation.correlation_matrix()
    pairs  = _correlation.high_correlation_pairs()

    return {
        "matrix": matrix,
        "high_correlation_pairs": [
            {"a": p.symbol_a, "b": p.symbol_b, "r": p.correlation}
            for p in pairs if p.is_high
        ],
        "threshold":   _correlation._threshold,
        "symbols":     _correlation.tracked_symbols,
        "timestamp":   time.time(),
    }


# ── Trade Journal ─────────────────────────────────────────────────────────────

@app.get("/journal", tags=["Journal"])
async def get_journal(
    days: int = Query(default=7, ge=1, le=90),
):
    """
    Return recent trades from the persistent trade journal.

    Query params:
        days — how many calendar days to look back (default 7, max 90)
    """
    trades = _journal.get_recent_trades(days=days)
    return {
        "trades": trades,
        "count":  len(trades),
        "days":   days,
        "timestamp": time.time(),
    }


@app.get("/performance", tags=["Journal"])
async def get_performance():
    """
    Aggregate performance stats from the trade journal combined with
    the current scaling profile.
    """
    stats = _journal.performance_stats()
    scale = _scaler.status()
    return {**stats, "scale_profile": scale, "timestamp": time.time()}


@app.get("/performance/equity", tags=["Journal"])
async def get_equity_curve():
    """
    Return the full timestamped equity curve for chart rendering.

    Response shape:
        {
            "equity_curve": [{"ts": "<ISO datetime>", "equity": <float>}, ...],
            "initial_capital": <float>,
            "current_equity": <float>,
            "timestamp": <unix epoch>
        }
    """
    stats = _journal.performance_stats()
    return {
        "equity_curve":    stats.get("equity_curve", []),
        "initial_capital": stats.get("initial_capital", 10_000.0),
        "current_equity":  stats.get("current_equity", stats.get("initial_capital", 10_000.0)),
        "timestamp":       time.time(),
    }


@app.get("/performance/daily", tags=["Journal"])
async def get_daily_performance():
    """Today's P&L summary from the trade journal."""
    summary = _journal.daily_summary()
    return {**summary, "timestamp": time.time()}


# ── Scale Manager ─────────────────────────────────────────────────────────────

@app.get("/scale", tags=["Scale"])
async def get_scale_status():
    """Current scaling profile status (risk tier, position limits, etc.)."""
    return {**_scaler.status(), "timestamp": time.time()}


@app.post("/scale/check", tags=["Scale"])
async def check_scale_promotion(
    trades: int   = Query(..., ge=1,   description="Total completed trades"),
    sharpe: float = Query(..., ge=0.0, description="Sharpe ratio over the period"),
):
    """
    Evaluate whether current trading stats qualify for a scale-up.

    Promotes the scaler profile in-memory if thresholds are met.
    Returns the promotion result and updated profile.
    """
    promoted = _scaler.check_promotion(trades, sharpe)
    return {
        "promoted":    promoted is not None,
        "new_profile": promoted.name if promoted else None,
        "current":     _scaler.status(),
        "timestamp":   time.time(),
    }


# ── Walk-Forward Validation ───────────────────────────────────────────────────

@app.get("/validate", tags=["Validation"])
async def run_validation(
    symbol:    str = Query(default="BTCUSDT", description="Symbol in Binance format, e.g. BTCUSDT"),
    timeframe: str = Query(default="4h"),
    limit:     int = Query(default=1000, ge=100, le=5000),
):
    """
    Run walk-forward validation on historical candles for a symbol.

    Fetches data via the native Binance REST client (no ccxt).
    Returns pass/fail result and per-fold metrics.
    """
    try:
        import pandas as pd
        from validation.walk_forward_validation import WalkForwardValidator, fetch_data

        # fetch_data uses the symbol in BTCUSDT format (no slash)
        df        = fetch_data(symbol.upper(), timeframe, limit)
        validator = WalkForwardValidator(df)
        passed    = validator.run_all()

        return {
            "passed":    passed,
            "results":   validator.results,
            "symbol":    symbol.upper(),
            "timeframe": timeframe,
            "candles":   limit,
            "timestamp": time.time(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Entry point (standalone mode)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host    = "0.0.0.0",
        port    = settings.api_port if hasattr(settings, "api_port") else 8001,
        reload  = False,
        workers = 1,
    )
