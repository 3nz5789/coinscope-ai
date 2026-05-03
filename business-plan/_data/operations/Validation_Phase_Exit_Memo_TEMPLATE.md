# Validation Phase Exit Memo — TEMPLATE

> **Use this template at validation phase end (~2026-05-09).** Fill in every section. Do not delete sections that "don't apply" — write "N/A" with a reason. The decision at the end binds; rewriting after the fact defeats the point of pre-committed criteria.

---

## 0. Header

| Field | Value |
|---|---|
| Validation phase start | 2026-04-10 |
| Validation phase end | 2026-05-09 |
| Memo author | Mohammed (Founder) |
| Memo date | YYYY-MM-DD |
| Reviewers | Strategy Chief of Staff (Scoopy); External Risk Reviewer (TBD) |
| Decision (one of: PASS / EXTEND / RESTART / KILL) | _____________ |
| Next gate evaluated | G1 (Closed Beta) only — G2 not evaluated at this point |

---

## 1. Executive Summary (≤200 words)

> Plain-language summary: what happened in the 30 days, did the engine behave as the policy says it should, and what is the recommendation. Lead with the decision, not the narrative.

```
[Decision: PASS / EXTEND / RESTART / KILL]

[2–3 sentences on why, in language a non-technical reader can verify.]

[1 sentence on what unlocks next, or what remains locked.]
```

---

## 2. Validation Phase Scope (what was actually run)

| Field | Value |
|---|---|
| Engine version(s) deployed | |
| Network | Binance Futures Testnet (USDT-M) |
| Symbols traded | |
| Calendar days live | |
| Engine uptime (% of calendar days) | |
| Total signals generated | |
| Total trades placed (paper) | |
| Total kill-switch trips | |

**Material configuration changes during phase** (list each, with date and rationale):
- [ ] None
- [ ] Yes — list:

---

## 3. Production Candidate Criteria Scorecard

> Reference: `docs/Production_Candidate_Criteria.md`. Score every criterion. The decision rule is: **all P0 must pass**, all P1 must pass for the gate evaluated. Any single P0 failure = EXTEND or worse.

### 3.1 Signal Quality (S)
| ID | Criterion | Threshold | Observed | Pass? | Notes |
|---|---|---|---|---|---|
| S0 | LLM not in hot path | binary | | ☐ | |
| S1 | Signal precision (rolling 30d) | ≥ baseline | | ☐ | |
| S2 | Confluence distribution | ≥80% of signals at confluence ≥ min | | ☐ | |
| S3 | Regime stability | ≤1 flip / 4h / symbol avg | | ☐ | |
| S4 | False-positive risk-gate pass-throughs | 0 | | ☐ | |
| S5 | Signal latency p95/p99 | ≤500/1500ms | | ☐ | |

### 3.2 Drawdown Discipline (D)
| ID | Criterion | Threshold | Observed | Pass? | Notes |
|---|---|---|---|---|---|
| D1 | Max drawdown | ≤10% | | ☐ | |
| D2 | Daily loss days | 0 days >5% | | ☐ | |
| D3 | Leverage cap | 0 trades >10x | | ☐ | |
| D4 | Concurrent positions | 0 windows >5 | | ☐ | |
| D5 | Position heat | 0 trades >80% at entry | | ☐ | |
| D6 | DD recovery | ≤5 trading days from any 5% intraday | | ☐ | |
| D7 | Kill-switch trip behavior | All trips halted entries within 1 cycle | | ☐ | |

### 3.3 Execution Integrity (X) — informational at G1; binding at G2
| ID | Criterion | Observed | Pass? | Notes |
|---|---|---|---|---|
| X1–X6 | (per criteria doc) | | ☐ | |

### 3.4 Operations & Reliability (O)
| ID | Criterion | Threshold | Observed | Pass? | Notes |
|---|---|---|---|---|---|
| O1 | MTBF | ≥168h | | ☐ | |
| O2 | MTTR | ≤30 min | | ☐ | |
| O3 | VPS hardened | binary | | ☐ | |
| O4 | Alert coverage | 100% of D1–D5, X1–X6 | | ☐ | |
| O5 | Alert false-positive rate | ≤10% | | ☐ | |
| O6 | Dashboard uptime | ≥99% | | ☐ | |
| O7 | Telegram delivery | ≥99% within 60s | | ☐ | |

### 3.5 Monitoring & Observability (M)
| ID | Pass? | Notes |
|---|---|---|
| M1 KPI dashboard | ☐ | |
| M2 Trade journal complete | ☐ | |
| M3 Vendor health panel | ☐ | |
| M4 Logs ≥90 days | ☐ | |
| M5 Audit-grade event log | ☐ | |

### 3.6 Rollback & Failure (R)
| ID | Pass? | Notes |
|---|---|---|
| R1 Manual kill switch | ☐ | |
| R2 Auto kill switch | ☐ | |
| R3 Position-close playbook | ☐ | |
| R4 Vendor failure tolerance | ☐ | |
| R5 Code rollback ≤10min | ☐ | |
| R6 Catastrophic stop | ☐ | |

