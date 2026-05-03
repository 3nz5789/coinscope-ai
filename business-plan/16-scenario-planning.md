# §16 Scenario Planning

**Status:** v1 LOCKED (single pass — synthesis from §11.6 + §14 + §2.4). Three primary scenarios (bull/base/bear) + three contingency scenarios (regulatory shock, vendor outage, founder unavailable) + trigger thresholds + pre-committed action playbooks + audit. §15 investor narrative inherits scenarios.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active. Scenarios are commitments to act *under conditions*, not predictions of likelihood. Probability framing avoided per anti-overclaim discipline.

---

## 16.0 Assumptions and inheritance

### Inherited from upstream

- **§11.6 sensitivity ranges:** Bull M24 ARR ~$3M / Base $1.9M / Bear ~$1.0M.
- **§11.6 sensitivity inputs (top 6):** per-seat density, Free→Trader conversion, annual/monthly mix, Trader→Preview conversion, Preview→Full migration, CAC.
- **§14 stop-the-line conditions (7):** cohort drawdown, vendor outage, regulatory event, billing disputes, engine bug, persona invalidation, gate-rejection acceptance <50%.
- **§2.4 thesis kill triggers (6):** Force 1 demand failure, Force 2 supply race, Force 3 geographic moat failure, Force 3 regulatory tightening, Force 2 incumbent bundling, cross-cutting cohort demonstration failure.
- **§5.4 phase map** for timing windows.
- **§13 KPIs** as the measurement instruments that detect scenario shifts.

### What §16 adds

- **Formal definition** of bull/base/bear (which inputs at which levels).
- **Contingency scenarios** distinct from primary scenarios — events that cut across all three primaries (regulatory shock can hit bull or bear; vendor outage can hit base or bear).
- **Trigger thresholds** that move us between scenarios mid-flight.
- **Pre-committed action playbooks** so we know what to do when triggers fire — not improvise under pressure.

### What §16 does *not* do

- **Probability assignment.** §16 does not say "20% bull, 60% base, 20% bear." Probabilities are inferred poorly pre-revenue; assigning them is anti-overclaim. §16 commits to actions per scenario, not bets on which lands.

---

## 16.1 Three primary scenarios

### Bull case — M24 ARR ~$3M

**Conditions (all or most must hold):**

- Free → Trader conversion observed at 8% (upside) over 90 days.
- Trader → Desk Preview conversion at 12% over 12 months.
- Desk Preview → Desk Full v2 migration at 90% at v2 launch.
- Per-seat density at Desk Full v2 = 2.5 early / 3.0 mature.
- Trader CAC validates below $100 organic; paid acquisition turns on M5+ at $150 CAC.
- §3.7 unprompted-discipline language >50% (well above 30% Force 1 floor).
- Soft cohort fills early; waitlist exceeds 300 by M3.

**Outcomes (at M24):**

- ARR ~$3M; cumulative revenue ~$2.4M; gross margin ~79%.
- Cohort size: ~300+ Trader, ~50+ Desk Preview, ~70+ Desk Full v2.
- Cumulative cash position by M24: ~+$2.0M.
- Validates investor narrative for raise.

**Strategic implications:**

- Vendor Phase 2 integration could be pulled forward from P6 to P5 if cash supports.
- v3 features (LP-style gates, tax-ready exports) accelerate; potential v3 ship M14–M18.
- §11 model refresh upward; §15 narrative leads with bull-case framing for upside investors.
- Hiring beyond P4 contractor scenario considered (full-time front-end + back-end).

### Base case — M24 ARR ~$1.9M

**Conditions:** all locked Phase-1 assumptions hold within ±25% variance. The §11 base case as drafted.

**Outcomes (at M24):**

- ARR ~$1.9M; cumulative revenue ~$1.5M; gross margin ~76%.
- Cohort size: ~230 Trader, ~24 Desk Preview, ~39 Desk Full v2 (per §11.1).
- Cumulative cash position by M24: ~+$1.2M.
- Validates investor narrative; raise optionality preserved.

**Strategic implications:**

- §5.4 roadmap proceeds as locked. P5 Desk Full launch M10–M12.
- Vendor Phase 2 integration deferred to P6 as locked.
- §11 contractor scenario at P4 used as planned.
- v3 planning begins post-P6 stabilization.

### Bear case — M24 ARR ~$1.0M

**Conditions (one or more triggers fired but not all):**

- Free → Trader conversion observed at 2–3% (downside) — half the base case.
- Trader → Desk Preview conversion at 4% over 12 months.
- Desk Preview → Desk Full v2 migration at 50%.
- Per-seat density at Desk Full v2 = 1.5 early / 2.0 mature (P3 cohort thinner than expected).
- Trader CAC observed at $300+ (founder-time-honest pricing closer to reality).
- §3.7 unprompted-discipline language 30–40% (just clears Force 1 floor).
- Waitlist by M3 ≤ 150.

**Outcomes (at M24):**

- ARR ~$1.0M; cumulative revenue ~$0.9M; gross margin ~65%.
- Cohort size: ~150 Trader, ~12 Desk Preview, ~20 Desk Full v2.
- Cumulative cash position by M24: roughly flat or modestly negative.
- Survival mode but not failure. Company sustained; growth slow.

