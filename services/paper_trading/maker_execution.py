"""
CoinScopeAI Paper Trading — Maker-Only Execution Layer
========================================================
Wraps OrderManager to enforce limit-order-only entry (maker strategy).

Key behaviour
─────────────
1. Fetch best bid / ask from the live order book.
2. Place a LIMIT BUY at the best bid (LONG) or LIMIT SELL at the best ask
   (SHORT) to earn the maker rebate and avoid market-order slippage.
3. Poll Binance for fill confirmation every `poll_interval` seconds.
4. If the order is still open after `fill_timeout` seconds, cancel it,
   nudge the price one tick toward the market, and retry.
5. After `max_retries` failed attempts fall back to a MARKET order so the
   signal is never silently dropped.
6. Emit a `MakerExecutionResult` with fill metadata and estimated slippage
   savings so callers can track the performance impact.

Thread-safety: each `execute()` call is independent; the class holds no
mutable per-symbol state.
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .exchange_client import BinanceFuturesTestnetClient, ExchangeError
from .order_manager import ManagedOrder, OrderManager, OrderStatus

logger = logging.getLogger("coinscopeai.paper_trading.maker")


# ── Result types ──────────────────────────────────────────────────────────────

class ExecutionStrategy(Enum):
    MAKER_FIRST_TRY = "maker_first_try"
    MAKER_RETRY     = "maker_retry"
    MARKET_FALLBACK = "market_fallback"
    REJECTED        = "rejected"
    FAILED          = "failed"


@dataclass
class MakerExecutionResult:
    success: bool
    symbol: str
    side: str
    quantity: float
    strategy: ExecutionStrategy
    order: Optional[ManagedOrder] = None

    initial_limit_price:    float = 0.0
    final_fill_price:       float = 0.0
    market_price_at_entry:  float = 0.0

    fill_latency_ms:    float = 0.0
    slippage_saved_bps: float = 0.0
    retries:            int   = 0
    error_message:      str   = ""

    @property
    def slippage_saved_usdt(self) -> float:
        notional = self.final_fill_price * self.quantity
        return notional * self.slippage_saved_bps / 10_000


# ── Maker executor ────────────────────────────────────────────────────────────

class MakerExecutor:
    """Maker-only execution strategy layer on top of OrderManager."""

    DEFAULT_FILL_TIMEOUT_S:   int   = 60
    DEFAULT_MAX_RETRIES:      int   = 3
    DEFAULT_POLL_INTERVAL_S:  float = 2.0
    DEFAULT_PRICE_ADJUST_PCT: float = 0.0005
    MAKER_REBATE_BPS:         float = 2.0

    def __init__(
        self,
        order_manager: OrderManager,
        exchange: BinanceFuturesTestnetClient,
        fill_timeout_s:   int   = DEFAULT_FILL_TIMEOUT_S,
        max_retries:      int   = DEFAULT_MAX_RETRIES,
        poll_interval_s:  float = DEFAULT_POLL_INTERVAL_S,
        price_adjust_pct: float = DEFAULT_PRICE_ADJUST_PCT,
    ):
        self._mgr              = order_manager
        self._exchange         = exchange
        self.fill_timeout_s    = fill_timeout_s
        self.max_retries       = max_retries
        self.poll_interval_s   = poll_interval_s
        self.price_adjust_pct  = price_adjust_pct

        self._lock             = threading.Lock()
        self._total_orders     = 0
        self._maker_fills      = 0
        self._market_fallbacks = 0
        self._total_bps_saved  = 0.0

    # ── Public API ─────────────────────────────────────────────

    def execute(
        self,
        symbol:            str,
        side:              str,
        quantity:          float,
        leverage:          int   = 3,
        stop_loss:         float = 0.0,
        take_profit:       float = 0.0,
        signal_confidence: float = 0.0,
        signal_edge:       float = 0.0,
    ) -> MakerExecutionResult:
        """
        Execute an order using maker-only strategy with market fallback.

        Places a limit order at best bid (BUY) or best ask (SELL), polls for
        fill, retries with price nudge on timeout, and falls back to MARKET
        after max_retries exhausted.
        """
        side     = side.upper()
        start_ts = time.time()

        logger.info(
            "MAKER EXECUTE: %s %s qty=%.6f lev=%dx conf=%.3f edge=%.4f",
            side, symbol, quantity, leverage, signal_confidence, signal_edge,
        )

        market_mid = self._get_mid_price(symbol)

        try:
            best_bid, best_ask = self._get_best_prices(symbol)
        except ExchangeError as exc:
            logger.error("Failed to fetch order book for %s: %s", symbol, exc)
            return MakerExecutionResult(
                success=False, symbol=symbol, side=side, quantity=quantity,
                strategy=ExecutionStrategy.FAILED,
                market_price_at_entry=market_mid,
                error_message=str(exc),
            )

        entry_price         = best_bid if side == "BUY" else best_ask
        initial_limit_price = entry_price

        logger.info(
            "ORDER BOOK: %s bid=%.4f ask=%.4f spread_bps=%.1f -> limit_price=%.4f",
            symbol, best_bid, best_ask,
            (best_ask - best_bid) / best_bid * 10_000 if best_bid else 0,
            entry_price,
        )

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                entry_price = self._nudge_toward_market(
                    entry_price, side, best_bid, best_ask, attempt
                )
                logger.info(
                    "RETRY %d/%d: adjusting limit price to %.4f",
                    attempt, self.max_retries, entry_price,
                )

            success, order = self._mgr.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=entry_price,
                order_type="LIMIT",
                leverage=leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reduce_only=False,
                signal_confidence=signal_confidence,
                signal_edge=signal_edge,
            )

            if not success:
                strategy = (
                    ExecutionStrategy.REJECTED
                    if order.status == OrderStatus.REJECTED_SAFETY
                    else ExecutionStrategy.FAILED
                )
                return MakerExecutionResult(
                    success=False, symbol=symbol, side=side, quantity=quantity,
                    strategy=strategy, order=order,
                    initial_limit_price=initial_limit_price,
                    market_price_at_entry=market_mid,
                    error_message=order.rejection_reason,
                )

            if order.status == OrderStatus.FILLED:
                result = self._build_result(
                    order=order, side=side, quantity=quantity,
                    initial_limit_price=initial_limit_price,
                    market_mid=market_mid,
                    strategy=(ExecutionStrategy.MAKER_FIRST_TRY
                              if attempt == 0 else ExecutionStrategy.MAKER_RETRY),
                    retries=attempt,
                    fill_latency_ms=(time.time() - start_ts) * 1000,
                )
                self._record_stats(filled_as_maker=True,
                                   bps_saved=result.slippage_saved_bps)
                return result

            deadline = time.time() + self.fill_timeout_s
            filled   = self._poll_until_filled(order, deadline)

            if filled:
                strategy = (ExecutionStrategy.MAKER_FIRST_TRY
                            if attempt == 0 else ExecutionStrategy.MAKER_RETRY)
                result = self._build_result(
                    order=order, side=side, quantity=quantity,
                    initial_limit_price=initial_limit_price,
                    market_mid=market_mid, strategy=strategy,
                    retries=attempt,
                    fill_latency_ms=(time.time() - start_ts) * 1000,
                )
                self._record_stats(filled_as_maker=True,
                                   bps_saved=result.slippage_saved_bps)
                logger.info(
                    "MAKER FILL: %s %s attempt=%d fill=%.4f latency=%.0fms saved=%.1fbps",
                    side, symbol, attempt, order.avg_fill_price,
                    result.fill_latency_ms, result.slippage_saved_bps,
                )
                return result

            logger.warning(
                "LIMIT TIMEOUT: %s %s attempt=%d price=%.4f -- cancelling",
                side, symbol, attempt, entry_price,
            )
            self._cancel_order(order)

            if attempt < self.max_retries:
                try:
                    best_bid, best_ask = self._get_best_prices(symbol)
                except ExchangeError:
                    pass

        # ── Market fallback ────────────────────────────────────
        logger.warning(
            "MARKET FALLBACK: %s %s -- limit failed after %d attempts",
            side, symbol, self.max_retries,
        )
        success, order = self._mgr.submit_order(
            symbol=symbol, side=side, quantity=quantity,
            price=0.0, order_type="MARKET",
            leverage=leverage, stop_loss=stop_loss, take_profit=take_profit,
            reduce_only=False,
            signal_confidence=signal_confidence, signal_edge=signal_edge,
        )

        self._record_stats(filled_as_maker=False, bps_saved=0.0)

        if success and order.status == OrderStatus.FILLED:
            return MakerExecutionResult(
                success=True, symbol=symbol, side=side, quantity=quantity,
                strategy=ExecutionStrategy.MARKET_FALLBACK,
                order=order,
                initial_limit_price=initial_limit_price,
                final_fill_price=order.avg_fill_price,
                market_price_at_entry=market_mid,
                fill_latency_ms=(time.time() - start_ts) * 1000,
                slippage_saved_bps=0.0,
                retries=self.max_retries,
            )

        return MakerExecutionResult(
            success=False, symbol=symbol, side=side, quantity=quantity,
            strategy=ExecutionStrategy.FAILED, order=order,
            initial_limit_price=initial_limit_price,
            market_price_at_entry=market_mid,
            fill_latency_ms=(time.time() - start_ts) * 1000,
            error_message=order.rejection_reason if order else "market fallback failed",
        )

    # ── Stats ──────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        with self._lock:
            total  = self._total_orders
            maker  = self._maker_fills
            market = self._market_fallbacks
            avg    = (self._total_bps_saved / maker) if maker else 0.0
            return {
                "total_orders":        total,
                "maker_fills":         maker,
                "market_fallbacks":    market,
                "maker_fill_rate_pct": (maker / total * 100) if total else 0.0,
                "avg_bps_saved":       avg,
                "total_bps_saved":     self._total_bps_saved,
            }

    # ── Private helpers ────────────────────────────────────────

    def _get_best_prices(self, symbol: str) -> Tuple[float, float]:
        book = self._exchange.get_orderbook(symbol, limit=5)
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        if not bids or not asks:
            raise ExchangeError(f"Empty order book for {symbol}")
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        if best_bid <= 0 or best_ask <= 0:
            raise ExchangeError(
                f"Invalid order book prices for {symbol}: bid={best_bid} ask={best_ask}"
            )
        return best_bid, best_ask

    def _get_mid_price(self, symbol: str) -> float:
        try:
            bid, ask = self._get_best_prices(symbol)
            return (bid + ask) / 2
        except ExchangeError:
            try:
                return self._exchange.get_ticker_price(symbol)
            except Exception:
                return 0.0

    def _poll_until_filled(self, order: ManagedOrder, deadline: float) -> bool:
        while time.time() < deadline:
            time.sleep(self.poll_interval_s)
            try:
                raw      = self._exchange.get_order(order.symbol,
                                                    order_id=order.exchange_order_id)
                status   = raw.get("status", "")
                avg_px   = float(raw.get("avgPrice", 0))
                exec_qty = float(raw.get("executedQty", 0))

                if status == "FILLED":
                    order.status         = OrderStatus.FILLED
                    order.avg_fill_price = avg_px
                    order.filled_qty     = exec_qty
                    order.filled_at      = time.time()
                    return True
                elif status == "PARTIALLY_FILLED":
                    order.status         = OrderStatus.PARTIALLY_FILLED
                    order.avg_fill_price = avg_px
                    order.filled_qty     = exec_qty
                elif status in ("CANCELED", "CANCELLED", "EXPIRED", "REJECTED"):
                    return False
            except ExchangeError as exc:
                logger.warning("Poll error for %s: %s", order.internal_id, exc)

        return False

    def _cancel_order(self, order: ManagedOrder) -> None:
        try:
            self._exchange.cancel_order(order.symbol,
                                        order_id=order.exchange_order_id)
            order.status       = OrderStatus.CANCELLED
            order.cancelled_at = time.time()
        except ExchangeError as exc:
            logger.warning("Cancel failed for %s: %s (may have filled)", order.internal_id, exc)

    def _nudge_toward_market(
        self,
        price:    float,
        side:     str,
        best_bid: float,
        best_ask: float,
        attempt:  int,
    ) -> float:
        adjust = price * self.price_adjust_pct * attempt
        if side == "BUY":
            return round(min(price + adjust, best_ask), 8)
        else:
            return round(max(price - adjust, best_bid), 8)

    def _build_result(
        self,
        order:               ManagedOrder,
        side:                str,
        quantity:            float,
        initial_limit_price: float,
        market_mid:          float,
        strategy:            ExecutionStrategy,
        retries:             int,
        fill_latency_ms:     float,
    ) -> MakerExecutionResult:
        fill_price = order.avg_fill_price
        if market_mid > 0 and fill_price > 0:
            if side == "BUY":
                raw_bps = (market_mid - fill_price) / market_mid * 10_000
            else:
                raw_bps = (fill_price - market_mid) / market_mid * 10_000
            slippage_saved_bps = max(raw_bps + self.MAKER_REBATE_BPS, 0.0)
        else:
            slippage_saved_bps = self.MAKER_REBATE_BPS

        return MakerExecutionResult(
            success=True, symbol=order.symbol, side=side, quantity=quantity,
            strategy=strategy, order=order,
            initial_limit_price=initial_limit_price,
            final_fill_price=fill_price,
            market_price_at_entry=market_mid,
            fill_latency_ms=fill_latency_ms,
            slippage_saved_bps=slippage_saved_bps,
            retries=retries,
        )

    def _record_stats(self, filled_as_maker: bool, bps_saved: float) -> None:
        with self._lock:
            self._total_orders += 1
            if filled_as_maker:
                self._maker_fills     += 1
                self._total_bps_saved += bps_saved
            else:
                self._market_fallbacks += 1
