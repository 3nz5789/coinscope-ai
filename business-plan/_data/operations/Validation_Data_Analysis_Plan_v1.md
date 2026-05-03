# CoinScopeAI — Validation Phase Data Analysis Plan v1.0

**Date:** 2026-05-01
**Validation phase window:** 2026-04-10 → 2026-05-09 (T-8 days at time of writing)
**Owner (executor):** Mohammed (Founder)
**Owner (interpreter):** Strategy Chief of Staff (Scoopy)
**Output:** A fully populated **Validation Data Pack** that fills every numeric cell in the Validation Phase Exit Memo template before 2026-05-09.

---

## 0. Purpose

The Validation Phase Exit Memo template has cells that look like this:

> | S1 | Signal precision (rolling 30d) | ≥ baseline | _____ | ☐ |

Today, none of those blank cells are derivable without doing the analysis. This document is the analysis: **for every blank cell, here is the query, the computation, the expected output, and the pass/fail rule.**

This plan also derives the two open numerical thresholds (PCC-OPEN-1: S1 baseline; PCC-OPEN-7: X1 slippage baseline) **from validation data**, not from aspiration.

---

## 1. Data Sources

| Source | What's in it | How to access |
|---|---|---|
| Engine API `/journal` | Trade records with entry rationale, regime, confluence, risk-gate result, sizing input, fill, P&L | `GET http://localhost:8001/journal?since=2026-04-10` |
| Engine API `/performance` | Equity curve, drawdown series, daily P&L | `GET http://localhost:8001/performance?since=2026-04-10` |
| Engine API `/scan` log | Triggered signals (pre-risk-gate) with confluence | Run history of `/scan` calls; archived in PG or logs |
| Engine API `/risk-gate` log | Risk-gate decisions (pass / reject / kill-switch trip) | Logs |
| Engine API `/position-size` log | Sizing decisions with leverage and heat | Logs |
| Engine API `/regime/{symbol}` time series | Regime label per symbol per minute | Logs |
| Engine logs (uptime / latency / errors) | MTBF, MTTR, latency p95/p99 | Wherever logs are stored (Sentry / Grafana / file) |
| Telegram bot delivery log | Message send timestamps | Bot log |
| Dashboard uptime probe | External uptime probe | Status page or external probe |

> **Schema assumption:** I'm assuming `/journal` records have fields `timestamp, symbol, regime, confluence, risk_gate_result, side, leverage, heat, intended_size, intended_price, sl, tp, fill_price, fill_size, status, pnl`. If the actual schema is different, swap in the equivalent fields in the queries below. **Verify schema with one quick `GET /journal?limit=1` before running anything else.**

---

## 2. Step 1 — Pull the Data (Run Today + Re-Run on May 8)

Run this block once on **2026-05-01** (to identify any analysis gaps with 8 days of buffer to fix) and a second time on **2026-05-08** (for the final exit-memo numbers).

```bash
# Save validation pull to a dated directory for reproducibility
DATE=$(date -u +%Y-%m-%dT%H:%MZ)
OUT="/Users/mac/Documents/Claude/Projects/CoinScopeAI/validation_pulls/$DATE"
mkdir -p "$OUT"

# Schema sanity check — run this FIRST and confirm fields match assumptions
curl -s "http://localhost:8001/journal?limit=1" | python3 -m json.tool > "$OUT/_schema_sample.json"

# Validation-window pulls (since validation phase start)
curl -s "http://localhost:8001/journal?since=2026-04-10" > "$OUT/journal.json"
curl -s "http://localhost:8001/performance?since=2026-04-10" > "$OUT/performance.json"
curl -s "http://localhost:8001/scan?since=2026-04-10" > "$OUT/scan_log.json"
curl -s "http://localhost:8001/risk-gate?since=2026-04-10" > "$OUT/risk_gate_log.json"
curl -s "http://localhost:8001/position-size?since=2026-04-10" > "$OUT/position_size_log.json"

# Per-symbol regime time series (loop over the symbols actually traded)
for SYM in BTCUSDT ETHUSDT SOLUSDT; do
  curl -s "http://localhost:8001/regime/$SYM?since=2026-04-10" > "$OUT/regime_$SYM.json"
done

# Quick row counts so we know we got data
echo "Row counts:"
for f in "$OUT"/*.json; do
  echo "  $f: $(python3 -c "import json,sys; d=json.load(open('$f')); print(len(d) if isinstance(d,list) else len(d.get('items',d)))")"
done
```

