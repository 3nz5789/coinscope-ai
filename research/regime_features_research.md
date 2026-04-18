---
title: "[RESEARCH] ML — Best Features for Regime Detection"
author: Scoopy (Claude)
date: 2026-04-17
phase: 30-Day Testnet Validation (COI-41)
status: Research only — no engine changes during validation phase
audit_scope: v3 regime classifier (ml/regime_classifier_v3.py)
---

# Best Features for Regime Detection — v3 Audit & Upgrade Candidates

## TL;DR

The v3 regime classifier is a soft-voting RF+XGB ensemble trained on **18 engineered features** (not 162 — that figure belongs to the broader signal engine). It reports 97% accuracy on held-out data, driven almost entirely by volatility features (atr_pct alone = 34.8% feature importance; top-5 all volatility/trend). **The feature set is narrow: no microstructure, no crypto-specific signals (funding, OI, liquidations), no memory/persistence metrics (Hurst, variance ratio), and no cross-asset context.** That high accuracy number is probably a label-leakage artifact of the rule-based labeler — the real test is post-validation live-trade separation across Trending / Mean-Reverting / Volatile / Quiet.

This brief is a **research artifact for the post-validation upgrade cycle**. No engine changes proposed during COI-41 code freeze.

---

## 1. What the v3 classifier uses today

Source: `ml/regime_classifier_v3.py` + `ml/regime_label_dataset_v1.py` (compute_features).

| Category | Count | Features |
|---|---|---|
| Returns / momentum | 3 | log_ret, abs_ret, roc_10 |
| Trend | 7 | adx, di_split, ema_align, price_vs_ema50, price_vs_ema200, macd_hist, stoch_k |
| Volatility | 6 | atr_pct, atr_pct_zscore, bb_width, bb_width_zscore, bb_pct_b, vol_of_vol |
| Volume | 1 | vol_zscore |
| **Total** | **18** | |

Top-5 feature importance (avg RF+XGB): atr_pct (0.348), bb_width (0.189), vol_of_vol (0.105), adx (0.091), price_vs_ema200 (0.083). Everything else is <5% each.

Known issues surfaced in the audit:
- The live `/regime/{symbol}` endpoint still points to the legacy 3-state HMM (`EnsembleRegimeDetector`), not the trained v3 model — the v3 classifier is trained but not served.
- `xgboost` and `joblib` are imported but not declared in `requirements.txt`.
- Feature definitions live in the label-dataset builder, not a separate config file — brittle for research iteration.

## 2. What's missing (high-leverage gaps)

Grouped by category; everything below is absent from the 18-feature set.

**Memory / persistence.** The single best separator of Trending vs Mean-Reverting in the literature is persistence of returns — and v3 has nothing to capture it. Candidates: **Hurst exponent** (R/S or DFA estimator), **variance ratio test (Lo-MacKinlay)**, return **autocorrelation lag-1 / lag-5**. Without these, the model is leaning on "is volatility low?" as a proxy for mean reversion, which conflates Mean-Reverting with Quiet.

**Advanced volatility estimators.** ATR is a noisy volatility proxy. For a 97%-accuracy ceiling claim, you want OHLC-based realized-volatility estimators: **Parkinson (high-low range)**, **Garman-Klass**, **Rogers-Satchell**, plus **realized volatility from intrabar ticks** and **bipower variation** for jump-robust RV. These separate Volatile from Trending far better than ATR alone (Parkinson is 5× more efficient than close-to-close).

**Crypto-specific / microstructure.** The entire perps ecosystem — funding, OI, liquidations, CVD — is missing. For Binance Futures this is free alpha: **funding rate + funding z-score**, **open interest delta (1h/4h)**, **liquidation volume (long/short split)**, **CVD slope / CVD divergence vs price**, **bid-ask spread**, **book imbalance (top 5 levels)**, **VPIN (flow toxicity)**. VPIN is particularly strong — sustained VPIN > 0.6 is documented as a trending-regime signal that disables mean-reversion strategies.

**Cross-asset / market context.** Regimes are not symbol-local. Add **BTC return correlation (60-bar)**, **BTC dominance delta**, **altseason index**, **correlation to SPX / DXY** (for macro beta on high-cap alts), and **BTC realized volatility** as a shared-context feature on non-BTC symbols.

**Distributional shape.** v3 has no higher-moment features. Add rolling **return skewness** and **return kurtosis** (volatile regimes have fat tails; quiet regimes are near-Gaussian), plus **tail ratio** (99th / 1st percentile).

**Multi-timeframe alignment.** v3 features are all single-timeframe. Add **MTF trend agreement score** (sign of EMA slope on 15m/1h/4h), **MTF RSI divergence**, and **MTF volatility ratio (short/long)** to separate local chop from global trends.

**Regime-transition features.** The classifier predicts the current regime but has no features for *change*. Add **rolling entropy of returns (Shannon)**, **CUSUM statistic**, and **changepoint score (Bayesian Online Changepoint Detection probability)** to flag transitions early — this is how you catch Quiet → Volatile before the ATR z-score spikes.

## 3. Shortlist: top 15 features to add (post-validation)

