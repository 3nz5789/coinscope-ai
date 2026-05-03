# CoinScopeAI — Production Candidate Criteria v2.0

**Date:** 2026-05-01
**Supersedes:** v1.0 (2026-05-01)
**Status:** Draft for Founder Review (F-7 and F-8 resolved 2026-05-01)
**Triggering change:** Architecture v5 introduced Customer Layer, Compliance rail, Trust rail, Cost Meter, Per-User State, and made the real-capital gate a named structural lock (`§8 gate`).
**Owner:** Mohammed (Founder)

---

## 0. What Changed From v1

| # | Change | Reason |
|---|---|---|
| 1 | Gate model redefined from **3 gates (G1/G2/G3)** to **4 gates (G1/G2/G3/G4)** | v5 separates "subscription product available" from "real-capital trading." These are different unlocks with different criteria. |
| 2 | Five new criteria categories: **CP** (Compliance), **T** (Trust), **CL** (Customer Layer), **B** (Billing), **US** (Per-User State) | v5 added these architectural surfaces; each carries its own correctness obligations. |
| 3 | **Leverage cap resolved to 10x** (was: 20x in project rules; v5 diagram showed 10x at Risk Manager) | Capital-preservation default. Project rules string is stale and must be updated. |
| 4 | **`§8 gate` formally defined as Section 8 of this document (Capital Cap & Phased Ramp)** | Architecture diagram references `§8 gate locked` at Order Manager; this section IS that gate. Document renumbered so §8 = Capital Cap. |
| 5 | Validation phase exit decision tree narrowed: governs **engine criteria only** (S, D, X) | v5 note: "additions sit around the engine, not in it; validation phase rules still apply." Product-layer criteria gate G1+, not the validation exit. |
| 6 | Stripe added to Rollback (R) and Vendor Failure mapping cross-references | v5 puts Stripe LIVE; an outage is now a P0 product event. |
| 7 | Audit log retention (7y trade / 1y auth / 90d req) elevated to a Compliance criterion | v5 Compliance rail commits to this; must be enforced, not aspirational. |
| 8 | LLM-not-in-hot-path moved from a "hard rule" footnote to an explicit S0 criterion + standing CI check | Architecture change risk: any future engine work must re-pass this. |
| 9 | Trust rail snapshot integrity added | "Tamper-evident" is a brand promise that must be technically defensible. |

---

## 1. Purpose

This document defines what "production-ready" means for CoinScopeAI. It is the gate-keeper for four distinct decisions. The default state of every gate is **LOCKED.**

Capital preservation is the prime directive. When v1 said "feels stable enough" never appears as a threshold, that still holds in v2 — just with more surfaces to evaluate.

---

## 2. The Four Gates

| Gate | What it controls | Approver | Tier in architecture |
|---|---|---|---|
| **G1 — Closed Subscription Beta** | 10–20 invited users on the read-only intelligence product. Engine paper-trading only. ToS / Risk Disclosure / Privacy in force. | Founder. | Customer Layer + Engine API + Compliance rail (P1.5 items). |
| **G2 — Public Subscription Availability** | Open signup. Jurisdictional gate live. KYC for Team tier active. Engine still paper-trading. | Founder + External Risk Reviewer. | Adds KYC/AML (P2), Trust rail full publication. |
| **G3 — Real Capital, Phase 1 (`§8 gate` first flip)** | Founder-only real capital, capped. Subscribers continue on paper-trading. | Founder + External Risk Reviewer. | Order Manager `§8 gate` flips with hard capital cap. **Defined in §8 below.** |
| **G4 — Real Capital, Phase 2 (Scaled)** | Capital cap removed; capital scales toward documented limits. | Founder + External Risk Reviewer + ≥90d clean G3 telemetry. | Order Manager `§8 gate` reauthorized at next tier. |

**Decision rules (unchanged from v1):**
- All P0 criteria for a gate must pass for that gate to unlock.
- All P1 criteria for that gate must pass.
- Any single P0 failure = automatic re-lock + 14-day cooling-off.
- Re-lock is automatic on any post-unlock P0 regression, kill-switch trip for non-test reason, or vendor outage exceeding documented tolerance without successful failover.

