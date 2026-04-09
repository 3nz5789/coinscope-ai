"""
CoinScopeAI Memory Hooks
==========================
Middleware / decorators that automatically capture events from the
trading engine into the memory system.

Two integration modes:
  1. API middleware  — wraps FastAPI endpoints to capture request/response data
  2. Engine hooks    — direct function calls from the paper trading engine
"""

from .api_middleware import MemoryMiddleware
from .engine_hooks import EngineMemoryHooks

__all__ = ["MemoryMiddleware", "EngineMemoryHooks"]
