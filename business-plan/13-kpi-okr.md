# §13 KPI / OKR Framework

**Status:** v1 LOCKED. North-star MAVT (+ VCSE companion) locked; 5-layer metric tree with persona segmentation; Q1 OKRs (validation + soft launch); risk KPIs paired with §14 stop-the-line; weekly + monthly reporting templates; §11 feedback loops; anti-overclaim audit. Downstream §14, §15, §16 draft against §13 v1.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active; KPIs are committed structurally at v0; specific targets are v1 territory. Anti-overclaim discipline applies to claims about cohort behavior.

---

## 13.0 Assumptions and inheritance

### Inherited from locked decisions

- **§11 highest-leverage metrics** (most-impactful sensitivity inputs): Free → Trader conversion (±$700k M24 ARR swing); Desk Preview → Desk Full v2 migration (±$200k swing). These are top-2 KPI candidates by financial leverage.
- **§3.8 cohort behavioral grid:** gate-rejection acceptance, multi-account setup, journal review frequency, tier-upgrade trigger pattern, NPS qualitative feedback.
- **§14 stop-the-line conditions (6):** drawdown, vendor outage, regulatory event, billing disputes, engine bug, persona invalidation. KPIs feeding these triggers must exist.
- **§13 conditional escalation rule:** cohort gate-rejection acceptance <50% → §13 red-line metric → escalates to §14 only if cause is fundamental ICP mismatch.
- **§2.4 thesis kill triggers** (cohort-demonstration failure cross-cutting). KPIs must surface validation cohort net performance.
- **§5.4.4 phase-gate criteria:** Trader-floor IB items at "stabilizing" must cross to VTN before P3→P4. KPIs track maturity progression.
- **§6.9 sensitivity flags:** per-seat density, annual/monthly mix — both KPIs at Desk Full tier.

### KPI cadence

- **Weekly internal:** founder + any contractor cohort. Operational tempo.
- **Monthly stakeholder:** investor updates (when applicable), advisor updates, founder-cohort users (light version).
- **Quarterly:** OKR review and reset.

### What the KPI tree must do

Three simultaneous jobs:

1. **Surface health.** Tell the founder/team what's working and what isn't, in real time.
2. **Trigger §14 stop-the-line** when a metric crosses red-line threshold.
3. **Inform §15 investor narrative** with credible, defensible numbers — not vanity metrics.

A KPI that does only one of the three is too narrow. A KPI that fails at any of the three is the wrong choice.

---

## 13.1 North-star metric — candidate analysis

The north-star is the single number that orients team priorities. It must be:

- **Measurable from observable data** (not inferred or composite-with-fuzzy-weights).
- **Brand-aligned** with capital preservation first.
- **Externally legible** for §15 investor narrative.
- **Hard to game** without driving the underlying value.
- **Sensitive to product use, not just subscription renewal** (so retention and engagement both move it).

### Candidate north-stars

#### Candidate A — MAVT (Monthly Active Validated Traders)

**Definition.** Paying users (Trader, Desk Preview, Desk Full v2) with ≥1 engine-scored signal evaluated in their account in the last 30 days.

**Pro:** Captures the union of paying + actually using. "Validated" qualifier means they engage with the engine, not just sit on a subscription. Differentiates from competitors who measure raw active users. Brand-aligned because "validated" implies the gate-respecting use we want.

**Con:** Definition needs operational precision (what counts as "evaluated"? Is a rejected gate decision a validation event?). Externally legible but requires a 30-second explanation to investors who haven't seen the metric before.

**Game resistance:** medium-high. Hard to inflate without actually using the product.

#### Candidate B — ARR (Annualized Recurring Revenue)

**Definition.** Sum of monthly recurring subscription revenue × 12, including per-seat additions.

**Pro:** Financial standard. Externally legible to all investors. Inherits cleanly from §11. Cannot drift from financial reality.

**Con:** Insensitive to product engagement. A churning user paying their last month still counts. Doesn't reflect capital-preservation outcomes — quality of cohort behavior is invisible. Tells you the company is making money; doesn't tell you the product is working.

**Game resistance:** very high. ARR is what it is.

#### Candidate C — CPS (Capital-Preservation Score)

**Definition.** Composite metric: cohort-level drawdown distribution + gate-rejection acceptance + kill-switch trigger rate, weighted to produce a single score 0–100 representing how well our locked operating principle is being delivered cohort-wide.

