# CoinScopeAI — OPS Workstream Linear-Ready Tickets v1.0

**Date:** 2026-05-01
**Status:** Draft for Founder Review (ready to file in Linear)
**Naming standard:** CoinScopeAI Task Naming Standard (`[TYPE] [AREA] — Action / Deliverable`)
**Allowed TYPE:** [BUILD], [FIX], [OPS], [DOC], [QA], [ML], [RISK], [DATA], [EXCHANGE], [UI], [RESEARCH], [INCIDENT]
**Allowed AREA:** INGEST, SENTIMENT, SIGNALS, REGIME, RISK, EXECUTION, PERF, ALERTS, DASHBOARD, REDIS, POSTGRES, BINANCE, BYBIT, OKX, HYPERLIQUID, DEVOPS, DOCS, MARKET SCAN, OPS, BILLING, PLATFORM

---

## Scope

These tickets decompose the OPS, Monitoring, and Reliability work surfaced in the Business Plan and Production Candidate Criteria into Linear-ready issues. Each ticket is sized to one PR / one deliverable.

**Sequencing logic:** the Now bucket clears the active blocker (COI-40 VPS) and the production-readiness scaffolding. Next layers on the runbooks, drills, and beta-readiness work. Later is for steady-state quality.

---

## Now (≤30 days)

### 1. [FIX] DEVOPS — COI-40 VPS Deployment Unblock
- **Objective:** Resolve the active blocker preventing engine deployment to the target VPS.
- **Acceptance:** Engine running on target VPS for ≥7 days continuous; auto-restart-on-crash verified; smoke test green.
- **Dependencies:** None.
- **Inputs:** COI-40 ticket history, VPS credentials, current deployment scripts.
- **Output:** Deployed engine + updated deploy doc + post-mortem on root cause.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria O3.

### 2. [DOC] OPS — Production Candidate Criteria v1 (publish + commit)
- **Objective:** Land the criteria document in the repo as the canonical gate.
- **Acceptance:** Document at `docs/Production_Candidate_Criteria.md`; referenced from CLAUDE.md; founder sign-off captured in commit message.
- **Dependencies:** Founder review of draft.
- **Inputs:** Draft document.
- **Output:** Committed doc + reference in CLAUDE.md.
- **Priority:** P0.
- **Resolves:** Business Plan §6.4 / §6.8.

### 3. [DOC] OPS — Vendor Failure-Mode Mapping v1 (publish + commit)
- **Objective:** Land the vendor mapping document as a referenced artifact.
- **Acceptance:** Document at `docs/vendor_failure_mapping.md`; linked from Production Candidate Criteria R4.
- **Dependencies:** Vendor mapping draft.
- **Inputs:** Draft document.
- **Output:** Committed doc.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria R4, Open Item O-6.

### 4. [BUILD] ALERTS — Risk Threshold Alert Wiring (D1–D5)
- **Objective:** Every P0 risk threshold (max DD, daily loss, leverage, max positions, position heat) emits an alert to the founder when crossed.
- **Acceptance:** Five alerts wired and tested with synthetic violations in staging; alerts deliver to founder within 60s; alert routing documented.
- **Dependencies:** Engine instrumentation on `/risk-gate`.
- **Inputs:** Risk thresholds (already defined), alert channel (Telegram + email).
- **Output:** Wired alerts + test log + routing doc.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria O4.

### 5. [BUILD] ALERTS — Vendor Health Alerts
- **Objective:** Per-vendor down/degraded alerts for Binance, CoinGlass, Tradefeeds, CoinGecko, Anthropic.
- **Acceptance:** 5 alerts wired; each distinguishes "degraded" from "down"; tested with simulated outage.
- **Dependencies:** Vendor health probes.
- **Inputs:** Vendor mapping doc.
- **Output:** Wired alerts + test log.
- **Priority:** P0.
- **Resolves:** Vendor Failure-Mode Mapping §5.

