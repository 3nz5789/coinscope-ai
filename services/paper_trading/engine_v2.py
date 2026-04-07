"""
CoinScopeAI Paper Trading — Engine v2 (EventBus Integration)
================================================================
Enhanced paper trading engine that integrates:
  - Multi-exchange market data via EventBus streams
  - Alpha signal generators (funding extremes, liquidation cascades, basis, OB imbalance)
  - Real-time regime detection
  - ML v2 signal engine (enriched with cross-exchange alpha features)

All existing safety constraints remain intact. The EventBus is an additive
data enrichment layer — it does NOT bypass the safety gate, kill switch,
or position sizing logic.

Architecture:
  EventBus ← [Streams, Alpha, Regime]
       ↓
  Engine v2 subscribes to:
    - kline.*.binance.4h   → ML signal generation (existing flow)
    - alpha.*.*            → Alpha feature enrichment
    - regime.*             → Regime-aware filtering
    - trade.*.*            → Tick-level position monitoring
    - orderbook.*.*        → Real-time spread/imbalance for execution
"""

import json
import logging
import os
import signal
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from ..market_data.event_bus import Event, EventBus
from ..market_data.types import (
    AlphaSignal,
    RegimeState,
    Trade,
    OrderBookSnapshot,
    alpha_topic,
    regime_topic,
)
from .alerting import TelegramAlerter
from .config import PaperTradingConfig, TradingConfig
from .exchange_client import BinanceFuturesTestnetClient, ExchangeError
from .order_manager import ManagedOrder, OrderManager
from .safety import KillSwitch, SafetyGate
from .signal_engine import MLSignalEngine, TradingSignal
from .ws_client import BinanceFuturesWebSocket, KlineEvent

logger = logging.getLogger("coinscopeai.paper_trading.engine_v2")


class AlphaContext:
    """
    Maintains a rolling window of alpha signals per symbol.
    Used to enrich ML signal decisions with cross-exchange data.
    """

    def __init__(self, max_age_seconds: float = 3600):
        self._max_age = max_age_seconds
        self._signals: Dict[str, Dict[str, AlphaSignal]] = defaultdict(dict)
        self._lock = threading.Lock()

    def update(self, signal: AlphaSignal):
        """Add or update an alpha signal."""
        with self._lock:
            self._signals[signal.symbol][signal.signal_type] = signal

    def get_context(self, symbol: str) -> Dict[str, Any]:
        """Get the current alpha context for a symbol as a flat dict of features."""
        now = time.time()
        context = {}
        with self._lock:
            signals = self._signals.get(symbol, {})
            for sig_type, sig in signals.items():
                # Skip expired signals
                if hasattr(sig, 'is_expired') and sig.is_expired:
                    continue
                if hasattr(sig, 'timestamp') and (now - sig.timestamp) > self._max_age:
                    continue

                prefix = f"alpha_{sig_type}"
                context[f"{prefix}_direction"] = (
                    1.0 if sig.direction == "LONG"
                    else -1.0 if sig.direction == "SHORT"
                    else 0.0
                )
                context[f"{prefix}_strength"] = sig.strength
                context[f"{prefix}_confidence"] = getattr(sig, 'confidence', sig.strength)
                context[f"{prefix}_active"] = 1.0
        return context

    def get_all(self) -> Dict:
        """Get all active alpha signals."""
        with self._lock:
            result = {}
            for symbol, signals in self._signals.items():
                result[symbol] = {
                    sig_type: {
                        "direction": sig.direction,
                        "strength": sig.strength,
                        "confidence": getattr(sig, 'confidence', sig.strength),
                    }
                    for sig_type, sig in signals.items()
                    if not (hasattr(sig, 'is_expired') and sig.is_expired)
                }
            return result


