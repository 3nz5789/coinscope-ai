> **ARCHIVED 2026-05-01.** Superseded by **Production_Candidate_Criteria_v2** (now in `_data/operations/`). v2 explicitly resolves leverage cap to 10x and defines the §8 gate as Section 8 of the document. Retained for historical traceability.

---

# CoinScopeAI — Production Candidate Criteria v1.0

**Date:** 2026-05-01
**Status:** Draft for Founder Review
**Owner:** Mohammed (Founder)
**Reviewers:** Strategy Chief of Staff (Scoopy), External Risk Reviewer (TBD)
**Gates:** Real-Capital Unlock | Closed Beta Onboarding | First Paid Tier

---

## 1. Purpose

This document defines what "production-ready" means for CoinScopeAI. It exists for one reason: to make sure the real-capital gate is unlocked on **evidence**, not on **enthusiasm or schedule pressure.**

It is the gate-keeper for three distinct decisions:

| Gate | What it controls | Approver |
|---|---|---|
| **G1 — Closed Beta** | Letting paper-trading users onto the dashboard. | Founder. |
| **G2 — Real Capital, Phase 1 (Capped)** | Switching the first live capital allocation on, capped at a hard ceiling. | Founder + External Risk Reviewer. |
| **G3 — Real Capital, Phase 2 (Scaled)** | Removing the capital cap and scaling toward documented limits. | Founder + External Risk Reviewer + 90 days of clean Phase 1 telemetry. |

**Default state of every gate is LOCKED.** A gate stays locked until **all** mandatory criteria below pass. There is no "soft pass" or "trending toward pass."

---

## 2. How the Gate Works

### 2.1 Decision rule
- **All P0 criteria must pass** for the gate to unlock.
- **All P1 criteria must pass** for the gate to unlock.
- **P2 criteria** are tracked but do not block the gate — they roll into the next review.
- **Any single P0 failure** = automatic re-lock and a 14-day cooling-off period before re-evaluation.

### 2.2 Verification rule
Every criterion has:
- A **threshold** (binary or numeric — never "looks ok").
- A **verification method** (the procedure to prove it).
- A **source of truth** (the system or doc it reads from).
- An **owner** (the person accountable).

Anything that can't be expressed this way is not a criterion — it's a feeling, and feelings don't unlock gates.

### 2.3 Sign-off rule
- G1: Founder sign-off + criteria pass log committed to the repo.
- G2: Founder + External Risk Reviewer sign-off + signed risk attestation.
- G3: Founder + External Risk Reviewer + ≥90 calendar days of Phase 1 telemetry under live capital with **zero P0 violations**.

### 2.4 Re-lock rule
The gate **automatically re-locks** if, at any point post-unlock:
- A P0 criterion regresses below threshold.
- The kill switch trips for a non-test reason.
- A vendor outage longer than the documented tolerance occurs without successful failover.

A re-lock requires re-passing the entire P0 set before re-unlocking.

---

## 3. Criteria

Criteria are grouped by category. Each category has a category-level summary plus the line-item table.

### 3.1 Signal Quality (S)

The engine must demonstrate that its signals behave like the policy says they do — not better, not worse, just consistent. Aspirational performance is not a criterion; **discipline** is.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| S1 | Signal precision (paper) over rolling 30 days | ≥ baseline target (TBD; documented and frozen before unlock — recommend ≥55% for confluence ≥7) | Compute from `/journal` over 30d window | Engine journal | Founder | P0 | G1, G2 |
| S2 | Confluence score distribution matches design | ≥80% of triggered signals have confluence ≥ documented minimum | Histogram from `/scan` log | Engine logs | Founder | P0 | G2 |
| S3 | Regime classification stability | No more than 1 regime flip per 4-hour window per symbol on average | `/regime/{symbol}` time series | Engine logs | Founder | P1 | G2 |
| S4 | False-positive risk-gate pass-throughs | 0 trades placed where `/risk-gate` should have rejected | Reconcile `/risk-gate` log vs. journal | Engine logs | Founder | P0 | G1, G2 |
| S5 | Signal latency (decision to journal write) | p95 ≤ 500ms; p99 ≤ 1500ms | Latency probe over 7d | Engine telemetry | Founder | P1 | G2 |

