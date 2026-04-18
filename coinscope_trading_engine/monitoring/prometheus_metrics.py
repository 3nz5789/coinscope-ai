"""
prometheus_metrics.py — Prometheus Metrics Integration
=======================================================
Exposes engine metrics via an HTTP endpoint scraped by Prometheus.

Metrics exposed
---------------
  Counters
    coinscopeai_scans_total            — scan cycles completed
    coinscopeai_signals_total{dir}     — signals generated, by direction
    coinscopeai_alerts_total{channel}  — alerts dispatched, by channel
    coinscopeai_ws_reconnects_total    — WebSocket reconnection count
    coinscopeai_api_requests_total{endpoint,status} — REST API calls

  Gauges
    coinscopeai_queue_size             — current alert queue depth
    coinscopeai_open_positions         — number of open positions
    coinscopeai_total_exposure_pct     — portfolio exposure %
    coinscopeai_daily_pnl_usdt         — running daily PnL
    coinscopeai_circuit_breaker_open   — 1 if open, 0 if closed
    coinscopeai_candle_cache_size{sym} — candles held per symbol
    coinscopeai_rate_limit_tokens{ch}  — remaining rate-limit tokens

  Histograms
    coinscopeai_scan_duration_seconds  — wall-clock time per scan cycle
    coinscopeai_signal_score           — confluence score distribution
    coinscopeai_api_latency_seconds{endpoint} — REST call latency

Usage
-----
    from monitoring.prometheus_metrics import metrics, start_metrics_server

    # At engine startup:
    start_metrics_server(port=9090)

    # In scan loop:
    metrics.scans_total.inc()
    with metrics.scan_duration.time():
        await run_one_scan()

    # For signals:
    metrics.signals_total.labels(direction="LONG").inc()
    metrics.signal_score.observe(signal.score)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy import — prometheus_client is optional
# ---------------------------------------------------------------------------

def _import_prometheus():
    try:
        import prometheus_client as prom
        return prom
    except ImportError:
        logger.warning(
            "prometheus_client not installed — metrics disabled. "
            "Install with: pip install prometheus-client"
        )
        return None


# ---------------------------------------------------------------------------
# No-op stubs (used when prometheus_client is unavailable)
# ---------------------------------------------------------------------------

class _NoopCounter:
    def inc(self, amount=1): pass
    def labels(self, **_): return self

class _NoopGauge:
    def set(self, v): pass
    def inc(self, v=1): pass
    def dec(self, v=1): pass
    def labels(self, **_): return self

class _NoopHistogram:
    def observe(self, v): pass
    def time(self):
        import contextlib
        return contextlib.nullcontext()
    def labels(self, **_): return self


# ---------------------------------------------------------------------------
# Metrics registry
# ---------------------------------------------------------------------------

@dataclass
class EngineMetrics:
    """
    Central registry of all Prometheus metrics for the CoinScopeAI engine.
    Falls back to no-op stubs when prometheus_client is unavailable.
    """

    # Counters
    scans_total:       object = field(init=False)
    signals_total:     object = field(init=False)
    alerts_total:      object = field(init=False)
    ws_reconnects:     object = field(init=False)
    api_requests:      object = field(init=False)

    # Gauges
    queue_size:        object = field(init=False)
    open_positions:    object = field(init=False)
    exposure_pct:      object = field(init=False)
    daily_pnl:         object = field(init=False)
    circuit_open:      object = field(init=False)
    candle_cache_size: object = field(init=False)
    rate_limit_tokens: object = field(init=False)

    # Histograms
    scan_duration:     object = field(init=False)
    signal_score:      object = field(init=False)
    api_latency:       object = field(init=False)

    def __post_init__(self) -> None:
        prom = _import_prometheus()
        if prom is None:
            self._init_noop()
            return
        self._init_prometheus(prom)

    def _init_prometheus(self, prom) -> None:
        # Counters
        self.scans_total = prom.Counter(
            "coinscopeai_scans_total",
            "Total scan cycles completed",
        )
        self.signals_total = prom.Counter(
            "coinscopeai_signals_total",
            "Signals generated",
            ["direction"],
        )
        self.alerts_total = prom.Counter(
            "coinscopeai_alerts_total",
            "Alerts dispatched",
            ["channel"],
        )
        self.ws_reconnects = prom.Counter(
            "coinscopeai_ws_reconnects_total",
            "WebSocket reconnection count",
        )
        self.api_requests = prom.Counter(
            "coinscopeai_api_requests_total",
            "Binance REST API calls",
            ["endpoint", "status"],
        )

        # Gauges
        self.queue_size = prom.Gauge(
            "coinscopeai_queue_size",
            "Current alert queue depth",
        )
        self.open_positions = prom.Gauge(
            "coinscopeai_open_positions",
            "Number of open positions",
        )
        self.exposure_pct = prom.Gauge(
            "coinscopeai_total_exposure_pct",
            "Portfolio exposure as percentage of balance",
        )
        self.daily_pnl = prom.Gauge(
            "coinscopeai_daily_pnl_usdt",
            "Running daily PnL in USDT",
        )
        self.circuit_open = prom.Gauge(
            "coinscopeai_circuit_breaker_open",
            "1 if circuit breaker is open (trading halted), 0 if closed",
        )
        self.candle_cache_size = prom.Gauge(
            "coinscopeai_candle_cache_size",
            "Candles held per symbol",
            ["symbol"],
        )
        self.rate_limit_tokens = prom.Gauge(
            "coinscopeai_rate_limit_tokens",
            "Remaining rate-limit tokens",
            ["channel"],
        )

        # Histograms
        self.scan_duration = prom.Histogram(
            "coinscopeai_scan_duration_seconds",
            "Wall-clock time per full scan cycle",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
        )
        self.signal_score = prom.Histogram(
            "coinscopeai_signal_score",
            "Distribution of confluence scores for generated signals",
            buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )
        self.api_latency = prom.Histogram(
            "coinscopeai_api_latency_seconds",
            "Binance REST call latency",
            ["endpoint"],
            buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
        )

        logger.info("Prometheus metrics registered.")

    def _init_noop(self) -> None:
        self.scans_total       = _NoopCounter()
        self.signals_total     = _NoopCounter()
        self.alerts_total      = _NoopCounter()
        self.ws_reconnects     = _NoopCounter()
        self.api_requests      = _NoopCounter()
        self.queue_size        = _NoopGauge()
        self.open_positions    = _NoopGauge()
        self.exposure_pct      = _NoopGauge()
        self.daily_pnl         = _NoopGauge()
        self.circuit_open      = _NoopGauge()
        self.candle_cache_size = _NoopGauge()
        self.rate_limit_tokens = _NoopGauge()
        self.scan_duration     = _NoopHistogram()
        self.signal_score      = _NoopHistogram()
        self.api_latency       = _NoopHistogram()

    def update_from_engine(self, engine_status: dict) -> None:
        """
        Bulk-update gauges from the engine's status() snapshot.
        Call this inside the health monitor loop.
        """
        exp = engine_status.get("exposure", {})
        cb  = engine_status.get("circuit_breaker", {})
        aq  = engine_status.get("alert_queue", {})
        rl  = engine_status.get("rate_limiter", {})

        self.open_positions.set(exp.get("position_count", 0))
        self.exposure_pct.set(exp.get("total_exposure_pct", 0.0))
        self.daily_pnl.set(exp.get("daily_pnl", 0.0))
        self.circuit_open.set(1 if cb.get("state") == "OPEN" else 0)
        self.queue_size.set(aq.get("queue_size", 0))

        # Rate-limiter token counts
        rl_telegram = rl.get("telegram", {}).get("available", 0)
        rl_webhook  = rl.get("webhook",  {}).get("available", 0)
        self.rate_limit_tokens.labels(channel="telegram").set(rl_telegram)
        self.rate_limit_tokens.labels(channel="webhook").set(rl_webhook)


# Singleton
metrics = EngineMetrics()


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def start_metrics_server(port: int = 9090) -> bool:
    """
    Start the Prometheus HTTP metrics endpoint on `port`.

    Returns True on success, False if prometheus_client is unavailable.
    """
    prom = _import_prometheus()
    if prom is None:
        return False
    try:
        prom.start_http_server(port)
        logger.info("Prometheus metrics server started on port %d.", port)
        return True
    except OSError as exc:
        logger.warning("Could not start metrics server on port %d: %s", port, exc)
        return False
