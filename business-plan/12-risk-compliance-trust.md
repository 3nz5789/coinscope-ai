# §12 Risk, Compliance, and Trust Model

**Status:** v1 LOCKED. Risk register consolidates inherited concerns from §3, §6, §7, §10, §11, §15, §16 plus §2.4 slower-burn risks. 41 entries across 7 categories.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active. Anti-overclaim discipline applied — no probability percentages assigned (per §16 framing); risks tracked by severity + status.

---

## 12.0 Assumptions, methodology, and inheritance

### Locked from upstream

- **§16 anti-probability framing:** §12 register does not assign probability percentages. Risks are tracked by severity (impact) + status (monitoring / active / triggered / resolved).
- **§14 stop-the-line conditions** (6 + 1 §13 conditional) — §12 risks that escalate to §14 are flagged.
- **§16 contingency protocols** — regulatory shock / vendor outage / founder unavailable. §12 risks that map to contingencies cross-reference.
- **§3 / §6 / §7 / §10 / §11 / §15 documented concerns** — inherited as register entries.

### Risk register schema

Each entry:

- **ID** (R-001 through R-041).
- **Title** — short risk name.
- **Category** — one of seven (regulatory / vendor / product / founder / market / financial / brand).
- **Severity** — 1 (low) to 5 (catastrophic) on impact if triggered.
- **Status** — Monitoring (latent) / Active (signs present) / Triggered (event occurred) / Resolved.
- **Description** — what the risk is.
- **Inherited from** — upstream section reference.
- **Mitigation** — what we do to reduce probability or impact.
- **Escalation trigger** — when this becomes §14 stop-the-line or §16 contingency.
- **Owner** — who tracks this (founder / contractor / vendor / external).

### Why severity + status, not severity × probability

§16 anti-probability framing applies to scenarios; §12 inherits the same discipline. Probability framings sound precise but are inferred poorly pre-revenue. Status (Monitoring / Active / Triggered) captures the same useful information without false precision: a "Monitoring" risk could become "Active" if signs emerge; "Active" risks get more attention; "Triggered" invokes contingency or stop-the-line.

---

## 12.1 Regulatory and compliance risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-001 | MENA regulator classifies as advisory | 5 | Monitoring | VARA / ADGM / DFSA / KSA / Bahrain / Oman categorizes CoinScopeAI as virtual-asset advisory or broker requiring license sole prop can't obtain | §16 Cont. A; §2.4 trigger | Maintain regulatory monitoring (legal counsel, news subscription); preserve geo-restrict + entity-restructure + product-modification optionality | Triggered → §16 Contingency A 24h/72h/1-week protocol; §14 condition 3 |
| R-002 | Solo PM regulatory line drift | 4 | Monitoring | Desk-tier copy drifts toward fund-formation framing; users misinterpret product as fund alternative; regulatory exposure | §3.5 doc concern; §15 Flag 5 | §9.6 objection table response #6 explicit; §6.8 / §15 audit constraints; quarterly copy audit | If founder-cohort or public copy violates: immediate copy retraction + audit pass |
| R-003 | Cross-border GCC VAT complexity | 3 | Monitoring | Customer base across UAE/KSA/Bahrain/Oman triggers per-country VAT obligations once registered | §6.8 | Below UAE VAT threshold at v1 (no collection); revisit at AED 30k/mo; per-country VAT only if specifically registered there | Triggered when §11 cost-side refresh on VAT setup ($5k+ ongoing) |
| R-004 | UAE VAT registration threshold trigger | 2 | Monitoring | Annual revenue approaching AED 375k (~$102k); mandatory registration | §6.8 step-function | Track monthly MRR against threshold; founder-time prep ~6 weeks before trigger; ~$2-5k setup + ~$200-500/mo ongoing | Triggered at ~$8.5k MRR; §11 cost-side refresh |
| R-005 | US-resident signup leakage | 3 | Monitoring | Geo-block at signup fails; US user enters product; regulatory exposure | §4.5 fence | Multi-layer geo-detection (IP + KYC declaration); §10 ops runbook for ban-and-refund flow | Any US-resident signup triggers immediate audit + remediation |
| R-006 | AED display implies local-entity registration | 2 | Monitoring | AED conversion at checkout misread as MENA-multi-country entity | §6.10 Flag 3 | Footer-text discipline: "Approximate AED equivalent — billed in USD. UAE sole prop"; §15 Flag 5 substantiation in due diligence | Triggered if users contest representation in support tickets |

