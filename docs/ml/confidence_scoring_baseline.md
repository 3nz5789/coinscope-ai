# [ML] SIGNALS — Confidence Scoring Baseline

**Status:** Draft v1 (framework + pre-live placeholders)
**Owner:** Mohammed / Scoopy
**Created:** 2026-04-17
**Phase:** 30-Day Testnet Validation (COI-41)
**Engine code freeze:** In effect — this doc is measurement + spec only, not an engine change.

---

## 1. Purpose

Establish the **measurement baseline** for how the CoinScopeAI engine scores confidence in a trading signal, across four dimensions, so that during and after the 30-day testnet validation phase we can answer:

1. Is confidence well-calibrated? (A 70% confidence signal should win ~70% of the time.)
2. Does confidence translate into PnL, or only into hit-rate?
3. Which confidence dimension discriminates best between winners and losers?
4. Does confidence behave differently across market regimes?
5. How much signal attrition happens at the risk gate, and does the risk gate preserve high-quality signals?

This baseline is the reference that any future scoring change (post-validation) must demonstrably improve against.

---

## 2. Non-Goals

- **No engine changes.** This doc defines measurement only. Weights, thresholds, and scoring logic in `confluence_scorer.py` / `signal_generator.py` remain frozen until validation completes.
- **No calibration adjustments** to live scoring during the 30-day window.
- **No new features** added to scorers.

---

## 3. The Four Confidence Dimensions

The engine produces confidence in four progressively-filtered layers. This baseline measures each in isolation and in combination.

### 3.1 Signal Confluence Score (C1)
**Source:** `coinscope_trading_engine/signals/confluence_scorer.py`
**Scale:** 0.0 – 100.0 (NOT 0–12 — the 0–12 value the scanner/dashboard shows is a dashboard-side roll-up; the authoritative engine value is the 0–100 float.)
**Formula (summary):**
```
raw_score      = Σ (hit.score × hit.weight)         # hit.weight ∈ {1,2,3} for WEAK/MED/STRONG
normalised     = (raw_score / MAX_RAW_SCORE) × 100  # MAX_RAW_SCORE = 300
+ BONUS_TREND      (+10) if trend aligned
+ BONUS_MOMENTUM   (+8)  if momentum aligned
+ BONUS_RSI_ZONE   (+5)  if RSI in supportive zone
+ BONUS_MACD_CROSS (+7)  on MACD signal-line cross
+ BONUS_ADX        (+5)  if ADX indicates trending
- PENALTY_CONTRA   (-8)  if indicators contradict direction
= final confluence score
```
**Strength labels:** WEAK (≥40), MODERATE (≥55), STRONG (≥70), VERY_STRONG (≥85).
**Fires when:** `score >= MIN_CONFLUENCE_SCORE` (from `.env`).

### 3.2 ML Model Probability (C2)
**Source:** `signal_generator.py` — component outputs from `FixedScorer`, `EnsembleRegimeDetector`, `MultiTimeframeFilter`, `VolumeScanner`, `LiquidationScanner`, aggregated as a weighted score.
**Scale:** 0.0 – 1.0
**Weights (canonical):**
| Component   | Weight |
|-------------|-------:|
| scorer      | 0.40 |
| regime      | 0.25 |
| mtf         | 0.15 |
| volume      | 0.10 |
| liquidation | 0.10 |
**Fires when:** weighted aggregate ≥ `SIGNAL_THRESHOLD = 0.55`.
**Underlying models:** LightGBM + Logistic Regression (per `coinscopeai-architecture` skill), 162-feature V3 model.

### 3.3 Regime-Conditioned Confidence (C3)
**Source:** `EnsembleRegimeDetector` + engine endpoint `GET /regime/{symbol}`.
**Regime labels (v3 ML):** Trending, Mean-Reverting, Volatile, Quiet.
**Definition:** C3 = (C1, C2) split into four per-regime cohorts, so the baseline captures per-regime calibration rather than a single global number.
**Why it matters:** A signal with C2 = 0.72 in a Volatile regime is not interchangeable with C2 = 0.72 in a Trending regime — risk and win-rate differ.

### 3.4 Risk-Gated Final Confidence (C4)
**Source:** `/risk-gate` pass × `/position-size` approval.
**Definition:** C4 is the subset of (C1, C2, C3) signals that actually reached `position-size` / execution. It represents what the engine would have traded.
**Risk gate thresholds (canonical — `coinscopeai-trading-rules`):**
- Daily loss limit: 5%
- Max drawdown: 10%
- Max leverage: 10x
- Position heat cap: 80%
- Max 5 open positions
**Kill switch:** armed state halts C4 to zero regardless of upstream score.

