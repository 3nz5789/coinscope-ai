"""
orderbook_scanner.py — Order Book Imbalance Detection
======================================================
Analyses the live order book depth to detect bid/ask imbalances,
large hidden walls, and absorption events.

Logic
-----
1. Imbalance ratio  — (bid_depth - ask_depth) / total_depth
   Strong buy-side pressure  → LONG  hit
   Strong sell-side pressure → SHORT hit

2. Large wall detection — a single price level with outsized qty
   vs the average level qty across the book.
   Walls above price → resistance → SHORT bias
   Walls below price → support    → LONG bias

3. Spread anomaly — unusually wide spread signals low liquidity
   or imminent volatility.

Thresholds
----------
  IMBALANCE_THRESHOLD  — min imbalance ratio to trigger (default 0.65 = 65% bid vs 35% ask)
  WALL_MULTIPLIER      — level must be N× the average to count as a wall
  SPREAD_THRESHOLD_PCT — spread > this % of mid price → anomaly
"""

from __future__ import annotations

import time
from typing import Optional

from config import settings
from data.binance_rest import BinanceRESTClient
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer, OrderBook, OrderBookLevel
from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult, SignalDirection, HitStrength
from utils.helpers import safe_divide, human_number
from utils.logger import get_logger

logger = get_logger(__name__)

IMBALANCE_THRESHOLD  = 0.65   # 65% one side to trigger
WALL_MULTIPLIER      = 5.0    # level must be 5× avg to be a wall
SPREAD_THRESHOLD_PCT = 0.05   # 0.05% spread is anomalous for perps
BOOK_DEPTH           = 20     # number of levels to fetch


