"""
main.py — CoinScopeAI Engine Orchestrator
==========================================
Single asyncio event loop that wires every module together:

  WebSocket feeds  →  Data queue
  Data queue       →  5 Scanners  →  ConfluenceScorer  →  EntryExitCalculator
  Signal           →  RiskGate (CircuitBreaker + ExposureTracker + CorrelationAnalyzer)
  Approved signal  →  AlertQueue  →  Telegram + Webhook
  Background       →  RegimeDetector, AnomalyDetector, SentimentAnalyzer
  Scheduler        →  Daily summary, daily PnL reset

Run
---
    python main.py                  # mainnet (requires BINANCE_API_KEY in .env)
    python main.py --testnet        # override to testnet
    python main.py --dry-run        # scan only, no alerts sent

Docker
------
    docker compose up               # see docker-compose.yml
"""

from __future__ import annotations

import argparse
import asyncio
import signal as os_signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.binance_websocket import BinanceWebSocketManager
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer, Candle

from scanner.volume_scanner import VolumeScanner
from scanner.liquidation_scanner import LiquidationScanner
from scanner.funding_rate_scanner import FundingRateScanner
from scanner.pattern_scanner import PatternScanner
from scanner.orderbook_scanner import OrderBookScanner
from scanner.base_scanner import SignalDirection

from signals.indicator_engine import IndicatorEngine
from signals.confluence_scorer import ConfluenceScorer
from signals.entry_exit_calculator import EntryExitCalculator

from alerts.telegram_notifier import TelegramNotifier
from alerts.webhook_dispatcher import WebhookDispatcher
from alerts.alert_queue import AlertQueue, AlertPriority
from alerts.rate_limiter import AlertRateLimiter

from risk.position_sizer import PositionSizer
from risk.exposure_tracker import ExposureTracker
from risk.correlation_analyzer import CorrelationAnalyzer
from risk.circuit_breaker import CircuitBreaker

from models.regime_detector import RegimeDetector, MarketRegime
from models.sentiment_analyzer import SentimentAnalyzer
from models.anomaly_detector import AnomalyDetector

