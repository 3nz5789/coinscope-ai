# CoinScopeAI — Business Plan Framework

**Owner:** Mohammed (Founder)
**Author:** Scoopy (operating agent)
**Status:** Draft framework — locks the structure; section content drafted in subsequent passes
**Last updated:** 2026-05-01
**Disclaimer:** Testnet only. 30-day validation phase. No real capital.

---

## 0. Preamble

### 0.1 Purpose

This document defines the structure, dependencies, deliverables, and working order for the CoinScopeAI business plan. It is a *framework*, not the plan itself. Each numbered section below points to a future artifact; this file governs how those artifacts are produced, in what order, and how they connect.

### 0.2 Operating principles applied to this plan

The plan inherits the four product-tier voice principles and the capital-preservation-first stance. In practice that means:

- Anti-overclaim. No "production-ready" claim until §8 Capital Cap criteria are met.
- Explicit assumptions before every claim. Every section opens with an Assumptions block.
- Risk-first. §12 (Risk, Compliance, Trust) is treated as a peer to §5 (Product), not a footer.
- Methodical & evidence-led. Every quantitative claim cites the model, dataset, or memory it came from.

### 0.3 Task naming convention

Each task uses: `[TYPE] [AREA] — Action / Deliverable`

Types: `RESEARCH`, `ANALYSIS`, `DECISION`, `DRAFT`, `REVIEW`, `FINALIZE`, `INTEGRATE`
Areas: `EXEC`, `MARKET`, `ICP`, `PROD`, `PRICE`, `GTM`, `SALES`, `BRAND`, `OPS`, `FIN`, `RISK`, `KPI`, `LAUNCH`, `INVEST`, `SCEN`

Example: `[DRAFT] [PROD] — Tier matrix v1 (Free / Trader / Desk / Fund)`

### 0.4 Status legend

`PROPOSED` → `IN-PROGRESS` → `BLOCKED` → `READY-FOR-REVIEW` → `LOCKED`. Locking requires founder sign-off and a dated decision-log entry.

### 0.5 Cross-cutting constraints (apply to every section)

- Jurisdictional: UAE-first sole prop; target UAE/MENA + global EN; US blocked at signup.
- Engine: leverage cap 10x (not 20x); risk thresholds per `coinscopeai-trading-rules`.
- Vendor stack: Phase-1 narrow (CCXT 4-ex, CoinGlass, Tradefeeds, CoinGecko, Claude minimal). P2/P3 layer on after validation passes.
- Validation: claims gated to testnet behavior + the active 30-day cohort.

---

## 1. Executive Summary

### Why it matters for CoinScopeAI

The exec summary is the only artifact most readers will finish. It must restate vision, mission, validation posture, and ask in under one page without overclaiming. Because we are pre-revenue and testnet-only, the wording here sets the tone for whether readers treat us as serious or as another retail bot.

### Output artifact

`01-executive-summary.md` (≤1 page, also rendered as a one-pager PDF in `_assets/`).

### Main decisions

- Single sentence positioning (lock from `project_vision_mission`).
- The "ask" framing: pilot users vs. capital vs. partner exchanges.
- Whether to disclose validation-phase status in the first paragraph (recommended: yes).

### Tasks

- `[DRAFT] [EXEC] — Skeleton (problem, solution, traction, ask) v0`
- `[INTEGRATE] [EXEC] — Pull locked vision/mission from memory`
- `[REVIEW] [EXEC] — Anti-overclaim sweep against §0.2`
- `[FINALIZE] [EXEC] — Lock after §11, §13, §14 are locked`

### Dependencies

Inbound: §2, §3, §4, §5, §11, §13, §14, §15.
Outbound: none — terminal section.

### Within-section order

1st: skeleton; 2nd: integration; 3rd: lock (last).

---

## 2. Market Thesis

### Why it matters for CoinScopeAI

Defines *why this product, why now*. Crypto-perp retail is saturated with signal sellers and copy-trade tools; our thesis must explain why a capital-preservation-first quant framework is differentiated and durable through cycles. This is the analytical foundation everything else inherits.

### Output artifact

`02-market-thesis.md` plus supporting research in `_data/market-thesis-research.md`.

### Main decisions

- Time horizon of the thesis (3y default).
- Which structural shifts we anchor to (regulatory clarity, exchange consolidation, AI-native tooling).
- Position relative to copy-trading, signal groups, retail terminals, and prop firms.

### Tasks

