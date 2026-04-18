"""
scanner — Real-time market scanning modules.

Each scanner runs on its own cycle, reads normalised market data from the
CacheManager, applies its detection logic, and returns a list of ScannerHit
objects that the confluence scorer aggregates into a final signal.

Modules
-------
base_scanner         : Abstract base class all scanners inherit from
volume_scanner       : Detects unusual volume spikes vs rolling baseline
liquidation_scanner  : Tracks large liquidation cascades
funding_rate_scanner : Flags extreme or rapidly shifting funding rates
pattern_scanner      : Recognises candlestick and chart patterns
orderbook_scanner    : Detects order-book imbalances and large walls
"""

from scanner.base_scanner import BaseScanner, ScannerHit, ScannerResult
from scanner.volume_scanner import VolumeScanner
from scanner.liquidation_scanner import LiquidationScanner
from scanner.funding_rate_scanner import FundingRateScanner
from scanner.pattern_scanner import PatternScanner
from scanner.orderbook_scanner import OrderBookScanner

__all__ = [
    "BaseScanner",
    "ScannerHit",
    "ScannerResult",
    "VolumeScanner",
    "LiquidationScanner",
    "FundingRateScanner",
    "PatternScanner",
    "OrderBookScanner",
]