**Pre-flight check:** before running any analysis, confirm `_schema_sample.json` field names match the assumptions in §1. If they don't, flag and adapt before continuing.

---

## 3. Engine Criteria Analysis

Each row below is a self-contained mini-analysis. Run each, fill the **Output for exit memo** column, and tag pass/fail.

### 3.1 Signal Quality (S)

| ID | Criterion | Query / Computation | Output for exit memo | Pass rule |
|---|---|---|---|---|
| **S0** | LLM not in hot path | `grep -rE "from anthropic\|import anthropic\|claude_client" engine/signal/ engine/risk/` in repo | "PASS" if zero matches in `signal/` or `risk/` paths; "FAIL" otherwise | Binary; PASS required |
| **S1** | Signal precision (paper) rolling 30d | Filter `journal.json` to last 30d, completed trades; compute `precision = (count of pnl > 0) / (count of completed trades)`; bucket by confluence band (≥7, ≥8, ≥9) | Single percentage per confluence band | **PCC-OPEN-1 resolution:** founder picks baseline from the data — recommend ≥55% at confluence ≥7 if data supports |
| **S2** | Confluence distribution | From `scan_log.json`, compute `% of triggered signals where confluence ≥ 65` (the v5-documented minimum) | Single % | ≥80% |
| **S3** | Regime classification stability | For each `regime_$SYM.json`, count regime-flip events; compute `flips_per_4h = total_flips / (validation_hours / 4)`; average across symbols | Single number (avg flips per 4h per symbol) | ≤1.0 |
| **S4** | False-positive risk-gate pass-throughs | Join `risk_gate_log.json` (decision=reject) with `journal.json` (trades placed); count any trades that should have been rejected | Integer | =0 |
| **S5** | Signal latency p95 / p99 | From engine telemetry: latency from `/scan` decision to `/journal` write per signal; compute p95 and p99 over 7d | Two numbers (ms) | p95 ≤500, p99 ≤1500 |

**S1 — PCC-OPEN-1 resolution recipe:**

```python
# Pseudocode
import json
import statistics
journal = json.load(open("journal.json"))
completed = [t for t in journal if t["status"] == "closed" and t["timestamp"] >= "2026-04-10"]
for confluence_min in (7, 8, 9):
    band = [t for t in completed if t["confluence"] >= confluence_min]
    if band:
        precision = sum(1 for t in band if t["pnl"] > 0) / len(band)
        print(f"Confluence ≥ {confluence_min}: n={len(band)}, precision={precision:.1%}")
```

**Decision rule for S1 baseline:**

- If precision at confluence ≥7 is ≥55% over n≥50 trades → set baseline at 55%, mark PCC-OPEN-1 resolved.
- If precision is 50–55% → set baseline at the observed value rounded down to the nearest 5%, with an explicit note in the exit memo.
- If precision is <50% → **do not set a baseline yet.** Flag as a near-miss; this affects the validation decision.

### 3.2 Drawdown Discipline (D)