from utils.logger import get_logger, setup_logging
from utils.helpers import safe_divide
from monitoring.prometheus_metrics import metrics, start_metrics_server

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANDLE_CACHE_LIMIT  = 200   # bars kept per symbol
SCAN_INTERVAL_S     = settings.scan_interval_seconds
HEALTH_CHECK_S      = 30
DAILY_SUMMARY_S     = 86_400   # 24 h
REGIME_CHECK_S      = 300      # 5 min


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class CoinScopeEngine:
    """
    Top-level orchestrator.  Owns all components and coordinates the
    asyncio tasks that make up the scanner pipeline.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self._dry_run = dry_run
        self._running = False
        self._start_time: float = 0.0

        # ── Exchange layer ────────────────────────────────────────────
        self._rest    = BinanceRESTClient(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = settings.testnet_mode,
        )
        self._ws      = BinanceWebSocketManager(
            api_key    = settings.active_api_key,
            api_secret = settings.active_api_secret,
            testnet    = settings.testnet_mode,
        )
        self._cache   = CacheManager(url=settings.redis_url)
        self._norm    = DataNormalizer()

        # ── Candle store {symbol: [Candle, ...]} ──────────────────────
        self._candles: dict[str, list[Candle]] = {}

        # ── Scanners ──────────────────────────────────────────────────
        self._scanners = [
            VolumeScanner(rest_client=self._rest,  cache=self._cache),
            LiquidationScanner(),
            FundingRateScanner(rest_client=self._rest, cache=self._cache),
            PatternScanner(),
            OrderBookScanner(),
        ]

        # ── Signal layer ──────────────────────────────────────────────
        self._indicator_engine    = IndicatorEngine()
        self._confluence_scorer   = ConfluenceScorer(
            min_score=settings.min_confluence_score
        )
        self._entry_exit_calc     = EntryExitCalculator()

        # ── Alerts ────────────────────────────────────────────────────
        self._notifier    = TelegramNotifier()
        self._dispatcher  = WebhookDispatcher()
        self._rate_limiter = AlertRateLimiter()
        self._alert_queue = AlertQueue(
            notifier   = self._notifier,
            dispatcher = self._dispatcher if not dry_run else None,
        )

        # ── Risk ──────────────────────────────────────────────────────
        self._position_sizer  = PositionSizer()
        self._exposure_tracker = ExposureTracker(balance=0.0)
        self._correlation     = CorrelationAnalyzer()
        self._circuit_breaker = CircuitBreaker(
            on_trip       = self._on_circuit_trip,
            reset_after_s = 3_600,   # 1 h auto-reset
        )

        # ── ML / statistical models ───────────────────────────────────
        self._regime_detector  = RegimeDetector()
        self._sentiment        = SentimentAnalyzer()
        self._anomaly_detector = AnomalyDetector()

        # ── Runtime stats ─────────────────────────────────────────────
        self._scan_count     = 0
        self._signal_count   = 0
        self._alert_count    = 0
        self._last_regime:  dict[str, MarketRegime] = {}

        # ── Async task references ─────────────────────────────────────
        self._tasks: list[asyncio.Task] = []

    # ====================================================================
    # Lifecycle
    # ====================================================================

    async def start(self) -> None:
        self._running    = True
        self._start_time = time.monotonic()

        setup_logging()
        logger.info("=" * 60)
        logger.info("CoinScopeAI Engine starting  [dry_run=%s]", self._dry_run)
        logger.info("Pairs : %s", settings.scan_pairs)
        logger.info("Mode  : %s", "TESTNET" if settings.testnet_mode else "MAINNET")
        logger.info("=" * 60)

        try:
            await self._init_connections()
            await self._alert_queue.start()
            await self._warm_candle_cache()

            if not self._dry_run:
                await self._alert_queue.enqueue_startup()

            self._tasks = [
                asyncio.create_task(self._ws_feed_loop(),        name="ws_feed"),
                asyncio.create_task(self._scan_loop(),           name="scanner"),
                asyncio.create_task(self._regime_loop(),         name="regime"),
                asyncio.create_task(self._health_loop(),         name="health"),
                asyncio.create_task(self._daily_summary_loop(),  name="daily"),
            ]

            start_metrics_server(port=9090)
            logger.info("All tasks started. Engine is live.")
            await asyncio.gather(*self._tasks, return_exceptions=True)

        except Exception as exc:
            logger.critical("Engine fatal error: %s", exc, exc_info=True)
        finally:
            await self.stop()

    async def stop(self) -> None:
        logger.info("Engine shutting down…")
        self._running = False

        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        await self._alert_queue.stop(drain=True)

        if self._ws:
            await self._ws.disconnect()
        if self._cache:
            await self._cache.close()

        elapsed = time.monotonic() - self._start_time
        logger.info(
            "Engine stopped. uptime=%.0fs scans=%d signals=%d alerts=%d",
            elapsed, self._scan_count, self._signal_count, self._alert_count,
        )

    # ====================================================================
    # Initialisation helpers
    # ====================================================================

    async def _init_connections(self) -> None:
        """Verify API + Redis connectivity."""
        logger.info("Connecting to Binance …")
        ok = await self._rest.ping()
        if not ok:
            raise RuntimeError("Binance REST ping failed — check API keys / connectivity.")
        logger.info("Binance REST: OK")

        try:
            await self._cache.ping()
            logger.info("Redis cache: OK")
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — running without cache.", exc)

        # Seed account balance
        try:
            balance = await self._rest.get_account_balance()
            usdt_balance = next(
                (float(b["balance"]) for b in balance if b.get("asset") == "USDT"),
                1_000.0,
            )
            self._exposure_tracker.update_balance(usdt_balance)
            logger.info("Account balance: %.2f USDT", usdt_balance)
        except Exception as exc:
            logger.warning("Could not fetch account balance: %s", exc)

    async def _warm_candle_cache(self) -> None:
        """Pre-fetch recent candles for all pairs before scanning starts."""
        logger.info("Warming candle cache for %d pairs…", len(settings.scan_pairs))
        tasks = [self._fetch_candles(sym) for sym in settings.scan_pairs]
        await asyncio.gather(*tasks, return_exceptions=True)
        loaded = sum(1 for sym in settings.scan_pairs if sym in self._candles)
        logger.info("Candle cache warm: %d/%d pairs loaded.", loaded, len(settings.scan_pairs))

    async def _fetch_candles(self, symbol: str) -> None:
        try:
            raw = await self._rest.get_klines(
                symbol, "1h", limit=CANDLE_CACHE_LIMIT
            )
            candles = self._norm.klines_to_candles(symbol, "1h", raw)
            self._candles[symbol] = candles
            self._correlation.update_prices(symbol, [c.close for c in candles])
        except Exception as exc:
            logger.warning("Candle warm failed for %s: %s", symbol, exc)

    # ====================================================================
    # WebSocket feed loop
    # ====================================================================

    async def _ws_feed_loop(self) -> None:
        """
        Subscribe to kline streams for all pairs and update the local
        candle store as bars close.
        """
        logger.info("WebSocket feed loop starting…")
        streams = [f"{sym.lower()}@kline_1h" for sym in settings.scan_pairs]

        reconnect_delay = 2.0
        while self._running:
            try:
                await self._ws.connect()
                async for event in self._ws.stream(streams):
                    if not self._running:
                        break
                    await self._handle_ws_event(event)
                reconnect_delay = 2.0  # reset on clean exit
            except Exception as exc:
                logger.warning(
                    "WebSocket disconnected: %s — reconnecting in %.0fs",
                    exc, reconnect_delay,
                )
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

    async def _handle_ws_event(self, event: dict) -> None:
        """Process a single WS kline event into the candle store."""
        try:
            candle = self._norm.ws_kline_to_candle(event)
            if candle is None:
                return
            symbol = candle.symbol
            if symbol not in self._candles:
                self._candles[symbol] = []
            buf = self._candles[symbol]
            if candle.is_closed:
                buf.append(candle)
                if len(buf) > CANDLE_CACHE_LIMIT:
                    buf.pop(0)
                # Update correlation feed
                self._correlation.append_price(symbol, candle.close)
        except Exception as exc:
            logger.debug("WS event handling error: %s", exc)

    # ====================================================================
    # Main scan loop
    # ====================================================================

    async def _scan_loop(self) -> None:
        """
        Every SCAN_INTERVAL_S seconds:
          1. Run all 5 scanners on every pair (concurrently).
          2. Score results through ConfluenceScorer.
          3. Calculate entry/exit levels.
          4. Gate through risk checks.
          5. Enqueue approved signals.
        """
        logger.info("Scan loop starting (interval=%ds).", SCAN_INTERVAL_S)
        while self._running:
            loop_start = time.monotonic()
            try:
                await self._run_one_scan_cycle()
            except Exception as exc:
                logger.error("Scan cycle error: %s", exc, exc_info=True)
            elapsed = time.monotonic() - loop_start
            await asyncio.sleep(max(0, SCAN_INTERVAL_S - elapsed))

    async def _run_one_scan_cycle(self) -> None:
        self._scan_count += 1
        metrics.scans_total.inc()

        # Circuit breaker gate
        if self._circuit_breaker.is_open:
            logger.warning("Circuit breaker OPEN — scan skipped.")
            return

        # Evaluate risk metrics
        self._circuit_breaker.check(
            daily_loss_pct     = self._exposure_tracker.daily_loss_pct,
            drawdown_pct       = max(0, -self._exposure_tracker.daily_loss_pct),
            consecutive_losses = 0,
        )

        pairs  = settings.scan_pairs
        logger.debug("Scan #%d  pairs=%d", self._scan_count, len(pairs))

        # Run all scanners on all pairs in parallel
        all_results: dict[str, list] = {}
        scan_tasks = []
        for symbol in pairs:
            for scanner in self._scanners:
                scan_tasks.append((symbol, scanner, asyncio.create_task(
                    scanner.scan(symbol)
                )))

        for symbol, scanner, task in scan_tasks:
            try:
                result = await task
                all_results.setdefault(symbol, []).append(result)
            except Exception as exc:
                logger.debug("Scanner %s/%s error: %s", type(scanner).__name__, symbol, exc)

        # Score each symbol
        for symbol, results in all_results.items():
            candles = self._candles.get(symbol, [])
            if len(candles) < 30:
                continue

            signal = self._confluence_scorer.score(symbol, results, candles)
            if signal is None or not signal.is_actionable:
                continue

            self._signal_count += 1
            metrics.signals_total.labels(direction=signal.direction.value).inc()
            metrics.signal_score.observe(signal.score)

            # Rate-limit: skip if symbol or Telegram is throttled
            if not self._rate_limiter.allow_signal(symbol):
                logger.debug("Signal for %s rate-limited.", symbol)
                continue

            # Anomaly check — skip if extreme anomaly
            anomaly = self._anomaly_detector.check(candles)
            if anomaly.is_anomaly and anomaly.severity == "HIGH":
                logger.info(
                    "Skipping %s signal — HIGH anomaly: %s",
                    symbol, anomaly.anomaly_types,
                )
                continue

            # Correlation gate
            safe, reason = self._correlation.is_safe_to_add(
                symbol, signal.direction, self._exposure_tracker.open_positions
            )
            if not safe:
                logger.info("Correlation gate blocked %s: %s", symbol, reason)
                continue

            # Entry/exit levels
            setup = self._entry_exit_calc.calculate(signal, candles)
            if not setup.valid:
                logger.debug("Setup invalid for %s: %s", symbol, setup.invalid_reason)
                continue

            # Position sizing
            pos_size = self._position_sizer.calculate(
                setup, self._exposure_tracker._balance
            )
            if not pos_size.valid:
                continue

            # Determine alert priority from signal strength
            priority = (
                AlertPriority.HIGH
                if signal.strength in ("STRONG", "VERY_STRONG")
                else AlertPriority.NORMAL
            )

            if not self._dry_run:
                await self._alert_queue.enqueue_signal(signal, setup, priority=priority)
                self._alert_count += 1
                metrics.alerts_total.labels(channel="telegram").inc()

            logger.info(
                "✅ Signal | %s %s score=%.1f | entry=%.4f sl=%.4f tp2=%.4f | %s",
                symbol, signal.direction.value, signal.score,
                setup.entry, setup.stop_loss, setup.tp2,
                "DRY-RUN" if self._dry_run else "QUEUED",
            )

    # ====================================================================
    # Regime / sentiment loop
    # ====================================================================

    async def _regime_loop(self) -> None:
        """Detect market regime for each pair every REGIME_CHECK_S seconds."""
        logger.info("Regime loop starting (interval=%ds).", REGIME_CHECK_S)
        while self._running:
            await asyncio.sleep(REGIME_CHECK_S)
            try:
                for symbol, candles in self._candles.items():
                    if len(candles) < 50:
                        continue
                    result = self._regime_detector.detect(candles)
                    prev   = self._last_regime.get(symbol)
                    if prev and prev != result.regime:
                        logger.info(
                            "Regime change %s: %s → %s (conf=%.2f)",
                            symbol, prev.value, result.regime.value, result.confidence,
                        )
                    self._last_regime[symbol] = result.regime
            except Exception as exc:
                logger.warning("Regime loop error: %s", exc)

    # ====================================================================
    # Health monitor
    # ====================================================================

    async def _health_loop(self) -> None:
        logger.info("Health monitor starting (interval=%ds).", HEALTH_CHECK_S)
        while self._running:
            await asyncio.sleep(HEALTH_CHECK_S)
            try:
                dead = [t.get_name() for t in self._tasks if t.done() and not t.cancelled()]
                if dead:
                    logger.error("Dead tasks detected: %s", dead)

                exp_snap = self._exposure_tracker.snapshot()
                cb_status = self._circuit_breaker.status()
                logger.info(
                    "Health | scans=%d signals=%d alerts=%d | "
                    "positions=%d exposure=%.1f%% daily_pnl=%.2f | "
                    "breaker=%s queue=%d",
                    self._scan_count, self._signal_count, self._alert_count,
                    exp_snap["position_count"], exp_snap["total_exposure_pct"],
                    exp_snap["daily_pnl"],
                    cb_status["state"],
                    self._alert_queue.queue_size,
                )
                metrics.update_from_engine(self.status())
            except Exception as exc:
                logger.warning("Health loop error: %s", exc)

    # ====================================================================
    # Daily summary
    # ====================================================================

    async def _daily_summary_loop(self) -> None:
        """Send daily summary and reset daily PnL at midnight UTC."""
        logger.info("Daily summary loop starting.")
        while self._running:
            await asyncio.sleep(DAILY_SUMMARY_S)
            try:
                if not self._dry_run:
                    await self._alert_queue.enqueue_daily_summary(
                        total_signals = self._signal_count,
                        actionable    = self._alert_count,
                        top_signals   = [],
                    )
                # Reset daily counters
                self._exposure_tracker.reset_daily_pnl()
                self._circuit_breaker.reset_daily()
                self._signal_count = 0
                self._alert_count  = 0
                logger.info("Daily reset complete.")
            except Exception as exc:
                logger.warning("Daily summary error: %s", exc)

    # ====================================================================
    # Circuit breaker callback
    # ====================================================================

    async def _on_circuit_trip(self, reason: str, daily_loss_pct: float) -> None:
        if not self._dry_run:
            await self._alert_queue.enqueue_circuit_breaker(reason, daily_loss_pct)

    # ====================================================================
    # Public status (used by api.py)
    # ====================================================================

    def status(self) -> dict:
        uptime = round(time.monotonic() - self._start_time) if self._start_time else 0
        return {
            "running":       self._running,
            "dry_run":       self._dry_run,
            "testnet":       settings.testnet_mode,
            "uptime_s":      uptime,
            "scan_count":    self._scan_count,
            "signal_count":  self._signal_count,
            "alert_count":   self._alert_count,
            "pairs":         settings.scan_pairs,
            "circuit_breaker": self._circuit_breaker.status(),
            "exposure":      self._exposure_tracker.snapshot(),
            "alert_queue":   self._alert_queue.stats(),
            "rate_limiter":  self._rate_limiter.stats(),
            "regimes": {
                sym: reg.value
                for sym, reg in self._last_regime.items()
            },
        }

    def reset_circuit_breaker(self) -> None:
        self._circuit_breaker.reset()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CoinScopeAI Trading Engine")
    parser.add_argument("--testnet",  action="store_true", help="Force testnet mode")
    parser.add_argument("--dry-run",  action="store_true", help="Scan only, no alerts")
    return parser.parse_args()


async def _async_main() -> None:
    args = _parse_args()

    if args.testnet:
        import os
        os.environ["TESTNET_MODE"] = "true"

    engine = CoinScopeEngine(dry_run=args.dry_run)

    loop = asyncio.get_running_loop()

    def _shutdown(*_):
        logger.info("Shutdown signal received.")
        asyncio.create_task(engine.stop())

    for sig in (os_signal.SIGINT, os_signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except (NotImplementedError, RuntimeError):
            pass  # Windows doesn't support add_signal_handler

    await engine.start()


def main() -> None:
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.critical("Fatal: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
