"""
data — Exchange connectivity, ingestion, normalisation, and caching.

Modules
-------
binance_websocket  : Persistent WebSocket connection manager (ws-fapi/v1)
binance_rest       : Async REST client (fapi/v1, fapi/v2)
data_normalizer    : Converts raw exchange payloads into internal schemas
cache_manager      : Redis-backed caching layer with TTL management
"""

from data.binance_rest import BinanceRESTClient, BinanceRESTError
from data.binance_websocket import BinanceWebSocketManager, BinanceAPIError
from data.cache_manager import CacheManager
from data.data_normalizer import DataNormalizer

__all__ = [
    "BinanceRESTClient",
    "BinanceRESTError",
    "BinanceWebSocketManager",
    "BinanceAPIError",
    "CacheManager",
    "DataNormalizer",
]
