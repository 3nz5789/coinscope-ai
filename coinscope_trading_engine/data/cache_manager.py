"""
cache_manager.py — Redis Caching Layer
=======================================
Provides a unified async interface for all engine caching needs:
key/value storage, JSON serialisation, pub/sub messaging, and
per-key TTL management.

Every module in the engine uses CacheManager rather than talking
to Redis directly — this keeps the Redis connection pool centralised
and makes swapping the cache backend (e.g. to in-memory for tests) trivial.

Key namespaces
--------------
  ticker:{symbol}          → latest Ticker data
  candle:{symbol}:{interval} → latest closed Candle
  orderbook:{symbol}       → latest OrderBook snapshot
  mark_price:{symbol}      → latest MarkPrice
  funding_rate:{symbol}    → latest FundingRate
  open_interest:{symbol}   → latest OpenInterest
  signal:{symbol}          → latest Signal from confluence scorer
  position:{symbol}        → active position tracking
  rate_limit:weight        → current API weight usage

Pub/Sub channels
----------------
  channel:signals          → published whenever a new signal is emitted
  channel:liquidations     → published on liquidation events
  channel:alerts           → published when alert queue dispatches

Usage
-----
    from data.cache_manager import CacheManager

    async with CacheManager() as cache:
        await cache.set("ticker:BTCUSDT", ticker_dict, ttl=10)
        data = await cache.get("ticker:BTCUSDT")

        # Publish to a channel
        await cache.publish("channel:signals", signal_dict)

        # Subscribe to a channel
        async for message in cache.subscribe("channel:signals"):
            print(message)
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel for "key not found" (distinct from None values)
# ---------------------------------------------------------------------------
_MISSING = object()


class CacheManager:
    """
    Async Redis caching layer for the CoinScopeAI engine.

    Parameters
    ----------
    url : str, optional
        Redis connection URL.  Defaults to ``settings.redis_url``.
    default_ttl : int, optional
        Default key expiry in seconds.  Defaults to ``settings.redis_cache_ttl_seconds``.
    pool_size : int, optional
        Connection pool size.  Defaults to ``settings.redis_pool_size``.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        default_ttl: Optional[int] = None,
        pool_size: Optional[int] = None,
    ) -> None:
        self._url         = url         or settings.redis_url
        self._default_ttl = default_ttl or settings.redis_cache_ttl_seconds
        self._pool_size   = pool_size   or settings.redis_pool_size
        self._client: Optional[aioredis.Redis] = None
        self._pubsub_client: Optional[aioredis.Redis] = None

    # ── Context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "CacheManager":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def connect(self) -> None:
        """Open the Redis connection pool."""
        self._client = aioredis.from_url(
            self._url,
            max_connections=self._pool_size,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connectivity
        await self._client.ping()
        logger.info("CacheManager connected → %s", _safe_url(self._url))

    async def close(self) -> None:
        """Close all Redis connections."""
        if self._client:
            await self._client.aclose()
            logger.debug("CacheManager disconnected.")
        if self._pubsub_client:
            await self._pubsub_client.aclose()

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("CacheManager not connected. Call connect() or use async with.")
        return self._client

    # ── Core get / set / delete ──────────────────────────────────────────

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """
        Store a value under ``key``.

        Non-string values are automatically JSON-serialised.
        TTL defaults to ``default_ttl`` if not specified; pass ``ttl=0``
        to store without expiry.
        """
        raw = value if isinstance(value, str) else json.dumps(value, default=str)
        expire = ttl if ttl is not None else self._default_ttl
        if expire > 0:
            await self.client.set(key, raw, ex=expire)
        else:
            await self.client.set(key, raw)
        logger.debug("SET %s  ttl=%s", key, expire)

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value by key.

        Automatically deserialises JSON.  Returns ``default`` if the key
        does not exist or has expired.
        """
        raw = await self.client.get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns the number of keys removed."""
        if not keys:
            return 0
        count = await self.client.delete(*keys)
        logger.debug("DEL %s  (removed %d)", keys, count)
        return count

    async def exists(self, key: str) -> bool:
        """Return True if the key exists and has not expired."""
        return bool(await self.client.exists(key))

    async def ttl(self, key: str) -> int:
        """
        Return the remaining TTL in seconds.
        -1 = no expiry set, -2 = key does not exist.
        """
        return await self.client.ttl(key)

    async def expire(self, key: str, seconds: int) -> bool:
        """Update the TTL on an existing key."""
        return bool(await self.client.expire(key, seconds))

    # ── Batch operations ─────────────────────────────────────────────────

    async def mget(self, keys: list[str]) -> dict[str, Any]:
        """Retrieve multiple keys in a single round-trip."""
        if not keys:
            return {}
        values = await self.client.mget(keys)
        result = {}
        for k, raw in zip(keys, values):
            if raw is not None:
                try:
                    result[k] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    result[k] = raw
        return result

    async def mset(
        self,
        mapping: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> None:
        """
        Store multiple key/value pairs.
        Uses a pipeline for efficiency.
        """
        if not mapping:
            return
        expire = ttl if ttl is not None else self._default_ttl
        async with self.client.pipeline(transaction=False) as pipe:
            for key, value in mapping.items():
                raw = value if isinstance(value, str) else json.dumps(value, default=str)
                if expire > 0:
                    pipe.set(key, raw, ex=expire)
                else:
                    pipe.set(key, raw)
            await pipe.execute()

    # ── Pattern scanning ─────────────────────────────────────────────────

    async def keys(self, pattern: str) -> list[str]:
        """
        Return all keys matching a glob pattern.
        Use sparingly in production — KEYS is O(N).
        """
        return await self.client.keys(pattern)

    async def scan_keys(self, pattern: str, count: int = 100) -> AsyncIterator[str]:
        """
        Lazily iterate keys matching a pattern using SCAN (production-safe).
        """
        cursor = 0
        while True:
            cursor, batch = await self.client.scan(cursor, match=pattern, count=count)
            for key in batch:
                yield key
            if cursor == 0:
                break

    # ── Increment / counters ─────────────────────────────────────────────

    async def incr(self, key: str, amount: int = 1) -> int:
        """Atomically increment an integer counter."""
        return await self.client.incrby(key, amount)

    async def decr(self, key: str, amount: int = 1) -> int:
        """Atomically decrement an integer counter."""
        return await self.client.decrby(key, amount)

    # ── Sorted sets (for signal history / leaderboards) ──────────────────

    async def zadd(self, key: str, score: float, member: str) -> None:
        """Add a member to a sorted set with a score."""
        await self.client.zadd(key, {member: score})

    async def zrange(
        self, key: str, start: int = 0, end: int = -1, desc: bool = False
    ) -> list[str]:
        """Return members of a sorted set by rank."""
        if desc:
            return await self.client.zrevrange(key, start, end)
        return await self.client.zrange(key, start, end)

    async def zrangebyscore(
        self, key: str, min_score: float, max_score: float
    ) -> list[str]:
        """Return members with scores between min and max."""
        return await self.client.zrangebyscore(key, min_score, max_score)

    # ── Pub / Sub ─────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish a message to a Redis channel.
        Non-string messages are JSON-serialised.
        Returns the number of subscribers that received the message.
        """
        payload = message if isinstance(message, str) else json.dumps(message, default=str)
        count = await self.client.publish(channel, payload)
        logger.debug("PUB %s → %d subscribers", channel, count)
        return count

    @asynccontextmanager
    async def subscribe(self, *channels: str) -> AsyncIterator[AsyncIterator[Any]]:
        """
        Async context manager that yields an async iterator of messages.

        Usage
        -----
            async with cache.subscribe("channel:signals") as messages:
                async for msg in messages:
                    print(msg)
        """
        # Use a dedicated connection for subscriptions
        sub_client = aioredis.from_url(
            self._url,
            decode_responses=True,
            socket_timeout=None,   # blocking read
        )
        pubsub: PubSub = sub_client.pubsub()
        await pubsub.subscribe(*channels)
        logger.info("Subscribed to channels: %s", channels)

        async def _iter() -> AsyncIterator[Any]:
            async for raw_msg in pubsub.listen():
                if raw_msg["type"] != "message":
                    continue
                data = raw_msg["data"]
                try:
                    yield json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    yield data

        try:
            yield _iter()
        finally:
            await pubsub.unsubscribe(*channels)
            await sub_client.aclose()
            logger.debug("Unsubscribed from channels: %s", channels)

    # ── Convenience domain helpers ────────────────────────────────────────

    async def cache_ticker(self, symbol: str, data: Any, ttl: int = 5) -> None:
        """Cache the latest ticker for a symbol (short 5 s TTL)."""
        await self.set(f"ticker:{symbol}", data, ttl=ttl)

    async def get_ticker(self, symbol: str) -> Optional[Any]:
        return await self.get(f"ticker:{symbol}")

    async def cache_candle(self, symbol: str, interval: str, data: Any, ttl: int = 60) -> None:
        """Cache the latest closed candle for a symbol/interval."""
        await self.set(f"candle:{symbol}:{interval}", data, ttl=ttl)

    async def get_candle(self, symbol: str, interval: str) -> Optional[Any]:
        return await self.get(f"candle:{symbol}:{interval}")

    async def cache_orderbook(self, symbol: str, data: Any, ttl: int = 2) -> None:
        """Cache the latest orderbook snapshot (very short TTL)."""
        await self.set(f"orderbook:{symbol}", data, ttl=ttl)

    async def get_orderbook(self, symbol: str) -> Optional[Any]:
        return await self.get(f"orderbook:{symbol}")

    async def cache_mark_price(self, symbol: str, data: Any, ttl: int = 10) -> None:
        await self.set(f"mark_price:{symbol}", data, ttl=ttl)

    async def get_mark_price(self, symbol: str) -> Optional[Any]:
        return await self.get(f"mark_price:{symbol}")

    async def cache_signal(self, symbol: str, data: Any, ttl: int = 300) -> None:
        """Cache the latest signal for a symbol (5-min TTL)."""
        await self.set(f"signal:{symbol}", data, ttl=ttl)

    async def get_signal(self, symbol: str) -> Optional[Any]:
        return await self.get(f"signal:{symbol}")

    async def get_all_signals(self) -> dict[str, Any]:
        """Return a dict of {symbol: signal} for all cached signals."""
        keys = await self.keys("signal:*")
        if not keys:
            return {}
        raw_map = await self.mget(keys)
        return {k.replace("signal:", ""): v for k, v in raw_map.items()}

    async def cache_rate_limit_weight(self, weight: int, ttl: int = 60) -> None:
        """Track current API request weight for rate-limit safety checks."""
        await self.set("rate_limit:weight", weight, ttl=ttl)

    async def get_rate_limit_weight(self) -> int:
        return await self.get("rate_limit:weight", default=0)

    # ── Health check ──────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return await self.client.ping()
        except Exception:
            return False

    async def info(self) -> dict:
        """Return Redis server INFO as a dict."""
        raw = await self.client.info()
        return dict(raw)

    def __repr__(self) -> str:
        connected = self._client is not None
        return f"<CacheManager url={_safe_url(self._url)} connected={connected}>"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_url(url: str) -> str:
    """Mask the password in a Redis URL for safe logging."""
    if "@" in url:
        proto, rest = url.split("://", 1)
        _, host = rest.split("@", 1)
        return f"{proto}://***@{host}"
    return url