Ranked by expected regime-separation lift × low compute cost × crypto-futures fit. Full detail in `regime_features_matrix.xlsx`.

1. **Hurst exponent (DFA, 100-bar window)** — direct trending vs mean-reverting separator
2. **Variance ratio (lag 2 vs lag 10)** — complements Hurst, cheaper to compute
3. **Parkinson realized volatility** — efficient OHLC RV estimator
4. **Return autocorrelation lag-1 (50-bar)** — mean-reversion persistence
5. **Funding rate z-score (168h)** — crypto-native regime signal
6. **Open interest delta % (1h, 4h)** — already computed in the scanner; reuse
7. **Liquidation volume ratio (longs/shorts, 1h)** — capitulation / squeeze detector
8. **CVD slope (50-bar)** — order flow persistence
9. **Bipower-variation jump test** — separates diffusive vol from jump vol
10. **Rolling return kurtosis (100-bar)** — tail risk / Volatile regime
11. **MTF trend agreement (15m/1h/4h)** — global vs local trend
12. **BTC return correlation (60-bar)** — cross-asset context for alts
13. **VPIN (50-bucket)** — flow toxicity / trending-regime confirmer
14. **Rolling Shannon entropy of returns** — regime-change early warning
15. **BB squeeze indicator (width percentile, 200-bar)** — Quiet regime confirmer

## 4. Why not more / what to deprioritize

The brief is deliberately a shortlist, not a kitchen sink. Reasons to **not** add:
- **Sentiment / news features** — valuable but outside the 30-day validation envelope and requires an ingest pipeline we don't have.
- **LSTM / deep learning** — current RF+XGB ensemble is strong; feature engineering gets more bang-for-buck than a model swap pre-v4.
- **Per-exchange basis / term structure** — perps-only, no futures curve; skip until spot-perp basis is wired in.
- **On-chain features (whale flows, exchange netflow)** — interesting but high-latency and expensive per-symbol; revisit when we care about multi-day regimes, not intraday.

## 5. Risks & caveats

- **Label quality is the real ceiling.** 97% accuracy vs the current rule-based labels is a ceiling *on matching the labeler*, not on predicting future returns. Any feature upgrade should be validated against out-of-sample per-regime PnL, not label F1.
- **Validation-phase freeze.** None of this ships during COI-41. Research-only until the 30-day testnet run completes with 7 clean days.
- **Audit mismatch.** `/regime/{symbol}` endpoint wiring is a bug, not a feature decision — file separately (not in the v3 feature plan).
- **Compute budget.** Hurst and VPIN are the two most expensive in the shortlist. If per-bar latency matters, use 100–200-bar windows and cache.

## 6. Next steps (post-validation)

1. Wire `/regime/{symbol}` to the trained v3 classifier (separate bug, not research).
2. Land the 15-feature shortlist as an opt-in `v3.1` feature set, gated behind a feature flag.
3. Re-label dataset with a *non-rule-based* labeler (e.g., HMM-labeled + human spot-checks) to remove the leakage ceiling.
4. Ablation study: drop existing features one at a time, add new ones one at a time, measure per-regime F1 AND per-regime live-paper PnL on testnet.
5. Decide on v4: keep RF+XGB ensemble or upgrade to LightGBM (better with wide feature sets) + calibrated probabilities.

## Sources

- [Thrive — Crypto Market Regime Detection](https://thrive.fi/blog/trading/crypto-market-regime-detection)
- [State Street Global Advisors — Decoding Market Regimes with Machine Learning (2025)](https://www.ssga.com/library-content/assets/pdf/global/pc/2025/decoding-market-regimes-with-machine-learning.pdf)
- [MDPI — Graph-Based Stock Volatility Forecasting with Hurst-Based Regime Adaptation](https://www.mdpi.com/2504-3110/9/6/339)
- [Springer — Regime switching forecasting for cryptocurrencies](https://link.springer.com/article/10.1007/s42521-024-00123-2)
- [QuantStart — Market Regime Detection using Hidden Markov Models](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/)
- [QuantInsti — ML for Market Regime Detection Using Random Forest](https://blog.quantinsti.com/epat-project-machine-learning-market-regime-detection-random-forest-python/)
- [Harbourfront — Regime Classification Framework for Mean-Reverting and Trending Markets (Apr 2026)](https://harbourfronttechnologies.wordpress.com/2026/04/12/regime-classification-framework-for-mean-reverting-and-trending-markets/)
- [Buildix — What Is VPIN? Flow Toxicity Detection for Crypto Traders](https://www.buildix.trade/blog/what-is-vpin-flow-toxicity-crypto-trading)
- [Cornell — Microstructure and Market Dynamics in Crypto Markets (Easley et al.)](https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf)
- [arXiv — Explainable Patterns in Cryptocurrency Microstructure](https://arxiv.org/html/2602.00776v1)
- [ScienceDirect — Forecasting Bitcoin volatility using machine learning techniques](https://www.sciencedirect.com/science/article/pii/S1042443124001306)
- [Springer — Crypto Volatility Forecasting: HAR, Sentiment, and Machine Learning Horserace](https://link.springer.com/article/10.1007/s10690-024-09510-6)