### 6. [BUILD] DASHBOARD — Validation Phase KPI Panel
- **Objective:** Real-time panel for validation phase KPIs (signal precision rolling, drawdown curve, regime mix, latency p95/p99, kill-switch trips).
- **Acceptance:** Dashboard URL accessible; data sourced from Engine API endpoints; survives session restart; refresh ≤60s.
- **Dependencies:** Engine endpoints `/scan`, `/performance`, `/journal`, `/risk-gate`, `/regime/{symbol}`.
- **Inputs:** Endpoint contracts.
- **Output:** Dashboard panel + URL.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria M1.

### 7. [BUILD] DASHBOARD — Vendor Health Panel
- **Objective:** Single panel showing live status of all P1 vendors.
- **Acceptance:** Panel shows: Binance (REST + WS), CoinGlass, Tradefeeds, CoinGecko, Anthropic; each with current status, last-check timestamp, latency.
- **Dependencies:** Vendor health probes.
- **Inputs:** Vendor mapping doc.
- **Output:** Panel + smoke-test log.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria M3, Vendor Mapping §5.

### 8. [DOC] OPS — Incident Response Runbook v1
- **Objective:** Predefined response playbook for the 5 most likely incidents.
- **Acceptance:** Runbook covers: engine down, kill-switch trip, Binance outage, vendor outage cascade, false-signal storm. Each entry has: detection signal, severity, paging path, immediate action, comms template, post-mortem trigger.
- **Dependencies:** Vendor mapping; alert wiring.
- **Inputs:** Engine architecture, kill-switch behavior.
- **Output:** Runbook at `docs/incident_response.md`.
- **Priority:** P0.
- **Resolves:** Business Plan §6.8.

### 9. [BUILD] EXECUTION — On-Exchange SL/TP Attachment Audit
- **Objective:** Verify every open position has an on-exchange SL attached, and surface violations.
- **Acceptance:** Audit job runs every cycle; alerts on any open position without SL within 60s; logged to journal.
- **Dependencies:** Engine order placement logic.
- **Inputs:** Order log, position state.
- **Output:** Audit job + alert + journal entries.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria X3, Vendor Mapping V-2.

### 10. [BUILD] EXECUTION — Account Reconciliation Job (Daily)
- **Objective:** Daily reconcile of engine view vs. exchange account state.
- **Acceptance:** Job runs daily; flags any unexplained delta >$1; produces a daily reconcile report.
- **Dependencies:** Engine state model, exchange account-state endpoint.
- **Inputs:** Engine journal, exchange API.
- **Output:** Recon job + report archive.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria X6.

### 11. [BUILD] PLATFORM — Engine Pre-Flight Check
- **Objective:** Engine refuses to start if any pre-flight check fails (network env, API connectivity, time sync, log-store reachable).
- **Acceptance:** Pre-flight check runs on every start; misconfigured env (e.g., mainnet vs. testnet drift) blocks start with explicit error.
- **Dependencies:** None.
- **Inputs:** Vendor mapping pre-flight requirements.
- **Output:** Pre-flight module + tests.
- **Priority:** P0.
- **Resolves:** Vendor Mapping §5, Production Candidate Criteria failure-mode B-7.

### 12. [QA] PLATFORM — LLM-Not-In-Hot-Path Audit
- **Objective:** Verify no LLM (Anthropic) call sits in any signal-generation or risk-gate path that can change risk behavior.
- **Acceptance:** Static audit of code paths; written attestation; CI check that fails the build if a flagged module imports the LLM client.
- **Dependencies:** Code base map.
- **Inputs:** Engine source.
- **Output:** Audit report + CI check.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria S0 hard rule.

---

## Next (30–90 days)

### 13. [DOC] OPS — Beta Cohort Onboarding Runbook
- **Objective:** Documented procedure for onboarding paper-trading beta users.
- **Acceptance:** Step-by-step from invite → ToS/risk acceptance → access → weekly check-in; templates included.
- **Dependencies:** Legal docs (ToS, Privacy, Risk Disclosure) committed; ICP card finalized.
- **Inputs:** Business Plan §6.6 cohort design.
- **Output:** Runbook at `docs/beta_onboarding.md`.
- **Priority:** P1.

