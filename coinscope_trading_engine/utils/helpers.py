"""
helpers.py — Common Helper Functions
======================================
Miscellaneous utility functions used across the CoinScopeAI engine.

Categories
----------
* Time         : ms ↔ datetime conversion, now_ms, timeframe_to_seconds
* Math         : pct_change, safe_divide, round_step, clamp
* Formatting   : format_usdt, format_pct, format_qty, human_number
* Collections  : chunk_list, flatten, dedupe, merge_dicts
* Async        : gather_with_concurrency, retry_async
* Misc         : symbol_base, symbol_quote, truncate_string

Usage
-----
    from utils.helpers import ms_to_dt, pct_change, format_usdt, chunk_list

    dt  = ms_to_dt(1705311512994)
    pct = pct_change(old=40000, new=42000)   # → 5.0
    txt = format_usdt(1234567.89)            # → "$1,234,567.89"
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, AsyncIterator, Callable, Iterable, Optional, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def ms_to_dt(ms: int) -> datetime:
    """Convert a Unix millisecond timestamp to a UTC-aware datetime."""
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def dt_to_ms(dt: datetime) -> int:
    """Convert a datetime to a Unix millisecond timestamp."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def now_ms() -> int:
    """Return the current UTC time as a Unix millisecond timestamp."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def timeframe_to_seconds(timeframe: str) -> int:
    """
    Convert a Binance timeframe string to the number of seconds it represents.

    Examples
    --------
    >>> timeframe_to_seconds("5m")   → 300
    >>> timeframe_to_seconds("1h")   → 3600
    >>> timeframe_to_seconds("4h")   → 14400
    >>> timeframe_to_seconds("1d")   → 86400
    """
    _MAP: dict[str, int] = {
        "1m":  60,
        "3m":  180,
        "5m":  300,
        "15m": 900,
        "30m": 1800,
        "1h":  3600,
        "2h":  7200,
        "4h":  14400,
        "6h":  21600,
        "8h":  28800,
        "12h": 43200,
        "1d":  86400,
        "3d":  259200,
        "1w":  604800,
        "1M":  2592000,   # 30 days
    }
    result = _MAP.get(timeframe.strip())
    if result is None:
        raise ValueError(
            f"Unknown timeframe {timeframe!r}. "
            f"Valid values: {list(_MAP)}"
        )
    return result


def timeframe_to_ms(timeframe: str) -> int:
    """Convert a timeframe string to milliseconds."""
    return timeframe_to_seconds(timeframe) * 1000


def start_of_candle(dt: datetime, timeframe: str) -> datetime:
    """Return the open-time of the candle that contains ``dt``."""
    period_s  = timeframe_to_seconds(timeframe)
    epoch_s   = int(dt.timestamp())
    floored_s = (epoch_s // period_s) * period_s
    return datetime.fromtimestamp(floored_s, tz=timezone.utc)


def elapsed_since_ms(ts_ms: int) -> float:
    """Return the number of seconds elapsed since the given ms timestamp."""
    return (now_ms() - ts_ms) / 1000.0


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def pct_change(old: float, new: float) -> float:
    """
    Calculate percentage change from ``old`` to ``new``.

    Returns
    -------
    float : e.g. 5.0 for +5%, -3.2 for -3.2%
            Returns 0.0 if ``old`` is zero (avoids ZeroDivisionError).
    """
    if old == 0.0:
        return 0.0
    return ((new - old) / abs(old)) * 100.0


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Divide two numbers, returning ``default`` if denominator is zero.

    Examples
    --------
    >>> safe_divide(10, 2)       → 5.0
    >>> safe_divide(10, 0)       → 0.0
    >>> safe_divide(10, 0, -1)   → -1.0
    """
    if denominator == 0.0:
        return default
    return numerator / denominator


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp ``value`` to the range [min_val, max_val]."""
    return max(min_val, min(value, max_val))


def round_step(value: float, step: float) -> float:
    """
    Round ``value`` down to the nearest multiple of ``step``.

    Used for aligning order quantities and prices to exchange tick/lot sizes.

    Examples
    --------
    >>> round_step(0.123456, 0.001)   → 0.123
    >>> round_step(42105.7, 0.1)      → 42105.7
    >>> round_step(42105.75, 1.0)     → 42105.0
    """
    if step <= 0:
        return value
    step_dec  = Decimal(str(step))
    value_dec = Decimal(str(value))
    result    = (value_dec // step_dec) * step_dec
    return float(result.quantize(step_dec, rounding=ROUND_DOWN))


def round_to_precision(value: float, precision: int) -> float:
    """Round ``value`` to ``precision`` decimal places."""
    factor = 10 ** precision
    return math.floor(value * factor) / factor


def atr_pct(atr: float, price: float) -> float:
    """Return ATR expressed as a percentage of current price."""
    return safe_divide(atr, price) * 100.0


def risk_reward_ratio(entry: float, stop_loss: float, take_profit: float) -> float:
    """
    Calculate the risk-to-reward ratio for a trade setup.

    Returns
    -------
    float : e.g. 2.0 means reward is 2× the risk.
    """
    risk   = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    return safe_divide(reward, risk)


def position_pnl_pct(entry: float, current: float, side: str) -> float:
    """
    Calculate unrealised PnL as a percentage for a futures position.

    Parameters
    ----------
    entry   : Entry price
    current : Current mark/last price
    side    : "LONG" or "SHORT"
    """
    if side.upper() == "LONG":
        return pct_change(entry, current)
    elif side.upper() == "SHORT":
        return pct_change(current, entry)
    return 0.0


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_usdt(amount: float, decimals: int = 2) -> str:
    """
    Format a dollar/USDT amount with commas and a $ prefix.

    Examples
    --------
    >>> format_usdt(1234567.89)    → "$1,234,567.89"
    >>> format_usdt(0.00123, 6)    → "$0.001230"
    """
    return f"${amount:,.{decimals}f}"


def format_pct(value: float, decimals: int = 2, sign: bool = True) -> str:
    """
    Format a percentage value.

    Examples
    --------
    >>> format_pct(5.42)       → "+5.42%"
    >>> format_pct(-1.3)       → "-1.30%"
    >>> format_pct(5.42, sign=False)  → "5.42%"
    """
    prefix = "+" if sign and value > 0 else ""
    return f"{prefix}{value:.{decimals}f}%"


def format_qty(qty: float, decimals: int = 4) -> str:
    """Format an order quantity without trailing zeros."""
    return f"{qty:.{decimals}f}".rstrip("0").rstrip(".")


def human_number(value: float) -> str:
    """
    Format large numbers with K/M/B suffixes.

    Examples
    --------
    >>> human_number(1_234_567)    → "1.23M"
    >>> human_number(45_200)       → "45.20K"
    >>> human_number(1_000_000_000) → "1.00B"
    """
    abs_val = abs(value)
    sign    = "-" if value < 0 else ""
    if abs_val >= 1_000_000_000:
        return f"{sign}{abs_val / 1_000_000_000:.2f}B"
    if abs_val >= 1_000_000:
        return f"{sign}{abs_val / 1_000_000:.2f}M"
    if abs_val >= 1_000:
        return f"{sign}{abs_val / 1_000:.2f}K"
    return f"{sign}{abs_val:.2f}"


def truncate_string(s: str, max_len: int = 80, suffix: str = "…") -> str:
    """Truncate a string to ``max_len`` characters, appending ``suffix``."""
    if len(s) <= max_len:
        return s
    return s[: max_len - len(suffix)] + suffix


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

_QUOTE_CURRENCIES = ("USDT", "BTC", "ETH", "BNB", "BUSD", "FDUSD")


def symbol_base(symbol: str) -> str:
    """
    Extract the base currency from a trading pair.

    Examples
    --------
    >>> symbol_base("BTCUSDT")   → "BTC"
    >>> symbol_base("ETHBTC")    → "ETH"
    """
    for quote in _QUOTE_CURRENCIES:
        if symbol.endswith(quote):
            return symbol[: -len(quote)]
    return symbol


def symbol_quote(symbol: str) -> str:
    """
    Extract the quote currency from a trading pair.

    Examples
    --------
    >>> symbol_quote("BTCUSDT")   → "USDT"
    >>> symbol_quote("ETHBTC")    → "BTC"
    """
    for quote in _QUOTE_CURRENCIES:
        if symbol.endswith(quote):
            return quote
    return ""


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def chunk_list(lst: list[T], size: int) -> list[list[T]]:
    """
    Split a list into chunks of at most ``size`` elements.

    Examples
    --------
    >>> chunk_list([1,2,3,4,5], 2)   → [[1,2],[3,4],[5]]
    """
    if size <= 0:
        raise ValueError(f"chunk size must be >= 1, got {size}")
    return [lst[i: i + size] for i in range(0, len(lst), size)]


def flatten(nested: Iterable[Iterable[T]]) -> list[T]:
    """Flatten one level of nesting in a list of lists."""
    return [item for sublist in nested for item in sublist]


def dedupe(lst: list[T], *, key: Optional[Callable[[T], Any]] = None) -> list[T]:
    """
    Remove duplicates from a list, preserving insertion order.

    Parameters
    ----------
    key : optional callable to extract a comparison key from each element
    """
    seen: set = set()
    result: list[T] = []
    for item in lst:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def merge_dicts(*dicts: dict) -> dict:
    """Merge multiple dicts left-to-right (later dicts win on key conflicts)."""
    result: dict = {}
    for d in dicts:
        result.update(d)
    return result


# ---------------------------------------------------------------------------
# Async helpers
# ---------------------------------------------------------------------------

async def gather_with_concurrency(
    limit: int,
    *coros: AsyncIterator,
) -> list[Any]:
    """
    Run coroutines with a concurrency cap using a semaphore.

    Parameters
    ----------
    limit : int    Max simultaneous coroutines
    *coros         Coroutines to run

    Returns
    -------
    list : Results in the same order as the input coroutines
    """
    semaphore = asyncio.Semaphore(limit)

    async def _bounded(coro):
        async with semaphore:
            return await coro

    return await asyncio.gather(*(_bounded(c) for c in coros))


async def retry_async(
    coro_fn: Callable,
    *args: Any,
    retries: int = 3,
    delay_s: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Parameters
    ----------
    coro_fn    : Async function to call
    *args      : Positional args to pass to coro_fn
    retries    : Max number of attempts (default 3)
    delay_s    : Initial delay between attempts (default 1.0 s)
    backoff    : Multiplier applied to delay each retry (default 2.0)
    exceptions : Exception types to catch and retry on
    **kwargs   : Keyword args to pass to coro_fn

    Returns
    -------
    Any : Return value of coro_fn on success

    Raises
    ------
    The last exception if all attempts are exhausted.
    """
    last_exc: Optional[Exception] = None
    current_delay = delay_s
    for attempt in range(1, retries + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except exceptions as exc:
            last_exc = exc
            if attempt < retries:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    raise last_exc  # type: ignore[misc]