- `[RESEARCH] [MARKET] — TAM/SAM/SOM model for crypto-perp retail + small-fund tooling`
- `[RESEARCH] [MARKET] — Cycle analysis: retention of trading-tool users across 2017/2021/2024 cycles`
- `[ANALYSIS] [MARKET] — Structural shifts thesis (3 forces)`
- `[DRAFT] [MARKET] — Thesis v1 with cited inputs`
- `[REVIEW] [MARKET] — Stress-test thesis against bear-cycle scenarios`

### Dependencies

Inbound: none (foundational).
Outbound: §3, §4, §5, §15, §16.

### Within-section order

1st: TAM/SAM/SOM; 2nd: structural shifts; 3rd: thesis draft.

---

## 3. ICP and Customer Segmentation

### Why it matters for CoinScopeAI

Wrong ICP = wrong product, wrong pricing, wrong channels. Two distinct buyers exist — disciplined retail traders and small funds/family offices — and they require different surfaces, comms, and trust artifacts. We need to declare them explicitly.

### Output artifact

`03-icp-segmentation.md` with persona cards and segment scorecards.

### Main decisions

- Primary ICP vs. secondary ICP (recommended primary: disciplined retail trader, $5k–$250k account, MENA/EN).
- Segments we explicitly *will not* serve (e.g., gamblers, US-resident retail).
- Buying triggers per segment.

### Tasks

- `[RESEARCH] [ICP] — Interview/observation log: 10+ target users (Telegram, X, Discord, founder network)`
- `[ANALYSIS] [ICP] — Segment matrix (size, account size, jurisdiction, sophistication, willingness-to-pay)`
- `[DRAFT] [ICP] — Persona cards (3 primary + 2 anti-personas)`
- `[DECISION] [ICP] — Lock primary ICP + anti-ICP list`
- `[REVIEW] [ICP] — Validate against jurisdictional posture (US blocked)`

### Dependencies

Inbound: §2.
Outbound: §4, §5, §6, §7, §9, §13.

### Within-section order

1st: research; 2nd: matrix; 3rd: persona lock.

---

## 4. Problem Statement and Value Proposition

### Why it matters for CoinScopeAI

We must articulate the problem in the customer's words, not ours, then prove the value prop is *capital preservation first*, not yet another alpha promise. The phrasing here directly drives §9 messaging and §15 investor narrative.

### Output artifact

`04-problem-value-prop.md` including a value-prop canvas per persona.

### Main decisions

- The single problem we lead with (recommended: "retail blows up accounts faster than they generate alpha").
- The 3 proof points we surface (regime detection, risk gate, position heat cap).
- What we explicitly do *not* solve (we are not a fund, not a copy-trade signal, not financial advice).

### Tasks

- `[RESEARCH] [ICP] — Pain-point ranking from §3 interviews`
- `[DRAFT] [PROD] — Value-prop canvas per primary persona`
- `[DRAFT] [BRAND] — Problem statement (≤2 sentences) and lead value prop (≤1 sentence)`
- `[REVIEW] [RISK] — Anti-overclaim sweep on every value claim`
- `[FINALIZE] [PROD] — Lock problem + value prop pair`

### Dependencies

Inbound: §2, §3.
Outbound: §5, §6, §7, §9, §15.

### Within-section order

1st: pain-point ranking; 2nd: canvas; 3rd: lock.

---

## 5. Product Strategy and Packaging

### Why it matters for CoinScopeAI

The engine is the product, but the *packaging* is what users buy. Tiering decisions here cascade into pricing, GTM, ops load, and investor unit economics. Packaging must respect the validation phase: no tier should imply more readiness than we can defend.

### Output artifact

`05-product-strategy.md` plus a tier matrix (`_assets/tier-matrix.md`) and a roadmap (`_assets/product-roadmap.md`).

### Main decisions

- Tier count and naming (recommended: Free / Trader / Desk / Fund — names provisional).
- What sits in each tier (signals view, journal, scan limits, regime label depth, position-sizer access, API).
- What is *gated* by validation passing vs. shipped pre-validation.
- Hosted dashboard vs. Telegram-first delivery for Tier 1.

### Tasks

