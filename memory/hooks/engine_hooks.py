"""
Engine Memory Hooks
====================
Direct integration hooks for the CoinScopeAI paper trading engine (v1/v2).
Call these from engine event handlers to capture events in real time.

These are designed to be called from:
  - PaperTradingEngine._handle_signal()
  - PaperTradingEngine._handle_rejection()
  - PaperTradingEngine._handle_position_close()
  - PaperTradingEngine._on_regime_update()
  - PaperTradingEngine.start() / stop()

Usage:
    from memory.hooks import EngineMemoryHooks

    hooks = EngineMemoryHooks()

    # In your signal handler:
    hooks.on_signal(symbol="BTCUSDT", signal="LONG", confidence=0.82, ...)

    # In your position close handler:
    hooks.on_position_close(symbol="BTCUSDT", side="LONG", ...)

    # On engine start:
    hooks.on_engine_start(version="v2", symbols=["BTCUSDT", "ETHUSDT"])
"""

import logging
from typing import Any, Dict, List, Optional

from ..config import MemoryConfig
from ..manager import MemoryManager

logger = logging.getLogger("coinscopeai.memory.hooks")


class EngineMemoryHooks:
    """
    Stateless hook class — instantiate once and call methods from
    engine event handlers.  All writes are synchronous but fast
    (ChromaDB upsert is typically <5ms).
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.mm = MemoryManager(config)
        self._last_regimes: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # Signal events
    # ------------------------------------------------------------------

    def on_signal(
        self,
        symbol: str,
        signal: str,
        confidence: float,
        regime: str,
        price: float,
        strategy: str = "",
        reasoning: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Called when the signal engine generates a signal."""
        return self.mm.trade_decisions.log_signal(
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            regime=regime,
            price=price,
            strategy=strategy,
            reasoning=reasoning,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # Trade lifecycle
    # ------------------------------------------------------------------

    def on_position_open(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        regime: str,
        confidence: float,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        kelly_usd: float = 0.0,
        reasoning: str = "",
    ) -> str:
        """Called when a new position is opened."""
        return self.mm.trade_decisions.log_entry(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            regime=regime,
            confidence=confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            kelly_usd=kelly_usd,
            reasoning=reasoning,
        )

    def on_position_close(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        pnl_pct: float,
        pnl_usd: float,
        reason: str = "",
        regime: str = "",
        reasoning: str = "",
    ) -> str:
        """Called when a position is closed."""
        return self.mm.trade_decisions.log_exit(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=pnl_pct,
            pnl_usd=pnl_usd,
            reason=reason,
            regime=regime,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Risk events
    # ------------------------------------------------------------------

    def on_risk_check(
        self,
        symbol: str,
        passed: bool,
        equity: float,
        daily_pnl: float,
        drawdown: float,
        consecutive_losses: int,
        open_positions: int,
        circuit_breaker_active: bool = False,
        circuit_breaker_reason: str = "",
    ) -> str:
        """Called on every risk gate check."""
        return self.mm.risk_events.log_risk_gate_check(
            symbol=symbol,
            passed=passed,
            equity=equity,
            daily_pnl=daily_pnl,
            drawdown=drawdown,
            consecutive_losses=consecutive_losses,
            open_positions=open_positions,
            circuit_breaker_active=circuit_breaker_active,
            circuit_breaker_reason=circuit_breaker_reason,
        )

    def on_rejection(
        self,
        symbol: str,
        reason: str,
        order_details: str = "",
    ) -> str:
        """Called when the safety gate rejects an order."""
        return self.mm.risk_events.log_rejection(
            symbol=symbol,
            reason=reason,
            order_details=order_details,
        )

    def on_kill_switch(
        self,
        activated: bool,
        reason: str = "",
        equity: float = 0.0,
    ) -> str:
        """Called when the kill switch is activated or deactivated."""
        return self.mm.risk_events.log_kill_switch(
            activated=activated,
            reason=reason,
            equity=equity,
        )

    def on_drawdown(
        self,
        drawdown_pct: float,
        equity: float,
        peak_equity: float,
        trigger: str = "",
    ) -> str:
        """Called when a significant drawdown threshold is crossed."""
        return self.mm.risk_events.log_drawdown_event(
            drawdown_pct=drawdown_pct,
            equity=equity,
            peak_equity=peak_equity,
            trigger=trigger,
        )

    # ------------------------------------------------------------------
    # Regime events
    # ------------------------------------------------------------------

    def on_regime_update(
        self,
        symbol: str,
        regime: str,
        confidence: float = 0.0,
        price: float = 0.0,
    ) -> Optional[str]:
        """
        Called on every regime detection update.
        Only logs to memory when the regime actually changes.
        Returns doc_id if a change was logged, None otherwise.
        """
        old = self._last_regimes.get(symbol, "")
        if old and old != regime:
            doc_id = self.mm.system_events.log_regime_change(
                symbol=symbol,
                old_regime=old,
                new_regime=regime,
                confidence=confidence,
                price=price,
            )
            self._last_regimes[symbol] = regime
            return doc_id
        self._last_regimes[symbol] = regime
        return None

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def on_engine_start(
        self,
        version: str = "",
        symbols: Optional[List[str]] = None,
        config_summary: str = "",
    ) -> str:
        """Called when the trading engine starts."""
        return self.mm.system_events.log_engine_start(
            engine_version=version,
            symbols=",".join(symbols) if symbols else "",
            config_summary=config_summary,
        )

    def on_engine_stop(
        self,
        reason: str = "",
        uptime_seconds: float = 0.0,
    ) -> str:
        """Called when the trading engine stops."""
        return self.mm.system_events.log_engine_stop(
            reason=reason,
            uptime_seconds=uptime_seconds,
        )

    # ------------------------------------------------------------------
    # Performance snapshots
    # ------------------------------------------------------------------

    def on_performance_snapshot(
        self,
        metrics: Dict[str, float],
        model_name: str = "live_engine",
        symbol: str = "PORTFOLIO",
    ) -> str:
        """Called periodically to capture performance metrics."""
        return self.mm.ml_models.log_performance_snapshot(
            model_name=model_name,
            symbol=symbol,
            metrics=metrics,
        )
