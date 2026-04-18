"""
validators.py — Input Validation
==================================
Reusable validation helpers used across scanners, signal generators,
risk management, and API endpoints.

All validators raise ``ValueError`` with a clear message on failure,
or return the (possibly cleaned) value on success.

Usage
-----
    from utils.validators import validate_symbol, validate_price, Validator

    symbol = validate_symbol("btcusdt")        # → "BTCUSDT"
    price  = validate_price("42100.50")         # → 42100.50
    qty    = validate_quantity("0.001", min_qty=0.001)

    # Chain validations with the fluent Validator class
    v = Validator({"symbol": "btcusdt", "price": "bad"})
    v.required("symbol").symbol("symbol").positive_float("price")
    cleaned = v.result()   # raises ValueError listing all errors at once
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Valid Binance Futures timeframe strings
VALID_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h",
                    "8h", "12h", "1d", "3d", "1w", "1M"}

# Valid order sides
VALID_SIDES = {"BUY", "SELL"}

# Valid order types
VALID_ORDER_TYPES = {
    "LIMIT", "MARKET", "STOP", "STOP_MARKET",
    "TAKE_PROFIT", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET",
}

# Valid time-in-force values
VALID_TIF = {"GTC", "IOC", "FOK", "GTX"}

# Regex for a valid Binance trading pair (e.g. BTCUSDT, ETHBTC, SOLUSDT)
_SYMBOL_RE = re.compile(r"^[A-Z]{2,12}(USDT|BTC|ETH|BNB|BUSD|FDUSD)$")

# Maximum leverage Binance Futures supports
MAX_BINANCE_LEVERAGE = 125


# ---------------------------------------------------------------------------
# Standalone validator functions
# ---------------------------------------------------------------------------

def validate_symbol(symbol: Any, *, allow_empty: bool = False) -> str:
    """
    Validate and normalise a Binance trading pair symbol.

    Parameters
    ----------
    symbol      : Raw value to validate (will be upper-cased and stripped)
    allow_empty : If True, returns "" for None/empty instead of raising

    Returns
    -------
    str : Upper-cased, stripped symbol (e.g. "BTCUSDT")

    Raises
    ------
    ValueError : If the symbol is missing or doesn't match the expected pattern
    """
    if symbol is None or str(symbol).strip() == "":
        if allow_empty:
            return ""
        raise ValueError("Symbol is required and cannot be empty.")
    cleaned = str(symbol).strip().upper()
    if not _SYMBOL_RE.match(cleaned):
        raise ValueError(
            f"Invalid symbol {cleaned!r}. "
            f"Expected format: BASE + QUOTE (e.g. BTCUSDT, ETHBTC). "
            f"Quote currencies accepted: USDT, BTC, ETH, BNB, BUSD, FDUSD."
        )
    return cleaned


def validate_symbols(symbols: Any) -> list[str]:
    """
    Validate a list or comma-separated string of symbols.

    Returns
    -------
    list[str] : List of valid, upper-cased symbols
    """
    if isinstance(symbols, str):
        raw_list = [s.strip() for s in symbols.split(",") if s.strip()]
    elif isinstance(symbols, (list, tuple, set)):
        raw_list = list(symbols)
    else:
        raise ValueError(f"symbols must be a string or list, got {type(symbols).__name__}")
    if not raw_list:
        raise ValueError("At least one symbol is required.")
    return [validate_symbol(s) for s in raw_list]


def validate_price(
    price: Any,
    *,
    min_price: float = 0.0,
    max_price: float = 10_000_000.0,
    allow_zero: bool = False,
) -> float:
    """
    Validate a price value.

    Binance sends prices as strings (DECIMAL rule) — this handles both
    string and numeric inputs.

    Returns
    -------
    float : The validated price

    Raises
    ------
    ValueError
    """
    try:
        value = float(Decimal(str(price)))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid price {price!r}: must be a numeric string or number.")
    if not allow_zero and value == 0.0:
        raise ValueError(f"Price cannot be zero.")
    if value < min_price:
        raise ValueError(f"Price {value} is below minimum {min_price}.")
    if value > max_price:
        raise ValueError(f"Price {value} exceeds maximum {max_price}.")
    return value


def validate_quantity(
    qty: Any,
    *,
    min_qty: float = 0.0,
    max_qty: float = 1_000_000.0,
    allow_zero: bool = False,
) -> float:
    """
    Validate an order quantity.

    Returns
    -------
    float : The validated quantity

    Raises
    ------
    ValueError
    """
    try:
        value = float(Decimal(str(qty)))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"Invalid quantity {qty!r}: must be a numeric string or number.")
    if not allow_zero and value == 0.0:
        raise ValueError("Quantity cannot be zero.")
    if value < 0:
        raise ValueError(f"Quantity cannot be negative, got {value}.")
    if min_qty > 0 and value < min_qty:
        raise ValueError(f"Quantity {value} is below minimum {min_qty}.")
    if value > max_qty:
        raise ValueError(f"Quantity {value} exceeds maximum {max_qty}.")
    return value


def validate_leverage(leverage: Any) -> int:
    """
    Validate a leverage value (1–125).

    Returns
    -------
    int : The validated leverage

    Raises
    ------
    ValueError
    """
    try:
        value = int(leverage)
    except (TypeError, ValueError):
        raise ValueError(f"Leverage must be an integer, got {leverage!r}.")
    if value < 1:
        raise ValueError("Leverage must be at least 1.")
    if value > MAX_BINANCE_LEVERAGE:
        raise ValueError(
            f"Leverage {value}x exceeds Binance maximum of {MAX_BINANCE_LEVERAGE}x."
        )
    return value


def validate_timeframe(timeframe: Any) -> str:
    """
    Validate a Binance candle interval string.

    Returns
    -------
    str : The validated timeframe (e.g. "5m", "1h")

    Raises
    ------
    ValueError
    """
    cleaned = str(timeframe).strip().lower()
    if cleaned not in VALID_TIMEFRAMES:
        raise ValueError(
            f"Invalid timeframe {timeframe!r}. "
            f"Valid values: {sorted(VALID_TIMEFRAMES)}"
        )
    return cleaned


def validate_side(side: Any) -> str:
    """
    Validate an order side ("BUY" or "SELL").

    Returns
    -------
    str : "BUY" or "SELL"
    """
    cleaned = str(side).strip().upper()
    if cleaned not in VALID_SIDES:
        raise ValueError(f"Invalid side {side!r}. Must be 'BUY' or 'SELL'.")
    return cleaned


def validate_order_type(order_type: Any) -> str:
    """Validate a Binance Futures order type string."""
    cleaned = str(order_type).strip().upper()
    if cleaned not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type {order_type!r}. "
            f"Valid types: {sorted(VALID_ORDER_TYPES)}"
        )
    return cleaned


def validate_confluence_score(score: Any) -> float:
    """
    Validate a confluence score in the range 0.0–100.0.

    Returns
    -------
    float
    """
    try:
        value = float(score)
    except (TypeError, ValueError):
        raise ValueError(f"Confluence score must be numeric, got {score!r}.")
    if not 0.0 <= value <= 100.0:
        raise ValueError(
            f"Confluence score {value} is out of range. Must be between 0 and 100."
        )
    return value


def validate_percentage(
    pct: Any,
    *,
    field: str = "percentage",
    min_val: float = 0.0,
    max_val: float = 100.0,
) -> float:
    """Validate a percentage value within an allowed range."""
    try:
        value = float(pct)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be numeric, got {pct!r}.")
    if not min_val <= value <= max_val:
        raise ValueError(
            f"{field} {value} is outside the allowed range [{min_val}, {max_val}]."
        )
    return value


def validate_positive_int(value: Any, *, field: str = "value") -> int:
    """Validate that a value is a positive integer (>= 1)."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer, got {value!r}.")
    if v < 1:
        raise ValueError(f"{field} must be >= 1, got {v}.")
    return v