| ID | Criterion | Query / Computation | Output for exit memo | Pass rule |
|---|---|---|---|---|
| D1 | Max drawdown | From `performance.json`, compute peak-to-trough on the equity curve | Single % | ≤10% |
| D2 | Daily loss days >5% | From daily P&L (group `journal.json` by day, sum `pnl`), count days with `pct_loss > 5%` | Integer | =0 |
| **D3** | Leverage cap (10x) | From `position_size_log.json`, count entries where `effective_leverage > 10` | Integer | =0 |
| D4 | Concurrent positions >3 | Walk `journal.json` chronologically, maintain open-position count, count any window where it exceeded 3 | Integer | =0 |
| D5 | Position heat >80% at entry | From `position_size_log.json`, count entries where `heat_at_entry > 0.80` | Integer | =0 |
| D6 | DD recovery profile | For each 5%+ intraday drawdown event in `performance.json`, measure trading-days to recover to prior equity high | List of recovery-day counts | Each ≤5 trading days |
| D7 | Kill-switch trip behavior | For each kill-switch trip in `risk_gate_log.json`, verify no new entries occurred in the next cycle | Binary per trip | All trips: PASS |

**D3 — leverage compliance check (post-resolution to 10x):**

```python
sizes = json.load(open("position_size_log.json"))
violations = [s for s in sizes if s.get("effective_leverage", 0) > 10]
print(f"Leverage violations (>10x): {len(violations)}")
for v in violations[:5]:
    print(v)
```

If any violations exist, this is a **D-category breach** and the validation exit decision tree triggers RESTART, not just EXTEND. Resolve immediately.

### 3.3 Execution Integrity (X)

| ID | Criterion | Query / Computation | Output for exit memo | Pass rule |
|---|---|---|---|---|
| **X1** | Slippage p95 | For each filled trade in `journal.json`: `slippage = abs(fill_price - intended_price) / intended_price`; compute p95 on majors only | Single % | **PCC-OPEN-7 resolution:** founder picks baseline from the data — recommend ≤0.10% if supported |
| X2 | Order placement success rate | `success / (success + failed)` from `journal.json` | Single % | ≥99.5% |
| X3 | SL attachment rate | `% of journal entries where sl is non-null at entry time` | Single % | =100% |
| X4 | TP/SL execution policy match | Sample n=20 closed trades; manually audit fill behavior vs. policy | Pass/fail per trade; aggregate | 0 divergences |
| X5 | Position size deviations | Reconcile `position_size_log.json` `intended_size` vs. `journal.json` `submitted_size` | Integer (count of deviations) | =0 |
| X6 | Daily account-state reconciliation | Run daily reconciliation job (engine state vs. exchange account) for each validation day; aggregate unexplained deltas | Sum of unexplained deltas (USD) | <$1 total |

**X1 — PCC-OPEN-7 resolution recipe:**

```python
trades = json.load(open("journal.json"))
filled = [t for t in trades if t["fill_price"] and t["intended_price"]]
slips = [abs(t["fill_price"] - t["intended_price"]) / t["intended_price"] for t in filled]
slips.sort()
p50 = slips[len(slips)//2]
p95 = slips[int(len(slips)*0.95)]
p99 = slips[int(len(slips)*0.99)]
print(f"Slippage: p50={p50:.4%}, p95={p95:.4%}, p99={p99:.4%}, n={len(slips)}")
```

**Decision rule for X1 baseline:**

- If observed p95 ≤0.05% → set baseline at 0.10% with margin.
- If observed p95 is 0.05–0.10% → set baseline at observed p95 + 0.02% buffer.
- If observed p95 >0.10% → **do not set a baseline at the recommended level.** Flag as exceeding industry-typical testnet expectation; investigate root cause before proceeding.

### 3.4 Operations & Reliability (O) — From Logs / Monitoring, Not Engine API

| ID | Criterion | Source | Computation | Pass rule |
|---|---|---|---|---|
| O1 | Engine MTBF | Process supervisor logs / Sentry crash log | Time between unplanned restarts | ≥168h sustained |
| O2 | Engine MTTR | Incident log | Time from incident detection to recovery | ≤30 min |
| O3 | VPS hardened (COI-40 unblocked) | Operational | Binary | Resolved per OPS ticket #1 |
| O4 | Alert coverage on D1–D5, X1–X6 | Alert configuration audit | Binary per criterion | 100% |
| O5 | Alert false-positive rate | Alert log review | `false_positives / total_alerts` | ≤10% |
| O6 | Dashboard uptime | External probe | Uptime % over 30d | ≥99% |
| O7 | Telegram bot delivery | Bot log | `% delivered within 60s of trigger` | ≥99% |