- `[ANALYSIS] [PROD] — Capability inventory from engine + dashboard + Telegram bot`
- `[DRAFT] [PROD] — Tier matrix v1 (4 tiers, feature gates, validation gates)`
- `[DRAFT] [PROD] — Packaging principles doc (what we never charge for, what is always behind a paywall)`
- `[DECISION] [PROD] — Tier names and order`
- `[DECISION] [PROD] — Pre-validation tier vs. post-validation tier`
- `[DRAFT] [PROD] — 12-month product roadmap aligned to phased vendor rollout`
- `[REVIEW] [RISK] — Confirm no tier markets unverified production claims`

### Dependencies

Inbound: §2, §3, §4.
Outbound: §6, §7, §9, §10, §11, §13, §14.

### Within-section order

1st: capability inventory; 2nd: tier matrix; 3rd: roadmap.

---

## 6. Pricing and Monetization

### Why it matters for CoinScopeAI

Pricing communicates positioning. Underprice and we look like a signal group; overprice and we look like a fund without the track record. Pricing also sets the financial model's revenue side, so it iterates with §11.

### Output artifact

`06-pricing-monetization.md` plus a pricing experiment log (`_data/pricing-experiments.md`).

### Main decisions

- Subscription vs. usage vs. hybrid (recommended: subscription tiered + per-seat for desks).
- Currency and jurisdiction handling (AED + USD; tax handling for UAE sole prop).
- Discounting policy and lifetime/founder offers.
- Free tier scope (lead-gen vs. permanent).

### Tasks

- `[RESEARCH] [PRICE] — Comp pricing: TradingView, 3Commas, Cryptohopper, signal-group avg, prop-firm subs`
- `[ANALYSIS] [PRICE] — Willingness-to-pay scoring per persona from §3`
- `[DRAFT] [PRICE] — Tier prices v1 (USD + AED) with rationale`
- `[INTEGRATE] [PRICE] — Plug into §11 financial model; iterate until LTV/CAC ≥ 3 in base case`
- `[DECISION] [PRICE] — Free tier scope and gate`
- `[DRAFT] [PRICE] — Discount, refund, and founder-cohort policy`
- `[FINALIZE] [PRICE] — Lock v1 prices for launch cohort`

### Dependencies

Inbound: §3, §4, §5; iterates with §11.
Outbound: §7, §11, §13, §15.

### Within-section order

1st: comp research; 2nd: WTP analysis; 3rd: lock-with-financial-model loop.

---

## 7. Go-to-Market Strategy

### Why it matters for CoinScopeAI

GTM is where most quant tools die: founders default to Twitter posting and call it a strategy. We need a channel-strategy with measurable funnels, anchored in MENA-first distribution and English global secondary, respecting US-blocked.

### Output artifact

`07-gtm-strategy.md` with channel playbooks per primary channel.

### Main decisions

- Lead-with channel (recommended: founder-led content + Telegram community).
- Paid vs. organic mix in months 1–6.
- Geographic sequencing (UAE → wider MENA → global EN).
- The "wedge" content/feature that drives top-of-funnel.

### Tasks

- `[ANALYSIS] [GTM] — Channel-fit matrix (X, Telegram, YouTube, Substack, podcasts, paid search, partnerships)`
- `[DRAFT] [GTM] — 90-day content calendar tied to validation milestones`
- `[DRAFT] [GTM] — Funnel model: visitor → free → paid, with target conversion rates`
- `[DECISION] [GTM] — Lead-with channel + secondary channel`
- `[DRAFT] [GTM] — Community strategy (Telegram-first; Discord deferred)`
- `[REVIEW] [GTM] — Confirm geo-sequencing matches jurisdictional posture`

### Dependencies

Inbound: §3, §4, §5, §6, §9.
Outbound: §8, §10, §11, §13, §14.

### Within-section order

1st: channel-fit matrix; 2nd: lead-with decision; 3rd: 90-day calendar.

---

## 8. Sales and Partnerships

### Why it matters for CoinScopeAI

For Trader-tier we are self-serve; for Desk-tier (Preview at v1, Full at v2) we are sales-assisted. Partnerships (exchanges, prop firms, education brands) can compress CAC dramatically if scoped right. (Fund-tier dropped per §5.2 lock — three-tier structure: Free / Trader / Desk.)

### Output artifact

`08-sales-partnerships.md` with a sales motion playbook and a partnership target list.

### Main decisions

- Self-serve cutoff vs. sales-assisted threshold.
- Whether to court an exchange referral deal (Binance, Bybit MENA region).
- Affiliate program scope and payout model.

### Tasks

