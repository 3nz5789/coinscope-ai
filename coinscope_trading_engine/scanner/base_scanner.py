"""
base_scanner.py — Abstract Base Scanner
=========================================
Defines the contract every scanner must implement and the shared
ScannerHit / ScannerResult data structures consumed by the
confluence scorer.

All scanners:
  1. Inherit from BaseScanner
  2. Implement ``scan(symbol) -> ScannerResult``
  3. Optionally override ``start()`` / ``stop()`` for background loops
  4. Use self.cache and self.rest to access data
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from config import settings
from data.cache_manager import CacheManager
from data.binance_rest import BinanceRESTClient
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared data structures
# ---------------------------------------------------------------------------

class SignalDirection(str, Enum):
    LONG    = "LONG"
    SHORT   = "SHORT"
    NEUTRAL = "NEUTRAL"


class HitStrength(str, Enum):
    WEAK   = "WEAK"      # score weight  1
    MEDIUM = "MEDIUM"    # score weight  2
    STRONG = "STRONG"    # score weight  3


@dataclass
class ScannerHit:
    """
    A single detection result from one scanner for one symbol.

    The confluence scorer collects all ScannerHits across all scanners
    and combines them into an overall signal score.
    """
    scanner:    str                     # e.g. "VolumeScanner"
    symbol:     str                     # e.g. "BTCUSDT"
    direction:  SignalDirection
    strength:   HitStrength
    score:      float                   # 0.0 – 100.0 contribution
    reason:     str                     # human-readable description
    metadata:   dict = field(default_factory=dict)
    timestamp:  float = field(default_factory=time.time)

    @property
    def weight(self) -> int:
        return {"WEAK": 1, "MEDIUM": 2, "STRONG": 3}[self.strength.value]

    def __repr__(self) -> str:
        return (
            f"<ScannerHit {self.scanner} {self.symbol} "
            f"{self.direction.value} {self.strength.value} "
            f"score={self.score:.1f}>"
        )


@dataclass
class ScannerResult:
    """
    Aggregated output of one scanner run for one symbol.

    Contains zero or more ScannerHits plus timing metadata.
    """
    scanner:    str
    symbol:     str
    hits:       list[ScannerHit] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error:      Optional[str] = None

    @property
    def has_signal(self) -> bool:
        return len(self.hits) > 0

    @property
    def dominant_direction(self) -> SignalDirection:
        """Return the direction with the highest total weight."""
        if not self.hits:
            return SignalDirection.NEUTRAL
        scores: dict[str, float] = {d.value: 0.0 for d in SignalDirection}
        for hit in self.hits:
            scores[hit.direction.value] += hit.weight
        best = max(scores, key=lambda k: scores[k])
        return SignalDirection(best)

    @property
    def total_score(self) -> float:
        return sum(h.score for h in self.hits)

    def __repr__(self) -> str:
        return (
            f"<ScannerResult {self.scanner} {self.symbol} "
            f"hits={len(self.hits)} score={self.total_score:.1f} "
            f"dir={self.dominant_direction.value}>"
        )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class BaseScanner(ABC):
    """
    Abstract base class for all CoinScopeAI market scanners.

    Subclasses must implement ``scan(symbol)``.
    The optional ``start()`` / ``stop()`` methods manage a background
    asyncio task that runs ``scan()`` on every configured symbol at
    ``scan_interval_seconds`` intervals.

    Parameters
    ----------
    cache  : CacheManager   — shared Redis cache
    rest   : BinanceRESTClient — shared REST client
    name   : str (optional) — human-readable scanner name (defaults to class name)
    """

    def __init__(
        self,
        cache: CacheManager,
        rest: BinanceRESTClient,
        name: Optional[str] = None,
    ) -> None:
        self.cache    = cache
        self.rest     = rest
        self.name     = name or self.__class__.__name__
        self._running = False
        self._task:   Optional[asyncio.Task] = None
        self._results: dict[str, ScannerResult] = {}   # last result per symbol

        logger.debug("%s initialised.", self.name)

    # ── Abstract interface ───────────────────────────────────────────────

    @abstractmethod
    async def scan(self, symbol: str) -> ScannerResult:
        """
        Run the scanner logic for a single symbol.

        Parameters
        ----------
        symbol : str  Trading pair, e.g. "BTCUSDT"

        Returns
        -------
        ScannerResult containing zero or more ScannerHits.
        """
        ...

    # ── Background loop ──────────────────────────────────────────────────

    async def start(
        self,
        symbols: Optional[list[str]] = None,
        interval_s: Optional[int] = None,
    ) -> None:
        """
        Start a background task that calls ``scan()`` on every symbol
        at the configured interval.

        Parameters
        ----------
        symbols    : List of pairs to scan. Defaults to settings.scan_pairs.
        interval_s : Scan cycle interval in seconds. Defaults to
                     settings.scan_interval_seconds.
        """
        if self._running:
            logger.warning("%s is already running.", self.name)
            return

        _symbols  = symbols    or settings.scan_pairs
        _interval = interval_s or settings.scan_interval_seconds
        self._running = True
        self._task    = asyncio.create_task(
            self._loop(_symbols, _interval), name=f"{self.name}_loop"
        )
        logger.info("%s started | symbols=%s interval=%ds", self.name, _symbols, _interval)

    async def stop(self) -> None:
        """Stop the background scanning loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("%s stopped.", self.name)

    async def _loop(self, symbols: list[str], interval_s: int) -> None:
        """Internal background scan loop."""
        while self._running:
            cycle_start = time.monotonic()
            for symbol in symbols:
                if not self._running:
                    break
                try:
                    result = await self.scan(symbol)
                    self._results[symbol] = result
                    if result.has_signal:
                        logger.info(
                            "%s hit | %s %s score=%.1f  %s",
                            self.name, symbol,
                            result.dominant_direction.value,
                            result.total_score,
                            " | ".join(h.reason for h in result.hits),
                        )
                except Exception as exc:
                    logger.error("%s error scanning %s: %s", self.name, symbol, exc)
                    self._results[symbol] = ScannerResult(
                        scanner=self.name, symbol=symbol, error=str(exc)
                    )

            elapsed = time.monotonic() - cycle_start
            sleep_s = max(0.0, interval_s - elapsed)
            await asyncio.sleep(sleep_s)

    # ── Result access ────────────────────────────────────────────────────

    def latest(self, symbol: str) -> Optional[ScannerResult]:
        """Return the most recent ScannerResult for a symbol."""
        return self._results.get(symbol)

    def all_results(self) -> dict[str, ScannerResult]:
        """Return a snapshot of the latest result for every scanned symbol."""
        return dict(self._results)

    def active_hits(self) -> list[ScannerHit]:
        """Return all ScannerHits across all symbols from the last cycle."""
        hits = []
        for result in self._results.values():
            hits.extend(result.hits)
        return hits

    # ── Helper builders ──────────────────────────────────────────────────

    def _make_result(
        self,
        symbol: str,
        hits: list[ScannerHit],
        elapsed_ms: float = 0.0,
    ) -> ScannerResult:
        return ScannerResult(
            scanner=self.name,
            symbol=symbol,
            hits=hits,
            elapsed_ms=elapsed_ms,
        )

    def _make_hit(
        self,
        symbol: str,
        direction: SignalDirection,
        strength: HitStrength,
        score: float,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> ScannerHit:
        return ScannerHit(
            scanner=self.name,
            symbol=symbol,
            direction=direction,
            strength=strength,
            score=score,
            reason=reason,
            metadata=metadata or {},
        )

    def __repr__(self) -> str:
        return f"<{self.name} running={self._running} symbols={list(self._results)}>"
