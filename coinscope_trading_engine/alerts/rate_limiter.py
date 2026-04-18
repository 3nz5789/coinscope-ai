"""
rate_limiter.py — Token-Bucket Rate Limiter
===========================================
Prevents alert flooding by enforcing per-channel and per-symbol
rate limits using a token-bucket algorithm.

Token Bucket Algorithm
----------------------
Each "bucket" holds tokens up to a maximum capacity.
* Tokens refill at a constant rate (tokens per second).
* Each alert consumes one token.
* If the bucket is empty the request is either blocked (async wait)
  or rejected (non-blocking check).

Buckets
-------
  global_channel  — total alerts per channel (Telegram / webhook)
  per_symbol      — per-symbol signal rate (prevent spam on one pair)

Default limits (overridable via constructor or .env)
-----------------------------------------------------
  Telegram:  20 msgs / 60 s  (Telegram Bot API cap ≈ 30 msg/s but group
             bots are limited to 20/min to avoid flood-wait errors)
  Webhook:   60 requests / 60 s
  Per-symbol: 3 signals / 300 s  (one signal per pair per 5 minutes)

Usage
-----
    limiter = AlertRateLimiter()

    # Non-blocking — returns True if allowed, False if rate limited
    if limiter.allow_telegram():
        await notifier.send_signal(...)

    # Blocking — waits until a token is available (up to max_wait_s)
    allowed = await limiter.acquire_telegram(max_wait_s=5.0)

    # Per-symbol check
    if limiter.allow_symbol("BTCUSDT"):
        await queue.enqueue_signal(...)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

# Default rate-limit parameters
TELEGRAM_CAPACITY   = 20      # max burst
TELEGRAM_RATE       = 20 / 60  # tokens per second  (20 per minute)

WEBHOOK_CAPACITY    = 60
WEBHOOK_RATE        = 60 / 60  # 1 per second (60 per minute)

SYMBOL_CAPACITY     = 3
SYMBOL_RATE         = 3 / 300  # 3 per 5 minutes per symbol


# ---------------------------------------------------------------------------
# Single token bucket
# ---------------------------------------------------------------------------

@dataclass
class _TokenBucket:
    """
    Thread-safe (and asyncio-friendly) token bucket.

    Parameters
    ----------
    capacity : Maximum tokens the bucket can hold (burst size).
    rate     : Tokens added per second.
    name     : Human-readable label for logging.
    """
    capacity: float
    rate:     float
    name:     str
    _tokens:  float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tokens      = float(self.capacity)   # start full
        self._last_refill = time.monotonic()
        self._lock        = Lock()

    def _refill(self) -> None:
        """Add tokens based on elapsed time (must be called under lock)."""
        now     = time.monotonic()
        elapsed = now - self._last_refill
        gained  = elapsed * self.rate
        self._tokens      = min(self.capacity, self._tokens + gained)
        self._last_refill = now

    def try_consume(self, tokens: float = 1.0) -> bool:
        """
        Non-blocking consume.  Returns True if token(s) available, else False.
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def time_until_available(self, tokens: float = 1.0) -> float:
        """Seconds until `tokens` tokens will be available."""
        with self._lock:
            self._refill()
            shortfall = tokens - self._tokens
            if shortfall <= 0:
                return 0.0
            return shortfall / self.rate

    @property
    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def reset(self) -> None:
        with self._lock:
            self._tokens      = float(self.capacity)
            self._last_refill = time.monotonic()

    def __repr__(self) -> str:
        return (
            f"<TokenBucket name={self.name!r} "
            f"tokens={self._tokens:.1f}/{self.capacity} "
            f"rate={self.rate:.3f}/s>"
        )


# ---------------------------------------------------------------------------
# Alert Rate Limiter
# ---------------------------------------------------------------------------

