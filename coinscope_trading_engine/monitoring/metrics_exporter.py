"""
Prometheus Metrics Exporter

Exposes /metrics on port 8000 for Grafana scraping.
Falls back to print-only if prometheus_client unavailable.
"""

import time

try:
    from prometheus_client import (
        start_http_server,
        Gauge,
        Counter,
        Histogram,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class MetricsExporter:
    """Prometheus metrics exporter"""

    def __init__(self, port: int = 8000):
        self.port = port
        self._started = False
        
        if PROMETHEUS_AVAILABLE:
            self.signal_total = Counter(
                "coinscopeai_signals_total",
                "Total signals generated",
                ["symbol", "direction"],
            )
            self.win_rate = Gauge("coinscopeai_win_rate", "Rolling win rate")
            self.sharpe = Gauge("coinscopeai_sharpe", "Rolling Sharpe ratio")
            self.equity = Gauge("coinscopeai_equity", "Current equity USD")
            self.drawdown = Gauge("coinscopeai_drawdown", "Current drawdown pct")
            self.regime_gauge = Gauge(
                "coinscopeai_regime",
                "Current regime (1=bull,0=chop,-1=bear)",
                ["symbol"],
            )
            self.trade_latency = Histogram(
                "coinscopeai_scan_latency_seconds", "Scan duration in seconds"
            )

    def start(self):
        """Start metrics HTTP server"""
        if PROMETHEUS_AVAILABLE and not self._started:
            start_http_server(self.port)
            self._started = True
            print(f"Metrics server started on :{self.port}")

    def record_signal(self, symbol: str, direction: str):
        """Record signal generation"""
        if PROMETHEUS_AVAILABLE:
            self.signal_total.labels(symbol=symbol, direction=direction).inc()

    def update_equity(self, equity: float, peak: float):
        """Update equity metrics"""
        if PROMETHEUS_AVAILABLE:
            self.equity.set(equity)
            self.drawdown.set((equity - peak) / peak if peak > 0 else 0)

    def update_performance(self, win_rate: float, sharpe: float):
        """Update performance metrics"""
        if PROMETHEUS_AVAILABLE:
            self.win_rate.set(win_rate)
            self.sharpe.set(sharpe)

    def update_regime(self, symbol: str, regime: str):
        """Update regime metric"""
        if PROMETHEUS_AVAILABLE:
            val = {"bull": 1, "chop": 0, "bear": -1}.get(regime, 0)
            self.regime_gauge.labels(symbol=symbol).set(val)

    def record_scan_time(self, seconds: float):
        """Record scan latency"""
        if PROMETHEUS_AVAILABLE:
            self.trade_latency.observe(seconds)

    def print_status(self, stats: dict):
        """Fallback: print metrics to console"""
        print(f"\n📊 METRICS | {time.strftime('%H:%M:%S')}")
        for k, v in stats.items():
            print(f"   {k:20s}: {v}")