### 3.7 Legal (L) — gating
| ID | Pass? | Notes |
|---|---|---|
| L1 ToS | ☐ | |
| L2 Risk Disclosure | ☐ | |
| L3 Privacy Policy | ☐ | |
| L4 No-advice memo | ☐ | |

### 3.8 Aggregate
- Total P0 criteria evaluated: ___
- P0 pass: ___ / ___
- P1 pass: ___ / ___
- **Any single P0 failure?** ☐ Yes ☐ No

---

## 4. Material Findings

### 4.1 What worked as documented
> List the policies the engine actually honored. Be specific — cite criterion IDs and observed numbers.

### 4.2 Surprises (positive)
> Things that were better than the documented baseline. Note: these are not reasons to relax criteria. They are evidence of margin.

### 4.3 Surprises (negative)
> Things that fell short of the baseline OR weren't visible until live. Each item should answer: how did we miss this in design?

### 4.4 Near-misses
> Cases that didn't trip a P0 but came close. These are the early warnings; treat them seriously.

---

## 5. Incidents (if any)

For each incident during the phase, fill one block:

```
Incident #: [ID]
Date / time:
Detection signal:
Severity (P0/P1/P2):
Duration:
Customer (paper users) impact:
Root cause:
Fix:
Permanent prevention:
Re-occurrence risk:
```

If zero incidents, write: "Zero incidents recorded. Verified by reviewing the alert log and the journal for the full validation window."

---

## 6. Vendor Behavior Summary

Per vendor, one line:

| Vendor | Outage events | Total downtime | Within tolerance? | Notes |
|---|---|---|---|---|
| Binance Futures (testnet) | | | ☐ | |
| CCXT | | | ☐ | |
| CoinGlass | | | ☐ | |
| Tradefeeds | | | ☐ | |
| CoinGecko | | | ☐ | |
| Anthropic Claude | | | ☐ | |

---

## 7. Decision

> Pre-committed decision rule (Production Candidate Criteria §10):
>
> - **All G1 P0 pass + ≥80% P1 pass** → **PASS** (unlock G1, closed paper-trading beta)
> - **G1 P0 partial pass (≥1 P0 fails)** → **EXTEND** (30-day extension; address failed criteria)
> - **≥2 P0 fail OR D-category breach observed** → **RESTART**
> - **Multiple D-category breaches OR kill-switch failure** → **KILL** (full engine review)

**Decision:** ☐ PASS  ☐ EXTEND  ☐ RESTART  ☐ KILL

**Reasoning (≤150 words):**
```


```

**If EXTEND:** specify the failed criteria, the corrective tasks, and the new end date.
**If RESTART:** specify the engine changes required before restart.
**If KILL:** specify the scope of the engine review.

---

## 8. What Unlocks Next (only if PASS)

| Item | Owner | Target date |
|---|---|---|
| Closed beta cohort recruited | Founder | |
| ToS + Risk Disclosure live | Founder + Counsel | |
| Beta onboarding flow live | Founder | |
| First beta user invited | Founder | |
| First weekly beta review | Founder | |

**G2 evaluation:** Not authorized at this point. G2 evaluation requires ≥60 days of clean closed-beta operation under G1, plus completion of all G2-specific P0 criteria (X1–X6, R3–R6, L5, L6, I1, I2).

---

## 9. What Stays Locked

> Even on PASS, list anything that remains explicitly off the table. This protects against scope creep into "well, since we passed validation..."

- Real-capital trading: **LOCKED** (G2 not evaluated).
- External user funds: **LOCKED** (C5 — never accepted under current product scope).
- Managed/discretionary trading: **LOCKED** (requires separate document and licensure).
- Production claims in marketing: **LOCKED** (we are in closed beta only; no "production" or "live" claims in public copy).

---

## 10. Sign-Offs

| Role | Name | Date | Signature/Commit hash |
|---|---|---|---|
| Founder | Mohammed | | |
| Strategy Chief of Staff | Scoopy | | |
| External Risk Reviewer | TBD | | |

> **G1 unlock requires:** Founder sign-off + commit hash of this memo in the repo.
> **G2 unlock requires:** All three sign-offs above + a separate G2 memo.

---

## 11. Appendix

- A. Full criteria scorecard (raw numbers): link
- B. Trade journal export for the validation window: link
- C. Incident log: link
- D. Alert log: link
- E. Vendor health log: link
- F. Engine version diff (start vs. end of validation): link

---

## 12. Filing instructions

When filled out:
1. Save as `docs/validation_exit_memo_2026-05-09.md` in the repo.
2. Commit with a message containing the decision (e.g., `docs: validation exit memo — DECISION: PASS`).
3. If PASS, open the G1 unlock checklist (separate doc).
4. If EXTEND/RESTART/KILL, update the project state memory file with the new phase end date and the corrective tasks.
5. Notify external reviewer regardless of decision.