## 12.2 Vendor and supply-chain risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-007 | CoinGlass dual customer-vendor relationship | 4 | Monitoring | We consume CoinGlass data + they sell direct to our user base; pricing change, product expansion, or partnership reframe possible | §6.1, §10.3, §15 | Quarterly relationship review; vendor-swap optionality (alternate liquidations data feed); explore partnership path if relationship reframes | API pricing >$200/mo deviation → §11 cost refresh; product expansion into our space → competitive threat reassessment |
| R-008 | P1 vendor outage (CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude) | 4 | Monitoring | Any P1 vendor experiences >24h outage with material engine impact | §16 Cont. B; §14 cond. 2 | Per-vendor failover documented in §10.3; uptime monitoring via BetterStack | >24h with no failover → §14 condition 2 fires; >5d → pro-rata refund |
| R-009 | P1 vendor pricing change | 3 | Monitoring | Vendor (especially CoinGlass) raises API tier pricing | §10.3, §11.7 Flag 6 | Quarterly cost review; vendor-swap optionality; alternate-vendor evaluation | >$200/mo deviation → §11 cost-side refresh; >$500/mo → vendor swap evaluated |
| R-010 | Tradefeeds integration still STN | 3 | Active | Per Rule A downgrade, Tradefeeds is at IB; integration may not cross to VTN at expected pace | §5.1 | §13.4 vendor uptime monitoring; alternate sentiment-data provider scouted | If Tradefeeds fails to cross IB→VTN by P3 end → drop sentiment input from regime classifier; replace |
| R-011 | Stripe processing fees underestimate | 2 | Monitoring | International cards + AED FX margin may exceed 3.5% blended assumption | §11.7 Flag | Quarterly Stripe fee actuals review; fee-blend recalibrated in §11 | If actual >4.5% blended → §11 cost-side refresh; consider Paddle merchant-of-record |
| R-012 | Vendor Phase 2 evaluation/integration cost | 2 | Monitoring | P3-evaluation deferred-to-P6 integration timing slips or costs exceed estimate | §5.4.3 | Vendor Phase 2 timing gate-driven not calendar-locked; evaluation cheap; integration deferred to P6 | Pull-forward only if base case turns to bull; otherwise sustain P1 stack |

## 12.3 Product and engine risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-013 | Engine bug — gate failure / position sizer / kill switch | 5 | Monitoring | Critical engine bug compromises capital-preservation primitives | §14 cond. 5 | Engine validation phase ongoing; comprehensive test suite; audit log for every engine decision; §10.2 incident-response runbook | Sev-1 incident → §14 condition 5 fires; engine paused; founder cohort notified |
| R-014 | Cohort drawdown spike beyond §8 thresholds | 5 | Monitoring | Cohort-level drawdown exceeds documented Capital Cap criteria | §14 cond. 1 | §13.4 daily monitoring during validation; weekly post-launch; engine kill-switch enforces user-level thresholds | Triggered → §14 condition 1; halt paid acquisition; investigate root cause |
| R-015 | Cohort gate-rejection acceptance <50% | 4 | Monitoring | Users override gates >50% of the time; capital-preservation principle not landing | §13 conditional red-line | Investigate cause: tuning / recruiting drift / UX / fundamental ICP mismatch | Structural ICP mismatch only → §14 stop-the-line; tunable causes handled via iteration |
| R-016 | Persona invalidation — §3 v1.1 replaces persona | 4 | Monitoring | §3.7 + §3.8 data shows a locked persona is wrong, not just refined | §14 cond. 6 | §3.7 interview validation in flight; §3.8 cohort behavioral grid measures | Replacement → §14 condition 6; halt public-launch comms; rewrite §9 messaging matrix |
| R-017 | Validation cohort demonstrates marginal/zero edge | 5 | Monitoring | Net cohort performance after risk gating is negative or zero — thesis intact, demonstration fails | §2.4 cross-cutting | Validation phase active; engine + cohort instrumentation tracking | Triggered → company-survival mode; §11 model refresh; pricing review; possible §3 re-cut |
| R-018 | Trader-floor IB items fail to cross VTN by P3 end | 3 | Monitoring | Dashboard live signal feed, regime visualization, gate configurator, journal UI fail to mature in P3 | §5.4.4 P3→P4 gate | Soft-cohort observation in §3.8 produces VTN graduation evidence; engineering capacity allocated | Triggered → P3 extends; P4 prep delays; §11 timeline refresh |
| R-019 | Desk Full v2 RM→IB items slip | 3 | Monitoring | Multi-account dashboard, audit-grade exports, role-based seats fail RM→IB transition by M9 end | §5.4.4 P4→P5 gate | §5.4.7 P4 contractor scenario funded; §11 contractor cost included; weekly status review | Slip >30 days → P5 launch slips; v2 launch comms updated |

