# §14 Launch Roadmap

**Status:** v1 LOCKED. Phase progression with go/no-go gates, consolidated stop-the-line conditions, launch comms plan, P0–P1 date locks, §5 roadmap mapping, anti-overclaim audit. §15, §16, §1 draft against §14 v1.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active. P1+ dates are gate-driven targets, not calendar commitments. Stop-the-line conditions extend any phase if triggered.

---

## 14.0 Assumptions and inheritance

§14 is largely a **consolidation document.** It does not invent new policy; it stitches locked decisions from §3, §5, §6, §11, §12, §13 into a launch-specific narrative that reaches §15 and §1.

### Inherited locks

- **§5.4 phase map (locked):** P0 (M0 validation) → P1 (M1–M2 soft) → P2 (M3–M4 v1 public) → P3 (M5–M7 stabilization) → P4 (M8–M9 v2 prep) → P5 (M10–M12 Desk Full launch) → P6 (post-M12 v2 stabilization).
- **§5.4.4 phase-gate triggers:** explicit reversion conditions per phase boundary.
- **§14 six stop-the-line conditions** (locked across multiple decision-log entries): cohort drawdown, vendor outage, regulatory event, billing disputes, engine bug, persona invalidation. Plus §13 conditional-escalation red-line on cohort gate-rejection acceptance.
- **§13 Q1 OKRs:** validation pass + soft cohort fill + persona validation + zero stop-the-line.
- **§6.6 founder-cohort pricing window:** first 60 days post-public-launch (P2). Locked through one renewal cycle.
- **§5.4.7 execution-resource flag:** P4 contractor support included per locked Scenario 3.

### What §14 adds beyond consolidation

- **Phase 1 (P0–P1) calendar date locks** — converting M0/M1/M2 indices to actual May/Jun/Jul 2026 dates so external commitments can be made.
- **Launch comms plan** — the only genuinely new content in §14. Maps audiences × channels × phases.
- **§5 roadmap items mapped to launch comms** — what gets announced when.

---

## 14.1 Phase progression with go/no-go gates

Each phase has explicit *entry gate* (must clear to enter) and *exit gate* (must clear to advance). Failure to clear an exit gate either extends the phase or reverts to a prior phase.

| Phase | Window | Entry gate | Exit gate | KPI signal source |
|---|---|---|---|---|
| **P0 Validation** | May 2026 (M0) | Already active | §8 Capital Cap criteria met + cohort drawdown within thresholds + zero engine-bug kill-switch triggers | §13.3 O1 KRs |
| **P1 Soft launch** | Jun–Jul 2026 (M1–M2) | P0 exit gate cleared | 30-day soft-cohort floor + zero §14 stop-the-line + IB items at "stabilizing-acceptable" maturity | §13.3 O2/O4 KRs |
| **P2 v1 public launch** | Aug–Sep 2026 (M3–M4) | P1 exit gate cleared | Trader stable in market + first §3.7/§3.8 data lands + Desk Preview opens | §13.3 O3 + cohort metrics |
| **P3 v1 stabilization** | Oct–Dec 2026 (M5–M7) | P2 exit gate cleared | All Trader-floor IB items cross to VTN + §3 v1.1 published + §11 model reconciled to actuals | §13.6 model variance |
| **P4 Desk Full prep** | Jan–Feb 2027 (M8–M9) | P3 exit gate cleared | Three RM → IB items cross (multi-account dashboard, audit-grade exports, role-based seats) | §5.4 capability flow |
| **P5 Desk Full launch** | Mar–May 2027 (M10–M12) | P4 RM → IB items cross IB → VTN | Desk Full opens; Preview users migrate; full P3 acquisition opens | §13.4 cohort migration metrics |
| **P6 v2 stabilization** | post-M12 | Desk Full open | All v2 commitments stable; Vendor Phase 2 integration begins | §13.6 quarterly review |

### Go/no-go gate decision protocol

- **At each phase boundary**, founder reviews exit gate criteria against §13 KPI feeds.
- **All criteria green:** phase advances.
- **One or more yellow:** investigation; founder decides to extend phase or accept and advance.
- **Any red (stop-the-line condition):** phase holds; revert to investigation.
- **Decision recorded** in `_decisions/decision-log.md` with date and KPI snapshot.

---

## 14.2 Stop-the-line conditions (consolidated)

Seven conditions total — six §14 stop-the-line + one §13 conditional-escalation red-line.

| # | Condition | Source | Action |
|---|---|---|---|
| 1 | Cohort drawdown exceeds §8 thresholds at cohort level | §13.4 risk KPI | Halt; investigate engine + cohort behavior; revert to validation if structural |
| 2 | Vendor outage (P1 stack) >24h with no failover | §13.4 risk KPI | Halt; activate manual failover; reassess vendor SLA |
| 3 | Regulatory event in UAE/MENA touching virtual-asset advisory framing | Manual + legal monitoring | Halt; legal review; revisit jurisdictional posture |
| 4 | Billing/refund disputes >5% of soft-cohort users | §13.4 risk KPI | Halt new signups; investigate root cause; refund policy review |
| 5 | Critical engine bug (gate-failure / position-sizer / kill-switch malfunction) | Engine error logs | Halt trading; engine fix priority over launch progression |
| 6 | Persona invalidation — §3 v1.1 *replaces* (not refines) a persona | §3.8 cohort grid + §3.7 interview validation | Halt public-launch comms; rewrite §9 messaging matrix; restart with v1.1 personas |
| **§13 red** | Cohort gate-rejection acceptance <50% across cohort | §13.4 weekly | Investigate cause. If structural ICP-mismatch → escalate to §14 stop-the-line; if tunable → fix and continue |

