"""
Liquidation Scanner
===================
Monitors on-chain / exchange liquidation events to detect over-leveraged
crowd positioning and potential mean-reversion or continuation setups.

In live mode this connects to the Binance Futures liquidation WebSocket
stream: wss://fstream.binance.com/ws/!forceOrder@arr

In backtest / offline mode it estimates liquidation exposure from
open-interest and price-range data.
"""

from __future__ import annotations

import os
import json
import time
import threading
import numpy as np
import pandas as pd
from collections import deque
from datetime import datetime, timezone


# ── Data Model ───────────────────────────────────────────────────────────────

class LiquidationEvent:
    """Single liquidation order from the exchange stream."""

    __slots__ = ("symbol", "side", "qty", "price", "usd_value", "ts")

    def __init__(self, symbol: str, side: str, qty: float,
                 price: float, ts: float | None = None):
        self.symbol    = symbol
        self.side      = side.upper()       # 'BUY' = shorts liquidated, 'SELL' = longs
        self.qty       = qty
        self.price     = price
        self.usd_value = qty * price
        self.ts        = ts or time.time()

    def __repr__(self):
        return (f"LiqEvent({self.symbol} {self.side} "
                f"${self.usd_value:,.0f} @ {self.price:.2f})")


# ── Scanner ──────────────────────────────────────────────────────────────────