## 12.4 Founder and key-person risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-020 | Founder unavailable >2 weeks | 5 | Monitoring | Illness, family event, personal emergency disrupts solo-founder operations | §16 Cont. C | Emergency-contact protocol; engine documentation accessible to skilled engineer with 1-week handover; engineering, vendor, billing credentials in encrypted vault | Triggered → §16 Contingency C protocol (1-week / 4-week phases) |
| R-021 | Solo execution risk at P4 (highest engineering load) | 4 | Active (mitigated) | P4 multi-account + audit-grade + seats build concurrent; founder solo can't do all three | §5.4.7 | 2 engineering contractors funded for ~3 months at $48k spike; founder retains overall ownership | If contractors not engaged by M7 → P4 timeline slips; revise §5.4.7 scenario down to 1 contractor or extend window |
| R-022 | Founder time scarcity — content + ops + engineering tradeoffs | 3 | Active | GTM time allocation (60/25/10/5 steady state) competes with engineering and ops | §7.2 phased GTM | Phased GTM allocation overlay (P0–P5); contractor support frees engineering time at P4; weekly time tracking in §13.5 reporting | If content cadence lags >30% for 2 consecutive weeks → review GTM allocation; consider contractor support |
| R-023 | Engineering documentation insufficient for handover | 4 | Monitoring | If founder unavailable, documentation gap blocks emergency-contact engineer | §16 Cont. C mitigation gap | Quarterly documentation audit; runbooks in Notion; secrets vault accessible | Triggered if §16 Contingency C activates and handover blocked → emergency-contact escalation; manual operation continues |

## 12.5 Market and competitive risks (§2.4 watchable, slower-burn)

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-024 | Force 1 cycle regression | 3 | Monitoring | Disciplined-trader preference reverses in next bull leg; YOLO returns to favor | §2.4 watchable | §3.7 unprompted-discipline language tracking; cohort retention curves observed | If unprompted-discipline rate drops sustainedly → §2 thesis re-evaluation; §11 model refresh |
| R-025 | Force 2 incumbent bundling | 4 | Monitoring | TradingView / Bybit / OKX / Binance ships free AI quant copilot in our space | §2.4 trigger | Quarterly competitive scan; differentiation through methodology transparency, capital-preservation positioning, MENA-rooted | 3+ credible MENA-or-global-EN AI quant tools with capital-preservation framing in 12 months → §2 thesis re-evaluation |
| R-026 | Force 2 OSS displacement | 2 | Monitoring | High-quality OSS crypto-perp quant framework matures; absorbs paid-tool demand | §2.4 watchable | Differentiation through trust + ops discipline; engine value beyond methodology code | Trigger to revisit if OSS framework gains 10k+ stars + active community |
| R-027 | AI-trading category trust collapse | 4 | Monitoring | High-profile AI trading tool blow-up (rugpull / fabricated track record / catastrophic losses) taints category | §2.4 watchable | Anti-overclaim discipline; methodology transparency; full-cohort backtest disclosure separate us from category-norm | Industry incident → category-wide messaging recalibration; §15 narrative re-framing |
| R-028 | Prop firm becomes direct competitor | 3 | Monitoring | Prop firm (FTMO, Apex, Topstep) launches its own AI quant copilot bundled with funded accounts | §2.7 trigger | Partnership pathway open; direct-competitor fallback if needed | Move from parallel to direct → §2.7 + §8 partnership long-list re-evaluated |

