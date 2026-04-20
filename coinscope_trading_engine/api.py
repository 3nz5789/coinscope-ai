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
import logging
import os
from dataclasses import asdict
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
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
    sys.path.append(_os.path.join(_os.path.dirname(__file__), ".."))
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


@app.on_event("startup")
async def _on_startup() -> None:
    """Open the Redis-backed cache pool before handling traffic, and start
    the background Binance-account sync task."""
    try:
        await _cache.connect()
    except Exception as exc:
        # Non-fatal: scanners will still short-circuit with a clear error,
        # but /health and other non-cache endpoints stay up.
        import logging
        logging.getLogger(__name__).error("CacheManager connect failed: %s", exc)

    # Kick off the live-account sync task. Non-fatal if Binance is unreachable.
    global _account_sync_task, _price_feed_task, _scan_loop_task, _liq_feed_task, _hist_refresh_task
    _account_sync_task  = asyncio.create_task(_account_sync_loop())
    _price_feed_task    = asyncio.create_task(_price_feed_loop())
    _liq_feed_task      = asyncio.create_task(_liq_feed_loop())
    _hist_refresh_task  = asyncio.create_task(_historical_refresh_loop())
    _scan_loop_task     = asyncio.create_task(_scan_loop())

    # Open the DecisionJournal's Postgres mirror (non-fatal if offline)
    asyncio.create_task(_decisions.pg_connect())

    # Telegram heartbeat so you can verify the bot is alive
    asyncio.create_task(_tg_send(
        f"<b>CoinScopeAI engine online</b>\n"
        f"Binance Futures Demo · scan every {max(5, int(settings.scan_interval_seconds or 60))}s · "
        f"autotrade <b>OFF</b> by default.",
        emoji="🚀",
    ))


@app.on_event("shutdown")
async def _on_shutdown() -> None:
    """Close the Redis pool cleanly on process exit."""
    try:
        await _decisions.pg_close()
    except Exception:
        pass
    global _account_sync_task, _price_feed_task, _scan_loop_task, _liq_feed_task, _hist_refresh_task
    for t in (_account_sync_task, _price_feed_task, _liq_feed_task, _hist_refresh_task, _scan_loop_task):
        if t is not None:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
    try:
        await _cache.close()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Shared singletons (lightweight — no persistent state between requests)
# ---------------------------------------------------------------------------

_rest         = BinanceRESTClient(
    api_key    = settings.active_api_key.get_secret_value(),
    api_secret = settings.active_api_secret.get_secret_value(),
    testnet    = settings.testnet_mode,
)
_cache        = CacheManager()
_norm         = DataNormalizer()

# Persistent decision journal (docs/risk/risk-framework.md invariant #5)
# Postgres DSN comes from settings (.env → pydantic), not os.getenv, because
# pydantic-settings doesn't rehydrate the process environment.
from storage.decision_journal import DecisionJournal as _DecisionJournal, DecisionEvent as _DecisionEvent
_decisions    = _DecisionJournal(
    path   = "logs/decisions.jsonl",
    pg_url = getattr(settings, "decisions_pg_url", "") or None,
)

# Historical klines store (90-day rolling SQLite; free Binance public API)
from storage.historical_klines import HistoricalKlinesStore as _KlinesStore
_klines_store = _KlinesStore(path="logs/klines.sqlite")
_HISTORICAL_INTERVALS    = ["5m", "15m", "1h", "4h"]
_HISTORICAL_LOOKBACK     = 90
_HISTORICAL_REFRESH_S    = 15 * 60       # refresh every 15 min
_hist_refresh_task: Optional[asyncio.Task] = None


async def _historical_refresh_loop() -> None:
    """Background: backfill on first run, then refresh every 15 min.
    Errors are swallowed — the store is a read-only signal source; its
    liveness is independent of trading.
    """
    # First run: backfill if any stream is empty
    try:
        gs = _klines_store.global_stats()
        if gs["total_rows"] == 0:
            logger.info("HistoricalKlines: empty DB, backfilling %dd × %d pairs × %d TFs…",
                        _HISTORICAL_LOOKBACK, len(settings.scan_pairs), len(_HISTORICAL_INTERVALS))
            r = await _klines_store.backfill(
                list(settings.scan_pairs), _HISTORICAL_INTERVALS,
                lookback_days=_HISTORICAL_LOOKBACK,
            )
            logger.info("HistoricalKlines backfill: inserted=%s pruned=%s errors=%s",
                        r["inserted"], r["pruned"], len(r["errors"]))
    except Exception as exc:
        logger.warning("HistoricalKlines initial backfill failed: %s", exc)

    while True:
        try:
            await asyncio.sleep(_HISTORICAL_REFRESH_S)
            r = await _klines_store.refresh(
                list(settings.scan_pairs), _HISTORICAL_INTERVALS,
                lookback_days=_HISTORICAL_LOOKBACK,
            )
            if r["inserted"] > 0:
                logger.info("HistoricalKlines refresh: +%d rows, pruned=%d",
                            r["inserted"], r["pruned"])
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.debug("HistoricalKlines refresh error: %s", exc)

# Telegram notifier (optional — no-op if credentials not set)
try:
    from alerts.telegram_notifier import TelegramNotifier
    _telegram = TelegramNotifier()
except Exception as _tg_exc:
    _telegram = None
    logging.getLogger(__name__).warning("TelegramNotifier init failed: %s", _tg_exc)


async def _tg_send(text: str, emoji: str = "ℹ️") -> None:
    """Fire-and-forget Telegram status send. Never raises."""
    if not _telegram or not getattr(_telegram, "_enabled", False):
        return
    try:
        await _telegram.send_status(text, emoji=emoji)
    except Exception as exc:
        logger.debug("telegram send failed: %s", exc)
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
    VolumeScanner(cache=_cache, rest=_rest),
    PatternScanner(cache=_cache, rest=_rest),
    FundingRateScanner(cache=_cache, rest=_rest),
    OrderBookScanner(cache=_cache, rest=_rest),
    LiquidationScanner(cache=_cache, rest=_rest),
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


class OrderRequest(BaseModel):
    """Request body for POST /orders (Phase 3b manual placement).

    Keep it explicit and simple. Only MARKET and LIMIT are supported for v1;
    SL/TP attach is a separate call via /orders/bracket (added in 3c).
    """
    symbol:        str
    side:          str                  # "BUY" | "SELL"
    type:          str     = "MARKET"   # "MARKET" | "LIMIT"
    qty:           float                 # base-asset quantity
    price:         Optional[float] = None  # required for LIMIT
    tif:           str     = "GTC"      # LIMIT only: GTC / IOC / FOK / GTX
    reduce_only:   bool    = False
    leverage:      Optional[int] = None # if set, change_leverage first
    client_id:     Optional[str] = None # idempotency token; autogen if omitted


class BracketRequest(BaseModel):
    """Protective bracket attached to a live position: SL + TP via STOP_MARKET
    and TAKE_PROFIT_MARKET with closePosition=true.
    """
    symbol:      str
    side:        str                    # side of the *entry*: BUY or SELL
    stop_price:  Optional[float] = None # SL trigger
    tp_price:    Optional[float] = None # TP trigger
    qty:         Optional[float] = None # if omitted, closePosition=true is used


class CloseRequest(BaseModel):
    """Market-close an open position by sending a reduce-only MARKET order."""
    symbol:      str
    qty:         Optional[float] = None  # if omitted, derive from current position


# ---------------------------------------------------------------------------
# Multi-Timeframe Filter (higher-timeframe trend gate)
# ---------------------------------------------------------------------------
#
# Only allow LONG signals when the 4h EMA trend is bullish, and SHORTs when
# it's bearish. Based on core/multi_timeframe_filter.py. The trend label is
# cached for `_HTF_CACHE_TTL_S` seconds per symbol so we don't hammer
# Binance — 4h bars don't move every 10 seconds anyway.

from core.multi_timeframe_filter import MultiTimeframeFilter

_mtf_filter = MultiTimeframeFilter(ema_fast=9, ema_slow=21)
_HTF_TIMEFRAME = "4h"
_HTF_CACHE_TTL_S = 5 * 60            # 5 minutes — well under one 4h bar
_htf_trend_cache: dict[str, tuple[float, str]] = {}   # symbol -> (expires_at, trend)


async def _get_htf_trend(symbol: str, limit: int = 60) -> str:
    """Return 'bull' / 'bear' / 'neutral' for `symbol`'s 4h trend.

    Cached per-symbol for HTF_CACHE_TTL_S seconds.
    """
    now = time.time()
    cached = _htf_trend_cache.get(symbol)
    if cached and cached[0] > now:
        return cached[1]

    try:
        raw = await _rest.get_klines(symbol, _HTF_TIMEFRAME, limit=limit)
        closes = [float(r[4]) for r in raw if len(r) > 4]    # column 4 is close
        import numpy as _np
        trend = _mtf_filter.get_4h_trend(_np.array(closes, dtype=float))
    except Exception as exc:
        logger.debug("HTF fetch failed for %s: %s", symbol, exc)
        trend = "neutral"

    _htf_trend_cache[symbol] = (now + _HTF_CACHE_TTL_S, trend)
    return trend


# ---------------------------------------------------------------------------
# Autotrade (Phase 3c — scan loop places trades autonomously)
# ---------------------------------------------------------------------------
#
# Default: OFF. Toggle via /autotrade/enable. Safety invariants:
#   * TESTNET_MODE must be True (enforced again at order time)
#   * Circuit breaker must be CLOSED
#   * No existing open position on that symbol
#   * Signal must be actionable AND its TradeSetup must be valid
#   * Respects cooldown between entries on the same symbol
#   * Exposure ≤ max_total_exposure_pct and position_count ≤ max_open_positions

_autotrade_state: dict = {
    "enabled":              False,
    "started_at":           None,
    "entries_total":        0,
    "entries_rejected":     0,
    "last_entry_at":        0.0,
    "last_reject_reason":   None,
    "recent_events":        [],        # capped list of {ts, symbol, action, reason/order_id, score}
    # Tunables exposed via /autotrade/config
    "risk_per_trade_pct":   None,      # None → use settings.risk_per_trade_pct
    "default_leverage":     5,
    "attach_bracket":       True,
    "min_score":            None,      # None → use settings.min_confluence_score
    "cooldown_s":           300,       # min gap between entries on same symbol
    # Backtest-proven: LONG-only is the only config that wasn't a money-loser
    # on the last 30d of 1h data. Defaults to LONG_ONLY as a safety rail.
    "allowed_directions":   "LONG_ONLY",  # "BOTH" | "LONG_ONLY" | "SHORT_ONLY"
    # Higher-timeframe trend gate: 4h EMA(9/21) must agree with signal direction.
    # NOTE: A/B backtest 2026-04-20 showed this gate REDUCES profitability on
    # the current scanner mix because ConfluenceScorer already applies
    # indicator-alignment bonuses (RSI/ADX/MACD) that capture trend
    # agreement internally. Default OFF; leave togglable for future
    # strategies that might benefit.
    "mtf_filter_enabled":   False,
    "mtf_block_neutral":    True,
    # Per-symbol health guards (consume DecisionJournal stats)
    "max_consec_losses_per_symbol": 3,
    "loss_pause_seconds":            3600,   # 1h pause when consec-loss threshold hit
    "max_daily_loss_per_symbol_pct": -1.5,   # pause symbol when realised daily hits -1.5%
}
_last_entry_per_symbol: dict[str, float] = {}


def _autotrade_record(event: dict) -> None:
    """Append to the bounded in-memory event log AND the persistent
    DecisionJournal on disk. The in-memory copy keeps dashboard polling
    fast; the JSONL file satisfies invariant #5 (reconstruct every verdict)."""
    evt = {"ts": time.time(), **event}
    _autotrade_state["recent_events"].insert(0, evt)
    if len(_autotrade_state["recent_events"]) > 50:
        _autotrade_state["recent_events"].pop()

    # Persist to disk as a typed DecisionEvent
    try:
        de = _DecisionEvent(
            ts           = evt["ts"],
            symbol       = evt.get("symbol", "-"),
            direction    = evt.get("side"),
            action       = evt.get("action", "reject"),
            reason       = evt.get("reason", ""),
            signal_score = evt.get("score"),
            order_id     = evt.get("order_id"),
            qty          = evt.get("qty"),
            extra        = {k: v for k, v in evt.items()
                            if k not in {"ts","symbol","side","action","reason","score","order_id","qty"}} or None,
            source       = "auto",
        )
        _decisions.record(de)
    except Exception as exc:
        logger.debug("decision_journal record failed: %s", exc)


def _gate_snapshot() -> dict:
    """Compact snapshot of live gate state — used in decision records for
    later reconstruction ("why didn't we trade at 3:15 on Tuesday?")."""
    return {
        "breaker":        _circuit.state.value if hasattr(_circuit.state, "value") else str(_circuit.state),
        "positions":      _exposure.position_count,
        "exposure_pct":   round(_exposure.total_exposure_pct, 2),
        "daily_pnl_pct":  round(_exposure.daily_loss_pct, 4),
        "available_bal":  round(float(_account_state["summary"].get("availableBalance", 0)) if _account_state.get("summary") else 0, 2),
    }


