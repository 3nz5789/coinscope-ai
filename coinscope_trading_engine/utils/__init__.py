"""
utils — Shared utility functions used across the entire engine.

Modules
-------
logger      : Rotating file + console logging setup
validators  : Symbol, price, quantity, and config input validation
helpers     : Time conversion, percentage math, formatting, and misc helpers
"""

from utils.logger import get_logger, setup_logging
from utils.validators import validate_symbol, validate_price, validate_quantity, Validator
from utils.helpers import (
    ms_to_dt,
    dt_to_ms,
    now_ms,
    pct_change,
    round_step,
    format_usdt,
    timeframe_to_seconds,
    chunk_list,
    safe_divide,
)

__all__ = [
    # logger
    "get_logger",
    "setup_logging",
    # validators
    "validate_symbol",
    "validate_price",
    "validate_quantity",
    "Validator",
    # helpers
    "ms_to_dt",
    "dt_to_ms",
    "now_ms",
    "pct_change",
    "round_step",
    "format_usdt",
    "timeframe_to_seconds",
    "chunk_list",
    "safe_divide",
]