## 12.6 Financial and operational risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-029 | Free → Trader conversion below 3% downside | 4 | Monitoring | Highest-impact §11.6 sensitivity input ($700k swing on M24 ARR) | §11.6 | §3.7 interview validation; §3.8 cohort observation; §13 weekly conversion tracking | <3% sustained → §16 bear-case trigger; §11 model refresh |
| R-030 | Per-seat density at Desk Full v2 below 1.5/2.0 downside | 3 | Monitoring | P3 cohort thinner than expected; seat-additions don't materialize | §11.6 | Time-varying base case (2.0 early / 2.5 mature) accommodates lower early density; §13 KPI tracking | <1.5 average → §11 ARPU refresh; §15 narrative recast for P3 |
| R-031 | Desk Preview → Desk Full migration <50% | 3 | Monitoring | v2 migration rate below downside scenario | §11.6 | §13 KPI tracking; Preview-to-Full incentive (first-look pricing); migration discount | <50% sustained → §16 bear-case trigger; v2 launch comms recalibrate |
| R-032 | Founder cost reality vs. $7k/mo implicit | 3 | Active | Founder draws actual cash <$7k/mo; model cash-burn line vs. fully-loaded P&L diverges | §11.7 Flag 4 | Two views in xlsx (cash-burn vs. fully-loaded); investor narrative fully-loaded; runway calc cash-burn | Sustained divergence → §11 v1.1 refresh with both views explicit |
| R-033 | Vendor cost variance >$200/mo from baseline | 2 | Monitoring | P1 stack pricing changes accumulate beyond baseline | §10.3, §11.7 Flag 6 | Quarterly vendor cost review; alternate-vendor evaluation | Sustained >$200/mo → §11 cost-side refresh |
| R-034 | Tenure assumptions benchmarked, not observed | 3 | Active | Trader 1.78yr / Preview 2.32yr / Desk Full 3.4yr tenure assumptions are `B` benchmarked, no `O` observed yet | §11.7 Flag 2 | First observed values at M12+ for Trader; §3.8 cohort retention measurement | Observed retention <50% of benchmark → LTV/CAC refresh; §15 narrative recasting |
| R-035 | Marketing budget run rate exceeds $60k M1–M12 plan | 2 | Monitoring | CAC inflates beyond §11.5 base bands; spend exceeds budget | §11.5 | Paid acquisition trigger (M5+ + Trader CAC <$200) gates spend; quarterly review | >$60k actual → §11 cost-side refresh; paid acquisition reduction or targeting refinement |
| R-036 | VAT step-function cost trigger | 2 | Monitoring | UAE VAT registration mandatory at AED 375k threshold (~$8.5k MRR) | §6.8 | Track monthly MRR vs. threshold; ~6-week prep ahead of trigger | Triggered at ~$8.5k MRR → §11 cost-side refresh; §6.8 VAT setup |

## 12.7 Reputation and brand risks

