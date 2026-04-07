"""
CoinScopeAI Phase 2 — Regime Enricher

Combines multiple alpha signals and data sources to classify the current
market regime for a given symbol.

Regime labels:
  - **Trending**       — strong directional move + expanding OI + normal funding
  - **Mean-reverting** — range-bound + declining OI + extreme funding
  - **Volatile**       — high liquidations + wide spreads + rapid OI changes
  - **Low-liquidity**  — thin books + wide spreads + low volume

The enricher handles missing data gracefully: if a data source is
unavailable, its contribution is simply omitted from the scoring.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from services.market_data.models import (
    AggregatedBasis,
    AggregatedOI,
    AlphaSignal,
    AssetContext,
    FundingSnapshot,
    L2OrderBook,
    LiquidationSnapshot,
    MarketRegime,
    RegimeState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RegimeConfig:
    """Tunable thresholds for regime classification."""

    # Trending
    oi_expansion_threshold: float = 0.03       # OI RoC > 3% → expanding
    funding_normal_range: tuple = (-0.0003, 0.0003)  # funding within this = normal

    # Mean-reverting
    oi_contraction_threshold: float = -0.02    # OI RoC < -2% → contracting
    funding_extreme_threshold: float = 0.0005  # |funding| > 0.05% → extreme

    # Volatile
    liquidation_z_threshold: float = 1.5       # liquidation z-score for "high"
    spread_z_threshold: float = 1.5            # spread z-score for "wide"
    oi_change_z_threshold: float = 1.5         # OI change z-score for "rapid"

    # Low-liquidity
    book_depth_threshold: float = 0.3          # imbalance or thin depth flag
    spread_wide_bps: float = 15.0              # spread > 15 bps = wide
    volume_low_threshold: float = 0.3          # volume z < -0.3 = low

    # Scoring
    min_score_gap: float = 0.1                 # minimum gap between top two regimes


# ---------------------------------------------------------------------------
# Regime Enricher
# ---------------------------------------------------------------------------

class RegimeEnricher:
    """
    Classifies market regime by scoring each candidate regime based on
    available data inputs.

    All inputs are **optional** — the enricher degrades gracefully when
    data sources are missing.
    """

    def __init__(self, config: Optional[RegimeConfig] = None) -> None:
        self.config = config or RegimeConfig()

    def classify(
        self,
        symbol: str,
        # Direct data inputs (any or all may be None)
        asset_context: Optional[AssetContext] = None,
        funding_snapshot: Optional[FundingSnapshot] = None,
        oi_snapshots: Optional[Sequence[AggregatedOI]] = None,
        liquidation_snapshots: Optional[Sequence[LiquidationSnapshot]] = None,
        book: Optional[L2OrderBook] = None,
        basis: Optional[AggregatedBasis] = None,
        # Pre-computed alpha signals (alternative input)
        alpha_signals: Optional[List[AlphaSignal]] = None,
        # Price series for trend detection
        prices: Optional[Sequence[float]] = None,
    ) -> RegimeState:
        """
        Produce a ``RegimeState`` for the given symbol.

        The method scores each regime candidate and returns the one with
        the highest score.  If no data is available at all, returns
        ``MarketRegime.UNKNOWN``.
        """
        scores: Dict[str, float] = {
            MarketRegime.TRENDING.value: 0.0,
            MarketRegime.MEAN_REVERTING.value: 0.0,
            MarketRegime.VOLATILE.value: 0.0,
            MarketRegime.LOW_LIQUIDITY.value: 0.0,
        }
        contributors: List[str] = []
        total_weight = 0.0

        # -- Score from OI data -----------------------------------------------
        if oi_snapshots and len(oi_snapshots) >= 2:
            oi_score, oi_contribs = self._score_from_oi(oi_snapshots)
            for regime, s in oi_score.items():
                scores[regime] += s
            contributors.extend(oi_contribs)
            total_weight += 1.0

        # -- Score from funding data ------------------------------------------
        funding_rate = None
        if asset_context:
            funding_rate = asset_context.funding_rate
        elif funding_snapshot and funding_snapshot.rates:
            funding_rate = funding_snapshot.mean_rate

        if funding_rate is not None:
            f_score, f_contribs = self._score_from_funding(funding_rate)
            for regime, s in f_score.items():
                scores[regime] += s
            contributors.extend(f_contribs)
            total_weight += 1.0

        # -- Score from liquidation data --------------------------------------
        if liquidation_snapshots and len(liquidation_snapshots) >= 2:
            l_score, l_contribs = self._score_from_liquidations(liquidation_snapshots)
            for regime, s in l_score.items():
                scores[regime] += s
            contributors.extend(l_contribs)
            total_weight += 1.0

        # -- Score from order book data ---------------------------------------
        if book:
            b_score, b_contribs = self._score_from_book(book)
            for regime, s in b_score.items():
                scores[regime] += s
            contributors.extend(b_contribs)
            total_weight += 1.0

        # -- Score from price trend -------------------------------------------
        if prices and len(prices) >= 5:
            p_score, p_contribs = self._score_from_prices(prices)
            for regime, s in p_score.items():
                scores[regime] += s
            contributors.extend(p_contribs)
            total_weight += 1.0

        # -- Score from pre-computed alpha signals ----------------------------
        if alpha_signals:
            a_score, a_contribs = self._score_from_alpha(alpha_signals)
            for regime, s in a_score.items():
                scores[regime] += s
            contributors.extend(a_contribs)
            total_weight += 1.0

        # -- Normalise and select ---------------------------------------------
        if total_weight == 0:
            return RegimeState(
                symbol=symbol,
                regime=MarketRegime.UNKNOWN,
                confidence=0.0,
                timestamp=time.time(),
                scores=scores,
                contributing_signals=contributors,
            )

        # Normalise scores to [0, 1]
        max_score = max(scores.values())
        if max_score > 0:
            norm_scores = {k: v / max_score for k, v in scores.items()}
        else:
            norm_scores = scores

        # Select top regime
        sorted_regimes = sorted(norm_scores.items(), key=lambda x: x[1], reverse=True)
        top_regime = sorted_regimes[0]
        second_regime = sorted_regimes[1] if len(sorted_regimes) > 1 else ("", 0.0)

        gap = top_regime[1] - second_regime[1]
        confidence = min(top_regime[1], 1.0) * min(gap / max(self.config.min_score_gap, 0.01), 1.0)

        return RegimeState(
            symbol=symbol,
            regime=MarketRegime(top_regime[0]),
            confidence=max(0.0, min(1.0, confidence)),
            timestamp=time.time(),
            scores=norm_scores,
            contributing_signals=contributors,
            metadata={"total_weight": total_weight, "raw_scores": scores},
        )

    # -----------------------------------------------------------------------
    # Scoring sub-routines
    # -----------------------------------------------------------------------

    def _score_from_oi(
        self, snapshots: Sequence[AggregatedOI]
    ) -> tuple[Dict[str, float], List[str]]:
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        totals = [s.total_oi for s in snapshots]
        if totals[-2] == 0:
            return scores, contribs

        roc = (totals[-1] - totals[-2]) / abs(totals[-2])

        if roc > self.config.oi_expansion_threshold:
            scores[MarketRegime.TRENDING.value] += 0.4
            scores[MarketRegime.VOLATILE.value] += 0.1
            contribs.append(f"oi_expanding(roc={roc:.4f})")
        elif roc < self.config.oi_contraction_threshold:
            scores[MarketRegime.MEAN_REVERTING.value] += 0.4
            contribs.append(f"oi_contracting(roc={roc:.4f})")

        # Rapid OI changes → volatile
        if abs(roc) > 0.08:
            scores[MarketRegime.VOLATILE.value] += 0.3
            contribs.append(f"oi_rapid_change(roc={roc:.4f})")

        return scores, contribs

    def _score_from_funding(
        self, rate: float
    ) -> tuple[Dict[str, float], List[str]]:
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        lo, hi = self.config.funding_normal_range
        if lo <= rate <= hi:
            scores[MarketRegime.TRENDING.value] += 0.2
            contribs.append(f"funding_normal({rate:.6f})")
        elif abs(rate) > self.config.funding_extreme_threshold:
            scores[MarketRegime.MEAN_REVERTING.value] += 0.4
            scores[MarketRegime.VOLATILE.value] += 0.1
            contribs.append(f"funding_extreme({rate:.6f})")

        return scores, contribs

    def _score_from_liquidations(
        self, snapshots: Sequence[LiquidationSnapshot]
    ) -> tuple[Dict[str, float], List[str]]:
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        totals = [s.total_usd for s in snapshots]
        if len(totals) < 2:
            return scores, contribs

        mean_val = sum(totals) / len(totals)
        std_val = (sum((t - mean_val) ** 2 for t in totals) / max(len(totals) - 1, 1)) ** 0.5
        current = totals[-1]

        z = (current - mean_val) / std_val if std_val > 0 else 0.0

        if z > self.config.liquidation_z_threshold:
            scores[MarketRegime.VOLATILE.value] += 0.5
            contribs.append(f"liquidation_high(z={z:.2f})")

        return scores, contribs

    def _score_from_book(
        self, book: L2OrderBook
    ) -> tuple[Dict[str, float], List[str]]:
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        spread_bps = book.spread_bps
        if spread_bps is not None and spread_bps > self.config.spread_wide_bps:
            scores[MarketRegime.LOW_LIQUIDITY.value] += 0.4
            scores[MarketRegime.VOLATILE.value] += 0.1
            contribs.append(f"spread_wide({spread_bps:.1f}bps)")

        # Thin book detection
        bid_depth = sum(lvl.size for lvl in book.bids)
        ask_depth = sum(lvl.size for lvl in book.asks)
        total_depth = bid_depth + ask_depth
        if total_depth > 0:
            imbalance = abs(bid_depth - ask_depth) / total_depth
            if imbalance > self.config.book_depth_threshold:
                scores[MarketRegime.LOW_LIQUIDITY.value] += 0.2
                contribs.append(f"book_imbalanced({imbalance:.2f})")

        if len(book.bids) < 5 or len(book.asks) < 5:
            scores[MarketRegime.LOW_LIQUIDITY.value] += 0.3
            contribs.append("thin_book")

        return scores, contribs

    def _score_from_prices(
        self, prices: Sequence[float]
    ) -> tuple[Dict[str, float], List[str]]:
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        if len(prices) < 5:
            return scores, contribs

        # Simple trend detection: directional consistency
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        pos_count = sum(1 for c in changes if c > 0)
        neg_count = sum(1 for c in changes if c < 0)
        total = len(changes)

        directional_ratio = max(pos_count, neg_count) / total if total > 0 else 0

        if directional_ratio > 0.7:
            scores[MarketRegime.TRENDING.value] += 0.4
            contribs.append(f"price_trending(dir_ratio={directional_ratio:.2f})")
        elif directional_ratio < 0.55:
            scores[MarketRegime.MEAN_REVERTING.value] += 0.3
            contribs.append(f"price_choppy(dir_ratio={directional_ratio:.2f})")

        # Volatility: standard deviation of returns
        returns = [changes[i] / prices[i] for i in range(len(changes)) if prices[i] > 0]
        if returns:
            mean_ret = sum(returns) / len(returns)
            vol = (sum((r - mean_ret) ** 2 for r in returns) / max(len(returns) - 1, 1)) ** 0.5
            if vol > 0.02:  # high intraday vol
                scores[MarketRegime.VOLATILE.value] += 0.3
                contribs.append(f"price_volatile(vol={vol:.4f})")

        return scores, contribs

    def _score_from_alpha(
        self, signals: List[AlphaSignal]
    ) -> tuple[Dict[str, float], List[str]]:
        """Incorporate pre-computed alpha signals into regime scoring."""
        scores = {r.value: 0.0 for r in MarketRegime if r != MarketRegime.UNKNOWN}
        contribs: List[str] = []

        signal_map = {s.signal_name: s for s in signals}

        # Funding mean reversion → mean_reverting
        if "funding_mean_reversion" in signal_map:
            sig = signal_map["funding_mean_reversion"]
            scores[MarketRegime.MEAN_REVERTING.value] += 0.3 * sig.confidence
            contribs.append(f"alpha:funding_mean_reversion(c={sig.confidence:.2f})")

        # Liquidation cascade → volatile
        if "liquidation_cascade" in signal_map:
            sig = signal_map["liquidation_cascade"]
            scores[MarketRegime.VOLATILE.value] += 0.4 * sig.confidence
            contribs.append(f"alpha:liquidation_cascade(c={sig.confidence:.2f})")

        # OI expansion → trending
        if "oi_expansion_rate" in signal_map:
            sig = signal_map["oi_expansion_rate"]
            if sig.value > 0:
                scores[MarketRegime.TRENDING.value] += 0.3 * sig.confidence
                contribs.append(f"alpha:oi_expanding(c={sig.confidence:.2f})")
            else:
                scores[MarketRegime.MEAN_REVERTING.value] += 0.2 * sig.confidence
                contribs.append(f"alpha:oi_contracting(c={sig.confidence:.2f})")

        # Spread z-score → low liquidity or volatile
        if "orderbook_spread_z" in signal_map:
            sig = signal_map["orderbook_spread_z"]
            if sig.z_score > 1.5:
                scores[MarketRegime.LOW_LIQUIDITY.value] += 0.3 * sig.confidence
                contribs.append(f"alpha:spread_wide(z={sig.z_score:.2f})")

        # Basis extreme → mean reverting
        if "basis_premium_extreme" in signal_map:
            sig = signal_map["basis_premium_extreme"]
            scores[MarketRegime.MEAN_REVERTING.value] += 0.2 * sig.confidence
            contribs.append(f"alpha:basis_extreme(c={sig.confidence:.2f})")

        return scores, contribs