**Strategic implications:**

- v2 Desk Full launch may slip to M14–M16; P4 contractor scenario revisited (defer to scenario-2 at 1 contractor).
- Vendor Phase 2 integration deferred indefinitely.
- §11 model refresh downward; §15 narrative recasts as "validation-pass survival" not "growth raise."
- Re-examine §3 ICP via §3.7 v1.1 data — possible persona refinement.
- Pricing review (§6) — possible Trader-tier price reduction to test conversion lift.

---

## 16.2 Three contingency scenarios

These cut across primary scenarios. Bull/base/bear is about how *growth* unfolds; contingencies are *exogenous events* that demand response regardless of growth trajectory.

### Contingency A — Regulatory shock

**Trigger.** VARA / ADGM / DFSA / KSA / Bahrain / Oman regulator classifies CoinScopeAI offering as virtual-asset advisory, virtual-asset broker, or another category requiring a license a UAE sole prop cannot obtain inside a 6-month window.

**24-hour response:**

- Pause public-launch comms (per §14.3 stop-the-line protocol).
- Founder consults legal counsel (UAE-licensed, virtual-asset specialist).
- Notify validation/soft-cohort users transparently: "We've received a regulatory action. We're pausing while we evaluate. Your account is unaffected during this window."

**72-hour response:**

- Legal-counsel review concludes whether action is jurisdictional only (apply geo-block) or category-wide (requires entity restructure or product modification).
- Investor / advisor notification (severity-1 communication).

**1-week response:**

- Decision branch:
  - **Branch 1: Geo-restrict only** (e.g., UAE-served users move out, MENA-only product narrows). Continue operations with reduced scope.
  - **Branch 2: Entity restructure** to ADGM or DIFC corp under appropriate license. Engineering/business work in parallel; fund restructure cost (~$25–50k initial + ongoing) from bootstrap or emergency raise.
  - **Branch 3: Product modification** to remove regulated functionality (e.g., "no auto-arming of orders") if specific product feature triggered the action.
  - **Branch 4: Wind-down** — if restructure path unviable and product modification can't preserve core offering, structured wind-down with refund to paying users.

**Recovery posture:** branches 1, 2, 3 preserve company; branch 4 is end-state. §12 risk register tracks regulatory monitoring weekly to give 6+ months of warning where possible.

### Contingency B — Vendor outage (P1 stack)

**Trigger.** Any P1 vendor (CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude) experiences outage >24 hours with no automatic failover, and the outage materially degrades engine output (e.g., signal scoring fails, regime classifier output stale).

**24-hour response:**

- Engine kill switch activated for affected functionality (per §13.4 risk KPI: vendor uptime).
- All paying users notified via Telegram-companion bot + dashboard banner: "X vendor experiencing outage; affected functionality paused. Engine non-affected functionality continues."
- Engineering effort: assess failover path (alternate vendor available? manual data substitution?).

**72-hour response:**

- Failover deployed if alternate available (e.g., Bybit data via CCXT replaces CoinGlass partial; alternate sentiment provider replaces Tradefeeds).
- If no failover, prolonged outage: refund affected users on pro-rata basis per §6.7 policy.

**1-week response:**

- Vendor relationship reviewed. If vendor performance is structurally unreliable, relationship terminated and replacement integrated.
- §11 vendor cost line item refreshed.
- Public communication: short post-mortem on Substack/X if >5 days of degradation.

**Recovery posture:** vendor outage rarely terminal; recovery is engineering-bounded. §10 ops runbook (when drafted) includes per-vendor failover procedures.

### Contingency C — Founder unavailable

**Trigger.** Founder unable to work materially for ≥2 weeks (illness, family event, personal emergency).

**Immediate response:**

- Engine kill switch *not* automatically activated; engine continues running per its locked rules (gate, kill switch, regime classifier) without founder input.
- Customer-facing communication: "We're operating under reduced founder availability. Engine and dashboard continue; new feature work and direct support are paused."
- Designated emergency contact notifies stakeholders (one trusted founder-network member with read-only access to status).

**1-week response:**

- If absence >1 week: paid users informed of status; soft-cohort communications paused.
- Vendor SLA escalations handled by emergency contact if reachable; otherwise vendors notified that response time will exceed normal.
- Investor / advisor notification per existing relationships.

**4-week response:**

- If absence >4 weeks: structured pause. New signups disabled. Existing users continue with engine/dashboard but no new features or active support.
- Refund offered to any user who requests on the basis of reduced service.
- Founder return triggers re-evaluation of §5.4 timeline; phase windows extend.

**Recovery posture:** this contingency is *the* hardest to plan for at solo-founder scale. §5.4.7 contractor scenario at P4 partially mitigates by introducing 2 engineering contractors who can sustain engineering functions during P4–P5. Pre-P4 founder absence is highest-risk; post-P4 less acute.

**Pre-emptive mitigation:**

- Founder maintains documented emergency-contact protocol with trusted MENA peer (advisor or co-founder-equivalent).
- Engine and dashboard documented well enough that a sufficiently-skilled engineer could maintain them with 1 week of context transfer.
- Engineering documentation, runbooks, and credentials stored in encrypted vault accessible to emergency contact.