**S0 hard rule:** Any LLM call in a signal-generation hot path that can change risk behavior = automatic G2 fail until removed.

### 3.2 Drawdown Discipline (D)

The risk thresholds in the project rules (max DD 10%, daily loss 5%, max leverage 20x, max 3 open positions, position heat cap 80%) are **promises**, not aspirations. They must be observed in practice, not just enforced in code.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| D1 | Max drawdown observed in validation | ≤ 10% of starting equity | `/performance` curve | Engine | Founder | P0 | G1, G2 |
| D2 | Daily loss limit observed | 0 days exceeding 5% net loss | Daily P&L from journal | Engine | Founder | P0 | G1, G2 |
| D3 | Leverage cap observed | 0 trades placed with effective leverage >20x | `/position-size` log vs. trade record | Engine | Founder | P0 | G1, G2 |
| D4 | Concurrent positions cap | 0 windows with >3 open positions | Journal snapshots | Engine | Founder | P0 | G1, G2 |
| D5 | Position heat cap | 0 trades with heat score >80% at entry | `/position-size` log | Engine | Founder | P0 | G1, G2 |
| D6 | Drawdown recovery profile | Time-to-recover from any 5% intraday drawdown ≤ 5 trading days | Performance curve | Engine | Founder | P1 | G2 |
| D7 | Kill-switch trip behavior | All trips correctly halted new entries within 1 cycle | Test in staging + audit live trips | Staging + journal | Founder | P0 | G1, G2 |

**D0 hard rule:** A single observed breach of D1–D5 in live capital = immediate re-lock + capital withdraw + post-mortem before any further trading.

### 3.3 Execution Integrity (X)

What the engine intends and what the exchange records must match. Slippage, partial fills, and order-type behavior are all in scope here.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| X1 | Slippage vs. expected | p95 slippage ≤ 0.10% on Binance Futures USDT-M majors | Compare intended vs. filled price in journal | Engine + exchange | Founder | P0 | G2 |
| X2 | Order placement success rate | ≥99.5% over 30d | Order log vs. exchange ack | Engine | Founder | P0 | G2 |
| X3 | Stop-loss attachment rate | 100% — no entries land without attached SL | Order audit | Engine | Founder | P0 | G1, G2 |
| X4 | Take-profit and SL execution match policy | 0 cases of TP/SL behavior diverging from policy | Trade-by-trade audit (sample n=50/wk) | Journal + exchange | Founder | P1 | G2 |
| X5 | Position size matches `/position-size` output | 0 deviations between requested and submitted size | Reconcile API outputs vs. orders | Engine + exchange | Founder | P0 | G2 |
| X6 | Reconciliation: account state vs. engine view | Daily reconcile, 0 unexplained deltas >$1 | Daily recon job | Engine + exchange | Founder | P0 | G2 |

### 3.4 Operations & Reliability (O)

Capital preservation requires operational reliability, not just risk math. A system that drops out during a Volatile regime with three open positions can violate D1–D5 by inaction alone.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| O1 | Engine MTBF (validation phase) | ≥168h (7 days) sustained without crash | Uptime probe | Monitoring | Founder | P0 | G2 |
| O2 | Engine MTTR | ≤30 minutes for any unplanned outage | Incident log | Incident records | Founder | P0 | G2 |
| O3 | VPS deployment hardened | COI-40 unblocked + monitored + auto-restart on crash | Smoke test + monitoring | VPS | Founder | P0 | G1, G2 |
| O4 | Alert coverage | 100% of P0 risk thresholds (D1–D5, X1–X6) have alerts wired to founder | Alert audit | Alerting platform | Founder | P0 | G1, G2 |
| O5 | Alert fatigue check | False-positive alert rate ≤10% over 7d | Alert log review | Alerting | Founder | P1 | G2 |
| O6 | Dashboard uptime | ≥99% over 30d | External probe | Status page | Founder | P1 | G1, G2 |
| O7 | Telegram bot delivery | ≥99% message delivery within 60s of trigger | Probe | Bot logs | Founder | P1 | G1, G2 |

### 3.5 Monitoring & Observability (M)

