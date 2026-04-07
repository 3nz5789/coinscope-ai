"""
CoinScopeAI Paper Trading — Engine Orchestrator
==================================================
The main engine that ties all components together:
  Exchange Client → WebSocket → ML Signals → Safety Gate → Order Manager → Alerting

Lifecycle:
  1. Initialize all components
  2. Pre-fill candle buffers with historical data
  3. Connect WebSocket for real-time candles
  4. On each closed candle: run ML → generate signal → validate → execute
  5. Monitor positions for SL/TP hits
  6. Send heartbeats and daily summaries
  7. Handle kill switch and graceful shutdown
"""

import json
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .alerting import TelegramAlerter
from .config import PaperTradingConfig, TradingConfig
from .exchange_client import BinanceFuturesTestnetClient, ExchangeError
from .order_manager import ManagedOrder, OrderManager
from .safety import KillSwitch, SafetyGate
from .signal_engine import MLSignalEngine, TradingSignal
from .ws_client import BinanceFuturesWebSocket, KlineEvent

logger = logging.getLogger("coinscopeai.paper_trading.engine")


class PaperTradingEngine:
    """
    The main paper trading engine orchestrator.

    Coordinates all subsystems and manages the trading loop.
    Designed to run as a long-lived process.
    """

    STATE_FILE = "/tmp/coinscopeai_paper_trading_state.json"

    def __init__(self, config: Optional[PaperTradingConfig] = None):
        self._config = config or PaperTradingConfig()
        self._running = False
        self._started_at = 0.0

        # ── Initialize Components ─────────────────────────────
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

        self._ws = BinanceFuturesWebSocket(
            self._config.exchange,
            rest_client=self._exchange,  # inject REST client for candle-miss fallback
        )

        self._alerter = TelegramAlerter(self._config.telegram)

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

    def start(self, model_path: Optional[str] = None, norm_params_path: Optional[str] = None, meta_path: Optional[str] = None):
        """
        Start the paper trading engine.

        Args:
            model_path: Path to trained ML model file (.joblib)
            norm_params_path: Path to normalization parameters (.joblib)
            meta_path: Path to model metadata JSON (v3 format)
        """
        logger.info("=" * 60)
        logger.info("CoinScopeAI Paper Trading Engine — STARTING")
        logger.info("Mode: TESTNET ONLY")
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

        # ── Step 2b: Load model metadata (v3 format) ─────────
        if meta_path:
            import json as json_mod
            with open(meta_path) as f:
                meta = json_mod.load(f)
            self._signal_engine._feature_names = meta.get("feature_names", [])
            self._signal_engine._norm_params = meta.get("norm_params", {})
            logger.info(
                "Model metadata loaded from: %s (%d features, %d norm_params)",
                meta_path, len(self._signal_engine._feature_names),
                len(self._signal_engine._norm_params),
            )
        elif norm_params_path:
            self._signal_engine.load_norm_params(norm_params_path)
            logger.info("Norm params loaded from: %s", norm_params_path)

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

        # ── Step 6: Subscribe to WebSocket streams ────────────
        self._ws.subscribe_klines(
            self._config.trading.symbols,
            self._config.trading.timeframe,
        )

        # ── Step 7: Register signal handlers ──────────────────
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # ── Step 8: Start ─────────────────────────────────────
        self._running = True
        self._started_at = time.time()

        # Send startup notification
        self._alerter.startup({
            "symbols": self._config.trading.symbols,
            "timeframe": self._config.trading.timeframe,
            "leverage": self._config.trading.leverage,
            "max_daily_loss_pct": self._config.trading.max_daily_loss_pct,
            "max_drawdown_pct": self._config.trading.max_drawdown_pct,
            "max_concurrent_positions": self._config.trading.max_concurrent_positions,
        })

        # Start WebSocket
        self._ws.start()

        logger.info("Engine started. Entering main loop.")

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

        logger.info("Stopping engine: reason=%s", reason)
        self._running = False

        # Stop WebSocket
        try:
            self._ws.stop()
        except Exception:
            pass

        # Save state
        self._save_state()

        # Send shutdown notification
        self._alerter.shutdown(reason)

        logger.info("Engine stopped.")

    def kill(self, reason: str = "manual_kill"):
        """
        Emergency kill: activate kill switch, close all positions, stop engine.
        """
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

                # Daily summary (at configured hour)
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

    # ── Event Handlers ────────────────────────────────────────

    def _handle_kline(self, event: KlineEvent):
        """Handle incoming kline from WebSocket."""
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
        """Handle a new ML signal."""
        self._signals_today += 1

        # Notify via Telegram
        self._alerter.signal_generated(signal_obj.to_dict())

        # Skip if kill switch is active
        if self._kill_switch.is_active:
            return

        # Skip non-actionable signals
        if not signal_obj.is_actionable:
            return

        # Check if we already have a position in this symbol
        positions = self._order_manager.positions
        if signal_obj.symbol in positions:
            existing = positions[signal_obj.symbol]
            # If signal is opposite to current position, close it
            if (signal_obj.direction == "LONG" and existing.side == "SHORT") or \
               (signal_obj.direction == "SHORT" and existing.side == "LONG"):
                logger.info("Signal reversal: closing %s %s", signal_obj.symbol, existing.side)
                self._order_manager.close_position(signal_obj.symbol, "signal_reversal")
            else:
                # Same direction — already positioned
                return

        # Calculate position size and order parameters
        order_params = self._calculate_order_params(signal_obj)
        if not order_params:
            return

        # Submit order
        success, order = self._order_manager.submit_order(**order_params)

        if success:
            self._alerter.order_submitted(order.to_dict())

    def _handle_fill(self, order: ManagedOrder):
        """Handle order fill."""
        self._trades_today += 1
        self._alerter.order_filled(order.to_dict())

    def _handle_rejection(self, order: ManagedOrder):
        """Handle order rejection."""
        self._alerter.order_rejected(order.to_dict())

        # Check if rejection was due to risk gate
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
        self._alerter.error("websocket", "Disconnected — max reconnect attempts reached")
        # Don't kill — the WS will try to reconnect

    def _signal_handler(self, signum, frame):
        """Handle OS signals (SIGINT, SIGTERM)."""
        logger.info("Received signal %d, shutting down...", signum)
        self.stop(f"signal_{signum}")

    # ── Helpers ───────────────────────────────────────────────

    def _calculate_order_params(self, signal_obj: TradingSignal) -> Optional[Dict]:
        """Calculate order parameters from a signal."""
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

        # Position size: use configured max position size
        position_value = balance * self._config.trading.max_position_size_pct
        notional = position_value * self._config.trading.leverage
        quantity = notional / current_price

        # Round quantity (crude rounding — exchange info would be better)
        if current_price > 1000:
            quantity = round(quantity, 3)
        elif current_price > 10:
            quantity = round(quantity, 2)
        else:
            quantity = round(quantity, 1)

        if quantity <= 0:
            return None

        # Calculate SL/TP based on ATR proxy (2% SL, 4% TP for 2:1 R:R)
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
        """Send heartbeat notification."""
        portfolio = self._order_manager.get_portfolio_summary()
        safety_status = self._safety.get_status()

        self._alerter.heartbeat({
            "equity": safety_status.get("equity", 0),
            "daily_pnl": safety_status.get("daily_pnl", 0),
            "drawdown_pct": safety_status.get("drawdown_pct", 0),
            "positions": portfolio.get("positions", {}),
            "kill_switch": self._kill_switch.is_active,
            "signals_today": self._signals_today,
            "trades_today": self._trades_today,
        })

    def _send_daily_summary(self):
        """Send end-of-day summary."""
        portfolio = self._order_manager.get_portfolio_summary()
        safety_status = self._safety.get_status()

        self._alerter.daily_summary({
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
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
            "consecutive_losses": safety_status.get("consecutive_losses", 0),
            "kill_switch": self._kill_switch.is_active,
        })

    def _save_state(self):
        """Save engine state to disk for recovery."""
        try:
            state = {
                "saved_at": time.time(),
                "started_at": self._started_at,
                "safety": self._safety.get_status(),
                "portfolio": self._order_manager.get_portfolio_summary(),
                "signal_stats": self._signal_engine.get_stats(),
                "alerter_stats": self._alerter.get_stats(),
            }
            Path(self.STATE_FILE).write_text(json.dumps(state, indent=2, default=str))
            logger.info("State saved to %s", self.STATE_FILE)
        except Exception as e:
            logger.error("Failed to save state: %s", e)

    def get_status(self) -> Dict:
        """Get comprehensive engine status."""
        return {
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
        }