---

## 16.3 Trigger thresholds — which scenario are we in?

We don't pick a scenario in advance; reality reveals which one we're in. §16.3 specifies the signals that move us between scenarios.

### Bull-case triggers (we're tracking ahead of base)

- M3 waitlist > 250.
- M3 paid users > 100 (vs. base 95).
- Free → Trader 90-day conversion observed > 7%.
- Trader retention at 6mo > 70% (base 60%).

If any 2 of 4 fire by M6, refresh §11 model upward and re-anchor §15 narrative.

### Bear-case triggers (we're tracking behind base)

- M3 waitlist < 150.
- M3 paid users < 60.
- Free → Trader 90-day conversion observed < 3%.
- Trader retention at 6mo < 50%.
- §3 v1.1 *replaces* (not refines) any persona — §14 condition 6.

If any 2 of 5 fire by M6, refresh §11 model downward and execute bear-case strategic implications (defer Vendor Phase 2; revisit §11 contractor scenario; consider pricing review).

### Contingency triggers (binary; immediate response)

- Regulatory action (any MENA regulator) → Contingency A.
- P1 vendor outage >24h with material engine impact → Contingency B.
- Founder unavailable ≥2 weeks → Contingency C.

### Detection cadence

- §13 weekly internal report tracks bull/bear triggers.
- §13 monthly stakeholder report logs scenario state ("currently tracking base" / "tracking toward bull on 2 of 4 indicators").
- §12 risk register monitors regulatory + vendor signals weekly.
- Founder availability is self-monitored; emergency-contact protocol addresses unforeseen.

---

## 16.4 Pre-committed action playbooks

Brief versions of what we do under each scenario. Detail expands in §10 ops runbooks (when drafted).

### If bull case confirmed (≥2 bull triggers fire by M6)

1. §11 v1.1 refresh upward — bull-case as new base.
2. §15 narrative re-leads with bull framing for global VC audience.
3. Vendor Phase 2 integration evaluated for pull-forward to P5.
4. Hiring decision: full-time engineers considered beyond P4 contractor scenario.
5. v3 planning starts (LP-style gates, tax exports) for accelerated ship M14–M18.
6. Founder-cohort pricing window NOT extended (per §5.3.5 lock).

### If bear case confirmed (≥2 bear triggers fire by M6)

1. §11 v1.1 refresh downward — bear-case sub-scenario as new base.
2. §15 narrative recast as "validation pass survival, deliberate growth."
3. Vendor Phase 2 deferred indefinitely.
4. P4 contractor scenario revisited (drop to 1 contractor, ~$24k spike instead of $48k).
5. v2 Desk Full launch slips to M14–M16; communicated honestly.
6. Pricing review — Trader-tier reduction tested if conversion lift validates.
7. §3 v1.1 persona analysis — possible re-cut if data warrants.

### Contingency A action (regulatory shock)

- Per §16.2 24h/72h/1-week protocol.
- Pause public-launch comms. Legal review. Decision branch (geo-restrict / restructure / modify / wind-down).
- §15 narrative paused; §11 cash position protected; founder-cohort users honored.

### Contingency B action (vendor outage)

- Per §16.2 protocol. Kill-switch affected functionality; failover or relationship terminate; pro-rata refund if >5d outage; vendor swap.
- §11 vendor cost refreshed.

### Contingency C action (founder unavailable)

- Per §16.2 1-week / 4-week protocol. Engine continues; new features pause; emergency contact notifies stakeholders.
- §5.4 phase windows extend per absence duration.

---

## 16.5 Anti-overclaim audit on §16

Audit performed against §16.0 through §16.4 on 2026-05-01.

### Flags applied

**Flag 1 — Probability framing avoided per anti-overclaim.**

§16 explicitly does not say "20/60/20 bull/base/bear." Justification documented (probabilities inferred poorly pre-revenue). §15 narrative must respect this — investor pitch should not assert probabilities for §16 scenarios.

**Flag 2 — Bull-case M24 $3M ARR is upside, not target.**

§15 narrative may quote bull case for upside framing but must distinguish from base case. "We see a path to $3M ARR if X / Y / Z conditions hold" is acceptable; "we will hit $3M" is not.

**Flag 3 — Founder-unavailable contingency is real risk under-communicated by some founders.**

The §16.2 Contingency C section is honest about solo-founder fragility. §15 due-diligence Q&A may surface this; pre-emptive mention demonstrates honest risk-awareness.

### What §16 audited clean

- Scenario conditions traceable to §11.6 sensitivity inputs.
- Contingency triggers traceable to §14 stop-the-line conditions and §2.4 thesis kill triggers.
- Action playbooks reference §11 model refresh, §15 narrative recast, §5.4 timeline implications without inventing new commitments.
- §13 KPI cadence supports trigger detection.
- §12 risk register inherits scenario monitoring (regulatory + vendor) when drafted.

### §16 v1 LOCKED

§16.0 through §16.5 all committed. §15 investor narrative inherits scenarios for deck and Q&A material.