**Sign-off rules:**
- G1: Founder sign-off + criteria pass log committed to repo.
- G2: Founder + External Risk Reviewer + ≥30d clean G1 telemetry.
- G3: Founder + External Risk Reviewer + signed risk attestation + KYC pipeline active for Team tier.
- G4: All G3 requirements + ≥90d clean G3 telemetry with **zero P0 violations**.

---

## 3. Validation-Phase Exit (Engine-Only)

Per v5: "Phase 1 engine flow is unchanged — additions sit around the engine, not in it, so validation phase rules still apply." So the validation-phase exit decision (≈2026-05-09) is governed by **engine criteria only** (categories S, D, X, plus the engine-side O, M, R items). It does **not** evaluate Customer Layer, Compliance, Trust, Billing, or Per-User State criteria — those gate G1, not the validation exit.

```
End of validation phase (engine criteria only)
        │
        ├── All engine P0 pass + ≥80% engine P1 pass
        │       └── ENGINE PASS → engine is candidate-ready;
        │                          G1 unlock now depends on
        │                          Customer Layer / Compliance / Legal
        │
        ├── Engine P0 partial pass (≥1 P0 fails)
        │       └── EXTEND validation by 30 days
        │
        ├── ≥2 P0 fail OR D-category breach observed
        │       └── RESTART validation
        │
        └── Multiple D-category breaches OR kill-switch failure
                └── KILL — full engine review
```

---

## 4. Engine Criteria (Govern Validation Exit + All Gates)

### 4.1 Signal Quality (S)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| **S0** | LLM not in any signal-generation or risk-gate hot path | binary | Static audit + CI check that fails build if flagged module imports LLM client | Source repo | Founder | P0 | All |
| S1 | Signal precision (paper) over rolling 30 days | ≥ baseline (PCC-OPEN-1; recommend ≥55% for confluence ≥7) | Compute from `/journal` over 30d window | Engine journal | Founder | P0 | G1, G3 |
| S2 | Confluence score distribution matches design | ≥80% of triggered signals have confluence ≥ documented minimum (≥65 per v5) | Histogram from `/scan` log | Engine logs | Founder | P0 | G3 |
| S3 | Regime classification stability | ≤1 regime flip per 4-hour window per symbol on average | `/regime/{symbol}` time series | Engine logs | Founder | P1 | G3 |
| S4 | False-positive risk-gate pass-throughs | 0 trades placed where `/risk-gate` should have rejected | Reconcile `/risk-gate` log vs. journal | Engine logs | Founder | P0 | G1, G3 |
| S5 | Signal latency (decision to journal write) | p95 ≤ 500ms; p99 ≤ 1500ms | Latency probe over 7d | Engine telemetry | Founder | P1 | G3 |

### 4.2 Drawdown Discipline (D)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| D1 | Max drawdown observed in validation | ≤10% of starting equity | `/performance` curve | Engine | Founder | P0 | G1, G3 |
| D2 | Daily loss limit observed | 0 days exceeding 5% net loss | Daily P&L from journal | Engine | Founder | P0 | G1, G3 |
| **D3** | **Leverage cap observed** | **0 trades placed with effective leverage > 10x** | `/position-size` log vs. trade record | Engine | Founder | P0 | G1, G3 |
| D4 | Concurrent positions cap | 0 windows with >3 open positions | Journal snapshots | Engine | Founder | P0 | G1, G3 |
| D5 | Position heat cap | 0 trades with heat score >80% at entry | `/position-size` log | Engine | Founder | P0 | G1, G3 |
| D6 | Drawdown recovery profile | Time-to-recover from any 5% intraday drawdown ≤ 5 trading days | Performance curve | Engine | Founder | P1 | G3 |
| D7 | Kill-switch trip behavior | All trips correctly halted new entries within 1 cycle | Test in staging + audit live trips | Staging + journal | Founder | P0 | G1, G3 |

> **Leverage resolution (2026-05-01):** D3 threshold is **10x system cap**, matching the v5 Risk Manager. The "max leverage 20x" in the prior project rules string is stale and is being phased out. If 20x ever needs to return as a per-tier ceiling for an explicit user segment, it requires a documented Change Control entry, External Risk Reviewer sign-off, and a re-attestation of D3.

### 4.3 Execution Integrity (X)

X1–X6 unchanged from v1; informational at G1, binding at G3.

