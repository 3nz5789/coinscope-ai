"""
CoinScopeAI Phase 2 — Base Alpha Generator

Provides shared statistical utilities and the abstract interface that all
alpha feature generators must implement.  Generators are **stateless** —
they receive data, compute signals, and return ``AlphaSignal`` objects
without retaining internal mutable state between calls.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from services.market_data.models import AlphaGeneratorConfig, AlphaSignal, SignalDirection


class BaseAlphaGenerator(ABC):
    """
    Abstract base for all alpha feature generators.

    Subclasses must implement ``generate()`` which accepts normalised
    market data and returns a list of ``AlphaSignal`` objects.
    """

    def __init__(self, config: Optional[AlphaGeneratorConfig] = None) -> None:
        self.config = config or AlphaGeneratorConfig()

    @abstractmethod
    def generate(self, *args, **kwargs) -> List[AlphaSignal]:
        """Produce alpha signals from the supplied data."""
        ...

    # -- shared statistical helpers ------------------------------------------

    @staticmethod
    def mean(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def std(values: Sequence[float], ddof: int = 1) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        m = sum(values) / n
        variance = sum((x - m) ** 2 for x in values) / (n - ddof)
        return math.sqrt(variance)

    @classmethod
    def z_score(cls, value: float, values: Sequence[float]) -> float:
        """Compute z-score of ``value`` relative to ``values``."""
        m = cls.mean(values)
        s = cls.std(values)
        if s == 0:
            return 0.0
        return (value - m) / s

    @staticmethod
    def ema(values: Sequence[float], alpha: float = 0.06) -> float:
        """Exponential moving average of a sequence (latest value last)."""
        if not values:
            return 0.0
        result = values[0]
        for v in values[1:]:
            result = alpha * v + (1 - alpha) * result
        return result

    @staticmethod
    def rate_of_change(current: float, previous: float) -> float:
        if previous == 0:
            return 0.0
        return (current - previous) / abs(previous)

    @staticmethod
    def direction_from_value(value: float, threshold: float = 0.0) -> SignalDirection:
        if value > threshold:
            return SignalDirection.BULLISH
        elif value < -threshold:
            return SignalDirection.BEARISH
        return SignalDirection.NEUTRAL

    @staticmethod
    def confidence_from_z(z: float, max_z: float = 4.0) -> float:
        """Map absolute z-score to a 0–1 confidence value."""
        return min(abs(z) / max_z, 1.0)