- `[DRAFT] [SALES] — Sales-motion matrix per tier (PLG, PLS, sales-led)`
- `[DRAFT] [SALES] — Discovery → demo → close playbook for Desk` *(Fund tier dropped per §5.2 lock)*
- `[RESEARCH] [SALES] — Partnership long-list (exchanges, education, MENA influencers, prop firms)`
- `[ANALYSIS] [SALES] — Partnership scoring (reach × fit × deal complexity)`
- `[DECISION] [SALES] — Top-3 partnership targets for first 90 days`
- `[DRAFT] [SALES] — Affiliate program v1 (commission, cookie, anti-abuse)`

### Dependencies

Inbound: §3, §5, §6, §7.
Outbound: §10, §11, §13, §14.

### Within-section order

1st: sales motion; 2nd: partnership scoring; 3rd: affiliate program.

---

## 9. Brand and Messaging

### Why it matters for CoinScopeAI

Brand voice is partially locked (product-tier vs. social-tier registers). What is *not* locked: messaging hierarchy, hero copy, objection-handling, differentiator phrasing, and asset templates. These must align before §7 ships content.

### Output artifact

`09-brand-messaging.md`, a messaging matrix (`_assets/messaging-matrix.md`), and a stock-objection table.

### Main decisions

- Hero one-liner (top of funnel).
- Three pillar messages (capital preservation, regime-aware, evidence-led).
- Tone calibration per channel (web = product tier; X/Threads = social tier).
- Naming of features (do we call it Risk Gate publicly? Heat cap? Regime label?).

### Tasks

- `[DRAFT] [BRAND] — Messaging matrix (audience × stage × pillar)`
- `[DRAFT] [BRAND] — Hero copy candidates (3 variants for A/B)`
- `[DRAFT] [BRAND] — Objection table (12 common objections + responses)`
- `[DECISION] [BRAND] — Public-facing feature naming`
- `[INTEGRATE] [BRAND] — Pull locked taglines and risk-disclaimer pattern from custom instructions`
- `[REVIEW] [BRAND] — Anti-overclaim audit on every page`

### Dependencies

Inbound: §3, §4, §5; partially pre-locked via custom instructions.
Outbound: §7, §8, §15.

### Within-section order

1st: messaging matrix; 2nd: hero copy; 3rd: objection table.

---

## 10. Operations and Support Model

### Why it matters for CoinScopeAI

A risk-first product implies a risk-first ops posture: clear incident response for engine downtime, a defined SLA per tier, and a support flow that keeps Mohammed out of every ticket. This section also covers vendor management (the P1 narrow stack).

### Output artifact

`10-operations-support.md` plus runbooks in `_data/runbooks/`.

### Main decisions

- Support channels per tier (email-only Free; Telegram + email Trader; dedicated Slack Connect Desk/Fund).
- On-call coverage during validation phase.
- Vendor SLAs and fallback paths (what happens when CoinGlass or Tradefeeds is down).
- Internal tooling stack (Linear + Notion + GitHub already locked).

### Tasks

- `[DRAFT] [OPS] — Support tier matrix with response SLAs`
- `[DRAFT] [OPS] — Engine incident-response runbook (kill-switch, comms, rollback)`
- `[DRAFT] [OPS] — Vendor SLA table for P1 stack (CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude)`
- `[DRAFT] [OPS] — On-call rotation for 30-day validation cohort`
- `[INTEGRATE] [OPS] — Link to coinscopeai-platform-sync rules`
- `[REVIEW] [RISK] — Confirm runbooks pair with §12 controls`

### Dependencies

Inbound: §5, §7, §8.
Outbound: §11, §12, §13, §14.

### Within-section order

1st: support tier matrix; 2nd: incident runbook; 3rd: vendor SLAs.

---

## 11. Financial Model Assumptions

### Why it matters for CoinScopeAI

This is the spine of the investor narrative and the sanity check on §6. Assumptions must be explicit, citation-backed, and stress-testable in §16. Pre-revenue + testnet-only means we trade precision for transparency: every input is labeled as `assumed`, `observed`, or `benchmarked`.

### Output artifact

`11-financial-model.md` (the assumptions document) and `11a-financial-model.xlsx` (the live model).

### Main decisions

- Modeling horizon (24m base + 36m extended).
- Currency of record (USD primary; AED reporting view).
- CAC by channel (assumed ranges with sensitivity).
- Gross margin target (≥75% by month 12).
- Burn rate ceiling and runway floor.

### Tasks