| ID | Criterion | Threshold | Priority | Gates |
|---|---|---|---|---|
| X1 | Slippage vs. expected | p95 ≤ 0.10% on Binance Futures USDT-M majors | P0 | G3 |
| X2 | Order placement success rate | ≥99.5% over 30d | P0 | G3 |
| X3 | Stop-loss attachment rate | 100% — no entries land without attached SL | P0 | G1, G3 |
| X4 | TP/SL execution matches policy | 0 cases of divergence | P1 | G3 |
| X5 | Position size matches `/position-size` output | 0 deviations | P0 | G3 |
| X6 | Daily account-state reconciliation | 0 unexplained deltas >$1 | P0 | G3 |

---

## 5. Product-Layer Criteria (Gate G1 and Beyond — NEW in v2)

### 5.1 Customer Layer (CL)

The Customer Layer covers signup, identity, ToS acceptance, entitlements, and access. Per v5, the API auth layer **refuses any request without signed ToS** — this is structural, not policy.

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| CL1 | Signed ToS required at API auth | 100% of authenticated requests have a verified ToS-signature timestamp | Auth logs vs. ToS-acceptance log | Auth + ToS store | Founder | P0 | G1, G2, G3 |
| CL2 | Signed Risk Disclosure required at API auth | 100% of authenticated requests have a verified Risk Disclosure acceptance | Auth logs vs. acceptance log | Auth + Disclosure store | Founder | P0 | G1, G2, G3 |
| CL3 | Email verification before access | 100% of accounts verified before first dashboard render | Onboarding logs | Onboarding | Founder | P0 | G1, G2 |
| CL4 | Entitlements enforced at API gate | 0 requests served above the user's entitled tier | Entitlement check log | Engine API | Founder | P0 | G1, G2 |
| CL5 | Per-user API key isolation | 0 cross-user key leakage in audit; key vault access logged | Vault audit | Vault | Founder | P0 | G1, G2, G3 |
| CL6 | Jurisdictional gate at signup (post-counsel) | Accounts from prohibited jurisdictions blocked at signup; **US persons blocked until Phase B counsel sign-off** | Signup logs vs. block list | Onboarding | Founder | P1 | G2 |
| CL7 | Account deletion / data-subject-rights flow | Documented + tested SLA per jurisdiction | Manual drill | Procedure | Founder | P1 | G2 |
| CL8 | Re-acceptance flow on material ToS change | Users re-accept before next request | Versioning audit | Auth | Founder | P1 | G2 |

### 5.2 Compliance (CP)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| CP1 | Audit log retention — trade journal | ≥7 years; tamper-evident | Sample retrieval at 7y boundary (synthetic) | Logs | Founder | P0 | G1, G2, G3 |
| CP2 | Audit log retention — auth events | ≥1 year | Sample retrieval at 1y boundary | Logs | Founder | P0 | G1, G2, G3 |
| CP3 | Audit log retention — request logs | ≥90 days | Sample retrieval at 90d boundary | Logs | Founder | P0 | G1, G2, G3 |
| CP4 | Counsel-reviewed ToS, Privacy, Risk Disclosure in force | All 3 documents committed to repo + click-through wired | Document audit | Onboarding | Founder + Counsel | P0 | G1, G2, G3 |
| CP5 | No-investment-advice memo applied to all marketing copy | Brand checklist run on every published page | Brand audit | Marketing | Founder + Brand | P0 | G1, G2 |
| CP6 | Data-subject-rights operational SLA | Met for first 4 weeks post-G1 | Drill | Procedure | Founder | P1 | G2 |
| CP7 | KYC/AML pipeline live for Team tier | Sumsub or Persona integration; documented vetting flow | Integration test | KYC vendor | Founder | P0 | G2 |
| CP8 | Sub-processor inventory current | All vendors disclosed in Privacy Policy | Audit vs. Vendor Failure-Mode Mapping | Privacy Policy | Founder | P0 | G1, G2, G3 |
| CP9 | Real-capital regulatory analysis (separate counsel memo) | Counsel sign-off on §8 unlock from a regulatory perspective | Memo | Counsel | Founder + Counsel | P0 | G3 |