class AlertRateLimiter:
    """
    Composite rate limiter: one bucket per channel + per-symbol buckets.

    Parameters
    ----------
    telegram_capacity : Burst size for Telegram channel.
    telegram_rate     : Refill rate for Telegram (tokens/second).
    webhook_capacity  : Burst size for webhook channel.
    webhook_rate      : Refill rate for webhook (tokens/second).
    symbol_capacity   : Burst size per trading symbol.
    symbol_rate       : Refill rate per symbol (tokens/second).
    """

    def __init__(
        self,
        telegram_capacity: float = TELEGRAM_CAPACITY,
        telegram_rate:     float = TELEGRAM_RATE,
        webhook_capacity:  float = WEBHOOK_CAPACITY,
        webhook_rate:      float = WEBHOOK_RATE,
        symbol_capacity:   float = SYMBOL_CAPACITY,
        symbol_rate:       float = SYMBOL_RATE,
    ) -> None:
        self._telegram = _TokenBucket(
            capacity=telegram_capacity, rate=telegram_rate, name="telegram"
        )
        self._webhook = _TokenBucket(
            capacity=webhook_capacity, rate=webhook_rate, name="webhook"
        )
        self._symbol_capacity = symbol_capacity
        self._symbol_rate     = symbol_rate
        self._symbol_buckets: dict[str, _TokenBucket] = {}
        self._lock = asyncio.Lock()

        self._telegram_limited = 0
        self._webhook_limited  = 0
        self._symbol_limited: dict[str, int] = {}

    # ── Telegram ─────────────────────────────────────────────────────────

    def allow_telegram(self) -> bool:
        """Non-blocking: True if Telegram token available."""
        ok = self._telegram.try_consume()
        if not ok:
            self._telegram_limited += 1
            logger.debug(
                "Telegram rate limited (total=%d). "
                "Available in %.1fs.",
                self._telegram_limited,
                self._telegram.time_until_available(),
            )
        return ok

    async def acquire_telegram(self, max_wait_s: float = 5.0) -> bool:
        """
        Async blocking acquire for Telegram.

        Waits up to `max_wait_s` seconds for a token.
        Returns True if acquired, False if timeout exceeded.
        """
        return await self._acquire_bucket(self._telegram, max_wait_s)

    # ── Webhook ──────────────────────────────────────────────────────────

    def allow_webhook(self) -> bool:
        """Non-blocking: True if webhook token available."""
        ok = self._webhook.try_consume()
        if not ok:
            self._webhook_limited += 1
            logger.debug(
                "Webhook rate limited (total=%d).", self._webhook_limited
            )
        return ok

    async def acquire_webhook(self, max_wait_s: float = 5.0) -> bool:
        """Async blocking acquire for webhook channel."""
        return await self._acquire_bucket(self._webhook, max_wait_s)

    # ── Per-symbol ───────────────────────────────────────────────────────

    def allow_symbol(self, symbol: str) -> bool:
        """Non-blocking: True if this symbol hasn't exceeded its signal rate."""
        bucket = self._get_symbol_bucket(symbol)
        ok = bucket.try_consume()
        if not ok:
            self._symbol_limited[symbol] = self._symbol_limited.get(symbol, 0) + 1
            logger.debug(
                "Symbol %s rate limited (total=%d). "
                "Available in %.0fs.",
                symbol,
                self._symbol_limited[symbol],
                bucket.time_until_available(),
            )
        return ok

    async def acquire_symbol(self, symbol: str, max_wait_s: float = 5.0) -> bool:
        """Async blocking acquire for a specific symbol."""
        bucket = self._get_symbol_bucket(symbol)
        return await self._acquire_bucket(bucket, max_wait_s)

    def time_until_symbol_available(self, symbol: str) -> float:
        """Seconds until the next signal for `symbol` is allowed."""
        return self._get_symbol_bucket(symbol).time_until_available()

    # ── Combined check ───────────────────────────────────────────────────

    def allow_signal(self, symbol: str) -> bool:
        """
        Combined gate: True only if BOTH Telegram AND symbol buckets allow.

        Telegram token is only consumed if the symbol check passes first
        (avoids wasting the more-precious Telegram token).
        """
        if not self.allow_symbol(symbol):
            return False
        if not self.allow_telegram():
            # symbol token was already consumed — refund it
            self._get_symbol_bucket(symbol)._tokens = min(
                self._symbol_capacity,
                self._get_symbol_bucket(symbol)._tokens + 1,
            )
            return False
        return True

    # ── Reset / stats ────────────────────────────────────────────────────

    def reset_all(self) -> None:
        """Refill all buckets to capacity (useful in tests)."""
        self._telegram.reset()
        self._webhook.reset()
        for b in self._symbol_buckets.values():
            b.reset()

    def reset_symbol(self, symbol: str) -> None:
        """Reset a single symbol's bucket."""
        if symbol in self._symbol_buckets:
            self._symbol_buckets[symbol].reset()

    def stats(self) -> dict:
        return {
            "telegram": {
                "available":       round(self._telegram.available, 2),
                "capacity":        self._telegram.capacity,
                "times_limited":   self._telegram_limited,
            },
            "webhook": {
                "available":       round(self._webhook.available, 2),
                "capacity":        self._webhook.capacity,
                "times_limited":   self._webhook_limited,
            },
            "symbols": {
                sym: {
                    "available":     round(b.available, 2),
                    "times_limited": self._symbol_limited.get(sym, 0),
                }
                for sym, b in self._symbol_buckets.items()
            },
        }

    # ── Internals ────────────────────────────────────────────────────────

    def _get_symbol_bucket(self, symbol: str) -> _TokenBucket:
        if symbol not in self._symbol_buckets:
            self._symbol_buckets[symbol] = _TokenBucket(
                capacity = self._symbol_capacity,
                rate     = self._symbol_rate,
                name     = f"symbol:{symbol}",
            )
        return self._symbol_buckets[symbol]

    @staticmethod
    async def _acquire_bucket(
        bucket: _TokenBucket,
        max_wait_s: float,
    ) -> bool:
        """
        Poll until the bucket has a token or `max_wait_s` is exceeded.
        Uses small sleep intervals proportional to the wait time.
        """
        deadline = time.monotonic() + max_wait_s
        while True:
            if bucket.try_consume():
                return True
            wait = bucket.time_until_available()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            sleep_s = min(wait, remaining, 0.5)
            await asyncio.sleep(sleep_s)

    def __repr__(self) -> str:
        return (
            f"<AlertRateLimiter "
            f"telegram={self._telegram.available:.1f}/{self._telegram.capacity} "
            f"webhook={self._webhook.available:.1f}/{self._webhook.capacity} "
            f"symbols={len(self._symbol_buckets)}>"
        )