async def _autotrade_consider(signal: dict) -> None:
    """Called from the scan loop for every signal in each tick. Decides
    whether this signal becomes a real trade.

    The decision trace is captured in `_autotrade_state['recent_events']`
    so the dashboard Pipeline page (Phase 3e) can show every 'why not'.
    """
    if not _autotrade_state["enabled"]:
        return

    symbol = signal.get("symbol", "?")

    # Guard 0: direction filter (LONG_ONLY / SHORT_ONLY / BOTH)
    allowed = _autotrade_state.get("allowed_directions", "BOTH")
    direction = signal.get("direction")
    if allowed == "LONG_ONLY" and direction != "LONG":
        return
    if allowed == "SHORT_ONLY" and direction != "SHORT":
        return

    # Guard 0b: higher-timeframe trend filter — only LONG in 4h bull, only
    # SHORT in 4h bear. Uses the cached htf_trend that the scan loop attaches
    # to every signal (falls back to live lookup if missing).
    if _autotrade_state.get("mtf_filter_enabled", True):
        htf = signal.get("htf_trend")
        if htf is None:
            try:
                htf = await _get_htf_trend(symbol)
            except Exception:
                htf = "neutral"
        block_neutral = _autotrade_state.get("mtf_block_neutral", True)
        allowed_by_mtf = (
            (direction == "LONG"  and htf == "bull") or
            (direction == "SHORT" and htf == "bear") or
            (not block_neutral and htf == "neutral")
        )
        if not allowed_by_mtf:
            _autotrade_state["entries_rejected"] += 1
            reason = f"MTF: {direction} blocked — 4h is {htf}"
            _autotrade_state["last_reject_reason"] = reason
            _autotrade_record({"symbol": symbol, "action": "reject", "reason": reason, "score": signal.get("score"), "side": direction})
            return

    # Guard 1: actionable signal + valid setup
    if not signal.get("actionable"):
        return                              # below threshold; no event spam
    setup = signal.get("setup") or {}
    if not setup.get("valid"):
        _autotrade_state["entries_rejected"] += 1
        _autotrade_state["last_reject_reason"] = f"{symbol}: setup invalid ({setup.get('reason')})"
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": f"setup invalid: {setup.get('reason')}", "score": signal.get("score")})
        return

    # Guard 2: circuit breaker
    if _circuit.is_open:
        _autotrade_state["entries_rejected"] += 1
        reason = f"circuit breaker {_circuit.state.value}"
        _autotrade_state["last_reject_reason"] = reason
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": reason, "score": signal.get("score")})
        return

    # Guard 3: already open on this symbol?
    open_syms = {p["symbol"] for p in _account_state.get("positions", []) if p.get("symbol")}
    if symbol in open_syms:
        _autotrade_record({"symbol": symbol, "action": "skip", "reason": "already open", "score": signal.get("score")})
        return

    # Guard 3b: per-symbol health — pause symbols that are bleeding
    paused, remaining = _decisions.is_symbol_paused(symbol)
    if paused:
        _autotrade_record({
            "symbol": symbol, "action": "skip",
            "reason": f"symbol paused for {int(remaining)}s more",
            "score": signal.get("score"),
        })
        return

    health = _decisions.symbol_health(symbol)
    max_consec = int(_autotrade_state.get("max_consec_losses_per_symbol", 3))
    if health.consecutive_losses >= max_consec:
        pause_s = int(_autotrade_state.get("loss_pause_seconds", 3600))
        _decisions.pause_symbol(
            symbol, pause_s,
            reason=f"{health.consecutive_losses} consecutive losses",
        )
        _autotrade_record({
            "symbol": symbol, "action": "reject",
            "reason": f"auto-paused: {health.consecutive_losses} consec losses",
            "score": signal.get("score"),
        })
        # Emit Telegram once per pause event
        asyncio.create_task(_tg_send(
            f"<b>Per-symbol pause: {symbol}</b>\n"
            f"{health.consecutive_losses} consecutive losses · paused for {pause_s//60}min.",
            emoji="⏸️",
        ))
        return

    max_daily_loss_sym = float(_autotrade_state.get("max_daily_loss_per_symbol_pct", -1.5))
    if health.daily_pnl_pct * 100 <= max_daily_loss_sym:
        _autotrade_record({
            "symbol": symbol, "action": "reject",
            "reason": f"per-symbol daily loss cap ({health.daily_pnl_pct*100:.2f}% ≤ {max_daily_loss_sym}%)",
            "score": signal.get("score"),
        })
        return

    # Guard 4: cooldown
    last = _last_entry_per_symbol.get(symbol, 0.0)
    cd = int(_autotrade_state["cooldown_s"] or 300)
    if time.time() - last < cd:
        _autotrade_record({"symbol": symbol, "action": "skip", "reason": f"cooldown {int(cd - (time.time()-last))}s", "score": signal.get("score")})
        return

    # Guard 5: exposure + position-count caps via ExposureTracker
    if _exposure.position_count >= (settings.max_open_positions or 3):
        reason = f"max positions reached ({_exposure.position_count})"
        _autotrade_state["entries_rejected"] += 1
        _autotrade_state["last_reject_reason"] = reason
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": reason, "score": signal.get("score")})
        return
    if _exposure.total_exposure_pct >= (settings.max_total_exposure_pct or 80):
        reason = f"exposure cap reached ({_exposure.total_exposure_pct:.1f}%)"
        _autotrade_state["entries_rejected"] += 1
        _autotrade_state["last_reject_reason"] = reason
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": reason, "score": signal.get("score")})
        return

    # Guard 6: min_score override (autotrade's threshold is ≥ scanner's)
    min_score = _autotrade_state["min_score"] or settings.min_confluence_score
    if (signal.get("score") or 0) < min_score:
        return

    # Guard 7: correlation — don't double-down on highly correlated pairs
    try:
        from scanner.base_scanner import SignalDirection as _SDir
        sig_dir = _SDir.LONG if signal.get("direction") == "LONG" else _SDir.SHORT
        safe, why = _correlation.is_safe_to_add(symbol, sig_dir, _exposure.open_positions)
        if not safe:
            _autotrade_state["entries_rejected"] += 1
            _autotrade_state["last_reject_reason"] = f"correlation: {why}"
            _autotrade_record({"symbol": symbol, "action": "reject", "reason": f"correlation: {why}", "score": signal.get("score")})
            return
    except Exception as exc:
        logger.debug("correlation check non-fatal: %s", exc)

    # All checks passed — compute size via PositionSizer and place it.
    side = "BUY" if signal.get("direction") == "LONG" else "SELL"
    entry_price = float(setup.get("entry") or 0)
    stop_price  = float(setup.get("stop_loss") or 0)
    tp_price    = float(setup.get("tp2") or setup.get("tp1") or 0)
    if entry_price <= 0 or stop_price <= 0 or entry_price == stop_price:
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": "bad entry/stop", "score": signal.get("score")})
        return

    try:
        from signals.confluence_scorer import Signal as _SignalCls
        from scanner.base_scanner import SignalDirection as _SDir
        from signals.entry_exit_calculator import TradeSetup as _TS
        # Build minimum TradeSetup/Signal that PositionSizer accepts
        sig_dir = _SDir.LONG if side == "BUY" else _SDir.SHORT
        ts = _TS(
            symbol=symbol, direction=sig_dir, signal_score=signal.get("score", 0),
            entry=entry_price, stop_loss=stop_price,
            tp1=entry_price + (entry_price - stop_price) * 1.0,
            tp2=tp_price or entry_price + (entry_price - stop_price) * 2.0,
            tp3=entry_price + (entry_price - stop_price) * 3.0,
            risk_pct=abs(entry_price - stop_price) / entry_price * 100,
            rr_ratio_tp2=(setup.get("rr_ratio") or 2.0),
            rr_ratio_tp3=(setup.get("rr_ratio") or 3.0),
            atr=abs(entry_price - stop_price) / 1.5,  # inverse of atr_sl_mult default
            atr_pct=abs(entry_price - stop_price) / entry_price * 100,
            recommended_qty=0,
            max_notional=0,
            method="AUTO",
            valid=True, invalid_reason=None, notes=None,
        )
        balance = _account_state["summary"] and float(_account_state["summary"].get("availableBalance") or 0) or 0
        balance = balance or _exposure._balance                                           # type: ignore[attr-defined]
        size = _sizer.calculate(ts, balance=balance)
        qty = float(size.qty or 0)
        if qty <= 0:
            _autotrade_record({"symbol": symbol, "action": "reject", "reason": f"sizer qty=0 ({size.reason or ''})", "score": signal.get("score")})
            return
    except Exception as exc:
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": f"sizing error: {exc}", "score": signal.get("score")})
        return

    try:
        result = await _execute_entry(
            symbol          = symbol,
            side            = side,
            qty             = qty,
            leverage        = int(_autotrade_state["default_leverage"] or 5),
            stop_price      = stop_price if _autotrade_state["attach_bracket"] else None,
            tp_price        = tp_price   if _autotrade_state["attach_bracket"] and tp_price else None,
            client_id_prefix= "auto",
            source          = "auto",
            signal_score    = float(signal.get("score") or 0),
            regime          = signal.get("regime", "UNKNOWN"),
            reasons         = signal.get("reasons") or [],
            strength        = signal.get("strength", ""),
            htf_trend       = signal.get("htf_trend", ""),
            scanner_hits    = [{"name": s} for s in (signal.get("scanners") or [])],
            indicators      = signal.get("indicators") or {},
            setup_entry     = float(entry_price),
        )
    except HTTPException as exc:
        _autotrade_state["entries_rejected"] += 1
        _autotrade_state["last_reject_reason"] = exc.detail
        _autotrade_record({"symbol": symbol, "action": "reject", "reason": str(exc.detail), "score": signal.get("score")})
        return
    except Exception as exc:
        _autotrade_state["entries_rejected"] += 1
        _autotrade_state["last_reject_reason"] = str(exc)
        _autotrade_record({"symbol": symbol, "action": "error",  "reason": str(exc), "score": signal.get("score")})
        logger.error("autotrade execute failed on %s: %s", symbol, exc)
        return

    _autotrade_state["entries_total"] += 1
    _autotrade_state["last_entry_at"]  = time.time()
    _last_entry_per_symbol[symbol]     = time.time()
    order_id = (result.get("order") or {}).get("orderId")
    _autotrade_record({
        "symbol":   symbol,
        "action":   "open",
        "side":     side,
        "qty":      qty,
        "score":    signal.get("score"),
        "entry":    entry_price,
        "sl":       stop_price,
        "tp":       tp_price,
        "order_id": order_id,
    })
    logger.info(
        "AUTO %s %s qty=%s @ %.4f SL=%.4f TP=%.4f score=%.1f order=%s",
        side, symbol, qty, entry_price, stop_price, tp_price or 0,
        signal.get("score") or 0, order_id,
    )

    # Telegram: announce the auto-entry
    try:
        direction = "LONG" if side == "BUY" else "SHORT"
        emoji = "🟢" if side == "BUY" else "🔴"
        msg = (
            f"<b>Auto {direction} {symbol}</b>\n"
            f"qty <code>{qty}</code> @ <code>{entry_price:.4f}</code> · {int(_autotrade_state['default_leverage'] or 5)}x\n"
            f"SL <code>{stop_price:.4f}</code> · TP <code>{(tp_price or 0):.4f}</code>\n"
            f"Score <b>{signal.get('score',0):.0f}</b> · {signal.get('strength','')}\n"
            f"Order <code>#{order_id}</code>"
        )
        asyncio.create_task(_tg_send(msg, emoji=emoji))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Continuous scan loop (Phase 3a — no trading yet, just transparency)
# ---------------------------------------------------------------------------
#
# A background task rescans every `settings.scan_interval_seconds` and
# drops the results into `_signal_cache`, so the dashboard Scanner page
# updates on its own. This is the foundation for auto-execution in 3c —
# first we make sure the signals look right, then we wire them to trades.

_scan_loop_state: dict = {
    "running":         False,
    "last_scan_at":    0.0,
    "next_scan_at":    0.0,
    "scans_total":     0,
    "scans_failed":    0,
    "last_error":      None,
    "last_duration_ms": 0,
    "last_signals":    0,       # total symbols that scored ≥ min_score on last pass
    "last_actionable": 0,       # symbols whose score crossed the threshold
}
_scan_loop_task: Optional[asyncio.Task] = None