### 5.3 Trust (T)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| T1 | Snapshot signing key isolated | Signing key in a separate secret store; only the snapshot service can sign | Vault audit | Vault | Founder | P0 | G1 (if dashboard public), G2 |
| T2 | Snapshot integrity verifiable | Any historical snapshot can be cryptographically verified by a third party with the public key | Verification probe | Snapshot store | Founder | P0 | G2 |
| T3 | Snapshot generation is deterministic | Re-running on the same source data produces an identical snapshot | Determinism test | Snapshot service | Founder | P0 | G2 |
| T4 | Snapshot publication includes required disclosures | Per the no-advice memo (CP5) | Page audit | Trust dashboard | Founder + Brand | P0 | G1 (if public), G2 |
| T5 | Methodology page accuracy | Page describes the engine truthfully; reviewed on every engine release | Doc review | Methodology page | Founder | P0 | G1 (if public), G2 |
| T6 | Third-party audit hooks documented | A reviewer can validate engine behavior against the published methodology with the documented interfaces | Doc + drill | Audit doc | Founder | P1 | G2 |
| T7 | Snapshot rollback is impossible without detection | Any retroactive change to a published snapshot must be detectable | Tamper test | Snapshot store | Founder | P0 | G2 |

### 5.4 Billing (B)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| B1 | Stripe webhook delivery handled idempotently | 0 duplicate-charge or duplicate-entitlement events in 30d | Webhook audit | Webhook handler | Founder | P0 | G1, G2 |
| B2 | Subscription state sync (Stripe ↔ Entitlements) | 0 drift between Stripe state and entitlement state in daily reconcile | Daily reconcile job | Reconcile log | Founder | P0 | G1, G2 |
| B3 | Payment-failure handling (dunning) | Documented retry + grace period; user notified | Drill | Billing flow | Founder | P1 | G2 |
| B4 | Refund + cancellation flow | Documented per ToS; first 5 cases drilled | Drill | Billing flow | Founder | P1 | G2 |
| B5 | Tax handling | Stripe Tax (or equivalent) configured for target jurisdictions | Config audit | Stripe | Founder + Counsel | P0 | G2 |
| B6 | Pricing display matches Stripe pricing | 0 drift between marketing site and Stripe live prices | Spot check | Marketing site + Stripe | Founder | P0 | G1, G2 |
| B7 | Webhook signature verification | 100% of webhook calls verified before processing | Code audit | Webhook handler | Founder | P0 | G1, G2 |

### 5.5 Per-User State (US)

| ID | Criterion | Threshold | Verification | Source | Owner | Priority | Gates |
|---|---|---|---|---|---|---|---|
| US1 | Per-user threshold respected | A user cannot exceed their tier's risk thresholds, or system thresholds, whichever is lower | Test cases | Engine + journal | Founder | P0 | G1, G3 |
| US2 | Per-user journal partitioning | A user can only retrieve their own journal entries; tested with synthetic cross-user request | Auth test | Engine API | Founder | P0 | G1, G2, G3 |
| US3 | Per-user key vault encryption | Keys encrypted at rest; no key visible in any log or error trace | Code + log audit | Vault | Founder | P0 | G1, G2, G3 |
| US4 | Per-user portfolio integrity | A user's portfolio config cannot be modified except by them (or admin RBAC) | Test cases | Engine API | Founder | P0 | G2 |
| US5 | Account-deletion data scrubbing | Within SLA, all per-user state purged except retained audit log per CP1–CP3 | Drill | Procedure | Founder | P1 | G2 |

---

## 6. Operational Criteria

### 6.1 Operations & Reliability (O)

| ID | Criterion | Threshold | Priority | Gates |
|---|---|---|---|---|
| O1 | Engine MTBF | ≥168h sustained | P0 | G3 |
| O2 | Engine MTTR | ≤30 min | P0 | G3 |
| O3 | VPS deployment hardened (COI-40 unblocked) | binary | P0 | G1, G3 |
| O4 | Alert coverage on all P0 risk thresholds | 100% of D1–D5, X1–X6 wired | P0 | G1, G3 |
| O5 | Alert false-positive rate | ≤10% over 7d | P1 | G3 |
| O6 | Dashboard uptime | ≥99% over 30d | P1 | G1, G3 |
| O7 | Telegram bot delivery | ≥99% within 60s | P1 | G1, G3 |
| O8 | Per-provider observability (Sentry + Grafana) | All P1 vendors instrumented; dashboards live | P0 | G1 |
| O9 | Multi-Region HA / DR | RTO <15min; RPO <6min — required for G4 only | P0 | G4 |