**Recovery from stop-the-line:**

- Each condition has a documented recovery path in §10 ops runbooks (when drafted).
- Recovery time depends on root cause. Some conditions (vendor outage) clear in days; others (regulatory event, persona invalidation) extend the phase by weeks or longer.
- Public communication during stop-the-line must follow §14.3 launch comms plan — never silent.

---

## 14.3 Launch comms plan

### Audience matrix

| Audience | Channels | Cadence | Tone register |
|---|---|---|---|
| Founder cohort (validation + soft-cohort users) | Direct (Telegram, email) | Weekly during P0–P1; monthly post-P2 | Product-tier — technical, specific, honest |
| Public (potential users) | X, Substack, Telegram channel, LinkedIn | Continuous content; phase-launch announcements | Product-tier on web; social-tier on X/Threads/Telegram per locked register |
| MENA regional network | Closed Telegram, WhatsApp, regional events (Token2049, Dubai Fintech) | Phase-launch announcements + relationship-driven | Product-tier with MENA framing |
| Investors / advisors | Email + monthly report | Monthly + ad-hoc on milestones | Product-tier with §15 narrative discipline |
| Press | Skipped at v1; revisit at P5 Desk Full launch | n/a (P0–P4) | n/a |

### Phase-launch comms

**P0 → P1 (Validation pass → Soft launch announcement).**

- *Founder cohort:* "Validation phase complete. Soft launch opens {date} with founder-cohort pricing. You're invited."
- *Public:* short post on X + Substack: "30-day validation cohort closed. Here's what we learned. Soft launch invite-only; waitlist open at {URL}."
- *Investors:* milestone email — validation summary, soft cohort plan, P2 target window.
- *MENA network:* warm intros to known disciplined-trader contacts.

**P1 → P2 (Soft launch → Public launch announcement).**

- *Public:* full launch — Substack post, X thread, Telegram channel announcement, LinkedIn post. Founder-cohort window framing ("first 60 days, 25–30% off").
- *Founder cohort:* "Public launch live. Your founder-cohort pricing locks at next renewal."
- *MENA network:* phase announcement at any active regional event in window.
- *Investors:* milestone email — public launch summary, cohort traction, M3–M4 outlook.

**P2 → P3 (v1 public → stabilization, no public announcement).** Internal phase shift; external comms continue at content cadence.

**P3 → P4 (no public announcement).** Internal phase. Investors get monthly update; founder cohort gets quarterly.

**P4 → P5 (Desk Full v2 launch announcement).**

- *Public:* full launch — Substack post, X thread, LinkedIn post, regional event announcement if available. "Desk Full v2 ships {date}. Persona 3 buyers off the waitlist; Preview users migrate."
- *Desk Preview cohort:* in-app + email notification with migration pathway.
- *Investors:* milestone email — Desk Full v2 launch, migration cohort metrics, v2 ARR ramp.
- *Press:* consider press release / interviews at this milestone — Desk Full launch is the v2 narrative anchor.

**P5 → P6 (no public announcement).** Internal stabilization.

### Stop-the-line comms

When any §14 stop-the-line fires:

- **Within 24 hours:** internal team / contractor cohort notified.
- **Within 72 hours:** founder cohort users notified directly. Honest framing: "We've paused {launch action} because {brief explanation}. Here's what we're doing about it. Your account is unaffected." No marketing-tier softening of bad news.
- **Within 7 days:** public update if event is material — tone: matter-of-fact, no over-explaining, no defensive.
- **Investors:** notified at next monthly cadence + ad-hoc if event is severity-1.
- **Recovery announcement:** honest summary of what happened, what changed, what we're now confident about.

### Content cadence (continuous, not phase-tied)

- **Substack:** 1–2 posts per month. Methodology-focused content (regime classifier, position sizing, gate logic). Lands with P1 and P2 personas primarily.
- **X / Twitter:** 3–5 posts per week. Mix of methodology threads and product updates. Includes social-tier posts for engagement.
- **Telegram channel:** Light cadence — phase milestones + occasional methodology snippets.
- **LinkedIn:** Monthly post. Operator-focused; lands with P3 and MENA founder networks.

---

## 14.4 Phase 1 date locks

P0 and P1 dates locked; P2+ dates remain gate-driven targets.