**Note:** O1–O7 are not derivable from the engine API alone. They depend on whether observability stack (Sentry, Grafana per v5) is wired up. If observability is incomplete, that itself is an OPS-category P0 failure that gates G1, even if engine criteria all pass.

### 3.5 Monitoring & Observability (M)

| ID | Criterion | Source | Pass rule |
|---|---|---|---|
| M1 | Real-time KPI dashboard live | Visual inspection of dashboard URL | All engine KPIs visible |
| M2 | Trade journal complete | Sample audit n=50 from `journal.json` for required fields | 50/50 complete |
| M3 | Vendor health panel | Visual inspection | All P1 vendors visible |
| M4 | Logs retained per CP1–CP3 | Log-store config audit | Configured |
| M5 | Audit-grade event log | Log-store config audit | Immutable + timestamped |
| M6 | Cost Meter visible per user | Dashboard inspection | Per-user usage + tier ceiling visible |

---

## 4. Near-Miss Audit (For Exit Memo §4.4)

The exit memo asks for "cases that didn't trip a P0 but came close." This is the early-warning signal.

Run these specific searches:

| Near-miss type | Query | Threshold to flag |
|---|---|---|
| Drawdown approach | From `performance.json`, find any intraday drawdown ≥7% (didn't trip D1's 10%) | List with date, magnitude, recovery time |
| Daily loss approach | From daily P&L, find any day with loss between 4% and 5% | List with date and magnitude |
| Leverage approach | From `position_size_log.json`, find any entry with `effective_leverage` between 8x and 10x | Count + list of top 5 |
| Heat approach | From `position_size_log.json`, find any entry with `heat_at_entry` between 0.70 and 0.80 | Count + list of top 5 |
| Concurrent-positions approach | Find any window with exactly 3 open positions (the cap) | Count + total time at cap |
| Slippage approach | Find any individual trade with slippage between 0.05% and 0.10% | Count |
| Kill-switch trip events | Every kill-switch trip in the validation window | Full list with trigger, response time |

**Rule:** any near-miss that has occurred more than 3 times needs to be discussed in §4.4 of the exit memo, even if no P0 was breached. Patterns matter more than single events.

---

## 5. Surprise / Anomaly Audit (For Exit Memo §4.2 and §4.3)

Run these to surface anything we didn't anticipate:

| Audit | Query |
|---|---|
| Regime distribution actually observed | Count time spent in each regime per symbol; compare to designed expected distribution. Anything dramatically different from design is worth a paragraph in §4.3. |
| Symbol distribution of trades | Count trades per symbol. If one symbol generated >50% of trades, surface in §4.3. |
| Hour-of-day distribution | Count trades by hour-UTC. If concentration in low-liquidity hours, flag. |
| Confluence-score distribution | Histogram of confluence scores. If actual distribution skews very different from design (e.g., almost all signals at minimum confluence), flag. |
| LLM call rate | If S0 verifies LLM is not in hot path, but logs show high LLM call volume, where? Narrative-only? Verify. |
| Vendor health correlation | Any 30-min window where a vendor was degraded — did engine behavior match documented degraded-mode policy? |
| Time-skew events | Any NTP skew incidents on the VPS? These can cause silent signed-request failures. |

---

## 6. Validation Data Pack — Output Format

Aggregate everything above into a single `validation_data_pack_2026-05-08.md` with this structure:

