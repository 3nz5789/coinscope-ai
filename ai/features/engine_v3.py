"""
CoinScopeAI — Feature Engineering Engine v3 (Phase 2 Alpha Features)
======================================================================
Extends v2 (LongTFFeatureEngine) with Phase 2 alpha signal proxy features
derived from OHLCV data. These proxy features approximate the microstructure
signals that the live alpha generators (funding, liquidation, OI, basis,
orderbook) produce from real-time streaming data.

New feature groups (all derived from OHLCV):
  1. Funding Extreme Proxies — cross-exchange divergence, mean reversion,
     predicted extremes from premium/discount patterns
  2. Liquidation Proxies — cascade detection from volume spikes + price moves,
     cluster analysis from consecutive large moves, long/short ratio
  3. Open Interest Proxies — expansion/contraction from volume trends,
     OI vs price divergence from volume-price correlation changes
  4. Basis Proxies — premium/discount extremes, convergence/divergence, z-score
  5. OrderBook Proxies — book imbalance from candle body ratios, depth-weighted
     mid from VWAP deviations, liquidity cliff detection

Total features: v2 (112) + Phase 2 alpha proxies (~45) = ~157 features
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ai.features.engine import FeatureEngine
from ai.features.engine_v2 import LongTFFeatureEngine, LongTFFeatureConfig

logger = logging.getLogger("coinscopeai.ai.features.v3")


@dataclass
class V3FeatureConfig(LongTFFeatureConfig):
    """Feature config with Phase 2 alpha proxy parameters."""
    # Funding proxy parameters
    funding_lookbacks: List[int] = field(default_factory=lambda: [8, 24, 48])
    funding_extreme_zscore: float = 2.0

    # Liquidation proxy parameters
    liq_vol_window: int = 5
    liq_cascade_threshold: float = 2.5  # Volume spike multiplier
    liq_cluster_window: int = 3

    # OI proxy parameters
    oi_lookbacks: List[int] = field(default_factory=lambda: [5, 10, 20])
    oi_divergence_window: int = 14

    # Basis proxy parameters
    basis_lookbacks: List[int] = field(default_factory=lambda: [10, 20, 50])
    basis_zscore_window: int = 50

    # OrderBook proxy parameters
    ob_lookbacks: List[int] = field(default_factory=lambda: [5, 10, 20])
    ob_depth_window: int = 10


class V3FeatureEngine:
    """
    v3 Feature Engine: v2 base features + Phase 2 alpha proxy features.

    All proxy features are derived from OHLCV data using the same
    statistical patterns that the live alpha generators detect from
    real-time microstructure data.
    """

    def __init__(self, config: Optional[V3FeatureConfig] = None):
        self.config = config or V3FeatureConfig()
        self._feature_names: List[str] = []

        # Reuse v2 engine for base features
        self._v2_engine = LongTFFeatureEngine(self.config)

    @property
    def feature_names(self) -> List[str]:
        return self._feature_names

    def extract(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract all v3 features: v2 base + Phase 2 alpha proxies.

        Args:
            df: DataFrame with columns: timestamp, open, high, low, close, volume

        Returns:
            Feature DataFrame aligned to input index.
        """
        # Start with v2 features (112 features)
        features = self._v2_engine.extract(df)

        close = df["close"].values.astype(np.float64)
        high = df["high"].values.astype(np.float64)
        low = df["low"].values.astype(np.float64)
        open_ = df["open"].values.astype(np.float64)
        volume = df["volume"].values.astype(np.float64)

        # Precompute common arrays
        n = len(close)
        log_ret = np.full(n, np.nan)
        log_ret[1:] = np.log(np.maximum(close[1:], 1e-10) / np.maximum(close[:-1], 1e-10))

        # ── Phase 2 Alpha Proxy Features ──────────────────────────

        # 1. Funding Extreme Proxies
        funding_feats = self._funding_extreme_features(close, open_, high, low, volume, log_ret)
        for name, values in funding_feats.items():
            features[name] = values

        # 2. Liquidation Proxies
        liq_feats = self._liquidation_features(close, volume, log_ret, high, low, open_)
        for name, values in liq_feats.items():
            features[name] = values

        # 3. Open Interest Proxies
        oi_feats = self._oi_features(close, volume, log_ret)
        for name, values in oi_feats.items():
            features[name] = values

        # 4. Basis Proxies
        basis_feats = self._basis_features(close, high, low, open_)
        for name, values in basis_feats.items():
            features[name] = values

        # 5. OrderBook Proxies
        ob_feats = self._orderbook_features(close, high, low, open_, volume)
        for name, values in ob_feats.items():
            features[name] = values

        self._feature_names = list(features.columns)
        n_v2 = len(self._v2_engine.feature_names)
        n_alpha = len(self._feature_names) - n_v2
        logger.info(
            "V3: Extracted %d features from %d bars (v2: %d + alpha: %d)",
            len(self._feature_names), len(df), n_v2, n_alpha,
        )
        return features

    # ═══════════════════════════════════════════════════════════════
    # 1. FUNDING EXTREME PROXY FEATURES
    # ═══════════════════════════════════════════════════════════════

    def _funding_extreme_features(
        self,
        close: np.ndarray,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        log_ret: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Proxy for cross-exchange funding rate signals.

        Funding rate reflects the premium between perpetual futures and spot.
        We proxy this using:
          - Close-to-open gaps (overnight sentiment / funding payment effect)
          - Premium persistence (rolling gap mean vs long-term)
          - Funding extreme z-score (when premium is statistically extreme)
          - Mean reversion signal (extreme funding tends to revert)
          - Predicted extreme (momentum of funding proxy)
        """
        feats = {}
        n = len(close)

        # Close-to-open gap as funding proxy
        gap = np.full(n, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            gap[1:] = np.where(close[:-1] > 0, open_[1:] / close[:-1] - 1.0, np.nan)

        # Cross-exchange divergence proxy: gap vs its own trend
        for p in self.config.funding_lookbacks:
            gap_ma = self._rolling_mean(gap, p)
            gap_std = self._rolling_std(gap, p)

            # Funding z-score: how extreme is current gap vs recent history
            with np.errstate(divide="ignore", invalid="ignore"):
                feats[f"funding_zscore_{p}"] = np.where(
                    gap_std > 1e-10, (gap - gap_ma) / gap_std, 0.0
                )

            # Cumulative funding proxy (rolling sum of gaps)
            feats[f"funding_cumul_{p}"] = self._rolling_sum(gap, p)

        # Mean reversion signal: when funding is extreme, expect reversion
        gap_48 = self._rolling_mean(gap, 48)
        gap_std_48 = self._rolling_std(gap, 48)
        with np.errstate(divide="ignore", invalid="ignore"):
            funding_extreme = np.where(
                gap_std_48 > 1e-10,
                (gap_48 - self._rolling_mean(gap, 200)) / gap_std_48,
                0.0,
            )
        feats["funding_mean_rev"] = -np.tanh(funding_extreme)  # Contrarian

        # Predicted extreme: momentum of funding proxy
        gap_8 = self._rolling_mean(gap, 8)
        gap_24 = self._rolling_mean(gap, 24)
        feats["funding_momentum"] = gap_8 - gap_24

        # Funding divergence: gap direction vs price direction
        price_dir = np.sign(log_ret)
        gap_dir = np.sign(gap)
        feats["funding_price_div"] = self._rolling_mean(
            price_dir * gap_dir, 10
        )

        return feats

    # ═══════════════════════════════════════════════════════════════
    # 2. LIQUIDATION PROXY FEATURES
    # ═══════════════════════════════════════════════════════════════

    def _liquidation_features(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        log_ret: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Proxy for liquidation cascade signals.

        Liquidations cause forced buying/selling, detectable as:
          - Volume spikes coinciding with large price moves
          - Consecutive large moves in one direction (cascade)
          - Long/short ratio proxy from candle body patterns
        """
        feats = {}
        n = len(close)

        # Cascade detection: volume spike * absolute return
        # High values indicate forced liquidation activity
        vol_ma = self._rolling_mean(volume, 20)
        with np.errstate(divide="ignore", invalid="ignore"):
            vol_spike = np.where(vol_ma > 0, volume / vol_ma, 1.0)

        # Liquidation intensity: volume spike * price move magnitude
        liq_intensity = vol_spike * np.abs(log_ret)
        for p in [3, 5, 10]:
            feats[f"liq_intensity_{p}"] = self._rolling_mean(liq_intensity, p)

        # Cascade detection: rolling sum of signed intensity
        # Positive = short liquidations (price going up), Negative = long liquidations
        signed_intensity = vol_spike * log_ret
        for p in [3, 5]:
            feats[f"liq_cascade_{p}"] = self._rolling_sum(signed_intensity, p)

        # Cluster analysis: consecutive bars with above-average volume + large moves
        large_move = (np.abs(log_ret) > self._rolling_std(log_ret, 20) * 1.5).astype(float)
        high_vol = (vol_spike > 1.5).astype(float)
        liq_cluster = large_move * high_vol

        # Rolling cluster count
        for p in [3, 5]:
            feats[f"liq_cluster_{p}"] = self._rolling_sum(liq_cluster, p)

        # Long/short ratio proxy from candle body patterns
        # Upper wick dominance suggests short squeeze (long liquidations absorbed)
        # Lower wick dominance suggests long squeeze (short liquidations absorbed)
        body = close - open_
        upper_wick = high - np.maximum(close, open_)
        lower_wick = np.minimum(close, open_) - low
        total_range = high - low

        with np.errstate(divide="ignore", invalid="ignore"):
            # Wick ratio: positive = more upper wick (selling pressure from liq)
            wick_ratio = np.where(
                total_range > 0,
                (upper_wick - lower_wick) / total_range,
                0.0,
            )

        for p in [5, 10]:
            feats[f"liq_wick_ratio_{p}"] = self._rolling_mean(wick_ratio, p)

        # Long/short ratio proxy: body direction weighted by volume
        with np.errstate(divide="ignore", invalid="ignore"):
            body_ratio = np.where(total_range > 0, body / total_range, 0.0)
        vol_weighted_body = body_ratio * vol_spike
        for p in [5, 10]:
            feats[f"liq_ls_ratio_{p}"] = self._rolling_mean(vol_weighted_body, p)

        return feats

    # ═══════════════════════════════════════════════════════════════
    # 3. OPEN INTEREST PROXY FEATURES
    # ═══════════════════════════════════════════════════════════════

    def _oi_features(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        log_ret: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Proxy for open interest signals.

        OI reflects the total number of outstanding contracts. We proxy using:
          - Volume trends (OI expansion → higher volume, contraction → lower)
          - Volume-price divergence (OI divergence proxy)
          - Cross-exchange OI divergence proxy from volume pattern changes
        """
        feats = {}
        n = len(close)

        # OI expansion/contraction proxy: volume trend
        # Rising volume with trending price = OI expansion
        # Falling volume with trending price = OI contraction (position closing)
        for p in self.config.oi_lookbacks:
            vol_trend = self._rolling_mean(volume, p)
            vol_trend_long = self._rolling_mean(volume, p * 4)

            with np.errstate(divide="ignore", invalid="ignore"):
                # OI expansion ratio: short-term vol vs long-term vol
                feats[f"oi_expansion_{p}"] = np.where(
                    vol_trend_long > 0, vol_trend / vol_trend_long - 1.0, 0.0
                )

        # OI vs price divergence proxy
        # When price trends but volume drops → OI contracting → trend weakening
        for p in [10, 20]:
            price_trend = self._rolling_mean(log_ret, p)
            vol_change = np.full(n, np.nan)
            vol_ma_short = self._rolling_mean(volume, p)
            vol_ma_long = self._rolling_mean(volume, p * 2)
            with np.errstate(divide="ignore", invalid="ignore"):
                vol_change = np.where(
                    vol_ma_long > 0, vol_ma_short / vol_ma_long - 1.0, 0.0
                )

            # Divergence: price trending up but volume declining = bearish divergence
            feats[f"oi_price_div_{p}"] = price_trend * vol_change

        # Cross-exchange OI divergence proxy: volume autocorrelation changes
        # Different exchanges show different OI patterns; we proxy via
        # changes in volume autocorrelation structure
        for p in [10, 20]:
            vol_autocorr = np.full(n, np.nan)
            for i in range(p, n):
                v1 = volume[i - p:i - 1]
                v2 = volume[i - p + 1:i]
                if len(v1) > 1 and np.std(v1) > 0 and np.std(v2) > 0:
                    vol_autocorr[i] = np.corrcoef(v1, v2)[0, 1]
            feats[f"oi_vol_autocorr_{p}"] = vol_autocorr

        return feats

    # ═══════════════════════════════════════════════════════════════
    # 4. BASIS PROXY FEATURES
    # ═══════════════════════════════════════════════════════════════

    def _basis_features(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Proxy for cross-exchange basis (premium/discount) signals.

        Basis = futures price - spot price. We proxy using:
          - Close vs VWAP-like midpoint (premium/discount)
          - Convergence/divergence of different price measures
          - Z-score of basis proxy for extreme detection
        """
        feats = {}
        n = len(close)

        # Premium/discount proxy: close vs typical price
        typical = (high + low + close) / 3.0
        with np.errstate(divide="ignore", invalid="ignore"):
            premium = np.where(typical > 0, close / typical - 1.0, 0.0)

        for p in self.config.basis_lookbacks:
            # Rolling premium
            feats[f"basis_premium_{p}"] = self._rolling_mean(premium, p)

            # Premium z-score (extreme detection)
            prem_ma = self._rolling_mean(premium, p)
            prem_std = self._rolling_std(premium, p)
            with np.errstate(divide="ignore", invalid="ignore"):
                feats[f"basis_zscore_{p}"] = np.where(
                    prem_std > 1e-10, (premium - prem_ma) / prem_std, 0.0
                )

        # Convergence/divergence: short-term vs long-term premium
        prem_short = self._rolling_mean(premium, 10)
        prem_long = self._rolling_mean(premium, 50)
        feats["basis_convergence"] = prem_short - prem_long

        # Basis momentum: is the premium increasing or decreasing?
        prem_10 = self._rolling_mean(premium, 10)
        prem_diff = np.full(n, np.nan)
        prem_diff[5:] = prem_10[5:] - prem_10[:-5]
        feats["basis_momentum"] = prem_diff

        # Close vs open premium persistence (overnight basis)
        with np.errstate(divide="ignore", invalid="ignore"):
            co_premium = np.where(open_ > 0, close / open_ - 1.0, 0.0)
        for p in [10, 20]:
            feats[f"basis_co_premium_{p}"] = self._rolling_mean(co_premium, p)

        return feats

    # ═══════════════════════════════════════════════════════════════
    # 5. ORDERBOOK PROXY FEATURES
    # ═══════════════════════════════════════════════════════════════

    def _orderbook_features(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        open_: np.ndarray,
        volume: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Proxy for order book microstructure signals.

        Order book imbalance and depth are proxied using:
          - Candle body ratio as bid/ask imbalance proxy
          - VWAP deviation as depth-weighted mid proxy
          - Range/ATR ratio as liquidity cliff detection
        """
        feats = {}
        n = len(close)

        # Book imbalance proxy: candle body position within range
        # Close near high = buy pressure (bid-heavy), close near low = sell pressure
        with np.errstate(divide="ignore", invalid="ignore"):
            range_ = high - low
            body_pos = np.where(range_ > 0, (close - low) / range_, 0.5)

        # Centered imbalance: 0 = balanced, +1 = all buying, -1 = all selling
        imbalance = 2.0 * body_pos - 1.0

        for p in self.config.ob_lookbacks:
            feats[f"ob_imbalance_{p}"] = self._rolling_mean(imbalance, p)

        # Persistent imbalance: fraction of bars with positive imbalance
        for p in [10, 20]:
            pos_frac = np.full(n, np.nan)
            for i in range(p - 1, n):
                window = imbalance[i - p + 1:i + 1]
                valid = window[~np.isnan(window)]
                if len(valid) > 0:
                    pos_frac[i] = np.mean(valid > 0)
            feats[f"ob_persistence_{p}"] = pos_frac

        # Depth-weighted mid proxy: VWAP deviation from midpoint
        mid = (high + low) / 2.0
        with np.errstate(divide="ignore", invalid="ignore"):
            vwap_dev = np.where(mid > 0, close / mid - 1.0, 0.0)

        for p in [5, 10]:
            feats[f"ob_depth_mid_{p}"] = self._rolling_mean(vwap_dev, p)

        # Liquidity cliff detection: sudden range expansion
        # When range >> ATR, it suggests hitting a liquidity void
        for atr_p in [7, 14]:
            atr = self._calc_atr(high, low, close, atr_p)
            with np.errstate(divide="ignore", invalid="ignore"):
                range_ratio = np.where(atr > 0, range_ / atr, 1.0)
            feats[f"ob_liq_cliff_{atr_p}"] = range_ratio

            # Asymmetric cliff: which side had the void?
            upper_range = high - np.maximum(close, open_)
            lower_range = np.minimum(close, open_) - low
            with np.errstate(divide="ignore", invalid="ignore"):
                cliff_asym = np.where(
                    range_ > 0,
                    (upper_range - lower_range) / range_,
                    0.0,
                )
            feats[f"ob_cliff_asym_{atr_p}"] = self._rolling_mean(cliff_asym, atr_p)

        # Spread proxy: high-low range normalized by close
        with np.errstate(divide="ignore", invalid="ignore"):
            spread = np.where(close > 0, range_ / close, 0.0)
        for p in [5, 10]:
            feats[f"ob_spread_{p}"] = self._rolling_mean(spread, p)

        return feats

    # ═══════════════════════════════════════════════════════════════
    # STATIC HELPERS
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _rolling_mean(data: np.ndarray, period: int) -> np.ndarray:
        return FeatureEngine._rolling_mean(data, period)

    @staticmethod
    def _rolling_std(data: np.ndarray, period: int) -> np.ndarray:
        return FeatureEngine._rolling_std(data, period)

    @staticmethod
    def _rolling_sum(data: np.ndarray, period: int) -> np.ndarray:
        n = len(data)
        result = np.full(n, np.nan, dtype=np.float64)
        for i in range(period - 1, n):
            window = data[i - period + 1:i + 1]
            valid = window[~np.isnan(window)]
            if len(valid) > 0:
                result[i] = np.sum(valid)
        return result

    @staticmethod
    def _calc_atr(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
    ) -> np.ndarray:
        n = len(close)
        tr = np.full(n, np.nan)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        return FeatureEngine._rolling_mean(tr, period)
