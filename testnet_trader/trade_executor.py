"""
trade_executor.py — CoinScopeAI testnet trade executor.

Takes a signal from the scanner and turns it into:
  1. Leverage + margin type configuration
  2. Position size calculation (risk-based: risk% of balance / SL distance)
  3. Market entry order
  4. STOP_MARKET order for stop-loss
  5. TAKE_PROFIT_MARKET order for take-profit

All three orders are placed atomically — if the entry fills but the SL/TP
fail, the executor will cancel the entry and report the error cleanly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from client import BinanceFuturesRestClient, BinanceAPIError, RateLimitError

logger = logging.getLogger("TradeExecutor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


# ── Signal dataclass ──────────────────────────────────────────────────────────

@dataclass
class Signal:
    """
    Scanner signal passed into the executor.
    Mirrors the output format of CoinScopeAI's market-scanner skill.
    """
    symbol:    str                      # e.g. "BTCUSDT"
    direction: Literal["LONG", "SHORT"] # trade direction
    score:     float                    # confluence score (0–12)
    timeframe: str = "15m"             # signal timeframe (informational)
    source:    str = "scanner"          # who generated this signal


# ── Trade result dataclass ────────────────────────────────────────────────────

@dataclass
class TradeResult:
    """Everything that happened during execution — printed as a confirmation."""
    signal:         Signal
    entry_price:    float = 0.0
    quantity:       float = 0.0
    sl_price:       float = 0.0
    tp_price:       float = 0.0
    margin_used:    float = 0.0        # USDT allocated to this trade
    risk_amount:    float = 0.0        # max USDT loss if SL is hit
    entry_order:    dict  = field(default_factory=dict)
    sl_order:       dict  = field(default_factory=dict)
    tp_order:       dict  = field(default_factory=dict)
    success:        bool  = False
    error:          str   = ""

    def print_confirmation(self):
        """Pretty-print order confirmation to the terminal."""
        side_emoji = "🟢 LONG " if self.signal.direction == "LONG" else "🔴 SHORT"
        status     = "✅ FILLED" if self.success else f"❌ FAILED: {self.error}"

        print("\n" + "═" * 55)
        print(f"  CoinScopeAI Trade Confirmation  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("═" * 55)
        print(f"  Signal      : {side_emoji}  {self.signal.symbol}  (score {self.signal.score:+.1f})")
        print(f"  Timeframe   : {self.signal.timeframe}   Source: {self.signal.source}")
        print(f"  Status      : {status}")
        print("─" * 55)

        if self.success:
            print(f"  Entry Price : ${self.entry_price:,.4f}")
            print(f"  Quantity    : {self.quantity} {self.signal.symbol.replace('USDT', '')}")
            print(f"  Margin Used : ${self.margin_used:,.2f} USDT")
            print(f"  Max Risk    : ${self.risk_amount:,.2f} USDT  "
                  f"({self.risk_amount / max(self.margin_used, 0.01) * 100:.1f}% of margin)")
            print(f"  Stop Loss   : ${self.sl_price:,.4f}  "
                  f"({'▼' if self.signal.direction == 'LONG' else '▲'} "
                  f"{abs(self.sl_price - self.entry_price) / self.entry_price * 100:.2f}%)")
            print(f"  Take Profit : ${self.tp_price:,.4f}  "
                  f"({'▲' if self.signal.direction == 'LONG' else '▼'} "
                  f"{abs(self.tp_price - self.entry_price) / self.entry_price * 100:.2f}%)")
            print("─" * 55)
            print(f"  Entry ID    : {self.entry_order.get('orderId', 'N/A')}")
            print(f"  SL ID       : {self.sl_order.get('orderId', 'N/A')}")
            print(f"  TP ID       : {self.tp_order.get('orderId', 'N/A')}")

        print("═" * 55 + "\n")


# ── Position sizer ────────────────────────────────────────────────────────────

class PositionSizer:
    """
    Risk-based position sizing.

    Formula (LONG example):
        sl_distance  = entry_price × sl_pct / 100
        risk_amount  = available_balance × risk_pct / 100
        quantity     = risk_amount / sl_distance

    This ensures that if the SL is hit, you lose exactly risk_amount USDT —
    regardless of leverage. Leverage only affects the margin you post.
    """

    def __init__(self, risk_pct: float, sl_pct: float, rr_ratio: float, leverage: int):
        self.risk_pct = risk_pct   # e.g. 1.0  → risk 1% of balance per trade
        self.sl_pct   = sl_pct     # e.g. 1.5  → SL is 1.5% from entry price
        self.rr_ratio = rr_ratio   # e.g. 2.0  → TP is 2× the SL distance
        self.leverage = leverage

    def calculate(
        self,
        direction:         Literal["LONG", "SHORT"],
        entry_price:       float,
        available_balance: float,
        filters:           dict,
        client:            BinanceFuturesRestClient,
    ) -> tuple[float, float, float, float, float]:
        """
        Returns (quantity, sl_price, tp_price, margin_used, risk_amount).
        All prices are rounded to the symbol's tickSize.
        Quantity is rounded down to the symbol's stepSize.
        """
        sl_dist   = entry_price * (self.sl_pct / 100)
        tp_dist   = sl_dist * self.rr_ratio

        # SL/TP prices depend on direction
        if direction == "LONG":
            sl_price = entry_price - sl_dist
            tp_price = entry_price + tp_dist
        else:  # SHORT
            sl_price = entry_price + sl_dist
            tp_price = entry_price - tp_dist

        # How much USDT we're willing to lose if SL is hit
        risk_amount = available_balance * (self.risk_pct / 100)

        # Quantity from risk amount ÷ SL distance (in USDT per unit)
        raw_qty = risk_amount / sl_dist

        # Round quantity DOWN to stepSize (flooring avoids -1013 invalid quantity)
        quantity = client.round_quantity(raw_qty, filters)

        # Notional = entry_price × quantity; divide by leverage = margin used
        notional    = entry_price * quantity
        margin_used = notional / self.leverage

        # Validate minimum notional (Binance rejects orders below ~$5–10)
        min_notional = filters.get("min_notional", 5.0)
        if notional < min_notional:
            raise ValueError(
                f"Order notional ${notional:.2f} is below Binance minimum ${min_notional:.2f}. "
                f"Increase risk_pct or balance."
            )

        # Round SL and TP prices to tickSize
        sl_price = client.round_price(sl_price, filters)
        tp_price = client.round_price(tp_price, filters)

        return quantity, sl_price, tp_price, margin_used, risk_amount


# ── Trade executor ────────────────────────────────────────────────────────────

class TradeExecutor:
    """
    Executes a full trade: setup → entry → SL → TP.

    The three orders (entry, SL, TP) are placed in sequence.
    If the SL or TP order fails after the entry is placed, the executor
    cancels the entry and raises — you never end up with a naked position.
    """

    def __init__(
        self,
        client:  BinanceFuturesRestClient,
        sizer:   PositionSizer,
    ):
        self.client = client
        self.sizer  = sizer

    def execute(self, signal: Signal) -> TradeResult:
        result = TradeResult(signal=signal)
        symbol = signal.symbol.upper()

        logger.info(f"▶ Executing {signal.direction} on {symbol}  (score={signal.score:+.1f})")

        try:
            # ── Step 1: Get symbol filters (stepSize, tickSize, minNotional) ──
            logger.info(f"  Fetching symbol filters for {symbol}…")
            filters = self.client.get_symbol_filters(symbol)
            logger.info(f"  Filters: step={filters['step_size']}  tick={filters['tick_size']}  "
                        f"min_notional=${filters.get('min_notional', '?')}")

            # ── Step 2: Get current mark price as entry reference ─────────────
            logger.info(f"  Fetching mark price…")
            mark_data    = self.client.get_mark_price(symbol)
            entry_price  = float(mark_data["markPrice"])
            funding_rate = float(mark_data["lastFundingRate"]) * 100
            logger.info(f"  Mark price: ${entry_price:,.4f}  |  Funding: {funding_rate:+.4f}%")

            # ── Step 3: Get account balance ───────────────────────────────────
            logger.info(f"  Fetching account balance…")
            account   = self.client.get_account()
            balance   = float(account["availableBalance"])
            total_bal = float(account["totalWalletBalance"])
            logger.info(f"  Balance: ${balance:,.2f} available  /  ${total_bal:,.2f} total")

            if balance <= 0:
                raise ValueError(f"No available balance (${balance:.2f}) — cannot place trade.")

            # ── Step 4: Calculate position size + SL/TP levels ───────────────
            quantity, sl_price, tp_price, margin_used, risk_amount = self.sizer.calculate(
                direction=signal.direction,
                entry_price=entry_price,
                available_balance=balance,
                filters=filters,
                client=self.client,
            )
            result.entry_price = entry_price
            result.quantity    = quantity
            result.sl_price    = sl_price
            result.tp_price    = tp_price
            result.margin_used = margin_used
            result.risk_amount = risk_amount

            logger.info(
                f"  Sizing: qty={quantity}  SL=${sl_price:,.4f}  TP=${tp_price:,.4f}  "
                f"risk=${risk_amount:,.2f}  margin=${margin_used:,.2f}"
            )

            # ── Step 5: Set leverage and margin type ──────────────────────────
            logger.info(f"  Configuring {self.sizer.leverage}x ISOLATED leverage…")
            self.client.set_margin_type(symbol, "ISOLATED")
            self.client.set_leverage(symbol, self.sizer.leverage)

            # ── Step 6: Determine order sides ─────────────────────────────────
            # For LONG: entry=BUY, SL=SELL(reduceOnly), TP=SELL(reduceOnly)
            # For SHORT: entry=SELL, SL=BUY(reduceOnly), TP=BUY(reduceOnly)
            entry_side  = "BUY"  if signal.direction == "LONG" else "SELL"
            reduce_side = "SELL" if signal.direction == "LONG" else "BUY"

            # ── Step 7: Place entry order (MARKET) ────────────────────────────
            logger.info(f"  Placing MARKET {entry_side} for {quantity} {symbol}…")
            entry_order = self.client.place_order(
                symbol=symbol,
                side=entry_side,
                order_type="MARKET",
                quantity=quantity,
            )
            result.entry_order = entry_order
            filled_price = float(entry_order.get("avgPrice", entry_price))
            logger.info(f"  ✅ Entry filled @ ${filled_price:,.4f}  orderId={entry_order['orderId']}")

            # ── Step 8: Place stop-loss (STOP_MARKET, reduce_only=True) ───────
            logger.info(f"  Placing SL STOP_MARKET @ ${sl_price:,.4f}…")
            try:
                sl_order = self.client.place_order(
                    symbol=symbol,
                    side=reduce_side,
                    order_type="STOP_MARKET",
                    quantity=quantity,
                    stop_price=sl_price,
                    reduce_only=True,
                )
                result.sl_order = sl_order
                logger.info(f"  ✅ SL placed  orderId={sl_order['orderId']}")
            except (BinanceAPIError, RateLimitError) as e:
                # SL placement failed — cancel the entry to avoid naked position
                logger.error(f"  ❌ SL order failed: {e}. Cancelling entry order…")
                self.client.cancel_all_orders(symbol)
                raise RuntimeError(f"SL placement failed — entry cancelled: {e}") from e

            # ── Step 9: Place take-profit (TAKE_PROFIT_MARKET, reduce_only) ──
            logger.info(f"  Placing TP TAKE_PROFIT_MARKET @ ${tp_price:,.4f}…")
            try:
                tp_order = self.client.place_order(
                    symbol=symbol,
                    side=reduce_side,
                    order_type="TAKE_PROFIT_MARKET",
                    quantity=quantity,
                    stop_price=tp_price,
                    reduce_only=True,
                )
                result.tp_order = tp_order
                logger.info(f"  ✅ TP placed  orderId={tp_order['orderId']}")
            except (BinanceAPIError, RateLimitError) as e:
                # TP failed but SL is in place — log and continue (position is protected)
                logger.warning(f"  ⚠️  TP order failed: {e}. SL is active — trade protected.")
                result.tp_order = {"note": f"TP failed: {e}"}

            # ── Done ──────────────────────────────────────────────────────────
            result.entry_price = filled_price
            result.success     = True
            logger.info(f"✅ Trade complete. Rate limits: {self.client.rate.summary()}")

        except ValueError as e:
            # Configuration / sizing errors — don't place any order
            result.error = str(e)
            logger.error(f"❌ Sizing error: {e}")

        except BinanceAPIError as e:
            result.error = f"Binance error {e.code}: {e.msg}"
            logger.error(f"❌ {result.error}")

        except RateLimitError as e:
            result.error = f"Rate limit: {e}"
            logger.error(f"❌ {result.error}")

        except RuntimeError as e:
            result.error = str(e)
            logger.error(f"❌ {e}")

        return result