```
# Validation Data Pack — 2026-05-08

## A. Engine Criteria Numerics
- S1 precision @ confluence ≥7: __% (n=__)
- S1 precision @ confluence ≥8: __% (n=__)
- D1 max drawdown observed: __%
- D2 days exceeding 5% loss: __
- D3 leverage violations: __
- D4 concurrent-position windows >3: __
- D5 heat violations: __
- D6 worst recovery time: __ trading days
- X1 slippage p95: __% (majors only, n=__)
- X2 order placement success: __%
- X3 SL attachment rate: __%
- ...

## B. Resolved Open Items
- PCC-OPEN-1 (S1 baseline): __% at confluence ≥7
- PCC-OPEN-7 (X1 slippage baseline): __%

## C. Near-Misses
[List from §4 of this plan]

## D. Surprises
[List from §5 of this plan]

## E. Operational Metrics (External Sources)
- O1 MTBF: __h
- O2 MTTR: __ min
- O6 dashboard uptime: __%
- ...

## F. Schema Assumptions Verified
[Confirm or flag any field-name divergence found in the schema sanity check]

## G. Reproducibility
- Pull date: 2026-05-08T__Z
- Pull script SHA: __
- Validation window: 2026-04-10 to 2026-05-08
- Engine version at end of phase: __
```

This data pack is then **attached to the Validation Phase Exit Memo as Appendix A**. Every numeric in the exit memo cites a row from this pack.

---

## 7. Run Cadence

| Date | Action |
|---|---|
| **2026-05-01 (today)** | First pull. Run §2 + the schema sanity check. Run §3 against current data. Identify any analysis gaps or schema mismatches. **Flag any P0 violation already present** (D-category breach today = RESTART trigger; finding it now is a 7-day head start). |
| 2026-05-04 | Mid-phase check. Re-run §3 D-category. Confirm trajectory of S1 (precision is improving, flat, or degrading). |
| 2026-05-07 | Penultimate run. Re-run all of §3, §4, §5. Begin filling the data pack. |
| **2026-05-08 (T-1)** | Final pull. Run §2 with end-of-phase data. Complete the data pack. Founder reviews. |
| **2026-05-09** | Validation phase ends. Open the Validation Phase Exit Memo template. Cells fill from the data pack. Decision is mechanical. |

---

## 8. What to Do If Numbers Fail

The exit memo decision tree is pre-committed. If a P0 fails:

| Failure pattern | Decision | Action |
|---|---|---|
| Single P0 fails by a small margin (e.g., D1 = 10.3%, threshold 10%) | EXTEND | 30-day extension; targeted fix; re-evaluate. |
| Multiple P0 fail | RESTART | Engine review before any further work. |
| **D-category breach** | RESTART minimum, KILL if multiple | This is the explicit "engine doesn't honor its policy" failure; non-negotiable. |
| Kill-switch failure during validation | KILL | Full engine review. |
| S0 fails (LLM in hot path) | RESTART minimum | Architectural violation; remove LLM from path before restart. |

**Do not, under any circumstance, retroactively relax a P0 threshold to convert a fail into a pass.** The threshold pre-commitment is the entire point of the exercise.

---

## 9. What This Plan Does Not Do

- It does not derive product-layer criteria (CL, CP, T, B, US). Those are gating G1, not the validation exit; they need separate analysis.
- It does not derive most operational criteria (O1–O7) from the engine API alone — they require observability stack data.
- It does not run the actual queries — that's the founder's execution. This plan is the runbook.
- It does not interpret marginal numbers. If S1 precision is exactly at the threshold, that's a founder-and-reviewer judgment call, not a mechanical decision.

---

## 10. Open Questions for Founder Before Running

1. **Schema confirmation.** Run the `_schema_sample.json` step in §2 first; flag if field names in §1's assumption diverge.
2. **Symbols traded during validation.** The pull script in §2 loops over `BTCUSDT, ETHUSDT, SOLUSDT`. Confirm the actual symbol list.
3. **Where are uptime / latency / Sentry / Grafana logs?** §3.4 needs a data source; if observability isn't wired yet, that's an O-category gap independent of engine criteria.
4. **Has any kill-switch trip occurred in validation so far?** A "yes" forces a careful audit of D7 even if no P0 numerics fail.
5. **Engine version stability.** Was the engine version held constant across the 30-day phase, or did material changes happen mid-phase? If yes, the validation window may need to be split.