**Pro:** Most brand-aligned. Reflects what we are actually optimizing for. Strongest §15 narrative anchor — "our north-star is whether your capital is preserved, not whether we're growing."

**Con:** Composite metrics are hard to track in real time. Weights are subjective; team can debate whether gate-rejection should be 40% or 60% of the score. Investors may not "get" it without explanation. Soft-cohort hasn't validated the right weights yet.

**Game resistance:** medium. Composite weights expose game surface (operate so one component looks good while others slip).

#### Candidate D — Active Paid Users

**Definition.** Count of paying users who logged into the dashboard at least once in the last 14 days.

**Pro:** Simplest. Easy to measure, easy to communicate.

**Con:** Doesn't capture engine engagement (logging in to look at numbers ≠ using gating). Doesn't differentiate us from any other SaaS metric. Fails the "brand-aligned" bar — there's nothing about capital preservation in this metric.

**Game resistance:** low. A weekly notification email could inflate dashboard logins without any product value.

### LOCKED north-star: MAVT + VCSE companion

**Primary north-star: MAVT (Monthly Active Validated Traders).** Paying users (Trader, Desk Preview, Desk Full v2) counted once per 30-day window if any of:

- **(a) Viewed at least 1 scored signal in the dashboard.** User-initiated engagement with engine output.
- **(b) Triggered at least 1 risk-gate evaluation.** User proposed a trade for gate review.
- **(c) Recorded at least 1 journal entry.** User logged trade reflection.
- **(d) Interacted with Telegram bot at least once.** Issued a command OR acknowledged an alert (matches Tier 1 delivery: dashboard canonical, Telegram companion).

All four triggers are user-initiated activity across the four product surfaces. Passive engine activity (signal scored by engine without user view) does not count.

**P0 companion metric: VCSE (Validation Cohort Signal Evaluations).** Non-paying validation-cohort users with engine activity, counted with the same operational definition as MAVT but without the paying qualifier. VCSE phase-rolls into MAVT at P1 soft launch when paid status begins.

**Pair with ARR** for §15 investor narrative — engagement health (MAVT) + financial outcome (ARR), two metrics two stories.

**Why MAVT over alternatives.**

Reasoning, in three parts:

**It captures product engagement, not just subscription presence.** A user with a ≥1 engine-scored signal in the last 30 days is using the product as designed. Trader who pays $79/mo but never has a signal scored is going to churn — MAVT catches that early; ARR doesn't.

**It is brand-aligned without being composite.** "Validated" maps directly to capital-preservation: we score and gate trades; users who interact with the gate are being validated. Stronger brand alignment than Active Paid Users; more measurable than CPS.

**It pairs cleanly with ARR as a financial summary metric.** §15 investor narrative quotes both: MAVT (engagement health) + ARR (financial outcome). Two metrics, two stories. Composite scores like CPS sound impressive but are harder to defend in due diligence.

**Operational definition tightening.** MAVT counts a user once per 30-day window if any of: (a) at least 1 signal scored by the engine for their watchlist, (b) at least 1 risk-gate evaluation, (c) at least 1 journal entry recorded. This widens the qualifying behaviors so a user using the product reflectively (not just transactionally) counts.

### Three confirmable alternatives

1. **Lock Candidate A — MAVT (recommended).**
2. **Lock Candidate B — ARR.** Pro: simplest, standard. Con: blind to engagement quality.
3. **Lock Candidate C — CPS.** Pro: strongest brand anchor. Con: composite-metric tracking risk; investor explanation overhead.

---

## 13.2 Supporting metric tree

Five-layer structure. Persona segmentation (P1 / P2 / P3) is applied as a **cross-cutting reporting attribute** in §13.5 reporting templates, not as a separate layer — every metric in the layers below is reported by persona segment where meaningful.

### Volume / acquisition layer

- Free signups (cumulative + new this month).
- Free → Trader conversion rate (90-day window).
- Trader cohort size (active paying).
- Desk Preview cohort size.
- Desk Full v2 cohort size (post-M10).

### Revenue / financial layer

- MRR (monthly recurring revenue).
- ARR (annualized).
- Effective ARPU per tier.
- Per-seat density at Desk Full.
- Annual/monthly mix per tier.
- Trader → Desk Preview migration rate.
- Desk Preview → Desk Full v2 migration rate.

### Engagement / quality layer (the north-star feeders)

- MAVT (if locked as north-star).
- Signal-evaluations per user per month.
- Journal entries per active user.
- Dashboard sessions per active user.
- Telegram bot interaction frequency.