- `[DRAFT] [FIN] — Assumptions doc v1 (every input tagged assumed/observed/benchmarked)`
- `[DRAFT] [FIN] — Revenue model (subs × tiers × cohort retention)`
- `[DRAFT] [FIN] — Cost model (vendor stack P1, infra, founder cost, future hires)`
- `[DRAFT] [FIN] — LTV/CAC model per channel`
- `[INTEGRATE] [FIN] — Iterate with §6 prices until base-case unit economics clear bar`
- `[REVIEW] [FIN] — Sensitivity table on top-5 sensitive inputs`
- `[FINALIZE] [FIN] — Lock v1 model for §15 investor narrative`

### Dependencies

Inbound: §5, §6, §7, §8, §10.
Outbound: §6 (iterative), §13, §15, §16.

### Within-section order

1st: assumptions doc; 2nd: revenue + cost models; 3rd: LTV/CAC + sensitivity.

---

## 12. Risk, Compliance, and Trust Model

### Why it matters for CoinScopeAI

A product whose first principle is capital preservation cannot afford a weak trust model. This covers regulatory exposure (UAE sole prop posture, US block, no investment advice), product trust (validation phase, kill-switch, audit log), and counterparty trust (vendor failure modes).

### Output artifact

`12-risk-compliance-trust.md` plus a risk register (`_data/risk-register.md`).

### Main decisions

- The legal-disclaimer pattern (recommended: pair every numerical claim with the testnet/30-day disclaimer).
- Whether to pursue a UAE virtual-asset advisory license (recommended: not yet; revisit at §15 fundraise).
- Audit-log retention policy.
- The "we are not a financial advisor" stance and where it lives in product.

### Tasks

- `[RESEARCH] [RISK] — UAE virtual-assets regulatory landscape (VARA, ADGM, DFSA) for our offering`
- `[DRAFT] [RISK] — Risk register (regulatory, product, vendor, founder-key-person, security)`
- `[DRAFT] [RISK] — Trust model: how users verify our claims (validation cohort, performance journal, open metrics)`
- `[DRAFT] [RISK] — Legal disclaimer placement spec`
- `[DECISION] [RISK] — License pursuit timing (now / pre-Series-A / never)`
- `[REVIEW] [RISK] — Cross-check every section's claims against the register`

### Dependencies

Inbound: §3 (jurisdictional), §5 (product claims), §10 (ops).
Outbound: every other section (cross-cutting review).

### Within-section order

1st: regulatory research; 2nd: risk register; 3rd: trust model spec.

---

## 13. KPI/OKR Framework

### Why it matters for CoinScopeAI

Without a KPI framework the validation phase produces vibes, not evidence. We need a layered metric stack: north-star, leading indicators, lagging indicators, and risk metrics that pair with §12.

### Output artifact

`13-kpi-okr.md` with a metric tree and an OKR template per quarter.

### Main decisions

- North-star metric (recommended: monthly active validated traders — MAVT — defined as users who passed at least N gated trades in last 30 days).
- Whether KPIs differ for self-serve vs. sales-assisted tiers.
- Reporting cadence (recommended: weekly internal, monthly stakeholder).
- Risk KPIs (max drawdown across cohort, kill-switch trigger rate, gate rejection rate).

### Tasks

- `[DRAFT] [KPI] — North-star + supporting metric tree`
- `[DRAFT] [KPI] — Q1 OKR draft (validation completion, paid pilot count, retention)`
- `[DRAFT] [KPI] — Risk KPIs paired with §12 register`
- `[INTEGRATE] [KPI] — Wire KPIs to §11 financial model so deviations move forecasts`
- `[DECISION] [KPI] — North-star definition lock`
- `[DRAFT] [KPI] — Reporting templates (weekly + monthly)`

### Dependencies

Inbound: §5, §6, §7, §10, §11, §12.
Outbound: §14, §15, §16.

### Within-section order

1st: metric tree; 2nd: north-star lock; 3rd: OKR + reporting template.

---

## 14. Launch Roadmap

### Why it matters for CoinScopeAI

A roadmap turns the rest of the plan into dated commitments. Given we are mid-validation, the roadmap must distinguish *internal milestones* (validation pass, §8 capital-cap criteria met) from *external milestones* (public launch, paid cohort opens, partnership announcements).

### Output artifact

`14-launch-roadmap.md` plus a Gantt or timeline view (`_assets/launch-timeline.md`).

### Main decisions