| Phase | Locked dates | Status |
|---|---|---|
| **P0 Validation** | May 1, 2026 — May 31, 2026 (M0; 30-day cohort) | LOCKED. Already active. |
| **P0 → P1 transition** | June 1, 2026 (target; gate-driven) | TARGET. §8 criteria pass required; stop-the-line clean required. |
| **P1 Soft launch** | June 1, 2026 — July 31, 2026 (M1–M2; 60-day window) | LOCKED for entry; 30-day floor + extensions per stop-the-line. |
| **P1 → P2 transition** | August 1, 2026 (target; gate-driven) | TARGET. Soft cohort exit gate must clear. |
| **P2 v1 public launch** | August 1, 2026 — Sep 30, 2026 (M3–M4) | TARGET window. |
| **Founder-cohort pricing window** | Aug 1, 2026 — Sep 30, 2026 (60 days post-public-launch) | LOCKED to P2 calendar. |
| **P2 → P3 transition** | October 1, 2026 (target) | TARGET. |
| **P3 v1 stabilization** | Oct 2026 — Dec 2026 | TARGET. |
| **P4 Desk Full prep** | Jan 2027 — Feb 2027 | TARGET. |
| **P4 → P5 transition** | March 2027 (target) | TARGET. |
| **P5 Desk Full launch** | March 2027 — May 2027 (M10–M12) | TARGET. |
| **P6 v2 stabilization** | post-May 2027 | OPEN. |

**Calendar fragility note.** P0 and P1 are locked because we're already inside or starting them. Everything from P2 onward is gate-driven; if exit gates don't clear, the calendar slips. §13 KPI cadence catches slip risk early.

---

## 14.5 §5 roadmap items mapped to launch phases

§5.4 capability flow translated into "what announcement category each item enables":

| Capability | Maturity at launch event | Comms relevance |
|---|---|---|
| Engine API endpoints (VTN) | Available P0+ | Foundation; not a launch headline |
| Dashboard live signal feed | IB → VTN target M5–M7 | P2 launch — "stabilizing in cohort" framing in announcement |
| Risk gate configurator | IB → VTN target M5–M7 | P2 launch — featured in copy |
| Performance journal UI | IB → VTN target M5–M7 | P2 launch — featured in copy; v1.1 R-multiples after observed data |
| Cohort drawdown chart | IB → VTN target M3–M5 | P2 launch — risk-side hero copy |
| Static monthly PDF report | IB → VTN target M3–M5 | P2 launch — Desk Preview headline feature |
| Multi-account dashboard | RM → IB target M8 | P5 Desk Full launch headline |
| Audit-grade journal export | RM → IB target M8 | P5 Desk Full launch headline |
| Role-based access (seats) | RM → IB target M9 | P5 Desk Full launch headline |
| LP-style book-level gates | v3-deferred | Not on this roadmap; mention only as forward direction |
| Tax-ready exports | v3-deferred | Not on this roadmap |
| Custom-rule backtester | v3-deferred | Not on this roadmap |
| Arabic-language UI | v3-deferred | Not on this roadmap; surface as direction in MENA comms |

### Comms anti-pattern to avoid

Per §5.5 audit and §6.10 audit: **never market v3-deferred features as v2.** §14 launch comms inherits this constraint. Specifically at P5 Desk Full launch: announcement copy must not include LP-style gates or tax-ready exports as v2 ship items.

---

## 14.6 Anti-overclaim audit on §14

Audit performed against §14.0 through §14.5 on 2026-05-01.

### Flags applied (documentation)

**Flag 1 — Calendar dates beyond P1 are targets, not commitments.**

Risk: external comms quoting "August 2026 public launch" creates expectation. §14.4 explicitly labels P2+ as "TARGET," but downstream comms (§15 deck, X posts) may compress this to definite dates.

*Mitigation:* §15 narrative inherits "target window" framing; X posts use "we're aiming for {month}" rather than "we launch on {date}." If asked specifically, founder commits only to P0 + P1 dates.

**Flag 2 — Stop-the-line comms must avoid defensive framing.**

The "matter-of-fact, no over-explaining, no defensive" tone is locked, but stop-the-line events are stressful and tone tends to drift apologetic or evasive. Founder must enforce the locked register.

*Mitigation:* §14.3 stop-the-line section explicitly carries the tone constraint. §10 ops runbook (when drafted) includes a sample stop-the-line announcement template.

**Flag 3 — Press skipped at P0–P4 is a deliberate non-decision.**

Some founders pursue press at every milestone. We skip until P5 Desk Full launch because (a) early-stage press carries no benefit before validated traction, (b) press cycles are slow and predictable, and (c) MENA-specific press is more relationship-driven than pitch-driven.

*Mitigation:* §14.3 explicitly notes "skipped at v1; revisit at P5." Investors who ask about press strategy can be told the rationale.

### What §14 audited clean

- Phase definitions and gates traceable to §5.4.
- Stop-the-line conditions all map to §13 KPI feeds.
- Launch comms plan respects the product-tier / social-tier register split per locked brand voice.
- §5 roadmap items mapped without v3-deferred features marketed as v2.
- Phase 1 date locks are calendar-realistic (M0 already active, M1 starts June 2026).

### §14 v1 LOCKED

§14.0 through §14.6 all committed.