---

## 4. Baseline Metrics (per dimension)

For each of C1, C2, C3, C4, compute:

### 4.1 Distribution
- Histogram of score values, bucketed.
  - C1 buckets: [0–40) discarded, [40–55), [55–70), [70–85), [85–100].
  - C2 buckets: [0.55–0.60), [0.60–0.70), [0.70–0.80), [0.80–0.90), [0.90–1.00].
- Volume per bucket (count of signals) and per symbol (BTC/ETH/SOL/BNB/XRP).

### 4.2 Calibration
- Reliability diagram: predicted confidence vs. realised hit-rate per bucket.
- **Brier score** (C2 only; C1 is not a probability but can be min-max rescaled for reporting).
- **Expected Calibration Error (ECE)**, 10-bin.
- **Maximum Calibration Error (MCE)**, 10-bin.

### 4.3 Discrimination
- **AUC-ROC** of C2 vs. realised win/loss label (C2 is the only true probability; AUC requires a ranking score, so C1 is also AUC'd after min-max rescale).
- **Hit-rate delta:** win_rate(top bucket) − win_rate(bottom bucket). Positive delta = dimension discriminates.

### 4.4 PnL Translation
- Mean R-multiple (realised PnL ÷ risk per trade) by bucket.
- Profit factor per bucket.
- PnL concentration: % of total PnL from top 20% of signals by confidence.

### 4.5 Regime Breakdown (C3-specific)
All of the above, computed independently per regime label.

### 4.6 Risk-Gate Attrition (C4-specific)
- Attrition rate: 1 − (count(C4) / count(C2 ≥ 0.55)).
- Reason codes: daily_loss_limit, drawdown, heat, max_positions, kill_switch.
- Calibration of C4 vs. C2: does gating improve per-bucket win-rate?

---

## 5. Acceptance Thresholds (baseline pass criteria)

These are the numbers the engine needs to beat to be considered **calibrated for promotion to staging-candidate**. They are deliberately conservative because capital preservation is the primary goal.

| Metric | C1 | C2 | C3 (each regime) | C4 |
|---|---|---|---|---|
| ECE (10-bin) | ≤ 0.10 | ≤ 0.08 | ≤ 0.12 | ≤ 0.08 |
| AUC-ROC (after rescale for C1) | ≥ 0.58 | ≥ 0.62 | ≥ 0.58 | ≥ 0.62 |
| Hit-rate delta (top − bottom bucket) | ≥ +10pp | ≥ +12pp | ≥ +8pp | ≥ +12pp |
| Mean R (top bucket) | ≥ +0.40R | ≥ +0.50R | ≥ +0.30R | ≥ +0.50R |
| Profit factor (top bucket) | ≥ 1.25 | ≥ 1.35 | ≥ 1.20 | ≥ 1.40 |

**Sample-size gates:** No bucket judged until it has ≥ 30 signals. No regime judged until it has ≥ 20 signals.

These are **working thresholds** — they are not final production-candidate criteria (which require the documented clean-day count and more).

---

## 6. Data Sources

### 6.1 Primary (when engine is live)
- `GET /scan` — live and recent signals with `confidence` float.
- `GET /journal` — realised trades with entry/exit/PnL.
- `GET /regime/{symbol}` — regime label per symbol at signal time.
- `GET /risk-gate` — pass/fail state.
- Notion `Signal Log` DB (`ed9457ff-78f7-4008-bc28-ef3046506039`) — persisted signal history.
- Notion `Trade Journal` DB (`1430e3fb-d21b-49e7-b260-9dfa4adcb5f0`) — persisted outcomes.

### 6.2 Current status (as of 2026-04-17)
Engine is **offline** — VPS (COI-40) not yet provisioned. Dashboard is serving mock-data fallback. Baseline numbers in Section 7 are therefore placeholders pending the first post-deployment run.

---

## 7. Baseline Snapshot — 2026-04-17

**Data available:** None from the live engine. This section is a placeholder intentionally left with empty cells; it will be populated by the first post-VPS run (see Section 8).

### 7.1 C1 — Confluence Score

| Bucket | Count | Hit-rate | Mean R | Profit Factor | ECE bin |
|--------|------:|---------:|-------:|--------------:|--------:|
| [40, 55) |  —  | — | — | — | — |
| [55, 70) |  —  | — | — | — | — |
| [70, 85) |  —  | — | — | — | — |
| [85, 100] | — | — | — | — | — |

### 7.2 C2 — ML Model Probability

| Bucket | Count | Hit-rate | Brier | Mean R | PF |
|--------|------:|---------:|------:|-------:|---:|
| [0.55, 0.60) | — | — | — | — | — |
| [0.60, 0.70) | — | — | — | — | — |
| [0.70, 0.80) | — | — | — | — | — |
| [0.80, 0.90) | — | — | — | — | — |
| [0.90, 1.00] | — | — | — | — | — |

**Aggregate:** Brier — / ECE — / MCE — / AUC —.

### 7.3 C3 — Regime-Conditioned

| Regime | Count | Mean C2 | Hit-rate | AUC | Notes |
|--------|------:|--------:|---------:|----:|------:|
| Trending       | — | — | — | — | — |
| Mean-Reverting | — | — | — | — | — |
| Volatile       | — | — | — | — | — |
| Quiet          | — | — | — | — | — |

### 7.4 C4 — Risk-Gated Final

| Metric | Value |
|---|---|
| Signals with C2 ≥ 0.55 | — |
| Signals reaching /position-size | — |
| Attrition rate | — |
| Top reason code | — |
| ECE after gating | — |
| AUC after gating | — |

---

## 8. Re-Run Procedure (post-VPS-live)

Run the following once COI-40 is resolved and the engine endpoints return real data:

1. **Health check:** `bash scripts/health_check.sh http://<VPS_IP>:8001` → all 6 endpoints UP.
2. **Pull window:** last 14 days of `/journal` + matched `/scan` signals, joined on `trade_id` ↔ `signal_id`.
3. **Regime join:** for each signal, fetch historical regime label (regime state at signal time, not at current time).
4. **Compute:** run `scripts/confidence_baseline.py` (to be added in a follow-up task — see Section 10) which outputs Section 7 tables as CSV + Markdown.
5. **Compare to Section 5 thresholds:** mark each cell PASS/FAIL/INSUFFICIENT_DATA.
6. **Commit results:** append to this doc as Section 7.N with a date-stamped snapshot. Do not overwrite earlier snapshots.

Cadence: weekly during validation (every Friday UTC+3), plus one run at validation close.

---

## 9. Known Risks & Caveats

- **Sample starvation:** at 5 symbols with conservative thresholds, several buckets (especially [85, 100]) may never reach n ≥ 30 inside 30 days. Report INSUFFICIENT_DATA rather than draw conclusions.
- **Regime instability:** regime labels are model outputs themselves; if the regime detector is miscalibrated, C3 inherits that error. Cross-check against a simple volatility quantile as a sanity regime.
- **Look-ahead bias:** join on regime-at-signal-time, not regime-at-current-time. A common bug.
- **Confluence vs. probability confusion:** C1 is NOT a probability. Do not compare C1 ECE to C2 ECE without explicit min-max rescale and a note.
- **Mock-data contamination:** during any window when the dashboard MOCK-DATA badge was on, exclude signals from that window.
- **Testnet microstructure:** Binance Testnet liquidity and fills do not reproduce mainnet. These baselines describe testnet behavior only.

---

## 10. Follow-up Tasks (to be tracked in Linear)

- `[BUILD] SIGNALS — scripts/confidence_baseline.py runner` — one-shot script that emits Section 7 tables.
- `[OPS] SIGNALS — Weekly confidence baseline run` — recurring Friday job (after VPS live).
- `[DOC] SIGNALS — Reliability-diagram plot generator` — PNGs for the weekly status report.
- `[RESEARCH] SIGNALS — C1 vs. dashboard 0–12 reconciliation` — document the relationship between the 0–100 engine score and the 0–12 dashboard roll-up.

---

## 11. References

- `coinscope_trading_engine/signals/confluence_scorer.py` — C1 source.
- `coinscope_trading_engine/signals/signal_generator.py` — C2 source + weights.
- `coinscopeai-engine-api` skill — endpoint contract.
- `coinscopeai-trading-rules` skill — C4 risk thresholds.
- `coinscopeai-architecture` skill — tech stack + ML model inventory.
- Notion: 08 Engineering & Architecture hub.

---

*This document establishes a measurement contract. It does not, by itself, change anything the engine does.*
