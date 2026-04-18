"""
risk — CoinScopeAI Risk Management Layer
=========================================
Exports all risk management components used by the engine core.
"""

from risk.position_sizer import PositionSizer, PositionSize
from risk.exposure_tracker import ExposureTracker, Position
from risk.correlation_analyzer import CorrelationAnalyzer, CorrelationPair
from risk.circuit_breaker import CircuitBreaker, BreakerState, TripEvent

__all__ = [
    "PositionSizer",
    "PositionSize",
    "ExposureTracker",
    "Position",
    "CorrelationAnalyzer",
    "CorrelationPair",
    "CircuitBreaker",
    "BreakerState",
    "TripEvent",
]