### 14. [BUILD] PLATFORM — Status Page (Public)
- **Objective:** Externally visible status for engine, dashboard, Telegram bot, and primary vendors.
- **Acceptance:** Public URL; updated automatically on incident; manual override available.
- **Dependencies:** Vendor health panel.
- **Inputs:** Health probes.
- **Output:** Status page + integration with alerting.
- **Priority:** P1.
- **Resolves:** Production Candidate Criteria O6.

### 15. [BUILD] PLATFORM — Audit-Grade Event Log
- **Objective:** Every order, gate decision, and kill-switch trip logged with immutable timestamps.
- **Acceptance:** Sample audit (n=50) shows complete chain; 90-day retention; tamper-evident.
- **Dependencies:** Logging infrastructure choice.
- **Inputs:** Current journal schema.
- **Output:** Logging module + retention policy + sample audit report.
- **Priority:** P0.
- **Resolves:** Production Candidate Criteria M5, M4.

### 16. [DOC] OPS — Code Rollback Procedure
- **Objective:** Documented procedure to roll back any deployed engine version to the prior version in ≤10 minutes.
- **Acceptance:** Procedure tested in a drill; rollback time measured; doc committed.
- **Dependencies:** Deployment automation.
- **Inputs:** Current deploy scripts.
- **Output:** Doc at `docs/rollback_procedure.md` + drill log.
- **Priority:** P1.
- **Resolves:** Production Candidate Criteria R5.

### 17. [QA] OPS — Vendor Failure Drill (Staging)
- **Objective:** Simulate each P1 vendor's outage in staging; verify degraded-mode behavior matches the Vendor Mapping doc.
- **Acceptance:** All 5 vendors drilled; results documented; any divergence from doc is fixed before drill closes.
- **Dependencies:** Vendor mapping doc; staging environment.
- **Inputs:** Vendor mapping.
- **Output:** Drill log + fixes.
- **Priority:** P1.
- **Resolves:** Vendor Mapping V-5.

### 18. [BUILD] EXECUTION — Position-Close Playbook (Manual + Automated)
- **Objective:** Documented + automated procedure to close all open positions in ≤15 minutes.
- **Acceptance:** Drilled in staging; ≤15 min wall-clock to flat; founder can trigger from any device.
- **Dependencies:** Kill-switch + order-placement infrastructure.
- **Inputs:** Engine order logic.
- **Output:** Playbook + automation script + drill log.
- **Priority:** P1.
- **Resolves:** Production Candidate Criteria R3.

### 19. [BUILD] PLATFORM — User Support Intake (Beta-Grade)
- **Objective:** Single channel for beta-user issues with documented SLA.
- **Acceptance:** Channel chosen (recommend: dedicated email + Telegram); SLA published (≤24h beta-grade); first-week response measured.
- **Dependencies:** Beta cohort design.
- **Inputs:** Beta cohort plan.
- **Output:** Channel live + SLA doc.
- **Priority:** P1.

### 20. [QA] PLATFORM — Catastrophic-Stop Logic Test
- **Objective:** Verify that disagreement among three monitoring channels causes engine to halt new entries.
- **Acceptance:** Synthetic disagreement injected in staging; engine halts within 1 cycle.
- **Dependencies:** Catastrophic-stop logic implementation.
- **Inputs:** Engine architecture.
- **Output:** Test report.
- **Priority:** P1.
- **Resolves:** Production Candidate Criteria R6.

---

## Later (90 days+)

### 21. [BUILD] PLATFORM — Backup Vendor for OI/Liquidations
- **Objective:** Reduce CoinGlass single-point-of-failure by adding a backup data source.
- **Acceptance:** Second vendor integrated; failover tested; CoinGlass mapping updated.
- **Dependencies:** Vendor evaluation memo.
- **Inputs:** Vendor mapping.
- **Output:** Integration + updated mapping doc.
- **Priority:** P2.
- **Resolves:** Vendor Mapping V-6.