class OrderBookScanner(BaseScanner):
    """
    Detects order-book imbalances and large price walls.

    Signals are contrarian when a large wall is present (price likely
    to reverse at the wall) and trend-following when imbalance is strong
    (large bid stack → buying pressure → LONG).
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        depth: int = BOOK_DEPTH,
        imbalance_threshold: float = IMBALANCE_THRESHOLD,
        wall_multiplier: float = WALL_MULTIPLIER,
    ) -> None:
        super().__init__(cache, rest, name="OrderBookScanner")
        self._normalizer   = DataNormalizer()
        self._depth        = depth
        self._imbalance_th = imbalance_threshold
        self._wall_mult    = wall_multiplier

    async def scan(self, symbol: str) -> ScannerResult:
        t0   = time.monotonic()
        hits: list[ScannerHit] = []

        try:
            book = await self._fetch_orderbook(symbol)

            hits += self._check_imbalance(symbol, book)
            hits += self._check_walls(symbol, book)
            hits += self._check_spread(symbol, book)

        except Exception as exc:
            logger.error("%s error for %s: %s", self.name, symbol, exc)
            return ScannerResult(scanner=self.name, symbol=symbol, error=str(exc))

        return self._make_result(symbol, hits, (time.monotonic() - t0) * 1000)

    # ── Imbalance check ──────────────────────────────────────────────────

    def _check_imbalance(self, symbol: str, book: OrderBook) -> list[ScannerHit]:
        hits = []
        ratio = book.imbalance_ratio   # > 0.5 → more bids

        if ratio >= self._imbalance_th:
            strength, score = self._classify_imbalance(ratio)
            hits.append(self._make_hit(
                symbol    = symbol,
                direction = SignalDirection.LONG,
                strength  = strength,
                score     = score,
                reason    = (
                    f"Bid-side dominance: {ratio:.0%} bid "
                    f"({human_number(book.bid_depth)} vs {human_number(book.ask_depth)} ask)"
                ),
                metadata  = {
                    "imbalance_ratio": round(ratio, 3),
                    "bid_depth_usd":   round(book.bid_depth, 0),
                    "ask_depth_usd":   round(book.ask_depth, 0),
                    "spread_pct":      round(book.spread_pct, 4),
                },
            ))

        elif ratio <= (1.0 - self._imbalance_th):
            ask_ratio = 1.0 - ratio
            strength, score = self._classify_imbalance(ask_ratio)
            hits.append(self._make_hit(
                symbol    = symbol,
                direction = SignalDirection.SHORT,
                strength  = strength,
                score     = score,
                reason    = (
                    f"Ask-side dominance: {ask_ratio:.0%} ask "
                    f"({human_number(book.ask_depth)} vs {human_number(book.bid_depth)} bid)"
                ),
                metadata  = {
                    "imbalance_ratio": round(ratio, 3),
                    "bid_depth_usd":   round(book.bid_depth, 0),
                    "ask_depth_usd":   round(book.ask_depth, 0),
                    "spread_pct":      round(book.spread_pct, 4),
                },
            ))
        return hits

    # ── Wall detection ───────────────────────────────────────────────────

    def _check_walls(self, symbol: str, book: OrderBook) -> list[ScannerHit]:
        hits = []
        if not book.bids or not book.asks:
            return hits

        mid_price = (book.best_bid.price + book.best_ask.price) / 2

        # Support wall (in bids) → bullish
        bid_wall = self._find_wall(book.bids)
        if bid_wall:
            hits.append(self._make_hit(
                symbol    = symbol,
                direction = SignalDirection.LONG,
                strength  = HitStrength.MEDIUM,
                score     = 20.0,
                reason    = (
                    f"Support wall @ {bid_wall.price:,.2f} "
                    f"({human_number(bid_wall.price * bid_wall.qty)} USDT)"
                ),
                metadata  = {
                    "wall_price": bid_wall.price,
                    "wall_qty":   bid_wall.qty,
                    "wall_side":  "bid",
                    "distance_pct": round(safe_divide(mid_price - bid_wall.price, mid_price) * 100, 2),
                },
            ))

        # Resistance wall (in asks) → bearish
        ask_wall = self._find_wall(book.asks)
        if ask_wall:
            hits.append(self._make_hit(
                symbol    = symbol,
                direction = SignalDirection.SHORT,
                strength  = HitStrength.MEDIUM,
                score     = 20.0,
                reason    = (
                    f"Resistance wall @ {ask_wall.price:,.2f} "
                    f"({human_number(ask_wall.price * ask_wall.qty)} USDT)"
                ),
                metadata  = {
                    "wall_price": ask_wall.price,
                    "wall_qty":   ask_wall.qty,
                    "wall_side":  "ask",
                    "distance_pct": round(safe_divide(ask_wall.price - mid_price, mid_price) * 100, 2),
                },
            ))
        return hits

    def _find_wall(self, levels: list[OrderBookLevel]) -> Optional[OrderBookLevel]:
        """Return the largest level if it exceeds WALL_MULTIPLIER × average."""
        if not levels:
            return None
        avg_qty = sum(lvl.qty for lvl in levels) / len(levels)
        largest = max(levels, key=lambda lvl: lvl.qty)
        if avg_qty > 0 and largest.qty >= avg_qty * self._wall_mult:
            return largest
        return None

    # ── Spread anomaly ───────────────────────────────────────────────────

    def _check_spread(self, symbol: str, book: OrderBook) -> list[ScannerHit]:
        hits = []
        if book.spread_pct >= SPREAD_THRESHOLD_PCT:
            hits.append(self._make_hit(
                symbol    = symbol,
                direction = SignalDirection.NEUTRAL,
                strength  = HitStrength.WEAK,
                score     = 8.0,
                reason    = (
                    f"Wide spread anomaly: {book.spread_pct:.4f}% "
                    f"(bid={book.best_bid.price:,.2f} ask={book.best_ask.price:,.2f})"
                ),
                metadata  = {"spread_pct": round(book.spread_pct, 4)},
            ))
        return hits

    # ── Classification ───────────────────────────────────────────────────

    def _classify_imbalance(self, dominant_ratio: float) -> tuple[HitStrength, float]:
        if dominant_ratio >= 0.80:
            return HitStrength.STRONG, 35.0 + (dominant_ratio - 0.80) * 100
        if dominant_ratio >= 0.72:
            return HitStrength.MEDIUM, 20.0 + (dominant_ratio - 0.72) * 187
        return HitStrength.WEAK, 10.0 + (dominant_ratio - self._imbalance_th) * 143

    # ── Data fetching ────────────────────────────────────────────────────

    async def _fetch_orderbook(self, symbol: str) -> OrderBook:
        cache_key = f"orderbook:{symbol}"
        cached = await self.cache.get(cache_key)
        if cached:
            return _dict_to_book(symbol, cached)
        raw  = await self.rest.get_order_book(symbol, limit=self._depth)
        book = self._normalizer.depth_to_orderbook(symbol, raw)
        await self.cache.set(cache_key, _book_to_dict(book), ttl=2)
        return book


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _book_to_dict(b: OrderBook) -> dict:
    return {
        "last_update_id": b.last_update_id,
        "bids": [[lvl.price, lvl.qty] for lvl in b.bids],
        "asks": [[lvl.price, lvl.qty] for lvl in b.asks],
    }


def _dict_to_book(symbol: str, d: dict) -> OrderBook:
    return OrderBook(
        symbol=symbol,
        last_update_id=d["last_update_id"],
        bids=[OrderBookLevel(b[0], b[1]) for b in d["bids"]],
        asks=[OrderBookLevel(a[0], a[1]) for a in d["asks"]],
    )