### Risk layer (paired with §12)

- Cohort drawdown distribution (max, mean, P95).
- Gate-rejection acceptance rate.
- Kill-switch activation count (per 1000 user-days).
- Gate-override attempt rate per user.
- Daily-loss-limit trigger rate.

### Operational layer

- Engine API latency (p95).
- Vendor uptime per P1 stack.
- Support ticket volume + response time.
- IB → VTN graduation status (per §5.4 capability flow).

### KPIs that feed §14 stop-the-line conditions

- Cohort drawdown vs. §8 thresholds → §14 condition 1.
- Vendor uptime <(threshold) → §14 condition 2.
- Regulatory-event tracking flag → §14 condition 3.
- Billing dispute rate → §14 condition 4.
- Engine bug detection rate → §14 condition 5.
- Persona invalidation signal from §3.8 cohort grid → §14 condition 6.

### KPIs that feed §13 red-lines (conditional §14 escalation)

- Gate-rejection acceptance <50% across cohort.
- (Future) other red-lines surfaced by §3.7 interview validation.

---

## 13.3 First-quarter OKRs (Q1 = validation + soft launch)

Q1 in this framework = the first quarter starting at the locked baseline (May 2026, M0). Spans M0 validation phase + M1–M2 soft launch (P0 + P1 per §5.4 phase map). Subsequent quarters are Q2 (M3–M5), Q3 (M6–M8), Q4 (M9–M11), Q5 (M12+).

### Q1 Objectives (qualitative)

- **O1.** Pass validation phase against §8 Capital Cap criteria.
- **O2.** Successfully fill and operate the soft cohort (40 users target, 50/30/20 mix per §3.8).
- **O3.** Validate or refine the three §3 sub-personas using §3.7 interview data + §3.8 cohort behavioral signals.
- **O4.** Complete §5.4 P0 → P1 phase gate cleanly (no §14 stop-the-line triggers fired).

### Q1 Key Results (measurable)

| Objective | Key Result | Source / measurement |
|---|---|---|
| O1 | §8 Capital Cap criteria met (production-candidate criteria pass) | §8 documented criteria; engine validation logs |
| O1 | Validation cohort net performance: zero negative kill-switch triggers due to engine bug | Engine audit log |
| O1 | Validation cohort drawdown stays within §8 thresholds | Cohort drawdown distribution |
| O2 | Soft cohort 40/40 filled by end of M1 | Signup record |
| O2 | Soft cohort tier mix lands within ±2 users of 30 Trader / 10 Desk Preview target | Cohort tag dataset |
| O2 | VCSE (validation P0) ≥ 35 by end of M0 | Signal evaluation count, validation cohort |
| O2 | MAVT (post-P1 transition) ≥ 36 by end of M2 (90% of soft cohort active) | MAVT 4-trigger definition |
| O3 | §3.7 interview count: ≥18 interviews completed (6 per persona target) | Interview log |
| O3 | §3.7 unprompted-discipline language rate: ≥30% (kills Force-1 trigger) | Interview transcript tagging |
| O3 | §3.8 cohort behavioral grid: ≥80% of cohort tagged matches behavioral signals | Persona-tag accuracy report |
| O3 | §3 v1.1 published with persona labels (validated/refined/replaced) | §3 file lock |
| O4 | Zero §14 stop-the-line triggers fired during M0–M2 | Stop-the-line monitoring |
| O4 | Vendor uptime ≥99% across P1 stack (CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude) | Vendor SLA monitoring |

**Q1 OKR cadence:** weekly internal review of KRs; monthly aggregated stakeholder summary. Quarterly OKR reset at M3 boundary.

---

## 13.4 Risk KPIs paired with §12

These metrics directly track conditions that escalate to §14 stop-the-line. They are the operational counterparts of the §12 risk register.

