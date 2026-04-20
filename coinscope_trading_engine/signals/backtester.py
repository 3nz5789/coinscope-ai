"""
backtester.py — Strategy Backtesting Engine
=============================================
Simulates the performance of the CoinScopeAI signal pipeline against
historical OHLCV data to evaluate strategy quality before live trading.

How it works
------------
1. Loads historical candles for each symbol/timeframe
2. Replays the IndicatorEngine + ConfluenceScorer on each bar
3. When a signal fires, opens a simulated trade using EntryExitCalculator levels
4. Tracks trade outcomes (TP hit, SL hit, or expired after max_bars)
5. Aggregates statistics: win rate, avg RR, profit factor, max drawdown, Sharpe

Usage
-----
    from signals.backtester import Backtester, BacktestConfig

    config = BacktestConfig(
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframe="5m",
        lookback_days=30,
        initial_balance=10_000,
    )

    backtester = Backtester(config)
    results    = await backtester.run(rest_client)
    print(results.summary())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from data.binance_rest import BinanceRESTClient
from data.data_normalizer import DataNormalizer, Candle
from scanner.base_scanner import SignalDirection
from signals.indicator_engine import IndicatorEngine
from signals.confluence_scorer import ConfluenceScorer, Signal
from signals.entry_exit_calculator import EntryExitCalculator, TradeSetup
from utils.helpers import pct_change, safe_divide, dt_to_ms, now_ms
from utils.logger import get_logger

logger = get_logger(__name__)

# Backtest defaults
DEFAULT_LOOKBACK_DAYS  = 30
DEFAULT_INITIAL_BALANCE = 10_000.0
DEFAULT_RISK_PER_TRADE_PCT = 1.0     # 1% of balance per trade
DEFAULT_MAX_BARS_IN_TRADE  = 20      # close trade after N bars if neither TP nor SL hit
MIN_CANDLES_BEFORE_SIGNAL  = 50      # warm-up period


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    symbols:               list[str]
    timeframe:             str          = "5m"
    lookback_days:         int          = DEFAULT_LOOKBACK_DAYS
    initial_balance:       float        = DEFAULT_INITIAL_BALANCE
    risk_per_trade_pct:    float        = DEFAULT_RISK_PER_TRADE_PCT
    max_bars_in_trade:     int          = DEFAULT_MAX_BARS_IN_TRADE
    min_confluence_score:  float        = 60.0
    commission_pct:        float        = 0.04    # 0.04% per side (Binance futures taker)
    slippage_pct:          float        = 0.01    # 0.01% slippage assumption
    use_tp1_partial:       bool         = True    # take 50% off at TP1
    tp1_close_pct:         float        = 0.50    # fraction closed at TP1
    # ATR-based entry/exit multipliers (default to EntryExitCalculator defaults)
    atr_sl_mult:           float        = 1.5
    atr_tp1_mult:          float        = 1.5
    atr_tp2_mult:          float        = 3.0
    atr_tp3_mult:           float        = 4.5
    min_rr:                Optional[float] = None
    # Direction filter — restrict to one side. Values: "BOTH", "LONG_ONLY", "SHORT_ONLY".
    allowed_directions:    str          = "BOTH"
    # Multi-timeframe trend filter: require the 4h EMA trend to agree with
    # signal direction. Drops signals that fire counter to higher-timeframe.
    mtf_filter_enabled:    bool         = False
    mtf_block_neutral:     bool         = True
    mtf_htf_timeframe:     str          = "4h"    # higher-timeframe bars used for the trend


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------

@dataclass
class BacktestTrade:
    """Record of a single simulated trade."""
    symbol:       str
    direction:    SignalDirection
    entry_price:  float
    stop_loss:    float
    tp1:          float
    tp2:          float
    signal_score: float
    entry_bar:    int              # index in candle list
    exit_bar:     int    = -1
    exit_price:   float  = 0.0
    exit_reason:  str    = ""      # "TP1" | "TP2" | "SL" | "EXPIRED" | "TP1+TP2"
    pnl_pct:      float  = 0.0
    pnl_usdt:     float  = 0.0
    risk_usdt:    float  = 0.0
    rr_achieved:  float  = 0.0
    is_winner:    bool   = False

    @property
    def bars_held(self) -> int:
        return max(0, self.exit_bar - self.entry_bar)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class BacktestResults:
    """Aggregated statistics for a completed backtest run."""
    config:        BacktestConfig
    trades:        list[BacktestTrade]  = field(default_factory=list)
    equity_curve:  list[float]          = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def winning_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.is_winner]

    @property
    def losing_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if not t.is_winner]

    @property
    def win_rate(self) -> float:
        return safe_divide(len(self.winning_trades), self.total_trades) * 100

    @property
    def avg_win_pct(self) -> float:
        wins = [t.pnl_pct for t in self.winning_trades]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss_pct(self) -> float:
        losses = [t.pnl_pct for t in self.losing_trades]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl_usdt for t in self.winning_trades)
        gross_loss   = abs(sum(t.pnl_usdt for t in self.losing_trades))
        return safe_divide(gross_profit, gross_loss)

    @property
    def total_pnl_usdt(self) -> float:
        return sum(t.pnl_usdt for t in self.trades)

    @property
    def final_balance(self) -> float:
        return self.config.initial_balance + self.total_pnl_usdt

    @property
    def total_return_pct(self) -> float:
        return pct_change(self.config.initial_balance, self.final_balance)

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for val in self.equity_curve:
            peak = max(peak, val)
            dd   = safe_divide(peak - val, peak) * 100
            max_dd = max(max_dd, dd)
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        """Simplified Sharpe using per-trade returns (not annualised)."""
        if len(self.trades) < 2:
            return 0.0
        returns = [t.pnl_pct for t in self.trades]
        mean    = sum(returns) / len(returns)
        std     = math.sqrt(sum((r - mean) ** 2 for r in returns) / len(returns))
        return safe_divide(mean, std)

    @property
    def avg_rr_achieved(self) -> float:
        if not self.trades:
            return 0.0
        return sum(t.rr_achieved for t in self.trades) / len(self.trades)

    def summary(self) -> str:
        return (
            f"\n{'='*56}\n"
            f"  CoinScopeAI Backtest Results\n"
            f"{'='*56}\n"
            f"  Period     : {self.config.lookback_days}d | TF: {self.config.timeframe}\n"
            f"  Symbols    : {self.config.symbols}\n"
            f"  Trades     : {self.total_trades} "
            f"(W:{len(self.winning_trades)} L:{len(self.losing_trades)})\n"
            f"  Win Rate   : {self.win_rate:.1f}%\n"
            f"  Avg Win    : +{self.avg_win_pct:.2f}%\n"
            f"  Avg Loss   : {self.avg_loss_pct:.2f}%\n"
            f"  Profit Factor : {self.profit_factor:.2f}\n"
            f"  Avg RR     : {self.avg_rr_achieved:.2f}x\n"
            f"  Total PnL  : ${self.total_pnl_usdt:+,.2f} ({self.total_return_pct:+.2f}%)\n"
            f"  Final Bal  : ${self.final_balance:,.2f}\n"
            f"  Max DD     : {self.max_drawdown_pct:.2f}%\n"
            f"  Sharpe     : {self.sharpe_ratio:.2f}\n"
            f"{'='*56}"
        )


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------

class Backtester:
    """
    Event-driven backtester for the CoinScopeAI signal pipeline.

    Replays historical candles bar-by-bar, fires the indicator engine
    and scorer on each bar, and simulates trade execution.
    """

    def __init__(self, config: BacktestConfig) -> None:
        self._config     = config
        self._normalizer = DataNormalizer()
        self._indicator  = IndicatorEngine()
        self._scorer     = ConfluenceScorer(
            min_score=config.min_confluence_score,
            require_indicator_alignment=True,
        )
        self._calculator = EntryExitCalculator(
            atr_sl_mult  = config.atr_sl_mult,
            atr_tp1_mult = config.atr_tp1_mult,
            atr_tp2_mult = config.atr_tp2_mult,
            atr_tp3_mult = config.atr_tp3_mult,
            min_rr       = config.min_rr,
        )

        # Multi-timeframe trend gate (computed from resampled 1h→4h closes)
        self._mtf_filter = None
        if config.mtf_filter_enabled:
            from core.multi_timeframe_filter import MultiTimeframeFilter
            self._mtf_filter = MultiTimeframeFilter(ema_fast=9, ema_slow=21)

    def _htf_ratio(self) -> int:
        """How many base-TF bars make one HTF bar (1h→4h = 4, 15m→4h = 16)."""
        tf = self._config.timeframe
        htf = self._config.mtf_htf_timeframe
        unit = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
                "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440}
        base = unit.get(tf, 60)
        high = unit.get(htf, 240)
        return max(1, high // base)

    async def run(self, rest: BinanceRESTClient) -> BacktestResults:
        """
        Execute the full backtest and return aggregated results.

        Parameters
        ----------
        rest : BinanceRESTClient
            Connected REST client to fetch historical klines.
        """
        results = BacktestResults(config=self._config)
        balance = self._config.initial_balance
        results.equity_curve.append(balance)

        for symbol in self._config.symbols:
            logger.info("Backtesting %s on %s for %d days…",
                        symbol, self._config.timeframe, self._config.lookback_days)
            candles = await self._fetch_candles(rest, symbol)
            if len(candles) < MIN_CANDLES_BEFORE_SIGNAL + 10:
                logger.warning("Not enough candles for %s (%d) — skipping", symbol, len(candles))
                continue

            trades, balance, equity = self._replay(symbol, candles, balance)
            results.trades.extend(trades)
            results.equity_curve.extend(equity)

        logger.info("Backtest complete: %d trades | balance=$%.2f",
                    results.total_trades, results.final_balance)
        return results

    # ── Bar replay ───────────────────────────────────────────────────────

    def _replay(
        self,
        symbol: str,
        candles: list[Candle],
        balance: float,
    ) -> tuple[list[BacktestTrade], float, list[float]]:
        """Replay all bars for one symbol."""
        trades:       list[BacktestTrade] = []
        equity_curve: list[float]         = []
        open_trade:   Optional[BacktestTrade] = None
        tp1_hit       = False

        for i in range(MIN_CANDLES_BEFORE_SIGNAL, len(candles)):
            window = candles[:i]      # candles seen so far (no lookahead)
            bar    = candles[i]       # current bar being evaluated

            # ── Manage open trade ─────────────────────────────────────────
            if open_trade:
                open_trade, tp1_hit, closed = self._update_trade(
                    open_trade, bar, i, tp1_hit
                )
                if closed:
                    pnl = self._settle_trade(open_trade, balance)
                    balance += pnl
                    open_trade.pnl_usdt = pnl
                    trades.append(open_trade)
                    equity_curve.append(balance)
                    open_trade = None
                    tp1_hit    = False
                continue   # no new entry while in trade

            # ── Check for new signal ──────────────────────────────────────
            signal = self._generate_signal(symbol, window)
            if not signal or not signal.is_actionable:
                continue
            # Direction filter
            if self._config.allowed_directions == "LONG_ONLY" and signal.direction != SignalDirection.LONG:
                continue
            if self._config.allowed_directions == "SHORT_ONLY" and signal.direction != SignalDirection.SHORT:
                continue

            # Multi-timeframe trend filter — only fire with the 4h trend
            if self._mtf_filter is not None:
                import numpy as _np
                ratio = self._htf_ratio()
                # Resample base-TF closes to HTF: take every `ratio`-th close
                htf_closes = _np.array(
                    [c.close for c in window[::ratio]],
                    dtype=float,
                )
                htf_trend = self._mtf_filter.get_4h_trend(htf_closes)
                want = "bull" if signal.direction == SignalDirection.LONG else "bear"
                agreed = (htf_trend == want)
                if not agreed:
                    if htf_trend == "neutral" and not self._config.mtf_block_neutral:
                        pass
                    else:
                        continue

            setup = self._calculator.calculate(signal, window)
            if not setup.valid or setup.entry <= 0:
                continue

            risk_usdt = balance * self._config.risk_per_trade_pct / 100
            open_trade = BacktestTrade(
                symbol       = symbol,
                direction    = signal.direction,
                entry_price  = bar.close,       # fill at next bar open approximation
                stop_loss    = setup.stop_loss,
                tp1          = setup.tp1,
                tp2          = setup.tp2,
                signal_score = signal.score,
                entry_bar    = i,
                risk_usdt    = risk_usdt,
            )
            logger.debug("Backtest entry: %s at bar %d price=%.2f", symbol, i, bar.close)

        # Close any trade still open at end of data
        if open_trade and len(candles) > open_trade.entry_bar:
            last_bar = candles[-1]
            open_trade.exit_price  = last_bar.close
            open_trade.exit_bar    = len(candles) - 1
            open_trade.exit_reason = "END_OF_DATA"
            pnl = self._settle_trade(open_trade, balance)
            balance += pnl
            open_trade.pnl_usdt = pnl
            trades.append(open_trade)
            equity_curve.append(balance)

        return trades, balance, equity_curve

    def _update_trade(
        self,
        trade: BacktestTrade,
        bar: Candle,
        bar_idx: int,
        tp1_hit: bool,
    ) -> tuple[BacktestTrade, bool, bool]:
        """
        Check if the current bar triggers TP1, TP2, or SL.
        Returns (updated_trade, tp1_hit, trade_closed).
        """
        is_long = trade.direction == SignalDirection.LONG
        closed  = False

        if is_long:
            # SL check
            if bar.low <= trade.stop_loss:
                trade.exit_price  = trade.stop_loss
                trade.exit_bar    = bar_idx
                trade.exit_reason = "SL"
                trade.is_winner   = False
                closed = True

            # TP1 check (partial close)
            elif not tp1_hit and bar.high >= trade.tp1:
                tp1_hit = True
                if not self._config.use_tp1_partial:
                    trade.exit_price  = trade.tp1
                    trade.exit_bar    = bar_idx
                    trade.exit_reason = "TP1"
                    trade.is_winner   = True
                    closed = True

            # TP2 check (full close)
            elif tp1_hit and bar.high >= trade.tp2:
                trade.exit_price  = trade.tp2
                trade.exit_bar    = bar_idx
                trade.exit_reason = "TP1+TP2"
                trade.is_winner   = True
                closed = True

        else:  # SHORT
            if bar.high >= trade.stop_loss:
                trade.exit_price  = trade.stop_loss
                trade.exit_bar    = bar_idx
                trade.exit_reason = "SL"
                trade.is_winner   = False
                closed = True

            elif not tp1_hit and bar.low <= trade.tp1:
                tp1_hit = True
                if not self._config.use_tp1_partial:
                    trade.exit_price  = trade.tp1
                    trade.exit_bar    = bar_idx
                    trade.exit_reason = "TP1"
                    trade.is_winner   = True
                    closed = True

            elif tp1_hit and bar.low <= trade.tp2:
                trade.exit_price  = trade.tp2
                trade.exit_bar    = bar_idx
                trade.exit_reason = "TP1+TP2"
                trade.is_winner   = True
                closed = True

        # Expiry check
        if not closed and (bar_idx - trade.entry_bar) >= self._config.max_bars_in_trade:
            trade.exit_price  = bar.close
            trade.exit_bar    = bar_idx
            trade.exit_reason = "EXPIRED"
            trade.is_winner   = (
                (trade.direction == SignalDirection.LONG  and bar.close > trade.entry_price) or
                (trade.direction == SignalDirection.SHORT and bar.close < trade.entry_price)
            )
            closed = True

        return trade, tp1_hit, closed

    def _settle_trade(self, trade: BacktestTrade, balance: float) -> float:
        """Compute PnL in USDT for a closed trade."""
        if trade.direction == SignalDirection.LONG:
            raw_pct = pct_change(trade.entry_price, trade.exit_price)
        else:
            raw_pct = pct_change(trade.exit_price, trade.entry_price)

        # Deduct commission and slippage (both sides)
        cost_pct = (self._config.commission_pct + self._config.slippage_pct) * 2
        net_pct  = raw_pct - cost_pct

        # Size trade by risk
        sl_pct   = safe_divide(abs(trade.entry_price - trade.stop_loss), trade.entry_price) * 100
        if sl_pct <= 0:
            return 0.0
        position_pct = safe_divide(self._config.risk_per_trade_pct, sl_pct)
        notional     = balance * position_pct

        pnl          = notional * net_pct / 100
        trade.pnl_pct    = net_pct
        trade.rr_achieved = safe_divide(abs(net_pct), sl_pct)
        return pnl

    # ── Signal generation (simplified — no full scanner stack) ───────────

    def _generate_signal(self, symbol: str, candles: list[Candle]) -> Optional[Signal]:
        """
        Lightweight signal generation for backtesting.
        Uses indicators only (no live scanner data).
        """
        if len(candles) < 50:
            return None
        ind = self._indicator.compute(candles)

        # Simple crossover signal for backtesting purposes
        score      = 0.0
        direction  = SignalDirection.NEUTRAL
        reasons: list[str] = []

        # EMA trend
        if ind.ema_9 and ind.ema_21 and ind.ema_9 > ind.ema_21:
            score += 20; direction = SignalDirection.LONG
            reasons.append("EMA9 > EMA21")
        elif ind.ema_9 and ind.ema_21 and ind.ema_9 < ind.ema_21:
            score += 20; direction = SignalDirection.SHORT
            reasons.append("EMA9 < EMA21")

        if direction == SignalDirection.NEUTRAL:
            return None

        # RSI confirmation
        if direction == SignalDirection.LONG and ind.rsi and ind.rsi < 70:
            score += 15; reasons.append(f"RSI={ind.rsi:.0f}")
        elif direction == SignalDirection.SHORT and ind.rsi and ind.rsi > 30:
            score += 15; reasons.append(f"RSI={ind.rsi:.0f}")

        # MACD
        if direction == SignalDirection.LONG and ind.macd_bullish_cross:
            score += 20; reasons.append("MACD bullish")
        elif direction == SignalDirection.SHORT and ind.macd_bearish_cross:
            score += 20; reasons.append("MACD bearish")

        # ADX
        if ind.is_trending:
            score += 10; reasons.append(f"ADX={ind.adx:.0f}")

        if score < self._config.min_confluence_score:
            return None

        from signals.confluence_scorer import Signal as Sig
        from scanner.base_scanner import ScannerHit, HitStrength
        dummy_hit = ScannerHit(
            scanner="IndicatorEngine", symbol=symbol,
            direction=direction, strength=HitStrength.MEDIUM,
            score=score, reason=", ".join(reasons),
        )
        return Sig(
            symbol=symbol, direction=direction, score=score,
            strength="MODERATE", contributing_hits=[dummy_hit],
            indicators=ind, reasons=reasons,
        )

    # ── Data fetching ────────────────────────────────────────────────────

    async def _fetch_candles(
        self, rest: BinanceRESTClient, symbol: str
    ) -> list[Candle]:
        """Fetch historical candles for the backtest window.

        Order of preference:
          1. Local SQLite store at `logs/klines.sqlite` — zero network, 10×
             faster, works offline. Requires the (symbol, timeframe) to be
             present in the store (backfilled on engine startup).
          2. Fallback to Binance REST if the local coverage is insufficient.
        """
        end_ms   = now_ms()
        start_ms = end_ms - self._config.lookback_days * 24 * 3600 * 1000

        # ── 1. Try the local historical-klines store ──────────────────
        try:
            from storage.historical_klines import HistoricalKlinesStore
            store = HistoricalKlinesStore(path="logs/klines.sqlite")
            # Ask for more than lookback so we capture full coverage
            rows = store.query(
                symbol=symbol, interval=self._config.timeframe,
                since_ms=start_ms, until_ms=end_ms,
                limit=50_000,     # plenty for any reasonable window
            )
            if rows:
                bars_expected = int((end_ms - start_ms) // _tf_ms(self._config.timeframe))
                if len(rows) >= bars_expected * 0.95:   # 95% coverage threshold
                    raw = [
                        [
                            r["open_time"], str(r["open"]), str(r["high"]),
                            str(r["low"]), str(r["close"]), str(r["volume"]),
                            r["close_time"], "0", r.get("num_trades") or 0,
                            "0", "0", "0",       # ignored fields
                        ]
                        for r in rows
                    ]
                    candles = self._normalizer.klines_to_candles(
                        symbol, self._config.timeframe, raw
                    )
                    logger.info("Backtest %s: used %d local klines (skipped Binance)", symbol, len(candles))
                    return candles
        except Exception as exc:
            logger.debug("Local klines lookup failed (%s) — falling back to REST", exc)

        # ── 2. Fallback: Binance REST pagination ──────────────────────
        all_raw: list = []
        cursor = start_ms
        while cursor < end_ms:
            raw = await rest.get_klines(
                symbol, self._config.timeframe,
                limit=1500, start_time=cursor, end_time=end_ms,
            )
            if not raw:
                break
            all_raw.extend(raw)
            last_close = int(raw[-1][6])
            if last_close >= end_ms or len(raw) < 1500:
                break
            cursor = last_close + 1

        candles = self._normalizer.klines_to_candles(
            symbol, self._config.timeframe, all_raw
        )
        logger.info("Backtest %s: fetched %d candles from Binance REST", symbol, len(candles))
        return candles


def _tf_ms(tf: str) -> int:
    """Convert a Binance timeframe string to milliseconds."""
    unit_ms = {"m": 60_000, "h": 3_600_000, "d": 86_400_000, "w": 604_800_000}
    try:
        n = int(tf[:-1]); u = tf[-1]
        return n * unit_ms[u]
    except Exception:
        return 60 * 60_000  # default 1h