- The sequence: validation pass → soft launch (founder cohort) → paid cohort → public open.
- Go/no-go gates between each phase.
- Stop-the-line conditions (drawdown, vendor failure, regulatory event).
- First public launch date target (proposed: end of validation + 30 days minimum).

### Tasks

- `[DRAFT] [LAUNCH] — Phase definitions (Validation → Soft → Paid Cohort → Public)`
- `[DRAFT] [LAUNCH] — Go/no-go gate criteria per phase, paired with §13 KPIs`
- `[DRAFT] [LAUNCH] — Launch comms plan (founder, community, press)`
- `[DRAFT] [LAUNCH] — Stop-the-line policy paired with §12`
- `[INTEGRATE] [LAUNCH] — Map §5 roadmap items to launch phases`
- `[FINALIZE] [LAUNCH] — Lock Phase 1 dates; later phases stay provisional`

### Dependencies

Inbound: §5, §7, §8, §10, §11, §12, §13.
Outbound: §1, §15.

### Within-section order

1st: phase definitions; 2nd: gate criteria; 3rd: launch comms.

---

## 15. Fundraising / Investor Narrative

### Why it matters for CoinScopeAI

If/when we raise, this section is the entry point. Pre-validation we are not raising — but the artifact still exists to (a) keep optionality, (b) force discipline on the financial model, and (c) shape inbound interest from MENA family offices.

### Output artifact

`15-investor-narrative.md` plus a 10–12 slide deck (`15a-pitch-deck.pptx`) and a one-pager.

### Main decisions

- Whether to pre-seed (recommended: not before validation passes).
- Investor segments (UAE family offices, MENA crypto-native VCs, global pre-seed AI funds).
- Use-of-funds frame (build vs. distribution split).
- Whether to disclose the leverage cap and risk-first stance as a differentiator (recommended: yes, lead with it).

### Tasks

- `[DRAFT] [INVEST] — Narrative arc: thesis → product → traction → ask`
- `[DRAFT] [INVEST] — Pitch deck v1 (10–12 slides)`
- `[DRAFT] [INVEST] — One-pager and email blurb`
- `[INTEGRATE] [INVEST] — Pull §11 model, §13 KPIs, §14 roadmap, §16 scenarios`
- `[DECISION] [INVEST] — Raise timing and target ticket size`
- `[REVIEW] [INVEST] — Anti-overclaim sweep, especially around traction`

### Dependencies

Inbound: §1, §2, §11, §12, §13, §14, §16.
Outbound: §1 (final exec-summary tightening).

### Within-section order

1st: narrative arc; 2nd: deck + one-pager; 3rd: timing decision.

---

## 16. Scenario Planning

### Why it matters for CoinScopeAI

Scenario plans force us to commit, in advance, to what we will do under bull, base, and bear conditions — including conditions we hope never to hit (regulatory shock, vendor outage, founder incapacity). Scenarios are the rehearsal we run before reality forces us to choose.

### Output artifact

`16-scenario-planning.md` with three primary scenarios and three contingency scenarios.

### Main decisions

- Which three primary scenarios to model (recommended: bull = paid cohort fills in 30 days; base = 30% of target; bear = validation fails or fails partially).
- Which three contingency scenarios (regulatory shock, vendor outage, founder unavailable >2 weeks).
- Trigger thresholds that flip us between scenarios.
- Pre-committed actions per scenario.

### Tasks

- `[DRAFT] [SCEN] — Scenario specs (bull / base / bear)`
- `[DRAFT] [SCEN] — Contingency specs (regulatory, vendor, founder)`
- `[INTEGRATE] [SCEN] — Run §11 model under each scenario; record output deltas`
- `[DRAFT] [SCEN] — Pre-committed action playbooks per scenario`
- `[REVIEW] [SCEN] — Confirm triggers map to §13 KPIs and §12 risk register`
- `[FINALIZE] [SCEN] — Lock scenario set ahead of §15 investor narrative`

### Dependencies

Inbound: §11, §12, §13, §14.
Outbound: §15.

### Within-section order

1st: primary scenarios; 2nd: contingencies; 3rd: action playbooks.

---

## 17. Phased Task Tree (consolidated)

### Phase 0 — Foundations (do first, sequential)