| Risk metric | §14 condition | Threshold (red-line) | Cadence | Source |
|---|---|---|---|---|
| Cohort max drawdown | §14.1 (cohort drawdown) | Exceeds §8 thresholds at cohort level | Daily during validation; weekly post-launch | Engine logs |
| Vendor uptime per P1 stack | §14.2 (vendor outage) | <99% over 24h, no failover | Continuous monitoring | Vendor APIs + status pages |
| Regulatory event flag | §14.3 (regulatory event) | Any VARA/ADGM/DFSA action touching virtual-asset advisory framing | Manual + alert subscription | News + legal monitoring |
| Billing dispute rate | §14.4 (billing/refund disputes) | >5% of soft-cohort users | Weekly | Stripe disputes dashboard |
| Engine bug detection rate | §14.5 (critical engine bug) | Any gate-failure / position-sizer error / kill-switch malfunction | Daily during validation; per-incident post-launch | Engine error logs + cohort feedback |
| Persona invalidation signal | §14.6 (persona invalidation per §3 v1.1) | Any persona *replaced* (not refined) | At §3 v1.1 publication | §3.8 cohort behavioral grid |
| Gate-rejection acceptance | §13 red-line (conditional §14 escalation) | <50% across cohort, structural ICP-mismatch cause | Weekly | Engine gate logs |
| MAVT-to-paid ratio | Churn-warning leading indicator | Drops below 70% (passive subscribers exceeding active) | Weekly | MAVT × paid-user joins |
| Override attempt rate | Anti-ICP signal | >20% of users attempting overrides repeatedly | Weekly | Engine override logs |
| Kill-switch activation rate | Risk-control health | >5% of user-days triggering kill switch | Weekly | Kill-switch event log |

### Risk KPI escalation flow

- **Yellow flag:** metric crosses warning level (defined per metric). Founder notified via internal weekly report; investigation begins.
- **Red flag:** metric crosses red-line threshold. §14 stop-the-line evaluation triggered. If structural cause confirmed, public-launch hold or revert per §5.4.4 phase-gate logic.

The §13 red-line for cohort gate-rejection acceptance follows the §3.8 conditional escalation rule: only escalates to §14 if root cause is fundamental ICP mismatch.

---

## 13.5 Reporting templates

### Weekly internal report (founder + any contractor cohort)

Single-page summary, sent every Monday for the prior week.

**Section 1 — North-star + financial:**

- MAVT (latest 30-day rolling) — total + by persona segment.
- ARR (current MRR × 12).
- New paying users this week — by tier.
- Churn this week — by tier, with reason if known.

**Section 2 — Engagement layer:**

- Avg signal-evaluations per active user (latest 7-day).
- Avg journal entries per active user (latest 7-day).
- Telegram interaction rate.
- MAVT-to-paid-user ratio (churn-warning leading indicator).

**Section 3 — Risk layer:**

- Cohort max drawdown (latest 7-day).
- Gate-rejection acceptance rate.
- Kill-switch activations (count this week).
- Override attempts (count this week, flagged users).
- Vendor uptime — P1 stack.

**Section 4 — Operational:**

- Engine API latency p95.
- Support ticket volume + median response time.
- IB → VTN graduation status (per §5.4 capability flow tracking).

**Section 5 — Stop-the-line status:**

- Zero / Yellow flag / Red flag indicator per §14 condition.
- Actions taken this week (if any flag fired).

### Monthly stakeholder report (investor / advisor / founder cohort)

Two-page summary, sent within 7 days of month-end. Lighter version for founder-cohort users (no §11 model details).

**Page 1 — Headline:**

- MAVT + ARR (the locked two-metric framing).
- Trajectory: prior 3 months + latest.
- Cohort composition by tier and persona.
- Q-current OKR status: green / yellow / red per KR.

**Page 2 — Operational + outlook:**

- §5.4 phase map status (P0/P1/P2/P3/P4/P5).
- Risk-layer summary (no red flags / X yellow flags / Y red flags).
- §11 model variance commentary (M-actual vs. M-base-case from §11.2).
- Next-30-day priorities (3–5 line items).
- Open stakeholder questions / asks.

### Persona segmentation in reporting

Per §13.2, every metric reported by persona segment where meaningful. Specifically in templates:

- MAVT split P1 / P2 / P3 in weekly + monthly.
- Conversion rates segmented by persona origin (waitlist vs. organic vs. referral).
- Retention curves by persona.
- Risk metrics — cohort drawdown distribution by persona (P3 expected lower drawdown given higher discipline).

---

## 13.6 §11 integration — KPI feedback loops to financial model

KPI deviations must move §11 forecasts. Without this loop, §11 is a static document; with it, §11 is a living model.

### Feedback loops

**MAVT deviation from §11.1 cohort sizing.**

If observed MAVT lags base case (e.g., M3 plan = 95 active Trader, actual = 70), §11.2 revenue projection updates monthly with actuals. Variance >10% triggers a §11 v1.1 refresh; variance >25% triggers a §11 v1 re-lock.

