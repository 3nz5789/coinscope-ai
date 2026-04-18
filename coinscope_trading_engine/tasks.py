"""
tasks.py — Celery Task Definitions
===================================
Offloads heavy or slow work from the main asyncio event loop to
background Celery workers running in separate processes.

Tasks are intentionally synchronous here (Celery workers run in
their own processes / threads), but they call async engine helpers
via asyncio.run() where needed.

Available tasks
---------------
  run_scan_cycle()          — full scan of all pairs
  run_regime_detection()    — HMM regime update for all tracked symbols
  run_price_prediction()    — LSTM next-bar prediction per symbol
  run_anomaly_detection()   — statistical anomaly scan
  dispatch_telegram_alert() — send a Telegram message
  dispatch_webhook_alert()  — POST to webhook URLs
  send_daily_summary()      — send the 24h summary alert
  backtest_symbol()         — run backtester on a symbol

Retry policy
------------
  All tasks retry up to MAX_RETRIES times with exponential backoff.
  Permanent failures are sent to the dead-letter queue (DLQ) in Redis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import hashlib
import time
from typing import Optional

from celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alert singleton
# ---------------------------------------------------------------------------
# A single TelegramNotifier is created once per worker process.
# Re-using it means the in-process dedup cache is shared across all
# dispatch_telegram_alert calls in this worker — preventing duplicates
# caused by task re-delivery after a transient failure.
_notifier: "Optional[object]" = None   # typed as object to avoid circular import at module load

def _get_notifier():
    """Lazy singleton: import + instantiate TelegramNotifier once per worker."""
    global _notifier
    if _notifier is None:
        from alerts.telegram_notifier import TelegramNotifier
        _notifier = TelegramNotifier()
    return _notifier


MAX_RETRIES   = 3
RETRY_BACKOFF = 5   # seconds (doubles each retry)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _get_rest():
    """Return a configured BinanceRESTClient."""
    from config import settings
    from data.binance_rest import BinanceRESTClient
    return BinanceRESTClient(
        api_key    = settings.active_api_key,
        api_secret = settings.active_api_secret,
        testnet    = settings.testnet_mode,
    )


def _send_to_dlq(task_name: str, args: dict, error: str) -> None:
    """Push a failed task payload to Redis DLQ for manual inspection."""
    try:
        import redis
        from config import settings
        r = redis.from_url(settings.redis_url)
        r.lpush("coinscopeai:dlq", json.dumps({
            "task":      task_name,
            "args":      args,
            "error":     error,
            "failed_at": time.time(),
        }))
        logger.warning("Task '%s' sent to DLQ: %s", task_name, error)
    except Exception as exc:
        logger.error("Could not write to DLQ: %s", exc)


# ---------------------------------------------------------------------------
# Scan tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name    = "tasks.run_scan_cycle",
    bind    = True,
    max_retries = MAX_RETRIES,
)
def run_scan_cycle(self, pairs: Optional[list] = None):
    """
    Run a full confluence scan for all (or specified) pairs.

    Returns a list of signal dicts for any actionable hits.
    """
    try:
        from config import settings
        from data.data_normalizer import DataNormalizer
        from scanner.pattern_scanner import PatternScanner
        from scanner.volume_scanner import VolumeScanner
        from scanner.funding_rate_scanner import FundingRateScanner
        from signals.confluence_scorer import ConfluenceScorer
        from signals.entry_exit_calculator import EntryExitCalculator

        target_pairs = pairs or settings.scan_pairs
        rest         = _get_rest()
        norm         = DataNormalizer()
        scanners     = [PatternScanner(), VolumeScanner(rest_client=rest, cache=None)]
        scorer       = ConfluenceScorer(min_score=settings.min_confluence_score)
        calc         = EntryExitCalculator()

        async def _scan_all():
            signals = []
            for symbol in target_pairs:
                try:
                    raw     = await rest.get_klines(symbol, "1h", limit=100)
                    candles = norm.klines_to_candles(symbol, "1h", raw)
                    if len(candles) < 30:
                        continue
                    results = []
                    for sc in scanners:
                        r = await sc.scan(symbol)
                        results.append(r)
                    signal = scorer.score(symbol, results, candles)
                    if signal and signal.is_actionable:
                        setup = calc.calculate(signal, candles)
                        signals.append({
                            "symbol":    symbol,
                            "direction": signal.direction.value,
                            "score":     round(signal.score, 2),
                            "strength":  signal.strength,
                            "entry":     setup.entry if setup.valid else None,
                            "sl":        setup.stop_loss if setup.valid else None,
                            "tp2":       setup.tp2 if setup.valid else None,
                        })
                except Exception as exc:
                    logger.warning("Scan error %s: %s", symbol, exc)
            return signals

        signals = _run(_scan_all())
        logger.info("Celery scan_cycle: %d signals from %d pairs.", len(signals), len(target_pairs))
        return signals

    except Exception as exc:
        logger.error("run_scan_cycle error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _send_to_dlq("run_scan_cycle", {"pairs": pairs}, str(exc))
            return []


# ---------------------------------------------------------------------------
# ML tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name    = "tasks.run_regime_detection",
    bind    = True,
    max_retries = MAX_RETRIES,
    queue   = "ml_tasks",
)
def run_regime_detection(self, symbols: Optional[list] = None):
    """
    Detect HMM market regime for each symbol.
    Returns {symbol: regime_label} dict.
    """
    try:
        from config import settings
        from data.data_normalizer import DataNormalizer
        from models.regime_detector import RegimeDetector

        target  = symbols or settings.scan_pairs
        rest    = _get_rest()
        norm    = DataNormalizer()
        det     = RegimeDetector()

        async def _detect():
            results = {}
            for sym in target:
                try:
                    raw     = await rest.get_klines(sym, "1h", limit=150)
                    candles = norm.klines_to_candles(sym, "1h", raw)
                    r       = det.detect(candles)
                    results[sym] = {
                        "regime":     r.regime.value,
                        "confidence": r.confidence,
                    }
                except Exception as exc:
                    logger.warning("Regime detection failed %s: %s", sym, exc)
            return results

        results = _run(_detect())
        logger.info("Celery regime_detection: %d symbols processed.", len(results))
        return results

    except Exception as exc:
        logger.error("run_regime_detection error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _send_to_dlq("run_regime_detection", {"symbols": symbols}, str(exc))
            return {}


@celery_app.task(
    name    = "tasks.run_price_prediction",
    bind    = True,
    max_retries = 1,
    queue   = "ml_tasks",
)
def run_price_prediction(self, symbol: str, timeframe: str = "1h"):
    """
    Run LSTM price direction prediction for a single symbol.
    Returns {"direction": "UP"|"DOWN"|"NEUTRAL", "confidence": float}.
    """
    try:
        from data.data_normalizer import DataNormalizer
        from models.price_predictor import PricePredictor

        rest    = _get_rest()
        norm    = DataNormalizer()
        pred    = PricePredictor()

        async def _predict():
            raw     = await rest.get_klines(symbol, timeframe, limit=200)
            candles = norm.klines_to_candles(symbol, timeframe, raw)
            pred.train(candles)
            result = pred.predict(candles)
            return {
                "symbol":     symbol,
                "direction":  result.direction.value if result else "UNKNOWN",
                "confidence": result.confidence      if result else 0.0,
            }

        return _run(_predict())

    except Exception as exc:
        logger.error("run_price_prediction(%s) error: %s", symbol, exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF)
        except self.MaxRetriesExceededError:
            _send_to_dlq("run_price_prediction", {"symbol": symbol}, str(exc))
            return {}


@celery_app.task(
    name    = "tasks.run_anomaly_detection",
    bind    = True,
    max_retries = MAX_RETRIES,
    queue   = "ml_tasks",
)
def run_anomaly_detection(self, symbols: Optional[list] = None):
    """
    Run statistical anomaly detection for all symbols.
    Returns {symbol: {"is_anomaly": bool, "severity": str}} dict.
    """
    try:
        from config import settings
        from data.data_normalizer import DataNormalizer
        from models.anomaly_detector import AnomalyDetector

        target  = symbols or settings.scan_pairs
        rest    = _get_rest()
        norm    = DataNormalizer()
        det     = AnomalyDetector()

        async def _detect():
            results = {}
            for sym in target:
                try:
                    raw     = await rest.get_klines(sym, "1h", limit=60)
                    candles = norm.klines_to_candles(sym, "1h", raw)
                    report  = det.check(candles)
                    results[sym] = {
                        "is_anomaly":    report.is_anomaly,
                        "severity":      report.severity,
                        "anomaly_types": report.anomaly_types,
                    }
                except Exception as exc:
                    logger.warning("Anomaly detection failed %s: %s", sym, exc)
            return results

        return _run(_detect())

    except Exception as exc:
        logger.error("run_anomaly_detection error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _send_to_dlq("run_anomaly_detection", {"symbols": symbols}, str(exc))
            return {}


# ---------------------------------------------------------------------------
# Alert tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name       = "tasks.dispatch_telegram_alert",
    bind       = True,
    max_retries = 1,        # reduced: dedup in notifier handles most cases
    queue      = "alerts",
    rate_limit = "20/m",
    acks_late  = False,     # ACK immediately — prevents re-delivery on worker crash
                            # which was the primary cause of duplicate messages
)
def dispatch_telegram_alert(self, message: str, parse_mode: str = "HTML"):
    """
    Send a pre-formatted message to Telegram via the module-level singleton.

    Design notes
    ------------
    * acks_late=False  — Task is ACKed before execution so Celery never
      re-queues it if the worker dies mid-send.  Combined with the notifier's
      in-process dedup cache this eliminates the main duplicate-send path.
    * Singleton notifier — _get_notifier() returns the same TelegramNotifier
      instance for the lifetime of the worker process, so the dedup cache
      persists across task invocations.
    * Idempotent task_id — callers should submit with a deterministic task_id
      (message hash + minute bucket) so Celery's result backend rejects
      duplicate submissions within the same minute.
    """
    try:
        notifier = _get_notifier()

        async def _send():
            return await notifier._send_message(message, parse_mode=parse_mode)

        ok = _run(_send())
        # _send_message returns True even for dedup-suppressed messages,
        # so False genuinely means a delivery failure.
        if not ok:
            raise RuntimeError("Telegram send returned False")
        return {"sent": True, "chars": len(message)}

    except Exception as exc:
        logger.error("dispatch_telegram_alert error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _send_to_dlq("dispatch_telegram_alert",
                         {"chars": len(message)}, str(exc))
            return {"sent": False, "error": str(exc)}


@celery_app.task(
    name    = "tasks.dispatch_webhook_alert",
    bind    = True,
    max_retries = MAX_RETRIES,
    queue   = "alerts",
)
def dispatch_webhook_alert(self, payload: dict, alert_type: str = "signal"):
    """POST an alert payload to all configured webhook URLs."""
    try:
        from alerts.webhook_dispatcher import WebhookDispatcher

        async def _dispatch():
            dispatcher = WebhookDispatcher()
            return await dispatcher._dispatch_all(alert_type, payload)

        results = _run(_dispatch())
        succeeded = sum(1 for v in results.values() if v)
        return {"dispatched": succeeded, "total": len(results)}

    except Exception as exc:
        logger.error("dispatch_webhook_alert error: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            _send_to_dlq("dispatch_webhook_alert",
                         {"type": alert_type}, str(exc))
            return {"dispatched": 0, "error": str(exc)}


@celery_app.task(
    name    = "tasks.send_daily_summary",
    bind    = True,
    max_retries = 1,
    queue   = "alerts",
)
def send_daily_summary(self):
    """Send the 24h trading summary to all configured alert channels."""
    try:
        notifier = _get_notifier()   # reuse singleton — shares dedup cache

        async def _send():
            return await notifier.send_daily_summary(
                total_signals = 0,
                actionable    = 0,
                top_signals   = [],
            )

        _run(_send())
        return {"sent": True}

    except Exception as exc:
        logger.error("send_daily_summary error: %s", exc)
        return {"sent": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Backtest task
# ---------------------------------------------------------------------------

@celery_app.task(
    name    = "tasks.backtest_symbol",
    bind    = True,
    max_retries = 1,
    queue   = "ml_tasks",
    time_limit = 300,   # 5-min hard limit
)
def backtest_symbol(self, symbol: str, lookback_days: int = 30):
    """
    Run the event-driven backtester for a single symbol and return results.
    """
    try:
        from signals.backtester import Backtester, BacktestConfig

        rest = _get_rest()

        async def _run_bt():
            cfg  = BacktestConfig(
                symbols      = [symbol],
                timeframe    = "1h",
                lookback_days = lookback_days,
            )
            bt      = Backtester(config=cfg)
            results = await bt.run(rest)
            return results.summary()

        return _run(_run_bt())

    except Exception as exc:
        logger.error("backtest_symbol(%s) error: %s", symbol, exc)
        try:
            raise self.retry(exc=exc, countdown=RETRY_BACKOFF)
        except self.MaxRetriesExceededError:
            return {"error": str(exc)}