### 6.2 Monitoring & Observability (M)

| ID | Criterion | Threshold | Priority | Gates |
|---|---|---|---|---|
| M1 | Real-time KPI dashboard live (engine) | All engine KPIs visible | P0 | G1, G3 |
| M2 | Trade journal complete | 100% of trades have entry rationale, regime, confluence, risk-gate result, sizing input, fill, P&L | P0 | G1, G3 |
| M3 | Vendor health panel (incl. Stripe + KYC vendor) | All P1 vendors visible | P0 | G1 |
| M4 | Logs retained per CP1–CP3 | binary | P0 | G1, G3 |
| M5 | Audit-grade event log (immutable, timestamped) | binary | P0 | G3 |
| M6 | Cost Meter visible per user | Per-user API usage + tier ceiling enforcement live | P0 | G1 |
| M7 | Operational metrics dashboard (business KPIs) | Subscribers, churn, support load visible | P1 | G2 |

### 6.3 Rollback & Failure Handling (R)

| ID | Criterion | Threshold | Priority | Gates |
|---|---|---|---|---|
| R1 | Manual kill switch reachable in 60s from any device | binary | P0 | G1, G3 |
| R2 | Auto kill switch on D1–D5 violation | within 1 cycle | P0 | G1, G3 |
| R3 | Position-close playbook | ≤15 min flat | P0 | G3 |
| R4 | Vendor failure tolerance (per Vendor Failure-Mode Mapping) | All P1 vendors have documented degraded mode | P0 | G3 |
| R5 | Code rollback ≤10 min | Drilled | P1 | G3 |
| R6 | Catastrophic stop on monitor disagreement | Within 1 cycle | P1 | G3 |
| R7 | Stripe outage degraded mode | Existing users keep access; signups blocked with explicit message | P0 | G1, G2 |
| R8 | KYC vendor outage degraded mode (Sumsub/Persona) | Team-tier signups queued; existing users unaffected | P0 | G2 |
| R9 | Trust dashboard outage | Public site degrades to a static last-known-good page; no broken signed snapshots served | P1 | G2 |

### 6.4 Legal (L) — Cross-Reference to Compliance Rail

L1–L4 from v1 are subsumed and expanded into **CP4** (counsel-reviewed ToS / Privacy / Risk Disclosure in force) and **CP5** (no-advice memo applied). Entity / banking and jurisdictional gating live under **CL6** and **CP9**.

This is a structural simplification — v5 puts the legal artifacts into the Compliance rail, so the criteria live there too.

### 6.5 Independent Review (I)

| ID | Criterion | Priority | Gates |
|---|---|---|---|
| I1 | External code review of risk path | P0 | G3 |
| I2 | External validation report review | P0 | G3 |
| I3 | Annual re-attestation | P1 | Post-G4 |

---

## 7. Open Items

| # | Open item | Owner | Resolves |
|---|---|---|---|
| **PCC-OPEN-1** | Set the numeric value for S1 (signal precision baseline) | Founder | S1 |
| **PCC-OPEN-2** | Identify and contract the External Risk Reviewer | Founder | I1, I2 |
| **PCC-OPEN-3** | Confirm Phase 1 capital cap (recommend $5k) | Founder | C1 |
| **PCC-OPEN-4** | Confirm Phase 1 duration (recommend ≥90d) | Founder | C3 |
| **PCC-OPEN-5** | Counsel review of CP4 / CP5 documents | Counsel | CP4, CP5 |
| **PCC-OPEN-6** | Vendor failure-mode mapping completed (incl. Stripe + future KYC vendor) | Founder | R4, R7, R8 |
| **PCC-OPEN-7** | Slippage baseline (X1) determined from validation data | Founder | X1 |
| **PCC-OPEN-8** | Decide whether C5 (external user funds) is permanent or revisitable | Founder | C5 |
| ~~PCC-OPEN-9~~ | ~~Resolve leverage cap discrepancy~~ | **RESOLVED 2026-05-01: 10x system cap** | D3 |
| ~~PCC-OPEN-10~~ | ~~Confirm what `§8 gate` refers to~~ | **RESOLVED 2026-05-01: §8 = Capital Cap & Phased Ramp section** | G3 reference |
| **PCC-OPEN-11** | KYC vendor selection (Sumsub or Persona) and integration timeline | Founder | CP7, R8 |
| **PCC-OPEN-12** | Stripe Tax configuration scope (which jurisdictions) | Founder + Counsel | B5 |
| **PCC-OPEN-13** | Trust dashboard public-launch decision (G1 with public Trust, or hold to G2) | Founder + Brand | T1, T4, T5 |
| **PCC-OPEN-14** | Real-capital regulatory analysis trigger (when to commission Phase C counsel work) | Founder | CP9 |