**Free → Trader conversion observed vs. base case.**

§11 base assumes 5% over 90 days. Observed rate from soft cohort + initial public launch produces the first `O` (observed) tag. Replaces `A` once 90-day window completes for first cohort. §11.6 sensitivity scenarios re-run against observed values.

**Cohort retention observed vs. base case.**

§11 LTV uses 60% / 70% / 80% retention assumptions. Monthly cohort retention measurements at M3, M6, M9 update LTV calculations. CAC tolerance ceilings (per §6.9) recalibrated.

**Per-seat density observed at Desk Full v2.**

Time-varying base assumes 2.0 early v2 → 2.5 mature. Observed per-seat density from M10+ updates the time-varying curve. ARPU at Desk Full v2 recalculated.

**Vendor cost variance.**

If P1 vendor cost varies from $945/mo mid-point assumption (e.g., CoinGlass changes pricing per §12 dual-relationship risk), §11.3 cost model updates and gross-margin projections shift. >$200/mo deviation triggers §11 v1 cost-side refresh.

**Founder cost reality vs. implicit baseline.**

§11 assumes $7k/mo implicit founder cost. Actual cash-burn view (xlsx) tracks real founder draw. Gap between implicit P&L and actual cash narrows or widens as runway dynamics evolve.

### §11 refresh cadence

- **Monthly micro-refresh:** observed MAVT, ARR, conversion, retention substituted into the model. Variance commentary in monthly stakeholder report.
- **Quarterly model review:** §11.6 sensitivity re-run with observed-vs-assumed comparison; bull/base/bear scenarios re-anchored.
- **Triggered v1.1 refresh:** when any sensitivity input variance exceeds ±25% from base case for two consecutive months.

---

## 13.7 Anti-overclaim audit on §13

Audit performed against §13.0 through §13.6 on 2026-05-01. Three flags surfaced; all resolved through documentation, no metric definition changes.

### Flags applied

**Flag 1 — MAVT terminology is bespoke; must be defined explicitly anywhere it appears.**

"MAVT" is not standard SaaS jargon. Anywhere MAVT is quoted (§15 deck, monthly reports, public commentary), the operational definition must be visible alongside the number.

*Mitigation:* §15 deck includes a glossary slide; monthly reports include a footer definition; public-facing claims (when applicable, post-validation) include parenthetical "(MAVT = paying users with engine activity in last 30 days; full definition in our methodology page)."

**Flag 2 — Validation-phase status disclaimer applies to all KPI claims.**

Any KPI quoted before validation pass is pre-validation. Cohort sizes, retention curves, MAVT — none are production-ready evidence yet.

*Mitigation:* §13 reporting templates carry the locked disclaimer ("Testnet only. 30-day validation phase. No real capital.") on every report until §8 criteria met.

**Flag 3 — Q1 OKR Key Results are aspirational anchors, not commitments.**

Specific KR numbers (40/40 cohort, ≥18 interviews, ≥30% unprompted-discipline rate) are §13 base-case targets. Real validation results may differ. KR misses do not equal company failure — they trigger investigation and §11 model refresh.

*Mitigation:* Monthly stakeholder reports frame KRs as "targets / actual / variance commentary," not "commitments / hit / miss." Anti-overclaim discipline applies to internal communication too.

### What §13 audited clean

- North-star locked (MAVT + VCSE) with operational definition that survives due diligence.
- Metric tree covers all five layers without redundancy.
- §14 stop-the-line conditions all have at least one feeding KPI.
- §11 feedback loops connect actuals to forecasts without static-document drift.
- Persona segmentation cross-cutting attribute applied consistently in reporting.
- §13 red-line (gate-rejection <50%) properly conditional-escalates to §14 only on structural ICP-mismatch root cause.

### §13 v1 LOCKED

§13.0 through §13.7 all committed. Downstream §14 (launch roadmap), §15 (investor narrative), §16 (scenarios) draft against §13 v1.

---


---

## Open questions for the founder (Phase 1 only)

1. **North-star lock** — MAVT, ARR, CPS, or Active Paid Users? My recommendation: MAVT.
2. **Metric-tree scope** — five-layer structure (volume / revenue / engagement / risk / operational) right, or want to adjust?
3. **MAVT operational definition** — three qualifying behaviors (signal scored / gate evaluation / journal entry) right, or tighter?
4. **Pairing with ARR for §15** — comfortable with two-metric framing for investor narrative (MAVT + ARR), or want a single-metric stance?