- `[RESEARCH] [MARKET] — TAM/SAM/SOM`
- `[ANALYSIS] [MARKET] — Structural shifts thesis`
- `[DRAFT] [MARKET] — Thesis v1`
- `[RESEARCH] [ICP] — Interview/observation log`
- `[ANALYSIS] [ICP] — Segment matrix`
- `[DRAFT] [ICP] — Persona cards + anti-personas`
- `[DECISION] [ICP] — Lock primary ICP`
- `[RESEARCH] [ICP] — Pain-point ranking`
- `[DRAFT] [PROD] — Value-prop canvas per persona`
- `[DRAFT] [BRAND] — Problem statement + lead value prop`
- `[FINALIZE] [PROD] — Lock problem + value prop`

### Phase 1 — Strategy (sections may run in parallel where marked)

Parallel track A (Product):

- `[ANALYSIS] [PROD] — Capability inventory`
- `[DRAFT] [PROD] — Tier matrix v1`
- `[DECISION] [PROD] — Tier names and validation gates`
- `[DRAFT] [PROD] — 12-month roadmap`

Parallel track B (Brand):

- `[DRAFT] [BRAND] — Messaging matrix`
- `[DRAFT] [BRAND] — Hero copy candidates`
- `[DRAFT] [BRAND] — Objection table`
- `[DECISION] [BRAND] — Public feature naming`

Parallel track C (Risk baseline):

- `[RESEARCH] [RISK] — UAE regulatory landscape`
- `[DRAFT] [RISK] — Risk register`
- `[DRAFT] [RISK] — Trust model spec`

### Phase 2 — Monetization, GTM, Ops (sections iterate)

Iterative loop (Pricing ↔ Financial Model):

- `[RESEARCH] [PRICE] — Comp pricing`
- `[ANALYSIS] [PRICE] — WTP scoring`
- `[DRAFT] [FIN] — Assumptions doc v1`
- `[DRAFT] [FIN] — Revenue + cost models`
- `[DRAFT] [PRICE] — Tier prices v1`
- `[INTEGRATE] [PRICE] — Iterate against §11 base case`
- `[FINALIZE] [PRICE] — Lock launch prices`
- `[DRAFT] [FIN] — LTV/CAC + sensitivity`
- `[FINALIZE] [FIN] — Lock model v1`

GTM track:

- `[ANALYSIS] [GTM] — Channel-fit matrix`
- `[DECISION] [GTM] — Lead-with channel`
- `[DRAFT] [GTM] — 90-day content calendar`
- `[DRAFT] [GTM] — Funnel model`
- `[DRAFT] [GTM] — Community strategy`

Sales track:

- `[DRAFT] [SALES] — Sales motion per tier`
- `[ANALYSIS] [SALES] — Partnership scoring`
- `[DECISION] [SALES] — Top-3 partnership targets`
- `[DRAFT] [SALES] — Affiliate program v1`

Ops track:

- `[DRAFT] [OPS] — Support tier matrix + SLAs`
- `[DRAFT] [OPS] — Engine incident runbook`
- `[DRAFT] [OPS] — Vendor SLAs (P1 stack)`

### Phase 3 — Synthesis (sequential)

- `[DRAFT] [KPI] — Metric tree`
- `[DECISION] [KPI] — North-star lock`
- `[DRAFT] [KPI] — Q1 OKRs + reporting templates`
- `[DRAFT] [LAUNCH] — Phase definitions + go/no-go gates`
- `[DRAFT] [LAUNCH] — Launch comms plan`
- `[FINALIZE] [LAUNCH] — Lock Phase 1 dates`
- `[DRAFT] [SCEN] — Primary scenarios`
- `[DRAFT] [SCEN] — Contingency scenarios`
- `[DRAFT] [SCEN] — Action playbooks`
- `[FINALIZE] [SCEN] — Lock scenario set`
- `[DRAFT] [INVEST] — Narrative arc`
- `[DRAFT] [INVEST] — Pitch deck + one-pager`
- `[DECISION] [INVEST] — Raise timing`
- `[DRAFT] [EXEC] — Skeleton`
- `[INTEGRATE] [EXEC] — Pull from locked sections`
- `[FINALIZE] [EXEC] — Lock executive summary (last)`

---

## 18. Suggested Working Order for Claude Co-Work

Sessions are scoped to one phase or one parallel track. Each session opens with the assumptions block of the relevant section and closes with a decision-log entry.