Anything that isn't observable is, in operational terms, broken.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| M1 | Real-time KPI dashboard live | All validation KPIs (signal precision, drawdown, regime mix, latency, kill-switch trips) visible | Dashboard URL + screenshot | Dashboard | Founder | P0 | G1, G2 |
| M2 | Trade journal complete | 100% of trades have entry rationale, regime, confluence, risk-gate result, sizing input, fill, P&L | Sample audit n=50 | Journal | Founder | P0 | G1, G2 |
| M3 | Vendor health visible | CoinGlass, Tradefeeds, CoinGecko, Binance API status visible on a single panel | Visual check | Dashboard | Founder | P0 | G2 |
| M4 | Logs retained ≥90 days | Any minute in last 90d is reconstructible | Sample retrieval | Log store | Founder | P1 | G2 |
| M5 | Audit-grade event log | Every order, gate decision, kill-switch trip is timestamped + immutable | Sample audit | Log store | Founder | P0 | G2 |

### 3.6 Rollback & Failure Handling (R)

A production candidate must be able to fail safely. Capital preservation in failure mode means **stopping**, not "trying harder."

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| R1 | Kill switch — manual | Founder can halt all new entries within 60s from any device | Drill | Operations | Founder | P0 | G1, G2 |
| R2 | Kill switch — automatic on threshold breach | Trips automatically on D1–D5 violation; halts new entries within 1 cycle | Staged test | Staging | Founder | P0 | G1, G2 |
| R3 | Position-close playbook | Documented procedure for orderly close of all open positions, ≤15 minutes | Drill | Runbook | Founder | P0 | G2 |
| R4 | Vendor failure tolerance | For each P1 vendor, documented behavior when it goes dark; degraded mode does not violate D1–D5 | Vendor failure mapping doc | Ops | Founder | P0 | G2 |
| R5 | Code rollback | Any deployed engine version is rollback-able to the prior version in ≤10 minutes | Drill | Deployment | Founder | P1 | G2 |
| R6 | Catastrophic stop | If three independent monitoring channels disagree, engine halts new entries automatically | Test | Engine | Founder | P1 | G2 |

### 3.7 Legal & Disclosure (L)

No user — paid or beta — touches the dashboard before these are in place. This is non-negotiable and applies to G1, not just G2.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| L1 | Terms of Service in force | Counsel-reviewed; user must accept before access | Click-through audit | Onboarding flow | Founder + Counsel | P0 | G1, G2 |
| L2 | Risk Disclosure document in force | Counsel-reviewed; explicit on testnet status, capital loss risk, no guaranteed performance | Click-through audit | Onboarding flow | Founder + Counsel | P0 | G1, G2 |
| L3 | Privacy Policy in force | Counsel-reviewed; reflects actual data flows | Audit | Onboarding flow | Founder + Counsel | P0 | G1, G2 |
| L4 | No-investment-advice posture documented | Internal red/yellow/green memo; brand and content checked against it | Memo + brand checklist | Legal memo | Counsel | P0 | G1, G2 |
| L5 | Entity & banking in place | Operating entity exists in a viable jurisdiction; banking active | Entity docs | Legal | Founder + Counsel | P0 | G2 |
| L6 | Jurisdictional gating | Onboarding blocks users from prohibited jurisdictions per L4 memo | Test cases | Onboarding flow | Founder | P1 | G2 |

### 3.8 Capital Cap & Phased Ramp (C)

Real capital is introduced in a deliberately small, capped, observable first phase. This is the single most important defense against the temptation to "just turn it on."

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| C1 | Phase 1 capital cap | Hard ceiling: ≤$5,000 USD-equivalent across all positions, founder funds only | Engine config | Engine + exchange | Founder + Risk Reviewer | P0 | G2 |
| C2 | Phase 1 user scope | Founder only. No external user funds. | Onboarding flow + engine config | Engine | Founder | P0 | G2 |
| C3 | Phase 1 duration | ≥90 calendar days under live conditions before any G3 evaluation | Calendar | — | Founder | P0 | G3 |
| C4 | Phase 1 telemetry expectation | All criteria above remain green for full 90d | Daily review | KPI dashboard | Founder | P0 | G3 |
| C5 | External user funds | Never accepted in any phase under current product scope (Intelligence/Co-pilot only). Managed-tier requires its own document and licensure path. | Policy doc | Legal + Brand | Founder + Counsel | P0 | All |
| C6 | Capital scale-up rule | After G3, capital may scale only by ≤2x per 30d, with re-pass of the full criteria set at each step. | Policy doc | — | Founder | P1 | G3+ |