### 22. [QA] PLATFORM — Quarterly Fire Drill
- **Objective:** Recurring quarterly drill for each P1 vendor outage; first run scheduled.
- **Acceptance:** Calendar invite for first drill; runbook for drill; second drill scheduled at end of first.
- **Dependencies:** Vendor failure drill (#17) complete.
- **Inputs:** Drill log from #17.
- **Output:** Recurring schedule + runbook.
- **Priority:** P2.

### 23. [DOC] OPS — Annual Re-Attestation Procedure
- **Objective:** Documented procedure to re-pass the full Production Candidate Criteria annually.
- **Acceptance:** Procedure documented; first re-attestation date scheduled.
- **Dependencies:** Production Candidate Criteria committed.
- **Inputs:** Criteria doc.
- **Output:** Re-attestation procedure + calendar entry.
- **Priority:** P2.
- **Resolves:** Production Candidate Criteria I3.

### 24. [BUILD] DASHBOARD — Operational Metrics (Business KPIs)
- **Objective:** Second dashboard for business KPIs (users, support load, content engagement, vendor cost burn) — distinct from engine telemetry.
- **Acceptance:** Weekly view live; deltas explainable; sourced from production systems.
- **Dependencies:** Beta cohort active; metrics sources connected.
- **Inputs:** Business Plan §6.14.
- **Output:** Dashboard + weekly review cadence.
- **Priority:** P2.

---

## Summary Table

| # | Title | Priority | Horizon |
|---|---|---|---|
| 1 | [FIX] DEVOPS — COI-40 VPS Deployment Unblock | P0 | Now |
| 2 | [DOC] OPS — Production Candidate Criteria v1 | P0 | Now |
| 3 | [DOC] OPS — Vendor Failure-Mode Mapping v1 | P0 | Now |
| 4 | [BUILD] ALERTS — Risk Threshold Alert Wiring | P0 | Now |
| 5 | [BUILD] ALERTS — Vendor Health Alerts | P0 | Now |
| 6 | [BUILD] DASHBOARD — Validation Phase KPI Panel | P0 | Now |
| 7 | [BUILD] DASHBOARD — Vendor Health Panel | P0 | Now |
| 8 | [DOC] OPS — Incident Response Runbook v1 | P0 | Now |
| 9 | [BUILD] EXECUTION — On-Exchange SL/TP Attachment Audit | P0 | Now |
| 10 | [BUILD] EXECUTION — Account Reconciliation Job | P0 | Now |
| 11 | [BUILD] PLATFORM — Engine Pre-Flight Check | P0 | Now |
| 12 | [QA] PLATFORM — LLM-Not-In-Hot-Path Audit | P0 | Now |
| 13 | [DOC] OPS — Beta Cohort Onboarding Runbook | P1 | Next |
| 14 | [BUILD] PLATFORM — Status Page | P1 | Next |
| 15 | [BUILD] PLATFORM — Audit-Grade Event Log | P0 | Next |
| 16 | [DOC] OPS — Code Rollback Procedure | P1 | Next |
| 17 | [QA] OPS — Vendor Failure Drill (Staging) | P1 | Next |
| 18 | [BUILD] EXECUTION — Position-Close Playbook | P1 | Next |
| 19 | [BUILD] PLATFORM — User Support Intake | P1 | Next |
| 20 | [QA] PLATFORM — Catastrophic-Stop Logic Test | P1 | Next |
| 21 | [BUILD] PLATFORM — Backup Vendor for OI/Liquidations | P2 | Later |
| 22 | [QA] PLATFORM — Quarterly Fire Drill | P2 | Later |
| 23 | [DOC] OPS — Annual Re-Attestation Procedure | P2 | Later |
| 24 | [BUILD] DASHBOARD — Operational Metrics | P2 | Later |

---

## Notes for Linear filing

- All tickets should be labelled with `workstream:OPS`.
- All P0/Now tickets should land in the current cycle.
- Each ticket should reference the relevant Production Candidate Criteria ID in its description for traceability.
- Each ticket title is unique on its first 5 words per the naming standard.