---

## 8. The §8 Gate — Capital Cap & Phased Ramp

This is the section that the v5 architecture diagram references when it marks the Order Manager `§8 gate locked`. **Real capital is locked behind the criteria in this section.**

| ID | Criterion | Threshold | Priority | Gates |
|---|---|---|---|---|
| C1 | Phase 1 capital cap | ≤$5,000 USD-equivalent, founder funds only — **PCC-OPEN-3** | P0 | G3 |
| C2 | Phase 1 user scope | Founder only | P0 | G3 |
| C3 | Phase 1 duration | ≥90 calendar days under live conditions before any G4 evaluation — **PCC-OPEN-4** | P0 | G4 |
| C4 | Phase 1 telemetry | All criteria green for full 90d | P0 | G4 |
| C5 | External user funds | Never — under current product scope (Intelligence/Co-pilot only). Managed-tier requires its own document and licensure path. | P0 | All |
| C6 | Capital scale-up rule | After G3, capital may scale only by ≤2x per 30d, with re-pass of the full criteria set at each step. | P1 | G4+ |

**G3 unlock = §8 gate first flip.** Requires:
- All engine P0 (S, D, X) green for ≥30d post-G1.
- All product-layer P0 (CL, CP, T, B, US) green for ≥30d post-G1.
- I1 (external code review of risk path) signed.
- I2 (external validation report review) signed.
- CP9 (real-capital regulatory counsel memo) signed.
- C1 capital cap configured at the engine.
- C2 user scope verified (founder only).

**G4 unlock = §8 gate scale.** Requires:
- ≥90d clean G3 telemetry with zero P0 violations.
- Re-pass of the full criteria set.
- Reviewer sign-off.

---

## 9. What This Document Does Not Do

- It does not prove the engine will be profitable. Profit is not a P0 criterion.
- It does not certify any specific trading strategy.
- It does not replace counsel's regulatory analysis.
- It does not authorize external user funds in any scenario.
- **It does not unlock subscriptions on its own.** G1 unlock additionally requires CP4 (counsel-reviewed legal docs in force) and CL1–CL5 (auth-layer enforcement live).
- **It does not unlock real capital on its own.** G3 unlock additionally requires CP9 (real-capital regulatory analysis sign-off) and the §8 criteria above.

---

## 10. Review Cadence

- **During validation:** weekly engine criteria review (S, D, X, engine-side O/M/R), founder-only.
- **Post G1 unlock:** weekly engine + product-layer criteria review; one external reviewer call/month.
- **Post G2 unlock:** daily P0 (automated); weekly review; monthly reviewer call.
- **Post G3 unlock:** daily P0 (automated); weekly reviewer call for first 30d, then monthly.
- **Annually:** full re-attestation.

---

## 11. Change Control

This document is the gate. Changes require:
- A written rationale.
- Founder sign-off.
- For G2/G3/G4-impacting changes: External Risk Reviewer sign-off.
- A versioned revision; the prior version remains in the repo.
- A loosening of any P0 criterion automatically re-locks the corresponding gate until the new threshold is independently validated.

---

## 12. Acceptance for v2

- [ ] All open items in §7 have a resolution path.
- [ ] Founder has reviewed and signed off on every P0 threshold.
- [ ] External Risk Reviewer is identified.
- [ ] Document committed to repo at `docs/Production_Candidate_Criteria.md` and referenced from CLAUDE.md.
- [ ] Each criterion has a verification probe or query mapped.
- [x] **PCC-OPEN-9 (leverage cap) resolved 2026-05-01: 10x system cap.**
- [x] **PCC-OPEN-10 (`§8 gate` reference) resolved 2026-05-01: §8 = Capital Cap & Phased Ramp.**