async def _scan_loop() -> None:
    """Every `scan_interval_seconds` re-run the pipeline for every pair.

    Emits nothing externally; just populates `_signal_cache`, which the
    `/signals` endpoint reads. Errors per pair are swallowed — one bad
    symbol shouldn't stop the loop.
    """
    global _last_scan_ts

    interval = max(5, int(settings.scan_interval_seconds or 60))
    # first tick waits 3s so the WS price feed + account sync have time to warm
    await asyncio.sleep(3)

    while True:
        _scan_loop_state["running"] = True
        t0 = time.monotonic()
        try:
            pairs = settings.scan_pairs or []
            signals_count = 0
            actionable_count = 0
            for sym in pairs:
                try:
                    res = await _scan_symbol(sym, timeframe="1h", limit=100)
                    if res is not None:
                        _signal_cache[sym] = res
                        signals_count += 1
                        if res.get("actionable"):
                            actionable_count += 1

                        # Persist every signal to the DecisionJournal so the
                        # audit log captures the full decision space, not
                        # just autotrade verdicts. action="signal".
                        try:
                            _decisions.record(_DecisionEvent(
                                ts           = time.time(),
                                symbol       = sym,
                                direction    = res.get("direction"),
                                action       = "signal",
                                reason       = "scan tick",
                                signal_score = res.get("score"),
                                strength     = res.get("strength"),
                                regime       = res.get("regime"),
                                htf_trend    = res.get("htf_trend"),
                                setup        = res.get("setup"),
                                scanners     = res.get("scanners") or [],
                                source       = "scan_loop",
                                extra        = {"reasons": res.get("reasons", [])[:5], "actionable": res.get("actionable")},
                            ))
                        except Exception as jex:
                            logger.debug("signal persist failed: %s", jex)

                        # Phase 3c: give the autotrader a chance to act on it
                        try:
                            await _autotrade_consider(res)
                        except Exception as auto_exc:
                            logger.warning("autotrade_consider(%s) errored: %s", sym, auto_exc)
                    else:
                        _signal_cache.pop(sym, None)
                except Exception as exc:
                    logger.warning("scan_loop: %s errored: %s", sym, exc)

            _last_scan_ts = time.time()
            _scan_loop_state["scans_total"]     += 1
            _scan_loop_state["last_scan_at"]     = _last_scan_ts
            _scan_loop_state["next_scan_at"]     = _last_scan_ts + interval
            _scan_loop_state["last_duration_ms"] = int((time.monotonic() - t0) * 1000)
            _scan_loop_state["last_signals"]     = signals_count
            _scan_loop_state["last_actionable"]  = actionable_count
            _scan_loop_state["last_error"]       = None

            # Breaker auto-trip on daily loss / drawdown / consecutive losses
            # (evaluated every scan tick instead of waiting for user action)
            try:
                prev_state = _circuit.state
                dd_pct    = abs(_exposure.daily_loss_pct) if _exposure.daily_loss_pct < 0 else 0.0
                _circuit.check(
                    daily_loss_pct    = _exposure.daily_loss_pct,
                    drawdown_pct      = dd_pct,
                    consecutive_losses= 0,
                )
                if _circuit.state != prev_state and _circuit.is_open:
                    last = _circuit.last_trip
                    reason = last.reason if last else "risk limit exceeded"
                    logger.warning("CircuitBreaker auto-tripped: %s", reason)
                    asyncio.create_task(_tg_send(
                        f"<b>Circuit breaker auto-tripped</b>\nReason: {reason}\nAutotrade halted until manual reset.",
                        emoji="⛔"))
            except Exception as exc:
                logger.debug("breaker check non-fatal: %s", exc)

            logger.info(
                "ScanLoop tick #%d | pairs=%d signals=%d actionable=%d in %dms",
                _scan_loop_state["scans_total"], len(pairs),
                signals_count, actionable_count,
                _scan_loop_state["last_duration_ms"],
            )
        except asyncio.CancelledError:
            _scan_loop_state["running"] = False
            return
        except Exception as exc:
            _scan_loop_state["scans_failed"] += 1
            _scan_loop_state["last_error"]    = f"{type(exc).__name__}: {exc}"
            logger.error("scan_loop unexpected error: %s", exc)

        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            _scan_loop_state["running"] = False
            return


# ---------------------------------------------------------------------------
# Live price feed (Binance Futures Demo WS mark-price stream)
# ---------------------------------------------------------------------------

_price_cache: dict[str, dict] = {}     # symbol → {mark_price, index_price, funding_rate, ts}
_price_feed_state: dict = {
    "connected":  False,
    "reconnects": 0,
    "last_msg_at": 0.0,
    "error":      None,
}
_price_feed_task: Optional[asyncio.Task] = None