| ID | Title | Sev | Status | Description | Inherited | Mitigation | Escalation |
|---|---|---|---|---|---|---|---|
| R-037 | Stop-the-line comms drift defensive/apologetic | 3 | Monitoring | Stress causes founder to lapse from matter-of-fact register into defensive framing during incidents | §14 audit Flag 2 | §10 incident-runbook tone constraint; sample stop-the-line announcement template in runbook | Audited per-incident; if drift detected, revise process |
| R-038 | Hero copy or marketing drifts toward "alpha" framing | 4 | Monitoring | Brand voice slips; capital-preservation positioning weakens | §9 prohibitions | §9 audit; weekly content review per §9.7; §13 weekly internal report content compliance check | Drift detected → immediate copy retraction; founder voice review |
| R-039 | Founder-cohort pricing drifts to "lifetime" framing | 3 | Monitoring | Marketing language implies permanent founder-cohort discount despite §5.3.5 time-bound | §9.6, §15.8 Flag 4 | Locked language: "founding-member pricing — locked through your first renewal cycle, then standard pricing applies" | Drift detected → copy retraction |
| R-040 | v3-deferred features marketed as v2 in any audience deck | 3 | Monitoring | Audience-variant Slide 5 (Product Detail) drifts; LP-style gates / tax exports / multi-strategy isolation appear in v2 framing | §5.5, §6.10, §15.8 Flag 1 | §15.8 audit constrains; per-audience deck review pre-circulation; quarterly audit | Drift detected → audience deck retracted from circulation; audit pass |
| R-041 | LTV/CAC ratios overstated without dual-view | 3 | Monitoring | §15 deck or due-diligence quotes only base CAC ratios (13–26×); founder-time-honest CAC view (5–10×) omitted | §11.7 Flag 1, §15.8 Flag 3 | Both views shown in §15.5 Slide 7 + §15.6 one-pager + §15.7 email blurb (Global VC variant) | Drift detected → corrective re-statement; audit pass |
| R-042 | MENA-built claim challenged in due diligence | 3 | Monitoring | "MENA-rooted" / "UAE-built" claim requires specific named relationships, not generic assertion | §7.6, §15.8 Flag 5 | Due-diligence Q&A prepared with named MENA contacts (with permission); UAE-resident posture documented | Challenge surfaces → strengthen substantiation; revise §15.8 prep |

---

## 12.8 Risk monitoring cadence

### Weekly (per §13.5 reporting)

- §13.4 risk KPIs (cohort drawdown, gate-rejection, kill-switch activations, vendor uptime, override attempts).
- Stop-the-line state (zero / yellow flag / red flag per §14 condition).
- Top-3 active risks reviewed; status changes logged.

### Monthly (stakeholder report)

- Full register status review.
- Sev-4+ risks reviewed in detail; mitigation effectiveness assessed.
- Slower-burn risks (§12.5) — competitive scan + cycle indicators tracked.

### Quarterly

- Full register audit; new risks added; resolved risks archived.
- Mitigation effectiveness reviewed against actuals.
- §11 model refresh against materialized risks.

### Triggered (event-driven)

- Any §14 stop-the-line condition fires → contingency-protocol invoked + risk register entry status update.
- §16 contingency triggered → 24h / 72h / 1-week protocol execution.

---

## 12.9 Anti-overclaim audit on §12

Audit performed against §12.0 through §12.8 on 2026-05-01. Three flags considered.

### Flags applied

**Flag 1 — Severity ratings are subjective.**

Sev-1 to Sev-5 ratings reflect founder judgment, not statistical validation. R-013 (engine bug) and R-014 (cohort drawdown) at Sev-5 reflect catastrophic-impact-if-triggered framing; lower-severity ratings on others reflect lower-impact-if-triggered.

*Mitigation:* Severity ratings reviewed quarterly; refined based on actuals. Cross-check via §16 scenario severity (bull/base/bear M24 ARR ranges) to validate consistency.

**Flag 2 — Status tracking ("Monitoring" vs. "Active") replaces probability.**

Per §16 anti-probability framing, §12 doesn't assign percentages. "Monitoring" = latent; "Active" = signs present; "Triggered" = event occurred. This loses some precision (a high-likelihood "Monitoring" risk reads same as low-likelihood) but preserves anti-overclaim discipline.

*Mitigation:* Active / Monitoring distinction surfaced in weekly report — keeps high-attention risks visible without faux-probability precision.

**Flag 3 — Some risks may be missing from the register.**

41 entries cover known concerns from upstream sections, but emergent risks not yet surfaced are by definition not in the register.

*Mitigation:* Quarterly register audit explicitly probes for emergent risks. §13 cohort behavioral signals + §3.7 interview data + competitive scan all feed new entries.

### What §12 audited clean

- Each risk traceable to upstream section reference.
- §14 stop-the-line conditions all have feeding §12 entries.
- §16 contingency protocols all have §12 entries flagged for trigger.
- Mitigation paths reference locked decisions (no invented mitigations).
- Owner column reflects realistic accountability (founder primary; vendor/external where applicable).
- Severity ratings consistent with §11 financial impact framing.

### §12 v1 LOCKED

§12.0 through §12.9 all committed. Risk register live in `_data/risk-register.md` (per §0.5 folder structure when populated as working artifact). Quarterly audit cadence locked.
