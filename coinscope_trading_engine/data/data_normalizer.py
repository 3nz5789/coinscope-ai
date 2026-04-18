"""
data_normalizer.py — Data Standardisation Layer
================================================
Converts raw Binance exchange payloads (REST and WebSocket) into consistent
internal schemas used throughout the engine.

Every scanner, signal, and risk module imports these dataclasses rather than
working with raw dicts, ensuring a single source of truth for field names,
types, and units.

Schemas
-------
Candle          : OHLCV candlestick (from REST klines or WS kline stream)
Ticker          : 24-hour price statistics
Trade           : Individual trade execution
OrderBook       : Bid/ask depth snapshot
MarkPrice       : Mark price + funding rate
FundingRate     : Historical funding rate entry
OpenInterest    : Open interest snapshot
LiquidationOrder: Forced liquidation event
AggTrade        : Aggregated trade

Usage
-----
    from data.data_normalizer import DataNormalizer

    normalizer = DataNormalizer()

    # From REST klines response
    candles = normalizer.klines_to_candles("BTCUSDT", raw_klines)

    # From WebSocket kline stream event
    candle = normalizer.ws_kline_to_candle(ws_event)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal schemas (dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    """OHLCV candlestick bar."""
    symbol:        str
    interval:      str
    open_time:     datetime
    close_time:    datetime
    open:          float
    high:          float
    low:           float
    close:         float
    volume:        float           # base asset volume
    quote_volume:  float           # quote asset (USDT) volume
    trades:        int             # number of trades in the bar
    taker_buy_base_volume:  float  # taker buy base asset volume
    taker_buy_quote_volume: float  # taker buy quote asset volume
    is_closed:     bool = True     # False for the currently-forming candle

    @property
    def body_pct(self) -> float:
        """Candle body size as % of the high-low range."""
        rng = self.high - self.low
        return abs(self.close - self.open) / rng * 100 if rng else 0.0

    @property
    def upper_wick_pct(self) -> float:
        top = max(self.open, self.close)
        rng = self.high - self.low
        return (self.high - top) / rng * 100 if rng else 0.0

    @property
    def lower_wick_pct(self) -> float:
        bottom = min(self.open, self.close)
        rng = self.high - self.low
        return (bottom - self.low) / rng * 100 if rng else 0.0

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


@dataclass
class Ticker:
    """24-hour rolling price statistics."""
    symbol:               str
    price_change:         float
    price_change_pct:     float
    weighted_avg_price:   float
    last_price:           float
    last_qty:             float
    open_price:           float
    high_price:           float
    low_price:            float
    volume:               float        # base asset volume
    quote_volume:         float        # quote asset volume
    open_time:            datetime
    close_time:           datetime
    trades:               int
    timestamp:            datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Trade:
    """Individual trade execution."""
    symbol:      str
    trade_id:    int
    price:       float
    qty:         float
    quote_qty:   float
    time:        datetime
    is_buyer_maker: bool


@dataclass
class AggTrade:
    """Compressed / aggregated trade."""
    symbol:         str
    agg_id:         int
    price:          float
    qty:            float
    first_trade_id: int
    last_trade_id:  int
    time:           datetime
    is_buyer_maker: bool


@dataclass
class OrderBookLevel:
    """Single price level in the order book."""
    price: float
    qty:   float


@dataclass
class OrderBook:
    """Depth snapshot — top N bids and asks."""
    symbol:       str
    last_update_id: int
    bids:         list[OrderBookLevel]
    asks:         list[OrderBookLevel]
    timestamp:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return 0.0

    @property
    def spread_pct(self) -> float:
        if self.best_ask and self.best_ask.price > 0:
            return self.spread / self.best_ask.price * 100
        return 0.0

    @property
    def bid_depth(self) -> float:
        """Total bid-side liquidity in quote asset."""
        return sum(lvl.price * lvl.qty for lvl in self.bids)

    @property
    def ask_depth(self) -> float:
        """Total ask-side liquidity in quote asset."""
        return sum(lvl.price * lvl.qty for lvl in self.asks)

    @property
    def imbalance_ratio(self) -> float:
        """
        Order book imbalance: > 0.5 → more bids (bullish pressure),
                               < 0.5 → more asks (bearish pressure).
        """
        total = self.bid_depth + self.ask_depth
        return self.bid_depth / total if total else 0.5


@dataclass
class MarkPrice:
    """Mark price and funding rate for a futures symbol."""
    symbol:              str
    mark_price:          float
    index_price:         float
    estimated_settle_price: float
    last_funding_rate:   float
    next_funding_time:   datetime
    interest_rate:       float
    time:                datetime


@dataclass
class FundingRate:
    """Single historical funding rate record."""
    symbol:       str
    funding_rate: float
    funding_time: datetime


@dataclass
class OpenInterest:
    """Open interest snapshot."""
    symbol:        str
    open_interest: float          # contracts
    time:          datetime


@dataclass
class LiquidationOrder:
    """Forced liquidation event."""
    symbol:        str
    side:          str            # "BUY" | "SELL"
    order_type:    str
    time_in_force: str
    qty:           float
    price:         float
    avg_price:     float
    status:        str
    time:          datetime

    @property
    def notional(self) -> float:
        return self.avg_price * self.qty


# ---------------------------------------------------------------------------
# Normalizer class
# ---------------------------------------------------------------------------

class DataNormalizer:
    """
    Converts raw Binance REST and WebSocket payloads into typed internal schemas.

    All methods are pure (no side effects) and return new dataclass instances.
    """

    # ── Candles ─────────────────────────────────────────────────────────

    def klines_to_candles(self, symbol: str, interval: str, raw: list[list]) -> list[Candle]:
        """
        Convert a list of raw REST kline arrays into Candle objects.

        Raw kline format (from GET /fapi/v1/klines):
        [open_time, open, high, low, close, volume, close_time,
         quote_vol, trades, taker_buy_base_vol, taker_buy_quote_vol, ignore]
        """
        candles = []
        for k in raw:
            try:
                candles.append(Candle(
                    symbol       = symbol,
                    interval     = interval,
                    open_time    = _ms_to_dt(int(k[0])),
                    close_time   = _ms_to_dt(int(k[6])),
                    open         = float(k[1]),
                    high         = float(k[2]),
                    low          = float(k[3]),
                    close        = float(k[4]),
                    volume       = float(k[5]),
                    quote_volume = float(k[7]),
                    trades       = int(k[8]),
                    taker_buy_base_volume  = float(k[9]),
                    taker_buy_quote_volume = float(k[10]),
                    is_closed    = True,
                ))
            except (IndexError, ValueError, TypeError) as exc:
                logger.warning("Skipping malformed kline for %s: %s", symbol, exc)
        return candles

    def ws_kline_to_candle(self, event: dict) -> Optional[Candle]:
        """
        Convert a WebSocket kline stream event into a Candle.

        WS kline event format:
        {"e":"kline","E":..., "s":"BTCUSDT",
         "k":{"t":...,"T":...,"s":"BTCUSDT","i":"5m","o":"...","c":"...","x":false,...}}
        """
        try:
            k = event["k"]
            return Candle(
                symbol       = k["s"],
                interval     = k["i"],
                open_time    = _ms_to_dt(int(k["t"])),
                close_time   = _ms_to_dt(int(k["T"])),
                open         = float(k["o"]),
                high         = float(k["h"]),
                low          = float(k["l"]),
                close        = float(k["c"]),
                volume       = float(k["v"]),
                quote_volume = float(k["q"]),
                trades       = int(k["n"]),
                taker_buy_base_volume  = float(k["V"]),
                taker_buy_quote_volume = float(k["Q"]),
                is_closed    = bool(k["x"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse WS kline event: %s | %s", exc, event)
            return None

    # ── Ticker ───────────────────────────────────────────────────────────

    def ticker_to_ticker(self, raw: dict) -> Ticker:
        """Convert a 24hr ticker REST response into a Ticker object."""
        return Ticker(
            symbol             = raw["symbol"],
            price_change       = float(raw["priceChange"]),
            price_change_pct   = float(raw["priceChangePercent"]),
            weighted_avg_price = float(raw["weightedAvgPrice"]),
            last_price         = float(raw["lastPrice"]),
            last_qty           = float(raw.get("lastQty", 0)),
            open_price         = float(raw["openPrice"]),
            high_price         = float(raw["highPrice"]),
            low_price          = float(raw["lowPrice"]),
            volume             = float(raw["volume"]),
            quote_volume       = float(raw["quoteVolume"]),
            open_time          = _ms_to_dt(int(raw["openTime"])),
            close_time         = _ms_to_dt(int(raw["closeTime"])),
            trades             = int(raw["count"]),
        )

    def ws_ticker_to_ticker(self, event: dict) -> Ticker:
        """Convert a WebSocket 24hr miniTicker / ticker stream event."""
        return Ticker(
            symbol             = event["s"],
            price_change       = float(event.get("p", 0)),
            price_change_pct   = float(event.get("P", 0)),
            weighted_avg_price = float(event.get("w", event.get("c", 0))),
            last_price         = float(event["c"]),
            last_qty           = float(event.get("Q", 0)),
            open_price         = float(event.get("o", 0)),
            high_price         = float(event["h"]),
            low_price          = float(event["l"]),
            volume             = float(event["v"]),
            quote_volume       = float(event["q"]),
            open_time          = _ms_to_dt(int(event.get("O", 0))),
            close_time         = _ms_to_dt(int(event.get("C", 0))),
            trades             = int(event.get("n", 0)),
            timestamp          = _ms_to_dt(int(event["E"])),
        )

    # ── Order Book ───────────────────────────────────────────────────────

    def depth_to_orderbook(self, symbol: str, raw: dict) -> OrderBook:
        """Convert a REST depth snapshot into an OrderBook."""
        return OrderBook(
            symbol         = symbol,
            last_update_id = int(raw["lastUpdateId"]),
            bids = [OrderBookLevel(float(b[0]), float(b[1])) for b in raw["bids"]],
            asks = [OrderBookLevel(float(a[0]), float(a[1])) for a in raw["asks"]],
        )

    def ws_depth_to_orderbook(self, symbol: str, event: dict) -> OrderBook:
        """Convert a WebSocket depthUpdate event into an OrderBook."""
        return OrderBook(
            symbol         = symbol,
            last_update_id = int(event.get("u", event.get("lastUpdateId", 0))),
            bids = [OrderBookLevel(float(b[0]), float(b[1])) for b in event.get("b", [])],
            asks = [OrderBookLevel(float(a[0]), float(a[1])) for a in event.get("a", [])],
            timestamp = _ms_to_dt(int(event.get("E", 0))) if event.get("E") else
                        __import__("datetime").datetime.now(timezone.utc),
        )

    # ── Mark Price & Funding Rate ────────────────────────────────────────

    def mark_price_to_schema(self, raw: dict) -> MarkPrice:
        """Convert a REST premiumIndex response into a MarkPrice object."""
        return MarkPrice(
            symbol                  = raw["symbol"],
            mark_price              = float(raw["markPrice"]),
            index_price             = float(raw["indexPrice"]),
            estimated_settle_price  = float(raw.get("estimatedSettlePrice", 0)),
            last_funding_rate       = float(raw["lastFundingRate"]),
            next_funding_time       = _ms_to_dt(int(raw["nextFundingTime"])),
            interest_rate           = float(raw.get("interestRate", 0)),
            time                    = _ms_to_dt(int(raw["time"])),
        )

    def funding_rate_history_to_schema(self, raw_list: list[dict]) -> list[FundingRate]:
        """Convert a list of REST fundingRate history items."""
        result = []
        for r in raw_list:
            try:
                result.append(FundingRate(
                    symbol       = r["symbol"],
                    funding_rate = float(r["fundingRate"]),
                    funding_time = _ms_to_dt(int(r["fundingTime"])),
                ))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed funding rate record: %s", exc)
        return result

    # ── Open Interest ────────────────────────────────────────────────────

    def open_interest_to_schema(self, raw: dict) -> OpenInterest:
        """Convert a REST openInterest response."""
        return OpenInterest(
            symbol        = raw["symbol"],
            open_interest = float(raw["openInterest"]),
            time          = _ms_to_dt(int(raw["time"])),
        )

    # ── Liquidations ─────────────────────────────────────────────────────

    def liquidation_to_schema(self, raw: dict) -> Optional[LiquidationOrder]:
        """
        Convert a REST allForceOrders entry or a WS forceOrder event
        into a LiquidationOrder.
        """
        try:
            # REST response has the order fields directly;
            # WS forceOrder event nests them under "o"
            order = raw.get("o", raw)
            return LiquidationOrder(
                symbol        = order["s"],
                side          = order["S"],
                order_type    = order["o"],
                time_in_force = order["f"],
                qty           = float(order["q"]),
                price         = float(order["p"]),
                avg_price     = float(order["ap"]),
                status        = order["X"],
                time          = _ms_to_dt(int(order["T"])),
            )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse liquidation order: %s | %s", exc, raw)
            return None

    # ── Trades ───────────────────────────────────────────────────────────

    def trade_to_schema(self, symbol: str, raw: dict) -> Trade:
        """Convert a REST recent trade entry."""
        return Trade(
            symbol         = symbol,
            trade_id       = int(raw["id"]),
            price          = float(raw["price"]),
            qty            = float(raw["qty"]),
            quote_qty      = float(raw["quoteQty"]),
            time           = _ms_to_dt(int(raw["time"])),
            is_buyer_maker = bool(raw["isBuyerMaker"]),
        )

    def agg_trade_to_schema(self, symbol: str, raw: dict) -> AggTrade:
        """Convert a REST aggTrade entry or WS aggTrade event."""
        # REST uses "a", WS uses "a" too — same field name
        return AggTrade(
            symbol         = symbol,
            agg_id         = int(raw.get("a", raw.get("A", 0))),
            price          = float(raw["p"]),
            qty            = float(raw["q"]),
            first_trade_id = int(raw["f"]),
            last_trade_id  = int(raw["l"]),
            time           = _ms_to_dt(int(raw["T"])),
            is_buyer_maker = bool(raw["m"]),
        )

    # ── Batch helpers ────────────────────────────────────────────────────

    def normalise_ticker_list(self, raw_list: list[dict]) -> list[Ticker]:
        """Normalise a list of 24hr ticker dicts (all-symbols response)."""
        tickers = []
        for raw in raw_list:
            try:
                tickers.append(self.ticker_to_ticker(raw))
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed ticker: %s", exc)
        return tickers


# ---------------------------------------------------------------------------
# Private helper
# ---------------------------------------------------------------------------

def _ms_to_dt(ms: int) -> datetime:
    """Convert a Unix millisecond timestamp to a UTC-aware datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