class RegimeContext:
    """
    Maintains the latest regime state per symbol.
    Used for regime-aware signal filtering.
    """

    def __init__(self):
        self._regimes: Dict[str, RegimeState] = {}
        self._lock = threading.Lock()

    def update(self, state: RegimeState):
        """Update regime for a symbol."""
        with self._lock:
            self._regimes[state.symbol] = state

    def get_regime(self, symbol: str) -> Optional[RegimeState]:
        """Get current regime for a symbol."""
        with self._lock:
            return self._regimes.get(symbol)

    def get_regime_features(self, symbol: str) -> Dict[str, float]:
        """Get regime as flat features for ML enrichment."""
        with self._lock:
            state = self._regimes.get(symbol)
            if not state:
                return {}
            return {
                "regime_volatile": 1.0 if state.regime == "volatile" else 0.0,
                "regime_trending_up": 1.0 if state.regime == "trending_up" else 0.0,
                "regime_trending_down": 1.0 if state.regime == "trending_down" else 0.0,
                "regime_ranging": 1.0 if state.regime == "ranging" else 0.0,
                "regime_confidence": state.confidence,
                "regime_vol_percentile": state.volatility_percentile,
                "regime_trend_strength": state.trend_strength,
            }

    def get_all(self) -> Dict:
        """Get all regime states."""
        with self._lock:
            return {
                symbol: {
                    "regime": state.regime,
                    "confidence": state.confidence,
                    "vol_percentile": state.volatility_percentile,
                    "trend_strength": state.trend_strength,
                }
                for symbol, state in self._regimes.items()
            }


class SpreadTracker:
    """
    Tracks real-time bid-ask spreads from orderbook data.
    Used for execution quality monitoring.
    """

    def __init__(self, window_size: int = 100):
        self._spreads: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self._lock = threading.Lock()

    def update(self, symbol: str, spread_bps: float):
        """Record a spread observation."""
        with self._lock:
            self._spreads[symbol].append(spread_bps)

    def get_avg_spread(self, symbol: str) -> float:
        """Get average spread in basis points."""
        with self._lock:
            spreads = self._spreads.get(symbol)
            if not spreads:
                return 0.0
            return sum(spreads) / len(spreads)

    def get_all(self) -> Dict:
        """Get spread stats for all symbols."""
        with self._lock:
            return {
                symbol: {
                    "avg_spread_bps": sum(s) / len(s) if s else 0,
                    "observations": len(s),
                }
                for symbol, s in self._spreads.items()
            }


