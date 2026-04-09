"""
API Memory Middleware
=====================
FastAPI middleware that automatically captures data from the trading
engine's REST endpoints into the MemPalace:

  /scan            → wing_trading (signals) + knowledge graph
  /risk-gate       → wing_risk (gate-checks)
  /regime/{symbol} → wing_system (regime-changes) + knowledge graph
  /performance     → wing_models (snapshots)

Usage::

    from memory.hooks import MemoryMiddleware

    app = FastAPI()
    memory_mw = MemoryMiddleware(app)
"""

import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..config import MemoryConfig
from ..manager import MemoryManager

logger = logging.getLogger("coinscopeai.memory.hooks")

# Track last-seen regime per symbol to detect changes
_regime_cache: Dict[str, str] = {}
_regime_lock = threading.Lock()

# Throttle performance snapshots
_PERF_INTERVAL = 300  # seconds
_last_perf_capture = 0.0
_perf_lock = threading.Lock()


class MemoryMiddleware:
    """
    Attach to a FastAPI app to automatically capture trading engine
    events into the MemPalace.  Memory writes happen in background
    threads — zero latency impact on the API.
    """

    def __init__(self, app=None, config: Optional[MemoryConfig] = None):
        self.mm = MemoryManager(config)
        if app is not None:
            self.attach(app)

    def attach(self, app) -> None:
        """Register FastAPI event hooks on the given app."""
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request
        from starlette.responses import Response as StarletteResponse

        mw = self

        class _CaptureMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                response = await call_next(request)
                path = request.url.path

                if response.status_code == 200 and any(
                    path.startswith(p)
                    for p in ("/scan", "/risk-gate", "/regime/", "/performance")
                ):
                    body_bytes = b""
                    async for chunk in response.body_iterator:
                        body_bytes += chunk if isinstance(chunk, bytes) else chunk.encode()

                    try:
                        data = json.loads(body_bytes)
                        threading.Thread(
                            target=mw._capture,
                            args=(path, data),
                            daemon=True,
                        ).start()
                    except (json.JSONDecodeError, Exception):
                        pass

                    return StarletteResponse(
                        content=body_bytes,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type=response.media_type,
                    )

                return response

        app.add_middleware(_CaptureMiddleware)
        logger.info("Memory middleware attached to FastAPI app")

    # ------------------------------------------------------------------
    # Capture router
    # ------------------------------------------------------------------

    def _capture(self, path: str, data: Dict[str, Any]) -> None:
        try:
            if path.startswith("/scan"):
                self._capture_scan(data)
            elif path.startswith("/regime/"):
                symbol = path.split("/regime/")[-1].strip("/").upper()
                self._capture_regime(symbol, data)
            elif path.startswith("/risk-gate"):
                self._capture_risk_gate(data)
            elif path.startswith("/performance"):
                self._capture_performance(data)
        except Exception as exc:
            logger.error("Memory capture error for %s: %s", path, exc)

    # ------------------------------------------------------------------
    # Capture handlers
    # ------------------------------------------------------------------

    def _capture_scan(self, data: Dict[str, Any]) -> None:
        """Capture signals → wing_trading/signals + knowledge graph."""
        signals = data.get("signals", [])
        if isinstance(data, dict) and not signals and "symbol" in data:
            signals = [data]

        for sig in signals:
            symbol = sig.get("symbol", "").replace("/", "")
            signal_type = sig.get("signal", sig.get("direction", "NEUTRAL"))
            confidence = float(sig.get("confidence", 0.0))
            regime = sig.get("regime", "unknown")
            price = float(sig.get("price", sig.get("entry_price", 0.0)))
            strategy = sig.get("strategy", "")

            reasoning_parts = []
            if sig.get("kelly_usd"):
                reasoning_parts.append(f"Kelly size=${sig['kelly_usd']:.2f}")
            if sig.get("sentiment_score"):
                reasoning_parts.append(f"sentiment={sig['sentiment_score']:.2f}")
            if sig.get("whale_filter"):
                reasoning_parts.append(f"whale_filter={sig['whale_filter']}")
            reasoning = "; ".join(reasoning_parts)

            self.mm.trading.log_signal(
                symbol=symbol,
                signal=signal_type,
                confidence=confidence,
                regime=regime,
                price=price,
                strategy=strategy,
                reasoning=reasoning,
                extra={k: v for k, v in sig.items()
                       if k not in ("symbol", "signal", "direction", "confidence",
                                    "regime", "price", "entry_price", "strategy")
                       and isinstance(v, (str, int, float, bool))},
            )

            # Knowledge graph: record signal fact
            if symbol and signal_type:
                self.mm.kg_add(
                    subject=symbol,
                    predicate=f"signal_{signal_type.lower()}",
                    obj=f"confidence={confidence:.3f}",
                    valid_from=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                )

    def _capture_regime(self, symbol: str, data: Dict[str, Any]) -> None:
        """Capture regime → wing_system/regime-changes + knowledge graph."""
        new_regime = data.get("regime", data.get("current_regime", "unknown"))
        confidence = float(data.get("confidence", 0.0))
        price = float(data.get("price", 0.0))

        with _regime_lock:
            old_regime = _regime_cache.get(symbol, "")
            if old_regime and old_regime != new_regime:
                self.mm.system.log_regime_change(
                    symbol=symbol,
                    old_regime=old_regime,
                    new_regime=new_regime,
                    confidence=confidence,
                    price=price,
                )
                # Knowledge graph: invalidate old regime, add new
                self.mm.kg_invalidate(symbol, "in_regime", old_regime)
                self.mm.kg_add(
                    subject=symbol,
                    predicate="in_regime",
                    obj=new_regime,
                    valid_from=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                )
            _regime_cache[symbol] = new_regime

    def _capture_risk_gate(self, data: Dict[str, Any]) -> None:
        """Capture risk gate → wing_risk/gate-checks."""
        self.mm.risk.log_risk_gate_check(
            symbol=data.get("symbol", "PORTFOLIO"),
            passed=bool(data.get("passed", not data.get("circuit_breaker_active", False))),
            equity=float(data.get("equity", data.get("account_equity", 0.0))),
            daily_pnl=float(data.get("daily_pnl", 0.0)),
            drawdown=float(data.get("drawdown", data.get("current_drawdown", 0.0))),
            consecutive_losses=int(data.get("consecutive_losses", 0)),
            open_positions=int(data.get("open_positions", 0)),
            circuit_breaker_active=bool(data.get("circuit_breaker_active", False)),
            circuit_breaker_reason=data.get("circuit_breaker_reason", ""),
        )

    def _capture_performance(self, data: Dict[str, Any]) -> None:
        """Capture performance → wing_models/snapshots (throttled)."""
        global _last_perf_capture
        now = time.time()
        with _perf_lock:
            if now - _last_perf_capture < _PERF_INTERVAL:
                return
            _last_perf_capture = now

        metrics = {
            k: float(v) for k, v in data.items()
            if isinstance(v, (int, float)) and k != "timestamp"
        }
        if metrics:
            self.mm.models.log_performance_snapshot(
                model_name="paper_engine",
                symbol="PORTFOLIO",
                metrics=metrics,
                context=f"Auto-captured at {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
            )

    # ------------------------------------------------------------------
    # Manual capture helpers
    # ------------------------------------------------------------------

    def capture_scan_result(self, data: Dict[str, Any]) -> None:
        self._capture_scan(data)

    def capture_regime(self, symbol: str, data: Dict[str, Any]) -> None:
        self._capture_regime(symbol, data)

    def capture_risk_gate(self, data: Dict[str, Any]) -> None:
        self._capture_risk_gate(data)

    def capture_performance(self, data: Dict[str, Any]) -> None:
        self._capture_performance(data)