### 3.9 Independent Review (I)

A founder-only sign-off is not sufficient for G2. The risk of self-deception is too high.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gate |
|---|---|---|---|---|---|---|---|
| I1 | External code review of risk path | Independent reviewer signs off on risk-gate, kill-switch, and position-sizing code | Signed review | Review doc | External Reviewer | P0 | G2 |
| I2 | External validation report review | Independent reviewer signs off on validation phase telemetry and conclusions | Signed review | Review doc | External Reviewer | P0 | G2 |
| I3 | Annual re-attestation | Full criteria re-passed annually | Calendar | Review log | Founder + Reviewer | P1 | Post-G3 |

---

## 4. The Validation-Phase Exit Decision Tree

Used at the end of the 30-day validation phase (~2026-05-09). Decided **before** the phase ends, not after.

```
End of validation phase
        │
        ├── All G1 P0 criteria pass + ≥80% P1 pass
        │       └── PASS → unlock G1 (closed paper-trading beta)
        │
        ├── G1 P0 partial pass (≥1 P0 fails)
        │       └── EXTEND validation phase by 30 days; address failed criteria; re-evaluate
        │
        ├── ≥2 P0 fail OR D-category breach observed
        │       └── RESTART validation phase from scratch + post-mortem on engine
        │
        └── Multiple D-category breaches OR kill-switch failure
                └── KILL — full engine review before any further work
```

The G2 gate is **never** evaluated at the end of the validation phase. G2 evaluation happens only after a clean closed-beta period (recommend ≥60 days under G1).

---

## 5. Things This Document Does Not Do

To prevent scope creep:

- It does not prove the engine will be **profitable.** Profit is not a P0 criterion. Discipline is.
- It does not certify any specific trading strategy. It certifies that the system **behaves as documented** under live conditions.
- It does not replace legal, regulatory, or licensure obligations. Those live in their own workstream.
- It does not authorize external user funds under any scenario.

---

## 6. Open Items / Decisions Needed Before This Document Is Final

Each of these blocks finalization. Track them as separate tasks.

| # | Open item | Owner | Resolves which criteria |
|---|---|---|---|
| O-1 | Set the numeric value for S1 (signal precision baseline) | Founder | S1 |
| O-2 | Identify and contract the External Risk Reviewer | Founder | I1, I2, G2 sign-off |
| O-3 | Confirm the Phase 1 capital cap (recommend $5k) | Founder | C1 |
| O-4 | Confirm the Phase 1 duration (recommend ≥90d) | Founder | C3 |
| O-5 | Counsel review of L1–L4 drafts | Counsel | L1–L4 |
| O-6 | Vendor failure-mode mapping completed | Founder | R4 |
| O-7 | Slippage baseline (X1) determined from validation data | Founder | X1 |
| O-8 | Decide whether C5 (external user funds) is permanent or revisitable | Founder | C5 |

---

## 7. Review Cadence

- **During validation:** weekly criteria review, founder-only.
- **Post G1 unlock:** weekly criteria review, with one external reviewer call per month.
- **Post G2 unlock:** daily P0 criteria check (automated), weekly review, monthly external reviewer call.
- **Annually:** full re-attestation against the criteria set.

---

## 8. Change Control

This document is the gate. Changes to it require:
- A written rationale.
- Founder sign-off.
- For G2/G3-impacting changes: External Risk Reviewer sign-off.
- A versioned revision; the prior version remains in the repo.

A loosening of any P0 criterion automatically re-locks the corresponding gate until the new threshold is independently validated.

---

## 9. Acceptance for v1 of This Document

- [ ] All open items in §6 have a resolution path.
- [ ] Founder has reviewed and signed off on every P0 threshold.
- [ ] External Risk Reviewer is identified.
- [ ] Document committed to repo at `docs/Production_Candidate_Criteria.md` and referenced from CLAUDE.md.
- [ ] Each criterion has a verification probe or query mapped (engine endpoint, log query, manual procedure).