async def _price_feed_loop() -> None:
    """Connect to demo-fstream and keep `_price_cache` fresh.

    Subscribes to `<sym>@markPrice@1s` for every pair in settings.scan_pairs.
    Each `markPriceUpdate` payload updates `_price_cache` and also feeds
    ExposureTracker.update_mark_price so open-position unrealised PnL stays
    current without any REST polling.

    On disconnect / error, reconnect with exponential backoff (1s → 60s cap).
    """
    import websockets
    import json as _json

    base = settings.binance_testnet_ws_url if settings.testnet_mode else settings.binance_ws_url
    pairs = [s.lower() for s in settings.scan_pairs]
    streams = "/".join(f"{p}@markPrice@1s" for p in pairs)
    url = f"{base}/stream?streams={streams}"

    backoff = 1.0
    while True:
        try:
            logger.info("PriceFeed connecting → %s", url)
            async with websockets.connect(
                url,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=15,
                max_queue=256,
            ) as ws:
                _price_feed_state["connected"]  = True
                _price_feed_state["reconnects"] = _price_feed_state["reconnects"] + 1 if backoff > 1 else _price_feed_state["reconnects"]
                _price_feed_state["error"]      = None
                backoff = 1.0
                async for raw in ws:
                    try:
                        msg = _json.loads(raw)
                        data = msg.get("data") or msg  # handle single or /stream wrapper
                        if data.get("e") != "markPriceUpdate":
                            continue
                        sym = data.get("s")
                        if not sym:
                            continue
                        mark = float(data.get("p", 0) or 0)
                        _price_cache[sym] = {
                            "mark_price":   mark,
                            "index_price":  float(data.get("i", 0) or 0),
                            "estimated_settle": float(data.get("P", 0) or 0),
                            "funding_rate": float(data.get("r", 0) or 0),
                            "next_funding_ts": int(data.get("T", 0) or 0),
                            "ts":           int(data.get("E", 0) or 0) / 1000.0,
                        }
                        _price_feed_state["last_msg_at"] = time.time()

                        # Keep ExposureTracker's positions marked-to-market
                        if mark > 0:
                            await _exposure.update_mark_price(sym, mark)
                            # Feed the correlation analyzer so it sees a live series
                            try:
                                _correlation.append_price(sym, mark)
                            except Exception:
                                pass
                    except Exception as ex:
                        logger.debug("PriceFeed parse error: %s", ex)
        except asyncio.CancelledError:
            _price_feed_state["connected"] = False
            return
        except Exception as exc:
            _price_feed_state["connected"] = False
            _price_feed_state["error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("PriceFeed disconnected: %s — reconnect in %.1fs", exc, backoff)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return
            backoff = min(backoff * 2, 60.0)


# ---------------------------------------------------------------------------
# Liquidation feed (WS — replaces the retired /fapi/v1/allForceOrders REST)
# ---------------------------------------------------------------------------
#
# Binance killed the REST endpoint in 2025. The `<symbol>@forceOrder` WS
# stream is the supported replacement but emits only "the largest one
# liquidation within each 1000ms" — still enough to detect cascades.
#
# We keep an in-memory deque per symbol, bounded to the last 30 minutes, and
# the LiquidationScanner reads from this buffer instead of REST.

from collections import deque
from datetime import datetime, timezone
from data.data_normalizer import LiquidationOrder as _LiquidationOrder

_LIQ_WINDOW_S  = 30 * 60               # keep 30 min of events
_LIQ_MAX_ITEMS = 2_000                 # hard cap per symbol
# Liquidation feed URL: defaults to MAINNET (public, unsigned) because
# Binance Futures Demo has almost no liquidations — the plumbing works
# but the data firehose is dry. Trading still goes through demo-fapi; this
# is a signal-only read-only subscription. Override via env to point at
# demo-fstream or a custom host.
_LIQ_FEED_WS_URL = os.getenv("LIQUIDATION_FEED_WS_URL", "wss://fstream.binance.com")
_liq_buffer: dict[str, "deque[_LiquidationOrder]"] = {}
_liq_feed_state: dict = {
    "connected":   False,
    "reconnects":  0,
    "last_msg_at": 0.0,
    "total_events": 0,
    "error":       None,
}
_liq_feed_task: Optional[asyncio.Task] = None


def _prune_liq(buf: "deque[_LiquidationOrder]") -> None:
    """Drop events older than `_LIQ_WINDOW_S` from the left of the deque."""
    cutoff = datetime.now(timezone.utc).timestamp() - _LIQ_WINDOW_S
    while buf and buf[0].time.timestamp() < cutoff:
        buf.popleft()


async def _liq_feed_loop() -> None:
    """Subscribe to `<sym>@forceOrder` for each scan_pair and buffer events.

    Same reconnect pattern as _price_feed_loop.
    """
    import websockets
    import json as _json

    # Use the dedicated liq-feed URL (mainnet by default) — public stream,
    # no auth. Trading still flows through demo-fapi (settings.testnet_mode).
    base = _LIQ_FEED_WS_URL
    pairs = [s.lower() for s in settings.scan_pairs]
    streams = "/".join(f"{p}@forceOrder" for p in pairs)
    url = f"{base}/stream?streams={streams}"

    # Pre-seed buffers so the scanner never hits a KeyError
    for s in settings.scan_pairs:
        _liq_buffer.setdefault(s, deque(maxlen=_LIQ_MAX_ITEMS))

    backoff = 1.0
    while True:
        try:
            logger.info("LiqFeed connecting → %s (signal-only)", url)
            async with websockets.connect(
                url,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=15,
                max_queue=256,
            ) as ws:
                _liq_feed_state["connected"]  = True
                _liq_feed_state["error"]      = None
                if backoff > 1:
                    _liq_feed_state["reconnects"] += 1
                backoff = 1.0

                async for raw in ws:
                    try:
                        msg = _json.loads(raw)
                        data = msg.get("data") or msg
                        if data.get("e") != "forceOrder":
                            continue
                        o = data.get("o") or {}
                        sym = o.get("s")
                        if not sym:
                            continue
                        evt = _LiquidationOrder(
                            symbol        = sym,
                            side          = o.get("S", ""),
                            order_type    = o.get("o", "LIMIT"),
                            time_in_force = o.get("f", "IOC"),
                            qty           = float(o.get("q") or 0),
                            price         = float(o.get("p") or 0),
                            avg_price     = float(o.get("ap") or o.get("p") or 0),
                            status        = o.get("X", "FILLED"),
                            time          = datetime.fromtimestamp(
                                int(o.get("T") or data.get("E") or 0) / 1000.0,
                                tz=timezone.utc,
                            ),
                        )
                        buf = _liq_buffer.setdefault(sym, deque(maxlen=_LIQ_MAX_ITEMS))
                        _prune_liq(buf)
                        buf.append(evt)
                        _liq_feed_state["last_msg_at"]  = time.time()
                        _liq_feed_state["total_events"] += 1
                    except Exception as ex:
                        logger.debug("LiqFeed parse error: %s", ex)
        except asyncio.CancelledError:
            _liq_feed_state["connected"] = False
            return
        except Exception as exc:
            _liq_feed_state["connected"] = False
            _liq_feed_state["error"]     = f"{type(exc).__name__}: {exc}"
            logger.warning("LiqFeed disconnected: %s — reconnect in %.1fs", exc, backoff)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                return
            backoff = min(backoff * 2, 60.0)


def _get_recent_liquidations(symbol: str, minutes: int) -> list:
    """Return LiquidationOrder events for `symbol` in the last `minutes`."""
    buf = _liq_buffer.get(symbol)
    if not buf:
        return []
    _prune_liq(buf)
    cutoff = datetime.now(timezone.utc).timestamp() - minutes * 60
    return [e for e in buf if e.time.timestamp() >= cutoff]


# ---------------------------------------------------------------------------
# Live Binance-account sync
# ---------------------------------------------------------------------------
#
# On top of the in-process ExposureTracker we maintain a small cache of the
# latest live account snapshot pulled from demo-fapi.binance.com. A
# background task refreshes it every ACCOUNT_SYNC_INTERVAL_S seconds and
# mirrors wallet balance + open positions into ExposureTracker so the
# existing /exposure and /positions endpoints read real values.

ACCOUNT_SYNC_INTERVAL_S = 10.0  # polling cadence; lowered on Binance rate-limit

_account_state: dict = {
    "updated_at":     0.0,         # unix seconds of last successful refresh
    "error":          None,        # last error message, if any
    "summary":        None,        # raw /fapi/v2/account summary
    "balances":       [],          # raw /fapi/v2/balance rows
    "positions":      [],          # non-zero rows from /fapi/v2/positionRisk
}
_account_sync_task: Optional[asyncio.Task] = None


async def _sync_account_once() -> None:
    """Refresh balance + positions from Binance and mirror into ExposureTracker.

    Does not raise — any error is captured on `_account_state['error']` so
    the endpoints can expose it for the dashboard.
    """
    try:
        summary  = await _rest.get_account()
        balances = await _rest.get_balance()
        raw_pos  = await _rest.get_positions()

        non_zero_pos = [p for p in raw_pos if float(p.get("positionAmt", 0)) != 0]

        # Reconcile journal: if an entry is OPEN but Binance has no matching
        # position, mark it CLOSED using the last known mark price as exit.
        try:
            live_symbols = {p["symbol"] for p in non_zero_pos}
            for e in list(_journal.entries):
                if e.status != "OPEN":
                    continue
                if e.symbol in live_symbols:
                    # Backfill entry_price if Binance logged zero earlier
                    if e.entry_price <= 0:
                        for p in non_zero_pos:
                            if p.get("symbol") == e.symbol:
                                ep = float(p.get("entryPrice") or 0)
                                if ep > 0:
                                    e.entry_price = ep
                                break
                    continue
                # Entry is in journal but position is flat → close it.
                # Try to determine WHICH side of the bracket fired by comparing
                # the last mark price against SL / TP. This is a best-effort
                # inference — the user-data WS in Phase 3d will give us the
                # definitive "which algo order executed" answer.
                exit_price = _price_cache.get(e.symbol, {}).get("mark_price") or e.entry_price
                trigger    = "reconcile"
                if e.sl_price and e.tp_price and exit_price > 0:
                    if e.side.upper() == "BUY":
                        if exit_price <= e.sl_price * 1.002: trigger = "sl_hit"
                        elif exit_price >= e.tp_price * 0.998: trigger = "tp_hit"
                    else:
                        if exit_price >= e.sl_price * 0.998: trigger = "sl_hit"
                        elif exit_price <= e.tp_price * 1.002: trigger = "tp_hit"
                if e.entry_price <= 0 or exit_price <= 0:
                    _journal.log_close(
                        e.id, exit_price or 0, 0.0, 0.0,
                        exit_trigger=trigger, closed_by="reconcile_loop",
                    )
                    continue
                pnl_per_unit = (exit_price - e.entry_price) if e.side.upper() == "BUY" else (e.entry_price - exit_price)
                pnl_usd = pnl_per_unit * e.quantity
                pnl_pct = (pnl_per_unit / e.entry_price) if e.entry_price else 0
                _journal.log_close(
                    e.id, exit_price, pnl_pct, pnl_usd,
                    exit_trigger = trigger,
                    closed_by    = "reconcile_loop",
                )
                _decisions.record_close(e.symbol, pnl_usd, pnl_pct)
        except Exception as exc:
            logger.debug("journal reconcile non-fatal: %s", exc)

        _account_state["summary"]    = summary
        _account_state["balances"]   = balances
        _account_state["positions"]  = non_zero_pos
        _account_state["updated_at"] = time.time()
        _account_state["error"]      = None

        # Mirror into ExposureTracker so /exposure, /positions reflect reality.
        # Use availableBalance as the "risk-available" balance for sizing.
        avail = float(summary.get("availableBalance", summary.get("totalWalletBalance", 0)) or 0)
        if avail > 0:
            _exposure.update_balance(avail)

        # Replace the tracker's in-memory positions with live ones. We reach
        # into the private _positions dict because this is an administrative
        # sync (bypassing open_position's max-position guard, which is meant
        # for user-initiated opens, not state reconciliation).
        from scanner.base_scanner import SignalDirection
        from risk.exposure_tracker import Position
        from datetime import datetime, timezone

        fresh: dict[str, "Position"] = {}
        for p in non_zero_pos:
            amt    = float(p["positionAmt"])
            direction = SignalDirection.LONG if amt > 0 else SignalDirection.SHORT
            qty    = abs(amt)
            entry  = float(p.get("entryPrice", 0) or 0)
            mark   = float(p.get("markPrice",  entry) or entry)
            fresh[p["symbol"]] = Position(
                symbol=p["symbol"],
                direction=direction,
                qty=qty,
                entry=entry,
                notional=qty * entry,
                mark_price=mark,
                opened_at=datetime.now(timezone.utc),
            )
        # Swap in one operation to keep snapshot() consistent between reads.
        _exposure._positions = fresh  # type: ignore[attr-defined]
    except Exception as exc:
        _account_state["error"] = f"{type(exc).__name__}: {exc}"
        logger.warning("Live account sync failed: %s", exc)


async def _account_sync_loop() -> None:
    """Background task: keep _account_state + ExposureTracker fresh."""
    # First pull immediately so /account/* works on the first request.
    await _sync_account_once()
    while True:
        try:
            await asyncio.sleep(ACCOUNT_SYNC_INTERVAL_S)
            await _sync_account_once()
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("account_sync_loop unexpected error: %s", exc)
            await asyncio.sleep(ACCOUNT_SYNC_INTERVAL_S)


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

        # Higher-timeframe trend (4h EMA) — cheap, cached. Attached so
        # autotrade gate and dashboard can see the direction alignment.
        try:
            htf_trend = await _get_htf_trend(symbol)
        except Exception:
            htf_trend = "neutral"

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
            "htf_trend": htf_trend,                 # 'bull' | 'bear' | 'neutral'
            "htf_agrees": (
                (signal.direction.value == "LONG"  and htf_trend == "bull") or
                (signal.direction.value == "SHORT" and htf_trend == "bear")
            ),
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


# ── Account (live Binance Futures Demo) ──────────────────────────────────────

@app.get("/account", tags=["Account"])
async def get_account():
    """Live Binance Futures Demo account summary.

    Mirrors `/fapi/v2/account` but only returns the dashboard-relevant
    fields. Populated by the background sync task (`_account_sync_loop`).
    """
    s = _account_state["summary"] or {}
    return {
        "updated_at":          _account_state["updated_at"],
        "age_s":               round(time.time() - _account_state["updated_at"], 1) if _account_state["updated_at"] else None,
        "error":               _account_state["error"],
        "can_trade":           bool(s.get("canTrade", False)),
        "fee_tier":            s.get("feeTier"),
        "total_wallet_balance":   float(s.get("totalWalletBalance", 0) or 0),
        "total_margin_balance":   float(s.get("totalMarginBalance", 0) or 0),
        "available_balance":      float(s.get("availableBalance", 0) or 0),
        "total_unrealized_pnl":   float(s.get("totalUnrealizedProfit", 0) or 0),
        "total_position_notional":float(s.get("totalPositionInitialMargin", 0) or 0),
        "total_maint_margin":     float(s.get("totalMaintMargin", 0) or 0),
        "position_count":      len(_account_state["positions"]),
    }


@app.get("/account/balance", tags=["Account"])
async def get_account_balance(only_non_zero: bool = True):
    """Per-asset balances from `/fapi/v2/balance`."""
    rows = _account_state["balances"] or []
    if only_non_zero:
        rows = [r for r in rows if float(r.get("balance", 0) or 0) > 0]
    return {
        "updated_at": _account_state["updated_at"],
        "error":      _account_state["error"],
        "balances": [
            {
                "asset":              r.get("asset"),
                "balance":            float(r.get("balance", 0) or 0),
                "available_balance":  float(r.get("availableBalance", 0) or 0),
                "cross_wallet":       float(r.get("crossWalletBalance", 0) or 0),
                "cross_unpnl":        float(r.get("crossUnPnl", 0) or 0),
                "max_withdraw":       float(r.get("maxWithdrawAmount", 0) or 0),
            }
            for r in rows
        ],
    }


@app.get("/account/positions", tags=["Account"])
async def get_account_positions():
    """Open positions from `/fapi/v2/positionRisk` (non-zero only)."""
    rows = _account_state["positions"] or []
    return {
        "updated_at": _account_state["updated_at"],
        "error":      _account_state["error"],
        "count":      len(rows),
        "positions": [
            {
                "symbol":            p.get("symbol"),
                "position_side":     p.get("positionSide"),   # BOTH / LONG / SHORT in hedge mode
                "position_amt":      float(p.get("positionAmt", 0) or 0),
                "side":              "LONG" if float(p.get("positionAmt", 0) or 0) > 0 else "SHORT",
                "entry_price":       float(p.get("entryPrice", 0) or 0),
                "mark_price":        float(p.get("markPrice", 0) or 0),
                "liquidation_price": float(p.get("liquidationPrice", 0) or 0),
                "leverage":          int(float(p.get("leverage", 0) or 0)),
                "margin_type":       p.get("marginType"),
                "isolated_margin":   float(p.get("isolatedMargin", 0) or 0),
                "unrealized_pnl":    float(p.get("unRealizedProfit", 0) or 0),
                "notional":          float(p.get("notional", 0) or 0),
                "update_time":       int(p.get("updateTime", 0) or 0),
            }
            for p in rows
        ],
    }


@app.post("/account/sync", tags=["Account"])
async def force_account_sync():
    """Force an immediate refresh from Binance (otherwise happens every 10s)."""
    await _sync_account_once()
    return {
        "updated_at": _account_state["updated_at"],
        "error":      _account_state["error"],
        "positions":  len(_account_state["positions"]),
    }


# ── Orders (Phase 3b — manual trade placement) ───────────────────────────────
#
# Safety invariants enforced on every entry:
#   * settings.testnet_mode must be True (Binance demo). A future
#     ALLOW_LIVE_TRADING guard would be required to flip this.
#   * Circuit breaker must be CLOSED.
#   * Symbol + side + qty must pass basic validation.
#
# We bypass BinanceRESTClient.place_order (it over-specifies fields for
# MARKET orders) and call the signed /fapi/v1/order endpoint directly with
# the minimal param set Binance expects per order type.

import uuid as _uuid
from decimal import Decimal, ROUND_DOWN

def _gen_client_id(prefix: str = "cs") -> str:
    """Idempotency token — Binance rejects duplicates (prevents double-submit)."""
    return f"{prefix}-{_uuid.uuid4().hex[:12]}"


# ─── Symbol filter cache (stepSize / tickSize / minNotional) ─────────────
# Fetched lazily the first time a symbol is traded and cached until process
# exit. Binance `/fapi/v1/exchangeInfo` is weight-1 so the hit is cheap, but
# doing it on every order placement would be wasteful.
_symbol_filters: dict[str, dict] = {}


async def _load_symbol_filters(symbol: str) -> dict:
    """Return {stepSize, tickSize, minQty, minNotional} for `symbol`.

    Raises HTTPException(404) if the symbol is unknown to the exchange.
    """
    if symbol in _symbol_filters:
        return _symbol_filters[symbol]
    info = await _rest.get_exchange_info()
    for sym in info.get("symbols", []):
        if sym.get("symbol") != symbol:
            continue
        filters = {f["filterType"]: f for f in sym.get("filters", [])}
        step = filters.get("LOT_SIZE", {}).get("stepSize", "0.001")
        tick = filters.get("PRICE_FILTER", {}).get("tickSize", "0.01")
        minq = filters.get("LOT_SIZE", {}).get("minQty", "0")
        mnot = filters.get("MIN_NOTIONAL", {}).get("notional", "0")
        spec = {
            "stepSize":     Decimal(step),
            "tickSize":     Decimal(tick),
            "minQty":       Decimal(minq),
            "minNotional":  Decimal(mnot),
            "baseAsset":    sym.get("baseAsset"),
            "quoteAsset":   sym.get("quoteAsset"),
        }
        _symbol_filters[symbol] = spec
        return spec
    raise HTTPException(404, f"Unknown symbol on exchange: {symbol}")


def _quantize_down(value: float, step: Decimal) -> Decimal:
    """Round `value` DOWN to the nearest multiple of `step`."""
    if step <= 0:
        return Decimal(str(value))
    v = Decimal(str(value))
    return (v // step) * step


async def _prepare_qty(symbol: str, qty: float) -> tuple[str, Decimal]:
    """Quantize qty to the symbol's LOT_SIZE.stepSize and check minQty.

    Returns (qty_str, qty_decimal). Raises HTTPException on violation.
    """
    filt = await _load_symbol_filters(symbol)
    q = _quantize_down(qty, filt["stepSize"])
    if q < filt["minQty"]:
        raise HTTPException(
            400,
            f"qty {qty} rounded to {q} is below minQty {filt['minQty']} for {symbol}",
        )
    # Normalize the string representation — strip trailing zeros but keep at
    # least one decimal if needed for Binance parser.
    qty_str = format(q.normalize(), "f")
    if "." not in qty_str:
        qty_str = f"{qty_str}"
    return qty_str, q


async def _prepare_price(symbol: str, price: float) -> str:
    """Quantize price to the symbol's PRICE_FILTER.tickSize."""
    filt = await _load_symbol_filters(symbol)
    p = _quantize_down(price, filt["tickSize"])
    s = format(p.normalize(), "f")
    return s


def _require_testnet_and_breaker() -> None:
    """Raise HTTPException if it's unsafe to place an order."""
    if not settings.testnet_mode:
        raise HTTPException(
            status_code=403,
            detail="Refusing to place orders: TESTNET_MODE=false. "
                   "Live trading requires an explicit ALLOW_LIVE_TRADING flag.",
        )
    if _circuit.is_open:
        raise HTTPException(
            status_code=423,   # Locked
            detail=f"Circuit breaker is {_circuit.state.value}. Reset it first.",
        )


async def _place_signed_order(params: dict) -> dict:
    """Signed POST /fapi/v1/order with only the keys given — no over-specify."""
    return await _rest._request("POST", "/fapi/v1/order", params=params, signed=True)  # type: ignore[attr-defined]


async def _execute_entry(
    symbol:   str,
    side:     str,                       # "BUY" | "SELL"
    qty:      float,
    *,
    leverage:        Optional[int]   = None,
    stop_price:      Optional[float] = None,
    tp_price:        Optional[float] = None,
    client_id_prefix: str            = "cs",
    source:          str             = "manual",   # 'manual' | 'auto' | 'api'
    signal_score:    float           = 0.0,
    regime:          str             = "UNKNOWN",
    reasons:         Optional[list]  = None,
    # Full provenance (recorded in the journal for later trace-back)
    strength:        str             = "",
    htf_trend:       str             = "",
    scanner_hits:    Optional[list]  = None,
    indicators:      Optional[dict]  = None,
    setup_entry:     Optional[float] = None,        # signal's intended entry — for slippage calc
) -> dict:
    """Shared entry path used by both the manual POST /orders endpoint and
    the autotrade loop (Phase 3c).

    Steps:
      1. testnet + circuit-breaker safety check
      2. optional leverage change
      3. stepSize/tickSize quantization
      4. signed POST /fapi/v1/order (MARKET entry)
      5. if stop_price or tp_price: attach Algo Order bracket
      6. log_open on the TradeJournal
      7. trigger account sync

    Returns a summary dict that the endpoint can return as-is and the
    autotrade logger can persist.
    """
    _require_testnet_and_breaker()
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(400, f"side must be BUY or SELL, got {side!r}")
    if qty <= 0:
        raise HTTPException(400, f"qty must be > 0, got {qty}")

    # Leverage change
    leverage_resp = None
    if leverage is not None:
        if leverage < 1 or leverage > settings.max_leverage:
            raise HTTPException(400, f"leverage {leverage} out of [1..{settings.max_leverage}]")
        try:
            leverage_resp = await _rest.change_leverage(symbol, leverage)
        except Exception as exc:
            logger.warning("change_leverage(%s→%dx) failed: %s", symbol, leverage, exc)

    qty_str, _ = await _prepare_qty(symbol, qty)
    client_id = _gen_client_id(client_id_prefix)
    params: dict = {
        "symbol":          symbol,
        "side":            side,
        "type":            "MARKET",
        "quantity":        qty_str,
        "newClientOrderId": client_id,
    }
    submit_ms = int(time.time() * 1000)
    resp = await _place_signed_order(params)
    fill_ms = int(resp.get("updateTime") or time.time() * 1000)

    bracket_results: dict = {}
    sl_algo_id = 0
    tp_algo_id = 0
    if stop_price is not None or tp_price is not None:
        exit_side = "SELL" if side == "BUY" else "BUY"
        if stop_price is not None:
            try:
                sp = await _prepare_price(symbol, stop_price)
                sl_resp = await _place_algo_conditional({
                    "algoType":     "CONDITIONAL",
                    "symbol":       symbol,
                    "side":         exit_side,
                    "type":         "STOP_MARKET",
                    "triggerPrice": sp,
                    "workingType":  "MARK_PRICE",
                    "clientAlgoId": _algo_client_id("sl"),
                    "closePosition":"true",
                })
                bracket_results["stop_loss"] = sl_resp
                sl_algo_id = int(sl_resp.get("algoId") or 0)
            except Exception as exc:
                bracket_results["stop_loss"] = {"error": str(exc)}
        if tp_price is not None:
            try:
                tp = await _prepare_price(symbol, tp_price)
                tp_resp = await _place_algo_conditional({
                    "algoType":     "CONDITIONAL",
                    "symbol":       symbol,
                    "side":         exit_side,
                    "type":         "TAKE_PROFIT_MARKET",
                    "triggerPrice": tp,
                    "workingType":  "MARK_PRICE",
                    "clientAlgoId": _algo_client_id("tp"),
                    "closePosition":"true",
                })
                bracket_results["take_profit"] = tp_resp
                tp_algo_id = int(tp_resp.get("algoId") or 0)
            except Exception as exc:
                bracket_results["take_profit"] = {"error": str(exc)}

    # Resolve the true fill price. Binance's synchronous response often
    # shows avgPrice="0.00" for MARKET orders before the engine finishes
    # matching; re-query once to pick up the fill, or fall back to the live
    # mark price so the journal doesn't land on 0.
    fill_price = float(resp.get("avgPrice") or resp.get("price") or 0)
    if fill_price <= 0 and resp.get("orderId"):
        await asyncio.sleep(0.4)
        try:
            q = await _rest.get_order(symbol=symbol, order_id=int(resp["orderId"]))
            fill_price = float(q.get("avgPrice") or q.get("price") or 0)
        except Exception:
            pass
    if fill_price <= 0:
        cached = _price_cache.get(symbol, {}).get("mark_price")
        if cached:
            fill_price = float(cached)

    # Journal the open with FULL provenance — so /journal/{id}/trace can
    # rebuild the entire story from signal → entry → bracket → exit.
    journal_entry = None
    try:
        notional = fill_price * qty
        # Slippage: how far fill_price drifted from the signal's proposed entry
        slippage_bps = 0.0
        if setup_entry and setup_entry > 0 and fill_price > 0:
            delta = (fill_price - setup_entry) / setup_entry
            # For SELL, positive delta is favorable (sold higher); flip sign
            slippage_bps = round(delta * 10_000 * (1 if side == "BUY" else -1), 2)

        journal_entry = _journal.log_open(
            symbol       = symbol,
            side         = side,
            regime       = regime if regime and regime != "UNKNOWN" else "—",
            confidence   = signal_score / 100.0 if signal_score else 0.0,
            entry_price  = fill_price,
            quantity     = qty,
            kelly_usd    = notional,
            signal_score = signal_score,
            leverage     = int(leverage or 0),
            source       = source,
            reasons      = reasons or [],
            strength     = strength or "",
            htf_trend    = htf_trend or "",
            scanner_hits = scanner_hits or [],
            indicators_at_entry = indicators or {},
            entry_client_id = client_id,
            entry_order_id  = int(resp.get("orderId") or 0),
            entry_submit_ms = submit_ms,
            entry_fill_ms   = fill_ms,
            slippage_bps    = slippage_bps,
            sl_price        = float(stop_price or 0.0),
            tp_price        = float(tp_price or 0.0),
            sl_algo_id      = sl_algo_id,
            tp_algo_id      = tp_algo_id,
        )
    except Exception as exc:
        logger.debug("journal.log_open non-fatal: %s", exc)

    # Fire-and-forget account sync so /positions reflects the new fill fast
    asyncio.create_task(_sync_account_once())

    return {
        "order":            resp,
        "client_id":        client_id,
        "leverage_change":  leverage_resp,
        "bracket":          bracket_results if bracket_results else None,
        "source":           source,
        "journal_id":       journal_entry.id if journal_entry else None,
        "slippage_bps":     slippage_bps if 'slippage_bps' in locals() else 0.0,
    }


@app.post("/orders", tags=["Orders"])
async def place_order(body: OrderRequest):
    """Place an order on Binance Futures Demo.

    For MARKET orders, delegates to `_execute_entry` so the path is
    identical to autotrade. LIMIT orders take a dedicated path because
    they set a price + TIF and don't attach a bracket automatically.
    """
    side  = body.side.upper()
    otype = body.type.upper()
    if otype not in ("MARKET", "LIMIT"):
        raise HTTPException(400, f"type must be MARKET or LIMIT, got {body.type!r}")

    if otype == "MARKET":
        try:
            return await _execute_entry(
                symbol   = body.symbol,
                side     = side,
                qty      = body.qty,
                leverage = body.leverage,
                client_id_prefix = "cs",
                source   = "manual",
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("place_order(market) failed: %s", exc)
            raise HTTPException(400, f"Binance rejected order: {exc}")

    # LIMIT
    _require_testnet_and_breaker()
    if body.qty <= 0:
        raise HTTPException(400, f"qty must be > 0, got {body.qty}")
    if not body.price:
        raise HTTPException(400, "LIMIT order requires a price")
    if side not in ("BUY", "SELL"):
        raise HTTPException(400, f"side must be BUY or SELL, got {body.side!r}")

    leverage_resp = None
    if body.leverage is not None:
        if body.leverage < 1 or body.leverage > settings.max_leverage:
            raise HTTPException(400, f"leverage {body.leverage} out of [1..{settings.max_leverage}]")
        try:
            leverage_resp = await _rest.change_leverage(body.symbol, body.leverage)
        except Exception as exc:
            logger.warning("change_leverage failed: %s", exc)

    qty_str, _ = await _prepare_qty(body.symbol, body.qty)
    price_str  = await _prepare_price(body.symbol, body.price)
    client_id  = body.client_id or _gen_client_id()
    params = {
        "symbol":          body.symbol,
        "side":            side,
        "type":            "LIMIT",
        "quantity":        qty_str,
        "price":           price_str,
        "timeInForce":     body.tif.upper(),
        "newClientOrderId": client_id,
    }
    if body.reduce_only:
        params["reduceOnly"] = "true"
    try:
        resp = await _place_signed_order(params)
    except Exception as exc:
        raise HTTPException(400, f"Binance rejected order: {exc}")

    asyncio.create_task(_sync_account_once())
    return {"order": resp, "client_id": client_id, "leverage_change": leverage_resp}


@app.post("/orders/close", tags=["Orders"])
async def close_position(body: CloseRequest):
    """Market-close an open position (reduceOnly)."""
    _require_testnet_and_breaker()

    # Find live position qty if not supplied
    qty = body.qty
    pos_side = "LONG"
    for p in _account_state["positions"]:
        if p.get("symbol") == body.symbol and float(p.get("positionAmt", 0) or 0) != 0:
            amt = float(p["positionAmt"])
            pos_side = "LONG" if amt > 0 else "SHORT"
            if qty is None:
                qty = abs(amt)
            break
    if qty is None or qty <= 0:
        raise HTTPException(404, f"No open position on {body.symbol}")

    side = "SELL" if pos_side == "LONG" else "BUY"
    client_id = _gen_client_id("close")
    qty_str, _ = await _prepare_qty(body.symbol, qty)

    # Capture the mark price now so we can journal a decent approximation
    # of the fill (user-data WS in Phase 3d will give us the real avg).
    mark_before = None
    cached_price = _price_cache.get(body.symbol, {}).get("mark_price")
    if cached_price:
        mark_before = float(cached_price)

    params = {
        "symbol":           body.symbol,
        "side":             side,
        "type":             "MARKET",
        "quantity":         qty_str,
        "reduceOnly":       "true",
        "newClientOrderId": client_id,
    }
    try:
        resp = await _place_signed_order(params)
    except Exception as exc:
        raise HTTPException(400, f"Binance rejected close: {exc}")

    # Log the close against the most recent OPEN journal entry on this symbol
    try:
        match = None
        for e in reversed(_journal.entries):
            if e.symbol == body.symbol and e.status == "OPEN":
                match = e; break
        if match is not None:
            exit_price = mark_before or match.entry_price
            pnl_per_unit = (exit_price - match.entry_price) if match.side.upper() == "BUY" else (match.entry_price - exit_price)
            pnl_usd = pnl_per_unit * match.quantity
            pnl_pct = (pnl_per_unit / match.entry_price) if match.entry_price else 0
            _journal.log_close(
                match.id, exit_price, pnl_pct, pnl_usd,
                exit_trigger  = "manual",
                exit_order_id = int(resp.get("orderId") or 0),
                closed_by     = "user/api:/orders/close",
            )
            _decisions.record_close(match.symbol, pnl_usd, pnl_pct)
    except Exception as exc:
        logger.debug("journal.log_close non-fatal: %s", exc)

    # Also cancel any outstanding algo brackets on this symbol (closePosition
    # orders usually auto-cancel but be explicit to avoid zombies).
    try:
        await _rest._request("DELETE", "/fapi/v1/algoOrder", params={"symbol": body.symbol}, signed=True)  # type: ignore[attr-defined]
    except Exception:
        pass

    asyncio.create_task(_sync_account_once())

    # Telegram alert for the close
    try:
        emoji = "✅"
        exit_est = mark_before or 0.0
        msg = (
            f"<b>Closed {pos_side} {body.symbol}</b>\n"
            f"qty <code>{qty}</code> @ ~<code>{exit_est:.4f}</code>\n"
            f"Order <code>#{resp.get('orderId')}</code>"
        )
        asyncio.create_task(_tg_send(msg, emoji=emoji))
    except Exception:
        pass

    return {"order": resp, "client_id": client_id, "closed_qty": qty, "was_side": pos_side}


async def _place_algo_conditional(params: dict) -> dict:
    """Signed POST /fapi/v1/algoOrder for conditional SL/TP (migrated 2025-12)."""
    return await _rest._request("POST", "/fapi/v1/algoOrder", params=params, signed=True)  # type: ignore[attr-defined]


def _algo_client_id(prefix: str) -> str:
    """clientAlgoId pattern: ^[\\.A-Z:/a-z0-9_-]{1,36}$"""
    return f"{prefix}-{_uuid.uuid4().hex[:12]}"


@app.post("/orders/bracket", tags=["Orders"])
async def attach_bracket(body: BracketRequest):
    """Attach SL + TP to an existing position via the Algo Order API.

    Binance migrated STOP_MARKET / TAKE_PROFIT_MARKET / STOP / TAKE_PROFIT /
    TRAILING_STOP_MARKET to `POST /fapi/v1/algoOrder` (algoType=CONDITIONAL)
    on 2025-12-09. Old endpoint returns -4120.
    """
    _require_testnet_and_breaker()
    entry_side = body.side.upper()
    if entry_side not in ("BUY", "SELL"):
        raise HTTPException(400, "side must be BUY or SELL (entry side)")

    exit_side = "SELL" if entry_side == "BUY" else "BUY"
    results: dict = {}

    def _base_params(order_type: str, trigger_str: str, prefix: str) -> dict:
        p = {
            "algoType":     "CONDITIONAL",
            "symbol":       body.symbol,
            "side":         exit_side,
            "type":         order_type,
            "triggerPrice": trigger_str,
            "workingType":  "MARK_PRICE",
            "clientAlgoId": _algo_client_id(prefix),
        }
        if body.qty is not None:
            # qty will be set by caller after _prepare_qty
            pass
        else:
            p["closePosition"] = "true"
        return p

    if body.stop_price is not None:
        stop_str = await _prepare_price(body.symbol, body.stop_price)
        params = _base_params("STOP_MARKET", stop_str, "sl")
        if body.qty is not None:
            qty_str, _ = await _prepare_qty(body.symbol, body.qty)
            params["quantity"]   = qty_str
            params["reduceOnly"] = "true"
        try:
            results["stop_loss"] = await _place_algo_conditional(params)
        except Exception as exc:
            results["stop_loss"] = {"error": str(exc)}

    if body.tp_price is not None:
        tp_str = await _prepare_price(body.symbol, body.tp_price)
        params = _base_params("TAKE_PROFIT_MARKET", tp_str, "tp")
        if body.qty is not None:
            qty_str, _ = await _prepare_qty(body.symbol, body.qty)
            params["quantity"]   = qty_str
            params["reduceOnly"] = "true"
        try:
            results["take_profit"] = await _place_algo_conditional(params)
        except Exception as exc:
            results["take_profit"] = {"error": str(exc)}

    return results


@app.get("/orders/open", tags=["Orders"])
async def list_open_orders(symbol: Optional[str] = None):
    """Open orders on Binance Futures Demo (optionally filtered by symbol)."""
    try:
        orders = await _rest.get_open_orders(symbol)
    except Exception as exc:
        raise HTTPException(400, f"Binance error: {exc}")
    return {"orders": orders, "count": len(orders)}


@app.get("/orders/algo/open", tags=["Orders"])
async def list_open_algo_orders(symbol: Optional[str] = None):
    """Active conditional (Algo) orders — SL / TP / trailing stop.

    Since 2025-12 Binance exposes these under /fapi/v1/openAlgoOrders
    (not the regular /fapi/v1/openOrders endpoint).
    """
    params: dict = {}
    if symbol:
        params["symbol"] = symbol
    try:
        resp = await _rest._request("GET", "/fapi/v1/openAlgoOrders", params=params, signed=True)  # type: ignore[attr-defined]
    except Exception as exc:
        raise HTTPException(400, f"Binance error: {exc}")
    orders = resp.get("orders") if isinstance(resp, dict) else resp
    return {"orders": orders or [], "count": len(orders or [])}


@app.delete("/orders/{order_id}", tags=["Orders"])
async def cancel_order(order_id: int, symbol: str):
    """Cancel a single order by id (symbol required per Binance spec)."""
    try:
        resp = await _rest.cancel_order(symbol=symbol, order_id=order_id)
    except Exception as exc:
        raise HTTPException(400, f"Binance error: {exc}")
    asyncio.create_task(_sync_account_once())
    return resp


@app.delete("/orders", tags=["Orders"])
async def cancel_all_orders(symbol: str):
    """Cancel every open order on a symbol."""
    try:
        resp = await _rest.cancel_all_orders(symbol)
    except Exception as exc:
        raise HTTPException(400, f"Binance error: {exc}")
    asyncio.create_task(_sync_account_once())
    return resp


# ── Autotrade (Phase 3c) ─────────────────────────────────────────────────────

class AutotradeConfigRequest(BaseModel):
    risk_per_trade_pct:  Optional[float] = None
    default_leverage:    Optional[int]   = None
    attach_bracket:      Optional[bool]  = None
    min_score:           Optional[int]   = None
    cooldown_s:          Optional[int]   = None
    allowed_directions:  Optional[str]   = None   # "BOTH" | "LONG_ONLY" | "SHORT_ONLY"
    mtf_filter_enabled:  Optional[bool]  = None
    mtf_block_neutral:   Optional[bool]  = None


@app.get("/autotrade/status", tags=["Autotrade"])
async def autotrade_status():
    """Full autotrade state: enabled, config, counters, recent decisions."""
    return {
        **_autotrade_state,
        "effective_min_score":   _autotrade_state["min_score"] or settings.min_confluence_score,
        "effective_risk_pct":    _autotrade_state["risk_per_trade_pct"] or settings.risk_per_trade_pct,
    }


@app.post("/autotrade/enable", tags=["Autotrade"])
async def autotrade_enable():
    """Turn autotrade ON. Does NOT close existing positions."""
    if not settings.testnet_mode:
        raise HTTPException(403, "Refusing: TESTNET_MODE=false.")
    _autotrade_state["enabled"]    = True
    _autotrade_state["started_at"] = time.time()
    _autotrade_record({"symbol": "-", "action": "enabled", "reason": "user toggle"})
    logger.warning("AUTOTRADE ENABLED by API request")
    asyncio.create_task(_tg_send("<b>Autotrade ON</b>\nEngine will place trades automatically on ≥min-score signals.", emoji="▶️"))
    return {"enabled": True, "started_at": _autotrade_state["started_at"]}


@app.post("/autotrade/disable", tags=["Autotrade"])
async def autotrade_disable():
    """Turn autotrade OFF. Does NOT close existing positions."""
    _autotrade_state["enabled"] = False
    _autotrade_record({"symbol": "-", "action": "disabled", "reason": "user toggle"})
    logger.warning("AUTOTRADE DISABLED by API request")
    asyncio.create_task(_tg_send("<b>Autotrade OFF</b>\nExisting positions remain open.", emoji="⏸️"))
    return {"enabled": False}


# ── Backtest (Phase 3f) ──────────────────────────────────────────────────────
#
# Replays the full scanner → scorer → entry/exit pipeline over historical
# Binance klines (no live orders placed) and returns win rate, profit factor,
# Sharpe, drawdown, per-trade records. Runs as a background asyncio task so
# the API stays responsive during long backtests.

_backtest_jobs: dict[str, dict] = {}


class BacktestRunRequest(BaseModel):
    pairs:                Optional[list[str]] = None   # defaults to settings.scan_pairs
    timeframe:            str                 = "1h"
    lookback_days:        int                 = 30
    initial_balance:      float               = 10_000.0
    risk_per_trade_pct:   float               = 1.0
    min_confluence_score: float               = 60.0
    commission_pct:       float               = 0.04    # Binance Futures taker
    slippage_pct:         float               = 0.01
    # ATR multipliers — tune SL tightness and TP distance
    atr_sl_mult:          float               = 1.5
    atr_tp1_mult:         float               = 1.5
    atr_tp2_mult:         float               = 3.0
    atr_tp3_mult:         float               = 4.5
    min_rr:               Optional[float]     = None
    # Direction filter: BOTH | LONG_ONLY | SHORT_ONLY
    allowed_directions:   str                 = "BOTH"
    # Multi-timeframe trend filter — require HTF trend to agree with signal
    mtf_filter_enabled:   bool                = False
    mtf_block_neutral:    bool                = True
    mtf_htf_timeframe:    str                 = "4h"


async def _run_backtest(job_id: str, req: BacktestRunRequest) -> None:
    from signals.backtester import Backtester, BacktestConfig

    def _trade_to_dict(t) -> dict:
        return {
            "symbol":        t.symbol,
            "direction":     t.direction.value if hasattr(t.direction, "value") else str(t.direction),
            "entry_price":   t.entry_price,
            "stop_loss":     t.stop_loss,
            "tp1":           t.tp1,
            "tp2":           t.tp2,
            "signal_score":  t.signal_score,
            "entry_bar":     t.entry_bar,
            "exit_bar":      t.exit_bar,
            "exit_price":    t.exit_price,
            "exit_reason":   t.exit_reason,
            "pnl_pct":       t.pnl_pct,
            "pnl_usdt":      t.pnl_usdt,
            "risk_usdt":     t.risk_usdt,
            "rr_achieved":   t.rr_achieved,
            "is_winner":     t.is_winner,
            "bars_held":     t.bars_held,
        }

    job = _backtest_jobs[job_id]
    try:
        cfg = BacktestConfig(
            symbols              = req.pairs or settings.scan_pairs,
            timeframe            = req.timeframe,
            lookback_days        = req.lookback_days,
            initial_balance      = req.initial_balance,
            risk_per_trade_pct   = req.risk_per_trade_pct,
            min_confluence_score = req.min_confluence_score,
            commission_pct       = req.commission_pct,
            slippage_pct         = req.slippage_pct,
            atr_sl_mult          = req.atr_sl_mult,
            atr_tp1_mult         = req.atr_tp1_mult,
            atr_tp2_mult         = req.atr_tp2_mult,
            atr_tp3_mult         = req.atr_tp3_mult,
            min_rr               = req.min_rr,
            allowed_directions   = req.allowed_directions,
            mtf_filter_enabled   = req.mtf_filter_enabled,
            mtf_block_neutral    = req.mtf_block_neutral,
            mtf_htf_timeframe    = req.mtf_htf_timeframe,
        )
        bt = Backtester(cfg)
        job["status"] = "running"
        job["started_at"] = time.time()
        res = await bt.run(_rest)
        job["status"] = "done"
        job["finished_at"] = time.time()
        job["results"] = {
            "config": {
                "symbols":              cfg.symbols,
                "timeframe":            cfg.timeframe,
                "lookback_days":        cfg.lookback_days,
                "initial_balance":      cfg.initial_balance,
                "risk_per_trade_pct":   cfg.risk_per_trade_pct,
                "min_confluence_score": cfg.min_confluence_score,
                "commission_pct":       cfg.commission_pct,
                "slippage_pct":         cfg.slippage_pct,
            },
            "summary": {
                "total_trades":     res.total_trades,
                "winning_trades":   len(res.winning_trades),
                "losing_trades":    len(res.losing_trades),
                "win_rate":         res.win_rate,
                "avg_win_pct":      res.avg_win_pct,
                "avg_loss_pct":     res.avg_loss_pct,
                "profit_factor":    res.profit_factor,
                "total_pnl_usdt":   res.total_pnl_usdt,
                "final_balance":    res.final_balance,
                "total_return_pct": res.total_return_pct,
                "max_drawdown_pct": res.max_drawdown_pct,
                "sharpe_ratio":     res.sharpe_ratio,
                "avg_rr_achieved":  res.avg_rr_achieved,
            },
            "equity_curve": res.equity_curve,
            "trades":       [_trade_to_dict(t) for t in res.trades],
        }
        logger.info(
            "Backtest %s done: %d trades · WR %.1f%% · PF %.2f · DD %.2f%% · Return %.2f%%",
            job_id, res.total_trades, res.win_rate, res.profit_factor,
            res.max_drawdown_pct, res.total_return_pct,
        )
    except Exception as exc:
        job["status"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"
        job["finished_at"] = time.time()
        logger.error("Backtest %s failed: %s", job_id, exc)


@app.post("/backtest/run", tags=["Backtest"])
async def backtest_run(body: BacktestRunRequest):
    """Kick off a backtest job. Returns a job_id; poll /backtest/jobs/{id}."""
    job_id = _gen_client_id("bt")
    _backtest_jobs[job_id] = {
        "job_id":      job_id,
        "status":      "queued",
        "created_at":  time.time(),
        "started_at":  None,
        "finished_at": None,
        "request":     body.model_dump(),
        "results":     None,
        "error":       None,
    }
    asyncio.create_task(_run_backtest(job_id, body))
    return {"job_id": job_id, "status": "queued"}


@app.get("/backtest/jobs", tags=["Backtest"])
async def backtest_list_jobs(limit: int = 20):
    """List the most recent backtest jobs."""
    jobs = sorted(_backtest_jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
    # Return a slim version without the full trade list
    return {
        "jobs": [
            {
                "job_id":      j["job_id"],
                "status":      j["status"],
                "created_at":  j["created_at"],
                "finished_at": j["finished_at"],
                "summary":     (j.get("results") or {}).get("summary"),
                "request":     j["request"],
                "error":       j["error"],
            }
            for j in jobs
        ],
        "count": len(jobs),
    }


@app.get("/backtest/jobs/{job_id}", tags=["Backtest"])
async def backtest_get_job(job_id: str):
    """Get the full state (including trades) for a single backtest job."""
    job = _backtest_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Backtest job {job_id!r} not found")
    return job


@app.delete("/backtest/jobs/{job_id}", tags=["Backtest"])
async def backtest_delete_job(job_id: str):
    """Delete a backtest job from memory."""
    if job_id not in _backtest_jobs:
        raise HTTPException(404, f"Backtest job {job_id!r} not found")
    del _backtest_jobs[job_id]
    return {"deleted": job_id}


# ── Decision journal (invariant #5) ──────────────────────────────────────────

@app.get("/decisions", tags=["Decisions"])
async def list_decisions(
    symbol: Optional[str] = None,
    action: Optional[str] = None,
    limit:  int           = 100,
):
    """Recent gate verdicts (accepts, rejects, skips) — newest first."""
    return {
        "decisions": _decisions.recent(symbol=symbol, action=action, limit=limit),
        "count":     limit,
    }


@app.get("/decisions/stats", tags=["Decisions"])
async def decisions_stats(window_s: int = 24 * 3600):
    """Aggregate action counts + rejection reason histogram over a window."""
    return _decisions.stats(window_s=window_s)


@app.get("/decisions/per-symbol", tags=["Decisions"])
async def decisions_per_symbol():
    """Per-symbol rolling health: accepts/rejects/skips, consec losses,
    daily PnL, pause state. Consumed by the Risk Gate dashboard panel."""
    h = _decisions.per_symbol_health()
    now = time.time()
    for rec in h.values():
        rec["is_paused"]       = (rec.get("paused_until", 0) > now)
        rec["pause_remaining"] = max(0, rec.get("paused_until", 0) - now)
    return {"symbols": h}


@app.post("/decisions/unpause/{symbol}", tags=["Decisions"])
async def unpause_symbol(symbol: str):
    """Clear a per-symbol pause immediately."""
    sym = symbol.upper()
    h = _decisions.symbol_health(sym)
    h.paused_until = 0.0
    h.consecutive_losses = 0
    _autotrade_record({"symbol": sym, "action": "unpause", "reason": "manual"})
    return {"symbol": sym, "ok": True}


# ── Historical klines store (90d rolling) ────────────────────────────────────

@app.get("/historical/stats", tags=["Historical"])
async def historical_stats():
    """Row count + coverage per (symbol, interval) stream + DB size."""
    gs = _klines_store.global_stats()
    return {
        **gs,
        "configured_intervals":   _HISTORICAL_INTERVALS,
        "configured_lookback_d":  _HISTORICAL_LOOKBACK,
        "refresh_interval_s":     _HISTORICAL_REFRESH_S,
    }


@app.get("/historical/klines", tags=["Historical"])
async def historical_klines(
    symbol: str,
    interval: str = "1h",
    since_ms: Optional[int] = None,
    until_ms: Optional[int] = None,
    limit: int = 500,
):
    """Query the local 90-day rolling store — fast, no Binance round-trip."""
    rows = _klines_store.query(
        symbol=symbol, interval=interval,
        since_ms=since_ms, until_ms=until_ms, limit=limit,
    )
    return {
        "symbol":   symbol,
        "interval": interval,
        "count":    len(rows),
        "rows":     rows,
    }


@app.post("/historical/backfill", tags=["Historical"])
async def historical_backfill(lookback_days: int = 90):
    """Force a full backfill (blocking). Rarely needed — runs on startup
    if the DB is empty. Safe to call again (uses INSERT OR IGNORE)."""
    r = await _klines_store.backfill(
        list(settings.scan_pairs), _HISTORICAL_INTERVALS,
        lookback_days=lookback_days,
    )
    return r


@app.post("/historical/refresh", tags=["Historical"])
async def historical_refresh():
    """Force an immediate incremental refresh (normally runs every 15min)."""
    r = await _klines_store.refresh(
        list(settings.scan_pairs), _HISTORICAL_INTERVALS,
        lookback_days=_HISTORICAL_LOOKBACK,
    )
    return r


@app.post("/autotrade/test-alert", tags=["Autotrade"])
async def send_test_telegram():
    """Send a test message to Telegram so the user can verify wiring."""
    enabled = bool(_telegram and getattr(_telegram, "_enabled", False))
    if not enabled:
        return {"sent": False, "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env"}
    await _tg_send("<b>Test alert</b> — Telegram wiring is live.", emoji="🧪")
    return {"sent": True}


@app.get("/autotrade/telegram-diagnose", tags=["Autotrade"])
async def diagnose_telegram():
    """Probe Telegram: verify the bot token, list the recent chat IDs it has
    seen (via getUpdates), and attempt a direct send with the current
    TELEGRAM_CHAT_ID so the dashboard can show the exact error.

    Common issue: if a group was upgraded to a supergroup, the old chat_id
    returns "chat not found" or "migrate to supergroup". Ask a member to
    send any message in the chat — the new ID appears in this response.
    """
    import httpx as _httpx
    token = settings.telegram_bot_token.get_secret_value() if settings.telegram_bot_token else ""
    if not token:
        return {"ok": False, "reason": "TELEGRAM_BOT_TOKEN empty"}
    chat_id = str(settings.telegram_chat_id or "")
    base = f"https://api.telegram.org/bot{token}"
    result: dict = {"configured_chat_id": chat_id}
    async with _httpx.AsyncClient(timeout=10) as c:
        # 1. getMe — is the token live?
        try:
            me = (await c.get(f"{base}/getMe")).json()
            result["bot"] = me.get("result") or me
        except Exception as exc:
            result["bot_error"] = str(exc)

        # 2. getUpdates — any chats that have interacted recently?
        try:
            up = (await c.get(f"{base}/getUpdates", params={"limit": 30})).json()
            chats = {}
            for u in (up.get("result") or [])[-30:]:
                msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or u.get("my_chat_member")
                if not msg or "chat" not in msg:
                    continue
                ch = msg["chat"]
                chats[str(ch.get("id"))] = {
                    "id":    ch.get("id"),
                    "type":  ch.get("type"),
                    "title": ch.get("title") or ch.get("username") or ch.get("first_name"),
                }
            result["seen_chats"] = list(chats.values())
        except Exception as exc:
            result["getUpdates_error"] = str(exc)

        # 3. Try sending to configured chat_id; expose migrate_to_chat_id if Telegram supplies it
        try:
            send = (await c.post(f"{base}/sendMessage", data={
                "chat_id": chat_id,
                "text": "🧪 diagnostic ping (ignore)",
            })).json()
            result["send_response"] = send
            mig = ((send.get("parameters") or {}).get("migrate_to_chat_id"))
            if mig:
                result["migrate_to_chat_id"] = mig
                result["hint"] = f"Telegram reports the chat migrated. Update TELEGRAM_CHAT_ID to {mig} in .env and restart."
        except Exception as exc:
            result["send_error"] = str(exc)

    return result


@app.post("/autotrade/config", tags=["Autotrade"])
async def autotrade_config(body: AutotradeConfigRequest):
    """Live-update autotrade tunables without a restart."""
    changed = {}
    if body.risk_per_trade_pct is not None:
        if not (0.1 <= body.risk_per_trade_pct <= 5):
            raise HTTPException(400, "risk_per_trade_pct must be 0.1..5")
        _autotrade_state["risk_per_trade_pct"] = body.risk_per_trade_pct
        changed["risk_per_trade_pct"] = body.risk_per_trade_pct
    if body.default_leverage is not None:
        if not (1 <= body.default_leverage <= settings.max_leverage):
            raise HTTPException(400, f"default_leverage out of [1..{settings.max_leverage}]")
        _autotrade_state["default_leverage"] = body.default_leverage
        changed["default_leverage"] = body.default_leverage
    if body.attach_bracket is not None:
        _autotrade_state["attach_bracket"] = body.attach_bracket
        changed["attach_bracket"] = body.attach_bracket
    if body.min_score is not None:
        if not (0 <= body.min_score <= 100):
            raise HTTPException(400, "min_score must be 0..100")
        _autotrade_state["min_score"] = body.min_score
        changed["min_score"] = body.min_score
    if body.cooldown_s is not None:
        if body.cooldown_s < 0:
            raise HTTPException(400, "cooldown_s must be ≥ 0")
        _autotrade_state["cooldown_s"] = body.cooldown_s
        changed["cooldown_s"] = body.cooldown_s
    if body.allowed_directions is not None:
        if body.allowed_directions not in ("BOTH", "LONG_ONLY", "SHORT_ONLY"):
            raise HTTPException(400, "allowed_directions must be BOTH, LONG_ONLY, or SHORT_ONLY")
        _autotrade_state["allowed_directions"] = body.allowed_directions
        changed["allowed_directions"] = body.allowed_directions
    if body.mtf_filter_enabled is not None:
        _autotrade_state["mtf_filter_enabled"] = body.mtf_filter_enabled
        changed["mtf_filter_enabled"] = body.mtf_filter_enabled
    if body.mtf_block_neutral is not None:
        _autotrade_state["mtf_block_neutral"] = body.mtf_block_neutral
        changed["mtf_block_neutral"] = body.mtf_block_neutral
    _autotrade_record({"symbol": "-", "action": "config", "reason": str(changed)})
    return {"updated": changed, "state": _autotrade_state}


# ── Live prices (Binance Futures Demo WS mark-price feed) ────────────────────

@app.get("/prices", tags=["Prices"])
async def get_prices():
    """Latest mark price per scan-pair from the demo-fstream WS feed.

    The feed updates once per second per symbol. If `connected=false` in
    `feed`, the dashboard should badge the prices as stale.
    """
    now = time.time()
    snapshot = [
        {
            "symbol":           sym,
            "mark_price":       p["mark_price"],
            "index_price":      p["index_price"],
            "funding_rate":     p["funding_rate"],
            "next_funding_ts":  p["next_funding_ts"],
            "ts":               p["ts"],
            "age_s":            round(now - p["ts"], 2) if p.get("ts") else None,
        }
        for sym, p in _price_cache.items()
    ]
    # Sort to match scan_pairs order, with any extra symbols appended.
    order = {s: i for i, s in enumerate(settings.scan_pairs)}
    snapshot.sort(key=lambda x: order.get(x["symbol"], 999))
    return {
        "feed": {
            "connected":    _price_feed_state["connected"],
            "reconnects":   _price_feed_state["reconnects"],
            "last_msg_at":  _price_feed_state["last_msg_at"],
            "last_msg_age_s": round(now - _price_feed_state["last_msg_at"], 2) if _price_feed_state["last_msg_at"] else None,
            "error":        _price_feed_state["error"],
        },
        "prices":   snapshot,
        "count":    len(snapshot),
    }


@app.get("/liquidations", tags=["Prices"])
async def get_liquidations(symbol: Optional[str] = None, minutes: int = 15):
    """Recent forced-liquidation events from the WS feed.

    `symbol` optional — omit to get a summary across all scan pairs.
    """
    def _summarize(sym: str, evts: list) -> dict:
        sell = sum(e.notional for e in evts if e.side == "SELL")
        buy  = sum(e.notional for e in evts if e.side == "BUY")
        largest = max((e.notional for e in evts), default=0.0)
        return {
            "symbol":        sym,
            "count":         len(evts),
            "sell_notional": round(sell, 2),
            "buy_notional":  round(buy, 2),
            "total_notional":round(sell + buy, 2),
            "largest":       round(largest, 2),
            "dominance":     (
                "SELL" if sell > buy * 1.5 else
                "BUY"  if buy  > sell * 1.5 else
                "MIXED"
            ) if (sell + buy) > 0 else "NONE",
        }

    out: dict = {
        "feed": {
            "connected":     _liq_feed_state["connected"],
            "reconnects":    _liq_feed_state["reconnects"],
            "last_msg_at":   _liq_feed_state["last_msg_at"],
            "last_msg_age_s":round(time.time() - _liq_feed_state["last_msg_at"], 1) if _liq_feed_state["last_msg_at"] else None,
            "total_events":  _liq_feed_state["total_events"],
            "error":         _liq_feed_state["error"],
            "source":        _LIQ_FEED_WS_URL,
            "is_mainnet":    "fstream.binance.com" in _LIQ_FEED_WS_URL and "demo" not in _LIQ_FEED_WS_URL,
        },
        "lookback_minutes":  minutes,
    }

    if symbol:
        sym = symbol.upper()
        evts = _get_recent_liquidations(sym, minutes)
        out["symbol"]   = sym
        out["summary"]  = _summarize(sym, evts)
        out["events"]   = [
            {
                "side":       e.side,
                "qty":        e.qty,
                "price":      e.price,
                "avg_price":  e.avg_price,
                "notional":   round(e.avg_price * e.qty, 2),
                "time":       e.time.isoformat(),
            }
            for e in evts[-100:]    # cap response size
        ]
    else:
        out["by_symbol"] = [
            _summarize(s, _get_recent_liquidations(s, minutes))
            for s in settings.scan_pairs
        ]

    return out


@app.get("/prices/{symbol}", tags=["Prices"])
async def get_price(symbol: str):
    """Latest mark price for a single symbol (404 if not in cache)."""
    sym = symbol.upper()
    p = _price_cache.get(sym)
    if not p:
        raise HTTPException(status_code=404, detail=f"No live price for {sym}; subscribe a scan_pair.")
    now = time.time()
    return {
        "symbol":         sym,
        "mark_price":     p["mark_price"],
        "index_price":    p["index_price"],
        "funding_rate":   p["funding_rate"],
        "next_funding_ts":p["next_funding_ts"],
        "ts":             p["ts"],
        "age_s":          round(now - p["ts"], 2) if p.get("ts") else None,
    }


# ── Signals ──────────────────────────────────────────────────────────────────

@app.get("/signals", tags=["Signals"])
async def get_signals():
    """Return the most recently cached signals + continuous-scan-loop state."""
    now = time.time()
    return {
        "signals":      list(_signal_cache.values()),
        "count":        len(_signal_cache),
        "actionable":   sum(1 for s in _signal_cache.values() if s.get("actionable")),
        "last_scan_at": _last_scan_ts,
        "age_s":        round(now - _last_scan_ts, 1) if _last_scan_ts else None,
        "loop": {
            "running":         _scan_loop_state["running"],
            "scans_total":     _scan_loop_state["scans_total"],
            "scans_failed":    _scan_loop_state["scans_failed"],
            "last_scan_at":    _scan_loop_state["last_scan_at"],
            "next_scan_at":    _scan_loop_state["next_scan_at"],
            "seconds_to_next": round(_scan_loop_state["next_scan_at"] - now, 1) if _scan_loop_state["next_scan_at"] else None,
            "last_duration_ms":_scan_loop_state["last_duration_ms"],
            "last_signals":    _scan_loop_state["last_signals"],
            "last_actionable": _scan_loop_state["last_actionable"],
            "last_error":      _scan_loop_state["last_error"],
            "interval_s":      max(5, int(settings.scan_interval_seconds or 60)),
        },
    }


@app.get("/scan/status", tags=["Signals"])
async def get_scan_status():
    """Health + cadence info for the background scan loop."""
    now = time.time()
    return {
        **_scan_loop_state,
        "age_s":           round(now - _scan_loop_state["last_scan_at"], 1) if _scan_loop_state["last_scan_at"] else None,
        "seconds_to_next": round(_scan_loop_state["next_scan_at"] - now, 1) if _scan_loop_state["next_scan_at"] else None,
        "interval_s":      max(5, int(settings.scan_interval_seconds or 60)),
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
    asyncio.create_task(_tg_send("<b>Circuit breaker reset</b> — trading enabled.", emoji="🟢"))
    return {"message": "Circuit breaker reset.", "state": _circuit.state.value}


async def _cancel_all_working_orders() -> dict:
    """Invariant #4: kill switch cancels working orders.

    Cancels regular open orders AND algo (SL/TP) orders across every symbol
    that has a live position. Runs best-effort — logs errors but does not
    raise, so the breaker trip itself always succeeds.
    """
    cancelled: dict = {"regular": [], "algo": [], "errors": []}
    symbols = set()
    for p in _account_state.get("positions", []):
        if p.get("symbol"):
            symbols.add(p["symbol"])

    # Also include any symbol with open algo orders (position may have closed
    # mid-way leaving an orphan bracket)
    try:
        algo_open = await _rest._request("GET", "/fapi/v1/openAlgoOrders", signed=True)  # type: ignore[attr-defined]
        for o in (algo_open.get("orders") if isinstance(algo_open, dict) else algo_open) or []:
            if o.get("symbol"):
                symbols.add(o["symbol"])
    except Exception as exc:
        cancelled["errors"].append(f"algo list: {exc}")

    for sym in symbols:
        try:
            r = await _rest.cancel_all_orders(sym)
            cancelled["regular"].append({"symbol": sym, "result": r})
        except Exception as exc:
            cancelled["errors"].append(f"cancel_all {sym}: {exc}")
        try:
            # No bulk cancel for algo — cancel each one
            # First list them again scoped to symbol
            algo = await _rest._request(  # type: ignore[attr-defined]
                "GET", "/fapi/v1/openAlgoOrders",
                params={"symbol": sym}, signed=True,
            )
            orders = (algo.get("orders") if isinstance(algo, dict) else algo) or []
            for o in orders:
                try:
                    await _rest._request(  # type: ignore[attr-defined]
                        "DELETE", "/fapi/v1/algoOrder",
                        params={"algoId": o["algoId"]}, signed=True,
                    )
                    cancelled["algo"].append({"symbol": sym, "algoId": o["algoId"]})
                except Exception as ex2:
                    cancelled["errors"].append(f"cancel algo {sym}/{o.get('algoId')}: {ex2}")
        except Exception as exc:
            cancelled["errors"].append(f"algo sweep {sym}: {exc}")

    return cancelled


@app.post("/circuit-breaker/trip", tags=["Risk"])
async def trip_circuit_breaker(body: CircuitBreakerTripRequest):
    """Manually halt trading by tripping the circuit breaker.

    Per docs/risk/risk-framework.md invariant #4, also cancels all working
    orders (regular + algo SL/TP brackets). Existing positions are NOT
    auto-closed — that remains a human call.
    """
    _circuit.trip(body.reason)
    # Mark any currently-OPEN entries as trip-context so /journal/.../trace
    # shows the breaker as the close trigger even if Binance fills later.
    try:
        for e in _journal.entries:
            if e.status == "OPEN" and not e.exit_trigger:
                e.exit_trigger = "killswitch"
        _journal._save()
    except Exception:
        pass
    cancellations = await _cancel_all_working_orders()

    # Journal the trip
    _autotrade_record({
        "symbol": "-", "action": "breaker_trip", "reason": body.reason,
        "extra": {"cancelled": {k: len(v) if isinstance(v, list) else v for k, v in cancellations.items()}},
    })

    asyncio.create_task(_tg_send(
        f"<b>Circuit breaker TRIPPED</b>\n"
        f"Reason: {body.reason}\n"
        f"Autotrade halted. Cancelled "
        f"{len(cancellations['regular'])} open orders + "
        f"{len(cancellations['algo'])} SL/TP brackets.",
        emoji="⛔",
    ))
    return {
        "message":       "Circuit breaker tripped.",
        "reason":        body.reason,
        "state":         _circuit.state.value,
        "cancellations": cancellations,
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
    days: int = Query(default=30, ge=1, le=365),
    include_open: bool = True,
):
    """
    Return journal entries (open + closed) mapped to the dashboard shape.

    The TradeJournal stores entries with {id, symbol, side, regime,
    confidence, entry_price, exit_price, quantity, kelly_usd, pnl_pct,
    pnl_usd, status, opened_at, closed_at, signal_score}. The dashboard
    reads a slightly friendlier shape — we map here.
    """
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    cutoff = _dt.utcnow() - _td(days=days)
    entries = []
    for e in _journal.entries:
        when = e.closed_at if e.status == "CLOSED" else e.opened_at
        try:
            ts = _dt.fromisoformat(when) if when else None
        except Exception:
            ts = None
        if ts and ts < cutoff:
            continue
        if e.status == "OPEN" and not include_open:
            continue

        # Optional duration
        duration_hours = None
        try:
            if e.closed_at and e.opened_at:
                d = _dt.fromisoformat(e.closed_at) - _dt.fromisoformat(e.opened_at)
                duration_hours = d.total_seconds() / 3600.0
        except Exception:
            pass

        entries.append({
            "id":              e.id,
            "symbol":          e.symbol,
            "side":            "LONG" if e.side.upper() == "BUY" else "SHORT",
            "entry_price":     e.entry_price,
            "exit_price":      e.exit_price if e.exit_price else None,
            "qty":             e.quantity,
            "size":            e.quantity,
            "leverage":        e.leverage if getattr(e, "leverage", 0) else None,
            "pnl":             e.pnl_usd if e.status == "CLOSED" else None,
            "pnl_pct":         e.pnl_pct * 100 if e.status == "CLOSED" else None,
            "entry_time":      e.opened_at,
            "exit_time":       e.closed_at or None,
            "duration_hours":  duration_hours,
            "strategy":        getattr(e, "source", "") or e.regime or "—",
            "regime":          e.regime if e.regime and e.regime != "—" else None,
            "reasons":         getattr(e, "reasons", None) or [],
            "notes":           None,
            "status":          e.status,
            "signal_score":    e.signal_score,
            "kelly_usd":       e.kelly_usd,
            # ── full provenance ────────────────────────────────
            "strength":        getattr(e, "strength", "") or None,
            "htf_trend":       getattr(e, "htf_trend", "") or None,
            "scanner_hits":    getattr(e, "scanner_hits", None) or [],
            "indicators_at_entry": getattr(e, "indicators_at_entry", None) or {},
            "entry_client_id": getattr(e, "entry_client_id", "") or None,
            "entry_order_id":  getattr(e, "entry_order_id", 0) or None,
            "entry_submit_ms": getattr(e, "entry_submit_ms", 0) or None,
            "entry_fill_ms":   getattr(e, "entry_fill_ms", 0) or None,
            "slippage_bps":    getattr(e, "slippage_bps", 0.0) or 0.0,
            "sl_price":        getattr(e, "sl_price", 0.0) or None,
            "tp_price":        getattr(e, "tp_price", 0.0) or None,
            "sl_algo_id":      getattr(e, "sl_algo_id", 0) or None,
            "tp_algo_id":      getattr(e, "tp_algo_id", 0) or None,
            "exit_trigger":    getattr(e, "exit_trigger", "") or None,
            "exit_order_id":   getattr(e, "exit_order_id", 0) or None,
            "closed_by":       getattr(e, "closed_by", "") or None,
        })

    # Sort: most recent first (by close time for CLOSED, opened time for OPEN)
    def _key(r):
        return r["exit_time"] or r["entry_time"] or ""
    entries.sort(key=_key, reverse=True)

    return {
        "entries":    entries,
        "count":      len(entries),
        "closed":     sum(1 for r in entries if r["status"] == "CLOSED"),
        "open":       sum(1 for r in entries if r["status"] == "OPEN"),
        "days":       days,
        "timestamp":  time.time(),
    }


@app.get("/journal/{entry_id}/trace", tags=["Journal"])
async def get_trade_trace(entry_id: str):
    """Full provenance trace for one trade.

    Returns:
      * `entry` — the JournalEntry with every field (signal origin, entry
        order ID + submit/fill times + slippage, bracket algo IDs, exit
        trigger + reason)
      * `decisions` — every DecisionJournal event for this symbol between
        opened_at and closed_at (or opened_at → now for OPEN trades).
        Lets you see the signal that preceded the entry, any rejections
        that happened around the same time, and the close event.
      * `algo_orders` — current live algo orders for the symbol (so you
        can see if the bracket is still armed or already filled).
    """
    # 1. Find the journal entry
    match = None
    for e in _journal.entries:
        if e.id == entry_id:
            match = e; break
    if not match:
        raise HTTPException(404, f"journal entry {entry_id!r} not found")

    entry_dict = asdict(match)

    # 2. Window for decisions: opened_at → (closed_at OR now)
    from datetime import datetime as _dt, timezone as _tz
    try:
        open_ts = _dt.fromisoformat(match.opened_at).replace(tzinfo=_tz.utc).timestamp()
    except Exception:
        open_ts = 0.0
    try:
        close_ts = _dt.fromisoformat(match.closed_at).replace(tzinfo=_tz.utc).timestamp() if match.closed_at else time.time()
    except Exception:
        close_ts = time.time()
    # Pad 5 minutes on each side to catch the pre-signal + post-close logs
    pad = 5 * 60
    window_lo = open_ts - pad
    window_hi = close_ts + pad

    # 3. Pull matching decisions from the in-memory cache
    all_dec = _decisions.recent(symbol=match.symbol, limit=1000)
    in_window = [
        d for d in all_dec
        if window_lo <= d.get("ts", 0) <= window_hi
    ]

    # 4. Current live algo orders on the symbol (best-effort — may fail if
    #    Binance is slow; not fatal for trace reconstruction).
    algo_open = []
    try:
        resp = await _rest._request(  # type: ignore[attr-defined]
            "GET", "/fapi/v1/openAlgoOrders",
            params={"symbol": match.symbol}, signed=True,
        )
        algo_open = (resp.get("orders") if isinstance(resp, dict) else resp) or []
    except Exception as exc:
        algo_open = [{"error": f"algo fetch: {exc}"}]

    return {
        "entry":        entry_dict,
        "decisions":    in_window,
        "algo_orders":  algo_open,
        "window": {
            "lo_ts":  window_lo,
            "hi_ts":  window_hi,
            "span_s": round(window_hi - window_lo, 1),
        },
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