def validate_timestamp_ms(ts: Any) -> int:
    """
    Validate a Unix millisecond timestamp.
    Must be a positive integer and not unreasonably far in the past or future.
    """
    try:
        value = int(ts)
    except (TypeError, ValueError):
        raise ValueError(f"Timestamp must be an integer, got {ts!r}.")
    if value < 0:
        raise ValueError(f"Timestamp cannot be negative, got {value}.")
    # Sanity check: after 2020-01-01 and before year 2100
    if not (1_577_836_800_000 <= value <= 4_102_444_800_000):
        raise ValueError(
            f"Timestamp {value} looks unreasonable. "
            "Expected a Unix millisecond timestamp between 2020 and 2100."
        )
    return value


# ---------------------------------------------------------------------------
# Fluent Validator class
# ---------------------------------------------------------------------------

class Validator:
    """
    Fluent multi-field validator that collects all errors before raising.

    Instead of failing on the first bad field, this class accumulates all
    validation errors and raises a single ``ValueError`` listing every issue.

    Usage
    -----
        v = Validator({"symbol": "btcusdt", "price": "-10", "qty": "0.001"})
        v.required("symbol").symbol("symbol")
        v.required("price").positive_float("price")
        v.required("qty").positive_float("qty")
        data = v.result()   # {"symbol": "BTCUSDT", "price": ..., "qty": 0.001}
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._raw    = dict(data)
        self._clean: dict[str, Any] = {}
        self._errors: list[str] = []

    def required(self, field: str) -> "Validator":
        """Assert that a field is present and non-empty."""
        val = self._raw.get(field)
        if val is None or str(val).strip() == "":
            self._errors.append(f"'{field}' is required.")
        return self

    def symbol(self, field: str) -> "Validator":
        """Validate and normalise a symbol field."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                self._clean[field] = validate_symbol(raw)
            except ValueError as e:
                self._errors.append(str(e))
        return self

    def positive_float(self, field: str, *, min_val: float = 0.0) -> "Validator":
        """Validate a field as a positive float."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                v = float(Decimal(str(raw)))
                if v < min_val:
                    raise ValueError(f"'{field}' must be >= {min_val}, got {v}.")
                self._clean[field] = v
            except (InvalidOperation, ValueError) as e:
                self._errors.append(f"'{field}': {e}")
        return self

    def positive_int(self, field: str) -> "Validator":
        """Validate a field as a positive integer."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                self._clean[field] = validate_positive_int(raw, field=field)
            except ValueError as e:
                self._errors.append(str(e))
        return self

    def timeframe(self, field: str) -> "Validator":
        """Validate a timeframe field."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                self._clean[field] = validate_timeframe(raw)
            except ValueError as e:
                self._errors.append(str(e))
        return self

    def side(self, field: str) -> "Validator":
        """Validate an order side field."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                self._clean[field] = validate_side(raw)
            except ValueError as e:
                self._errors.append(str(e))
        return self

    def percentage(self, field: str, *, min_val: float = 0.0, max_val: float = 100.0) -> "Validator":
        """Validate a percentage field."""
        raw = self._raw.get(field)
        if raw is not None:
            try:
                self._clean[field] = validate_percentage(
                    raw, field=field, min_val=min_val, max_val=max_val
                )
            except ValueError as e:
                self._errors.append(str(e))
        return self

    def result(self) -> dict[str, Any]:
        """
        Return the cleaned data dict, or raise ``ValueError`` if any
        validations failed.

        The error message lists every problem found.
        """
        if self._errors:
            raise ValueError(
                f"Validation failed with {len(self._errors)} error(s):\n"
                + "\n".join(f"  • {e}" for e in self._errors)
            )
        # Merge raw (unchecked) fields with cleaned fields
        merged = {**self._raw, **self._clean}
        return merged

    @property
    def is_valid(self) -> bool:
        """True if no errors have been recorded yet."""
        return len(self._errors) == 0

    @property
    def errors(self) -> list[str]:
        """Return the current list of validation error messages."""
        return list(self._errors)