class LiquidationScanner:
    """
    Tracks recent liquidations and fires signals when cumulative
    liquidation volume exceeds a configurable threshold.

    Signal logic:
      • Large SELL liquidations (longs blown out) → potential LONG reversal
        (price has likely overshot to the downside — watch for bounce).
      • Large BUY  liquidations (shorts blown out) → potential SHORT reversal
        (price has likely overshot to the upside — watch for fade).

    Parameters
    ----------
    window_seconds : int
        Time window to aggregate liquidations (default 300 s = 5 min).
    threshold_usd : float
        Minimum cumulative USD liquidated within the window to fire a signal
        (default $1 million).
    """

    def __init__(self, window_seconds: int = 300,
                 threshold_usd: float = 1_000_000):
        self.window_seconds  = window_seconds
        self.threshold_usd   = threshold_usd
        self._events: deque  = deque(maxlen=10_000)
        self._lock           = threading.Lock()
        self._ws_thread: threading.Thread | None = None
        self._running        = False

    # ── Event ingestion ──────────────────────────────────────────────────────

    def add_event(self, event: LiquidationEvent):
        with self._lock:
            self._events.append(event)

    def _parse_ws_message(self, msg: dict):
        """Parse Binance forceOrder stream message."""
        try:
            o = msg.get("o", msg)   # handle both wrapped and unwrapped
            evt = LiquidationEvent(
                symbol = o["s"],
                side   = o["S"],
                qty    = float(o["q"]),
                price  = float(o["ap"]),      # average price
                ts     = float(o.get("T", time.time() * 1000)) / 1000,
            )
            self.add_event(evt)
        except Exception as e:
            print(f"[LiqScanner] parse error: {e}")

    # ── WebSocket feed ───────────────────────────────────────────────────────

    def start_live_feed(self, symbols: list[str] | None = None):
        """
        Start background thread consuming Binance liquidation WebSocket.
        NOTE: Updated URL uses new /market path (Binance change April 2026).
        """
        self._running = True
        self._ws_thread = threading.Thread(
            target=self._ws_loop, daemon=True, name="liq-scanner-ws"
        )
        self._ws_thread.start()
        print("[LiqScanner] Live feed started.")

    def stop_live_feed(self):
        self._running = False
        print("[LiqScanner] Live feed stopped.")

    def _ws_loop(self):
        """WebSocket consumer loop (runs in background thread)."""
        try:
            import websocket

            # Updated base URL (Binance April 2026 migration)
            url = "wss://fstream.binance.com/market/!forceOrder@arr"

            def on_message(ws, message):
                self._parse_ws_message(json.loads(message))

            def on_error(ws, error):
                print(f"[LiqScanner] WS error: {error}")

            def on_close(ws, *args):
                print("[LiqScanner] WS closed.")

            ws = websocket.WebSocketApp(
                url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            while self._running:
                ws.run_forever(ping_interval=30)
                if self._running:
                    time.sleep(5)   # reconnect delay
        except ImportError:
            print("[LiqScanner] websocket-client not installed — live feed unavailable.")

    # ── Signal Generation ─────────────────────────────────────────────────────

    def get_window_events(self, symbol: str | None = None) -> list[LiquidationEvent]:
        """Return events within the configured time window."""
        cutoff = time.time() - self.window_seconds
        with self._lock:
            events = list(self._events)
        events = [e for e in events if e.ts >= cutoff]
        if symbol:
            sym = symbol.replace("/", "").upper()
            events = [e for e in events if e.symbol.upper() == sym]
        return events

    def scan(self, symbol: str | None = None) -> dict:
        """
        Compute cumulative liquidation stats and return a signal.

        Returns
        -------
        dict:
          signal        : int  (+1 long-reversal, -1 short-reversal, 0 neutral)
          buy_liq_usd   : float — USD value of BUY  liquidations  (shorts blown)
          sell_liq_usd  : float — USD value of SELL liquidations  (longs blown)
          net_bias      : str  — 'LONG_DOMINATED' | 'SHORT_DOMINATED' | 'MIXED'
          event_count   : int
          direction     : str
        """
        events = self.get_window_events(symbol)

        buy_usd  = sum(e.usd_value for e in events if e.side == "BUY")
        sell_usd = sum(e.usd_value for e in events if e.side == "SELL")
        total    = buy_usd + sell_usd

        signal    = 0
        direction = "NEUTRAL"
        net_bias  = "MIXED"

        if total >= self.threshold_usd:
            if sell_usd > buy_usd * 1.5:
                signal    = 1           # longs liquidated → potential bounce
                direction = "LONG_REVERSAL"
                net_bias  = "LONG_DOMINATED"
            elif buy_usd > sell_usd * 1.5:
                signal    = -1          # shorts liquidated → potential fade
                direction = "SHORT_REVERSAL"
                net_bias  = "SHORT_DOMINATED"

        return {
            "signal":       signal,
            "buy_liq_usd":  round(buy_usd, 2),
            "sell_liq_usd": round(sell_usd, 2),
            "total_usd":    round(total, 2),
            "net_bias":     net_bias,
            "event_count":  len(events),
            "direction":    direction,
            "window_s":     self.window_seconds,
        }

    # ── OI-based estimation (offline / backtest) ─────────────────────────────

    @staticmethod
    def estimate_liq_level(entry_price: float, leverage: float,
                           side: str = "LONG") -> float:
        """
        Estimate approximate liquidation price for a position.
        Assumes isolated margin, no funding.
        """
        if side.upper() == "LONG":
            return entry_price * (1 - 1 / leverage)
        else:
            return entry_price * (1 + 1 / leverage)


# ── CLI smoke-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    scanner = LiquidationScanner(threshold_usd=500_000)

    # Inject synthetic events
    for i in range(20):
        scanner.add_event(LiquidationEvent(
            symbol="BTCUSDT", side="SELL",
            qty=0.5, price=65_000 - i * 100,
        ))

    result = scanner.scan(symbol="BTCUSDT")
    print(f"Signal: {result['signal']}  Direction: {result['direction']}")
    print(f"Sell liq: ${result['sell_liq_usd']:,.0f}  Buy liq: ${result['buy_liq_usd']:,.0f}")

    # Estimate liq price
    liq_px = LiquidationScanner.estimate_liq_level(65_000, leverage=10, side="LONG")
    print(f"Est. liquidation price (10x LONG @ $65k): ${liq_px:,.0f}")