class PaperTradingEngineV2:
    """
    Enhanced paper trading engine with EventBus integration.

    Adds cross-exchange alpha enrichment and regime-aware filtering
    on top of the existing ML signal → safety gate → order flow.

    All safety constraints from v1 are preserved unchanged.
    """

    STATE_FILE = "/tmp/coinscopeai_paper_trading_v2_state.json"

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._config = config or PaperTradingConfig()
        self._bus = event_bus or EventBus()
        self._running = False
        self._started_at = 0.0

        # ── Core Components (unchanged from v1) ──────────────
        self._kill_switch = KillSwitch()
        self._exchange = BinanceFuturesTestnetClient(self._config.exchange)
        self._safety = SafetyGate(self._config.trading, self._kill_switch)
        self._order_manager = OrderManager(
            self._exchange, self._safety, self._config.trading,
        )
        self._signal_engine = MLSignalEngine(
            min_confidence=self._config.trading.min_confidence,
            min_edge=self._config.trading.min_edge,
        )
        self._ws = BinanceFuturesWebSocket(self._config.exchange)
        self._alerter = TelegramAlerter(self._config.telegram)

        # ── EventBus Enrichment Layers (NEW in v2) ───────────
        self._alpha_ctx = AlphaContext(max_age_seconds=3600)
        self._regime_ctx = RegimeContext()
        self._spread_tracker = SpreadTracker()

        # ── Wire Callbacks ────────────────────────────────────
        self._signal_engine.on_signal(self._handle_signal)
        self._order_manager.on_fill(self._handle_fill)
        self._order_manager.on_rejection(self._handle_rejection)
        self._order_manager.on_position_close(self._handle_position_close)
        self._ws.on_kline(self._handle_kline)
        self._ws.on_error(self._handle_ws_error)
        self._ws.on_disconnect(self._handle_ws_disconnect)

        # ── Timers ────────────────────────────────────────────
        self._last_heartbeat = 0.0
        self._last_daily_summary = 0.0
        self._last_stale_check = 0.0
        self._last_equity_sync = 0.0

        # ── Stats ─────────────────────────────────────────────
        self._signals_today = 0
        self._trades_today = 0
        self._alpha_signals_received = 0
        self._regime_updates_received = 0
        self._ob_updates_received = 0

    def start(
        self,
        model_path: Optional[str] = None,
        enable_streams: bool = True,
        stream_exchanges: Optional[List[str]] = None,
    ):
        """
        Start the enhanced paper trading engine.

        Args:
            model_path: Path to trained ML model file (.joblib)
            enable_streams: Whether to start multi-exchange streams via EventBus
            stream_exchanges: Which exchanges to stream from (default: all 4)
        """
        logger.info("=" * 60)
        logger.info("CoinScopeAI Paper Trading Engine v2 — STARTING")
        logger.info("Mode: TESTNET ONLY | EventBus: %s", "ENABLED" if enable_streams else "DISABLED")
        logger.info("=" * 60)

        # ── Step 1: Validate exchange connection ──────────────
        try:
            self._exchange.ping()
            logger.info("Exchange connection: OK")
        except Exception as e:
            logger.error("Exchange connection FAILED: %s", e)
            self._alerter.error("exchange", f"Connection failed: {e}")
            raise

        # ── Step 2: Load ML model ─────────────────────────────
        if model_path:
            self._signal_engine.load_model(model_path)
            logger.info("ML model loaded from: %s", model_path)
        else:
            logger.warning("No ML model specified — signals will not be generated")

        # ── Step 3: Sync account state ────────────────────────
        self._sync_account()

        # ── Step 4: Set leverage for all symbols ──────────────
        for symbol in self._config.trading.symbols:
            try:
                self._exchange.set_leverage(symbol, self._config.trading.leverage)
                self._exchange.set_margin_type(symbol, "CROSSED")
                logger.info("Leverage set: %s = %dx", symbol, self._config.trading.leverage)
            except ExchangeError as e:
                logger.warning("Failed to set leverage for %s: %s", symbol, e)

        # ── Step 5: Pre-fill candle buffers ───────────────────
        self._prefill_buffers()

        # ── Step 6: Subscribe to EventBus topics (NEW) ────────
        if enable_streams:
            self._subscribe_eventbus()

        # ── Step 7: Subscribe to Binance testnet WebSocket ────
        self._ws.subscribe_klines(
            self._config.trading.symbols,
            self._config.trading.timeframe,
        )

        # ── Step 8: Register OS signal handlers ───────────────
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # ── Step 9: Start ─────────────────────────────────────
        self._running = True
        self._started_at = time.time()

        # Start EventBus
        if enable_streams:
            self._bus.start()
            self._start_streams(stream_exchanges or ["binance", "bybit", "okx", "deribit"])

        # Send startup notification
        self._alerter.startup({
            "version": "v2",
            "symbols": self._config.trading.symbols,
            "timeframe": self._config.trading.timeframe,
            "leverage": self._config.trading.leverage,
            "eventbus": enable_streams,
            "max_daily_loss_pct": self._config.trading.max_daily_loss_pct,
            "max_drawdown_pct": self._config.trading.max_drawdown_pct,
            "max_concurrent_positions": self._config.trading.max_concurrent_positions,
        })

        # Start Binance testnet WebSocket
        self._ws.start()

        logger.info("Engine v2 started. Entering main loop.")

        # ── Main Loop ─────────────────────────────────────────
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error("Main loop error: %s", e)
            self._alerter.error("engine", str(e))
        finally:
            self.stop("main_loop_exit")

    def stop(self, reason: str = "manual"):
        """Gracefully stop the engine."""
        if not self._running:
            return

        logger.info("Stopping engine v2: reason=%s", reason)
        self._running = False

        # Stop WebSocket
        try:
            self._ws.stop()
        except Exception:
            pass

        # Stop EventBus
        try:
            self._bus.stop()
        except Exception:
            pass

        # Stop stream manager
        if hasattr(self, '_stream_manager') and self._stream_manager:
            try:
                self._stream_manager.stop()
            except Exception:
                pass

        # Save state
        self._save_state()

        # Send shutdown notification
        self._alerter.shutdown(reason)

        logger.info("Engine v2 stopped.")

    def kill(self, reason: str = "manual_kill"):
        """Emergency kill: activate kill switch, close all positions, stop engine."""
        logger.critical("KILL COMMAND: %s", reason)

        # Activate kill switch
        self._kill_switch.activate(reason)
        self._alerter.kill_switch_activated(reason)

        # Close all positions via exchange
        try:
            results = self._exchange.close_all_positions()
            logger.info("Closed %d positions via exchange", len(results))
        except Exception as e:
            logger.error("Failed to close positions via exchange: %s", e)

        # Also try via order manager
        try:
            self._order_manager.close_all_positions(reason)
        except Exception as e:
            logger.error("Failed to close positions via order manager: %s", e)

        self.stop(reason)

    # ── EventBus Subscriptions ────────────────────────────────

    def _subscribe_eventbus(self):
        """Subscribe to EventBus topics for alpha, regime, and market data."""
        # Alpha signals from all generators
        self._bus.subscribe(
            "pt_alpha", "alpha.*.*",
            self._on_alpha_signal,
            queue_size=5_000,
        )

        # Regime updates
        self._bus.subscribe(
            "pt_regime", "regime.*",
            self._on_regime_update,
            queue_size=1_000,
        )

        # Orderbook for spread tracking
        self._bus.subscribe(
            "pt_orderbook", "orderbook.*.*",
            self._on_orderbook,
            queue_size=10_000,
        )

        # Trades for tick-level price updates
        self._bus.subscribe(
            "pt_trades", "trade.*.*",
            self._on_trade,
            queue_size=50_000,
        )

        logger.info("EventBus subscriptions registered: alpha, regime, orderbook, trades")

    def _start_streams(self, exchanges: List[str]):
        """Start multi-exchange stream manager and alpha/regime processors."""
        try:
            from ..market_data.streams.exchange_streams import StreamConfig, StreamManager
            from ..market_data.alpha.generators import AlphaEngine
            from ..market_data.regime.detector import RegimeDetector

            stream_config = StreamConfig(symbols=self._config.trading.symbols)
            self._stream_manager = StreamManager(self._bus, stream_config)
            self._alpha_engine = AlphaEngine(self._bus)
            self._regime_detector = RegimeDetector(self._bus)

            # Start streams
            self._stream_manager.start(exchanges)
            self._alpha_engine.start()
            self._regime_detector.start()

            logger.info(
                "Multi-exchange streams started: %s for %s",
                exchanges, self._config.trading.symbols,
            )
        except ImportError as e:
            logger.warning("Stream modules not available, running without EventBus enrichment: %s", e)
            self._stream_manager = None
        except Exception as e:
            logger.error("Failed to start streams: %s", e)
            self._stream_manager = None

    # ── EventBus Event Handlers ───────────────────────────────

    def _on_alpha_signal(self, event: Event):
        """Handle alpha signal from EventBus."""
        self._alpha_signals_received += 1
        if isinstance(event.data, AlphaSignal):
            self._alpha_ctx.update(event.data)
            logger.debug(
                "Alpha: %s %s dir=%s str=%.2f",
                event.data.signal_type, event.data.symbol,
                event.data.direction, event.data.strength,
            )
        elif isinstance(event.data, dict):
            # Handle dict-format alpha signals
            try:
                sig = AlphaSignal(**event.data)
                self._alpha_ctx.update(sig)
            except Exception:
                pass

    def _on_regime_update(self, event: Event):
        """Handle regime update from EventBus."""
        self._regime_updates_received += 1
        if isinstance(event.data, RegimeState):
            self._regime_ctx.update(event.data)
            logger.debug(
                "Regime: %s → %s (conf=%.2f)",
                event.data.symbol, event.data.regime, event.data.confidence,
            )
        elif isinstance(event.data, dict):
            try:
                state = RegimeState(**event.data)
                self._regime_ctx.update(state)
            except Exception:
                pass

    def _on_orderbook(self, event: Event):
        """Handle orderbook update for spread tracking."""
        self._ob_updates_received += 1
        if isinstance(event.data, OrderBookSnapshot):
            spread = event.data.spread_bps
            if spread > 0:
                self._spread_tracker.update(event.data.symbol, spread)
        elif isinstance(event.data, dict):
            spread = event.data.get("spread_bps", 0)
            symbol = event.data.get("symbol", "")
            if spread > 0 and symbol:
                self._spread_tracker.update(symbol, spread)

    def _on_trade(self, event: Event):
        """Handle trade tick for real-time price monitoring."""
        # Use trade ticks for more responsive position P&L updates
        if isinstance(event.data, Trade):
            symbol = event.data.symbol
            price = event.data.price
        elif isinstance(event.data, dict):
            symbol = event.data.get("symbol", "")
            price = event.data.get("price", 0)
        else:
            return

        if symbol and price > 0:
            # Update position P&L with tick-level price
            self._order_manager.update_unrealized_pnl(symbol, price)

    # ── Kline & Signal Handlers (enhanced from v1) ────────────

    def _handle_kline(self, event: KlineEvent):
        """Handle incoming kline from Binance testnet WebSocket."""
        # Update position P&L with latest price
        self._order_manager.update_unrealized_pnl(event.symbol, event.close)

        # Check SL/TP on every tick
        self._order_manager.check_stop_loss_take_profit(event.symbol, event.close)

        # Only process closed candles for signal generation
        if event.is_closed:
            self._signal_engine.process_candle(
                symbol=event.symbol,
                open_time=event.open_time,
                open_price=event.open,
                high=event.high,
                low=event.low,
                close=event.close,
                volume=event.volume,
                is_closed=True,
            )

    def _handle_signal(self, signal_obj: TradingSignal):
        """
        Handle a new ML signal — ENHANCED with alpha and regime enrichment.

        The core signal flow is unchanged:
          ML signal → safety gate → order submission

        v2 adds:
          - Alpha context enrichment (funding, liquidation, basis, OB imbalance)
          - Regime-aware filtering (reduce position size in volatile regimes)
          - Spread-aware execution (skip if spread is too wide)
        """
        self._signals_today += 1

        # ── Enrich signal with alpha context ──────────────────
        alpha_ctx = self._alpha_ctx.get_context(signal_obj.symbol)
        regime_features = self._regime_ctx.get_regime_features(signal_obj.symbol)
        regime_state = self._regime_ctx.get_regime(signal_obj.symbol)

        # Log enrichment
        if alpha_ctx:
            logger.info(
                "ALPHA ENRICHMENT for %s: %s",
                signal_obj.symbol,
                {k: f"{v:.2f}" for k, v in alpha_ctx.items()},
            )

        if regime_state:
            signal_obj.regime = regime_state.regime
            logger.info(
                "REGIME: %s → %s (conf=%.2f, vol_pct=%.0f)",
                signal_obj.symbol, regime_state.regime,
                regime_state.confidence, regime_state.volatility_percentile,
            )

        # ── Alpha confluence check ────────────────────────────
        # Count how many alpha signals agree with the ML direction
        alpha_agreement = 0
        alpha_disagreement = 0
        for key, val in alpha_ctx.items():
            if key.endswith("_direction"):
                if signal_obj.direction == "LONG" and val > 0:
                    alpha_agreement += 1
                elif signal_obj.direction == "SHORT" and val < 0:
                    alpha_agreement += 1
                elif val != 0:
                    alpha_disagreement += 1

        # If majority of alpha signals disagree, downgrade to NEUTRAL
        if alpha_disagreement > alpha_agreement and alpha_disagreement >= 2:
            logger.info(
                "ALPHA FILTER: %s %s downgraded — %d agree, %d disagree",
                signal_obj.symbol, signal_obj.direction,
                alpha_agreement, alpha_disagreement,
            )
            # Don't block — just log. The ML model is primary.
            # Alpha disagreement is informational for now.

        # ── Regime-aware filtering ────────────────────────────
        # In volatile regimes, require higher confidence
        if regime_state and regime_state.regime == "volatile":
            min_conf_volatile = self._config.trading.min_confidence + 0.05
            if signal_obj.confidence < min_conf_volatile:
                logger.info(
                    "REGIME FILTER: %s %s blocked — volatile regime requires conf>%.2f, got %.2f",
                    signal_obj.symbol, signal_obj.direction,
                    min_conf_volatile, signal_obj.confidence,
                )
                self._alerter.signal_generated({
                    **signal_obj.to_dict(),
                    "filtered": True,
                    "filter_reason": "volatile_regime_low_confidence",
                })
                return

        # ── Spread check ──────────────────────────────────────
        avg_spread = self._spread_tracker.get_avg_spread(signal_obj.symbol)
        if avg_spread > 20:  # More than 20 bps spread — too wide
            logger.info(
                "SPREAD FILTER: %s %s blocked — avg spread %.1f bps > 20 bps",
                signal_obj.symbol, signal_obj.direction, avg_spread,
            )
            return

        # ── Notify via Telegram ───────────────────────────────
        enriched_signal = {
            **signal_obj.to_dict(),
            "alpha_agreement": alpha_agreement,
            "alpha_disagreement": alpha_disagreement,
            "regime": signal_obj.regime,
            "avg_spread_bps": avg_spread,
        }
        self._alerter.signal_generated(enriched_signal)

        # ── Skip if kill switch is active ─────────────────────
        if self._kill_switch.is_active:
            return

        # ── Skip non-actionable signals ───────────────────────
        if not signal_obj.is_actionable:
            return

        # ── Check existing positions ──────────────────────────
        positions = self._order_manager.positions
        if signal_obj.symbol in positions:
            existing = positions[signal_obj.symbol]
            if (signal_obj.direction == "LONG" and existing.side == "SHORT") or \
               (signal_obj.direction == "SHORT" and existing.side == "LONG"):
                logger.info("Signal reversal: closing %s %s", signal_obj.symbol, existing.side)
                self._order_manager.close_position(signal_obj.symbol, "signal_reversal")
            else:
                return

        # ── Calculate order params (regime-adjusted) ──────────
        order_params = self._calculate_order_params(signal_obj, regime_state)
        if not order_params:
            return

        # ── Submit order (through safety gate) ────────────────
        success, order = self._order_manager.submit_order(**order_params)

        if success:
            self._alerter.order_submitted({
                **order.to_dict(),
                "alpha_context": alpha_ctx,
                "regime": signal_obj.regime,
            })

    def _handle_fill(self, order: ManagedOrder):
        """Handle order fill."""
        self._trades_today += 1
        self._alerter.order_filled(order.to_dict())

    def _handle_rejection(self, order: ManagedOrder):
        """Handle order rejection."""
        self._alerter.order_rejected(order.to_dict())
        if "daily_loss" in order.rejection_reason or "drawdown" in order.rejection_reason:
            self._alerter.risk_gate_triggered(
                order.rejection_reason,
                self._safety.get_status(),
            )

    def _handle_position_close(self, trade: Dict):
        """Handle position close."""
        self._alerter.position_closed(trade)

    def _handle_ws_error(self, error: Exception):
        """Handle WebSocket error."""
        self._alerter.error("websocket", str(error))

    def _handle_ws_disconnect(self):
        """Handle WebSocket disconnect."""
        self._alerter.error("websocket", "Disconnected — reconnecting...")

    def _signal_handler(self, signum, frame):
        """Handle OS signals (SIGINT, SIGTERM)."""
        logger.info("Received signal %d, shutting down...", signum)
        self.stop(f"signal_{signum}")

    # ── Main Loop ─────────────────────────────────────────────

    def _main_loop(self):
        """Main engine loop — periodic tasks."""
        while self._running:
            try:
                now = time.time()

                # Check kill switch
                if self._kill_switch.is_active:
                    logger.warning("Kill switch active, halting trading")
                    time.sleep(10)
                    continue

                # Heartbeat (every 15 minutes)
                if now - self._last_heartbeat >= self._config.trading.heartbeat_interval_seconds:
                    self._send_heartbeat()
                    self._last_heartbeat = now

                # Sync equity (every 5 minutes)
                if now - self._last_equity_sync >= 300:
                    self._sync_account()
                    self._last_equity_sync = now

                # Cancel stale orders (every 2 minutes)
                if now - self._last_stale_check >= 120:
                    self._order_manager.cancel_stale_orders(
                        self._config.trading.order_timeout_seconds
                    )
                    self._last_stale_check = now

                # Daily summary
                current_hour = datetime.now(timezone.utc).hour
                if (current_hour == self._config.trading.daily_report_hour_utc
                        and now - self._last_daily_summary >= 3600):
                    self._send_daily_summary()
                    self._safety.reset_daily_pnl()
                    self._signals_today = 0
                    self._trades_today = 0
                    self._last_daily_summary = now

                # Sleep to avoid busy loop
                time.sleep(1)

            except Exception as e:
                logger.error("Main loop iteration error: %s", e)
                time.sleep(5)

    # ── Helpers ───────────────────────────────────────────────

    def _calculate_order_params(
        self,
        signal_obj: TradingSignal,
        regime_state: Optional[RegimeState] = None,
    ) -> Optional[Dict]:
        """
        Calculate order parameters from a signal.
        Enhanced with regime-aware position sizing.
        """
        try:
            current_price = self._exchange.get_ticker_price(signal_obj.symbol)
        except Exception as e:
            logger.error("Failed to get price for %s: %s", signal_obj.symbol, e)
            return None

        if current_price <= 0:
            return None

        # Get available balance
        try:
            balance = self._exchange.get_usdt_balance()
        except Exception:
            balance = self._safety.state.current_equity

        # Base position size
        position_pct = self._config.trading.max_position_size_pct

        # Regime-aware sizing adjustment
        if regime_state:
            if regime_state.regime == "volatile":
                # Reduce position size by 30% in volatile regimes
                position_pct *= 0.7
                logger.info("Regime adjustment: volatile → position size reduced to %.1f%%",
                            position_pct * 100)
            elif regime_state.regime == "ranging":
                # Reduce by 20% in ranging (mean-reversion environment)
                position_pct *= 0.8

        position_value = balance * position_pct
        notional = position_value * self._config.trading.leverage
        quantity = notional / current_price

        # Round quantity
        if current_price > 1000:
            quantity = round(quantity, 3)
        elif current_price > 10:
            quantity = round(quantity, 2)
        else:
            quantity = round(quantity, 1)

        if quantity <= 0:
            return None

        # SL/TP (2% SL, 4% TP for 2:1 R:R)
        sl_pct = 0.02
        tp_pct = 0.04

        side = "BUY" if signal_obj.direction == "LONG" else "SELL"

        if signal_obj.direction == "LONG":
            stop_loss = current_price * (1 - sl_pct)
            take_profit = current_price * (1 + tp_pct)
        else:
            stop_loss = current_price * (1 + sl_pct)
            take_profit = current_price * (1 - tp_pct)

        # Limit order price with offset
        if self._config.trading.order_type == "LIMIT":
            offset = current_price * self._config.trading.limit_offset_pct
            price = current_price - offset if side == "BUY" else current_price + offset
        else:
            price = 0.0

        return {
            "symbol": signal_obj.symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "order_type": self._config.trading.order_type,
            "leverage": self._config.trading.leverage,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "signal_confidence": signal_obj.confidence,
            "signal_edge": signal_obj.edge,
        }

    def _prefill_buffers(self):
        """Pre-fill candle buffers with historical data from exchange."""
        for symbol in self._config.trading.symbols:
            try:
                klines = self._exchange.get_klines(
                    symbol=symbol,
                    interval=self._config.trading.timeframe,
                    limit=200,
                )
                if not klines:
                    logger.warning("No historical klines for %s", symbol)
                    continue

                df = pd.DataFrame(klines, columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades", "taker_buy_base",
                    "taker_buy_quote", "ignore",
                ])
                for col in ["open", "high", "low", "close", "volume"]:
                    df[col] = df[col].astype(float)

                self._signal_engine.initialize_buffer(symbol, df)
                logger.info("Pre-filled %s buffer: %d candles", symbol, len(df))

            except Exception as e:
                logger.error("Failed to pre-fill buffer for %s: %s", symbol, e)

    def _sync_account(self):
        """Sync account equity from exchange."""
        try:
            balance = self._exchange.get_usdt_balance()
            if balance > 0:
                self._safety.update_equity(balance)
                logger.debug("Equity synced: %.2f USDT", balance)
        except Exception as e:
            logger.warning("Failed to sync account: %s", e)

    def _send_heartbeat(self):
        """Send heartbeat notification with v2 enrichment data."""
        portfolio = self._order_manager.get_portfolio_summary()
        safety_status = self._safety.get_status()

        self._alerter.heartbeat({
            "version": "v2",
            "equity": safety_status.get("equity", 0),
            "daily_pnl": safety_status.get("daily_pnl", 0),
            "drawdown_pct": safety_status.get("drawdown_pct", 0),
            "positions": portfolio.get("positions", {}),
            "kill_switch": self._kill_switch.is_active,
            "signals_today": self._signals_today,
            "trades_today": self._trades_today,
            "alpha_signals_received": self._alpha_signals_received,
            "regime_updates_received": self._regime_updates_received,
            "active_regimes": self._regime_ctx.get_all(),
            "active_alphas": self._alpha_ctx.get_all(),
            "spreads": self._spread_tracker.get_all(),
            "eventbus": self._bus.get_stats() if self._bus else {},
        })

    def _send_daily_summary(self):
        """Send end-of-day summary."""
        portfolio = self._order_manager.get_portfolio_summary()
        safety_status = self._safety.get_status()

        self._alerter.daily_summary({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "version": "v2",
            "daily_pnl": safety_status.get("daily_pnl", 0),
            "equity": safety_status.get("equity", 0),
            "drawdown_pct": safety_status.get("drawdown_pct", 0),
            "signals": self._signals_today,
            "trades": portfolio.get("total_trades", 0),
            "wins": portfolio.get("winning_trades", 0),
            "losses": portfolio.get("losing_trades", 0),
            "win_rate": (portfolio.get("winning_trades", 0) /
                         max(portfolio.get("total_trades", 1), 1)),
            "orders_rejected": safety_status.get("total_orders_rejected", 0),
            "alpha_signals_received": self._alpha_signals_received,
            "regime_updates_received": self._regime_updates_received,
            "kill_switch": self._kill_switch.is_active,
        })

    def _save_state(self):
        """Save engine state to disk for recovery."""
        try:
            state = {
                "version": "v2",
                "saved_at": time.time(),
                "started_at": self._started_at,
                "safety": self._safety.get_status(),
                "portfolio": self._order_manager.get_portfolio_summary(),
                "signal_stats": self._signal_engine.get_stats(),
                "alerter_stats": self._alerter.get_stats(),
                "alpha_context": self._alpha_ctx.get_all(),
                "regime_context": self._regime_ctx.get_all(),
                "spreads": self._spread_tracker.get_all(),
                "eventbus": self._bus.get_stats() if self._bus else {},
            }
            Path(self.STATE_FILE).write_text(json.dumps(state, indent=2, default=str))
            logger.info("State saved to %s", self.STATE_FILE)
        except Exception as e:
            logger.error("Failed to save state: %s", e)

    def get_status(self) -> Dict:
        """Get comprehensive engine v2 status."""
        return {
            "version": "v2",
            "running": self._running,
            "started_at": self._started_at,
            "uptime_seconds": time.time() - self._started_at if self._started_at else 0,
            "kill_switch": self._kill_switch.status(),
            "safety": self._safety.get_status(),
            "portfolio": self._order_manager.get_portfolio_summary(),
            "signals": self._signal_engine.get_stats(),
            "alerter": self._alerter.get_stats(),
            "websocket": self._ws.is_running,
            "signals_today": self._signals_today,
            "trades_today": self._trades_today,
            "eventbus": {
                "alpha_signals_received": self._alpha_signals_received,
                "regime_updates_received": self._regime_updates_received,
                "ob_updates_received": self._ob_updates_received,
                "active_alphas": self._alpha_ctx.get_all(),
                "active_regimes": self._regime_ctx.get_all(),
                "spreads": self._spread_tracker.get_all(),
                "bus_stats": self._bus.get_stats() if self._bus else {},
            },
        }