| Session | Scope | Inputs to load | Output |
|---------|-------|----------------|--------|
| 1 | §2 Market Thesis | Memory: vision, jurisdictional. Web research allowed. | `02-market-thesis.md` v1 |
| 2 | §3 ICP — research + matrix | §2; user interviews | `03-icp-segmentation.md` v1 |
| 3 | §3 ICP lock + §4 problem/VP | §3 v1 | `03` locked; `04` v1 |
| 4 | §5 Product capability + tier matrix | §3, §4; engine docs; phased rollout memory | `05` v1 + tier matrix |
| 5 | §9 Brand messaging (parallel allowed) | §3, §4, §5; brand voice instructions | `09` v1 + messaging matrix |
| 6 | §12 Risk baseline (parallel allowed) | §3 jurisdictional; engine thresholds | `12` v1 + risk register |
| 7 | §6 Pricing v0 + §11 model v0 | §5, comp research | `06` + `11` v0 |
| 8 | §6 ↔ §11 iteration | §6 v0, §11 v0 | `06` locked, `11` v1 |
| 9 | §7 GTM | §3, §5, §6, §9 | `07` v1 |
| 10 | §8 Sales + partnerships | §6, §7 | `08` v1 |
| 11 | §10 Ops + runbooks | §5, §7, §8 | `10` v1 + runbooks |
| 12 | §13 KPI/OKR | §11, §12, §10 | `13` v1 |
| 13 | §14 Launch roadmap | §5, §10, §13 | `14` v1 |
| 14 | §16 Scenarios | §11, §13 | `16` v1 |
| 15 | §15 Investor narrative + deck | §11, §13, §14, §16 | `15` v1 + `15a` deck |
| 16 | §1 Executive summary final | All locked sections | `01` locked |

Two governance rules apply across all sessions:

- Every session ends with a decision-log entry in `_decisions/decision-log.md` describing what was locked, what is provisional, and what blocked progress.
- No section advances to LOCKED without an anti-overclaim review from §0.2 and a cross-check against §12.

---

## 19. Recommended Folder/Doc Structure

```
business-plan/
├── 00-framework.md                     ← this document
├── 01-executive-summary.md
├── 02-market-thesis.md
├── 03-icp-segmentation.md
├── 04-problem-value-prop.md
├── 05-product-strategy.md
├── 06-pricing-monetization.md
├── 07-gtm-strategy.md
├── 08-sales-partnerships.md
├── 09-brand-messaging.md
├── 10-operations-support.md
├── 11-financial-model.md               ← assumptions doc
├── 11a-financial-model.xlsx            ← live model
├── 12-risk-compliance-trust.md
├── 13-kpi-okr.md
├── 14-launch-roadmap.md
├── 15-investor-narrative.md
├── 15a-pitch-deck.pptx
├── 16-scenario-planning.md
│
├── _data/                              ← research inputs, never user-facing
│   ├── market-thesis-research.md
│   ├── icp-interviews/
│   │   └── interview-NN-handle.md
│   ├── competitor-analysis.md
│   ├── pricing-experiments.md
│   ├── runbooks/
│   │   ├── engine-incident.md
│   │   └── vendor-failover.md
│   └── risk-register.md
│
├── _decisions/                         ← single source of truth for what is locked
│   ├── decision-log.md
│   └── adr-NNN-{title}.md
│
└── _assets/                            ← shareable derivative artifacts
    ├── one-pager.md
    ├── tier-matrix.md
    ├── messaging-matrix.md
    ├── product-roadmap.md
    └── launch-timeline.md
```

Naming rules:

- Top-level numbered files map 1-to-1 with sections of this framework. The number prefix freezes their order.
- Underscore-prefixed folders (`_data`, `_decisions`, `_assets`) hold supporting material. They are never the canonical artifact.
- Decision log entries use date + section: `2026-05-01 §3 primary ICP locked`.
- ADRs (architecture/business decision records) are reserved for irreversible commitments — pricing model shape, license posture, raise timing.

---

## 20. Open questions for the founder

These are the immediate unblockers before Phase 0 can start cleanly:

- Confirm primary ICP working hypothesis (disciplined retail trader, $5k–$250k, MENA + global EN). Yes/no/refine?
- Confirm Telegram-first delivery for Tier 1 (vs. hosted dashboard primary). Yes/no?
- Confirm the modeling horizon for §11 (24m base + 36m extended). Yes/no?
- Confirm raise posture: not before validation passes. Yes/no?
- Confirm public launch target window: validation pass + 30 days minimum. Yes/no?

Once these five are answered, Phase 0 sessions 1–3 can run back-to-back without re-litigating scope.
