# CoinScopeAI — Business Plan v1.0

**Date:** 2026-05-01
**Status:** Draft for Review (Strategy Chief of Staff)
**Phase:** 30-day validation (Apr 10 – May 9, 2026)
**Owner:** Mohammed (Founder)

---

## 1. Executive Summary

CoinScopeAI is an AI-assisted crypto futures intelligence and trading platform built around a single non-negotiable principle: **capital preservation first, profit generation second.** Today, the system runs an ML-driven signal engine, a regime detector (Trending / Mean-Reverting / Volatile / Quiet), a risk-gated position-sizing layer, and a command-center dashboard — all operating exclusively on Binance Testnet. The real-capital gate is **locked** and will remain locked until documented readiness criteria are met.

The business is **not yet a revenue-bearing product.** It is in a 30-day validation phase whose primary purpose is to (a) prove that the engine's behavior matches its stated risk discipline under live market conditions, (b) generate the operational evidence base required to unlock real capital safely, and (c) sharpen positioning, ICP, and GTM before exposing users.

The strategic posture for the next 90 days is therefore narrow and deliberate: **finish validation, harden ops, define readiness criteria, and run a closed paper-trading beta with a tightly scoped ICP** — not "launch." Revenue and growth motions are designed to switch on only after the gate-unlock decision is made on evidence, not enthusiasm.

The longer-term ambition is to become the trusted institutional-grade intelligence layer for crypto futures, with a tiered product that can serve a serious retail trader through to a small fund, optionally extending into managed-portfolio offerings once the trust, ops, and regulatory groundwork is in place.

This plan is structured as a task list across 14 workstreams, each task scoped with an objective, owner, dependencies, acceptance criteria, priority, and time horizon. The most urgent items are flagged in the **Immediate Next 5 Tasks** section at the end.

---

## 2. Strategic Framing

### 2.1 Current State (as of 2026-05-01)

- **Engine:** Live on Binance Testnet only. No real orders, ever. v3 ML regime detection deployed.
- **Risk architecture:** Max DD 10%, daily loss 5%, max leverage 10x, max 5 open positions, position heat cap 80%. Kill switch in place.
- **Vendor stack (P1, narrow):** CCXT (4 exchanges), CoinGlass, Tradefeeds, CoinGecko, Claude (minimal).
- **Surface:** Engine API at `localhost:8001`; primary dashboard at `app.coinscope.ai`; Telegram bot operational.
- **Open blocker:** COI-40 VPS deployment.
- **Vision/Mission:** Locked 2026-04-22 — Vision A (capital-preservation default), Mission 1 (operational, what we build).
- **Phased rollout:** Decided 2026-04-29 — P1 ships narrow; P2/P3 layer on **after** validation passes.
- **Revenue:** $0. No paying users. No public launch.
- **Real-capital gate:** **LOCKED.** Unlock criteria not yet finalized.

### 2.2 Near-Term Plan (Now → ~90 days)

1. Complete the 30-day validation phase and produce a defensible validation report.
2. Define and publish formal **readiness criteria** for unlocking the real-capital gate.
3. Resolve the COI-40 VPS blocker and stabilize ops.
4. Run a closed **paper-trading beta** with 10–20 hand-picked users from a narrow ICP.
5. Stand up the legal, brand, and metrics scaffolding required to take money safely.
6. Establish the financial model and a pre-revenue runway plan.

### 2.3 Long-Term Ambition (12–36 months)

- A tiered product: **Intelligence (read-only)** → **Co-pilot (signal + assisted execution)** → **Managed (delegated execution under documented risk policy)**, with a possible **Fund/Desk** tier later.
- Trusted brand built on transparency: published validation reports, public risk policy, post-mortems on every drawdown.
- A regulatory and entity structure that allows a co-pilot product without crossing into investment-advice/discretionary-fund territory unless and until that's a deliberate strategic move.
- Provider portfolio diversified beyond P1 vendors with formal SLAs and fallback paths.

---

## 3. Assumptions

| # | Assumption | Sensitivity |
|---|---|---|
| A1 | The 30-day validation phase will conclude by ~2026-05-09 with usable results. | High — drives all timelines downstream. |
| A2 | The founder remains the sole full-time operator for the next 6 months; outside hires are contract-only. | High — capacity-bound. |
| A3 | We will **not** offer discretionary/managed trading in the next 12 months. Co-pilot ("user clicks confirm") is the boundary. | High — drives legal/regulatory posture. |
| A4 | Binance Futures (USDT-M) remains the primary execution venue once gates unlock; CCXT abstraction allows expansion later. | Medium. |
| A5 | The ICP is sophisticated retail / prosumer / small-fund operators — not first-time traders. | Medium — repositioning is expensive but possible. |
| A6 | We are pre-seed and intend to bootstrap or raise an angel round (≤$500k) before approaching institutional seed. | Medium. |
| A7 | LLM (Claude) usage stays "minimal" through P1; no LLM is in any signal-generation hot path that would change risk behavior. | High — guards risk integrity. |
| A8 | Provider costs (CoinGlass, Tradefeeds, CoinGecko) remain within current pricing tiers through validation. | Low. |
| A9 | The product remains testnet-only until **all** readiness criteria are met. No exceptions. | Critical — non-negotiable. |

---

## 4. Information Gaps

These are unresolved questions that materially affect the plan. Each is mapped to a task below.

1. **Readiness criteria** — what specifically must be true (drawdown profile, hit rate, latency, slippage, ops MTBF, etc.) to unlock real capital? Currently undefined.
2. **ICP truth** — we have hypotheses, not validated personas. No problem-discovery interviews have been run.
3. **Pricing** — no benchmark study, no willingness-to-pay data.
4. **Regulatory exposure** — no jurisdictional analysis. Founder location and target user geographies will determine entity structure.
5. **Provider fragility** — no documented failure-mode mapping for CoinGlass, Tradefeeds, CoinGecko, or Binance API outages.
6. **Brand voice** — vision/mission is locked, but external-facing voice, terminology, and risk-communication tone are not.
7. **Validation results** — the validation phase is mid-flight. Until it concludes, several downstream decisions are blocked.
8. **Funding intent** — no decision yet on bootstrap vs. raise; affects burn tolerance, hiring, and timeline.

---

## 5. Decisions Needed

These are forward-looking calls that need a yes/no/path before tasks can advance from `Next` to `Now`.

| # | Decision | Default if no decision | Owner |
|---|---|---|---|
| D1 | What is the unlock threshold for the real-capital gate? | Stay locked. | Founder |
| D2 | Bootstrap vs. raise an angel round in the next 6 months? | Bootstrap. | Founder |
| D3 | Is the first paid product "Intelligence (read-only signals + dashboard)" or "Co-pilot (assisted execution)"? | Intelligence. | Founder + Strategy |
| D4 | Geographic ICP focus for closed beta — UAE/MENA, US, Asia, or global English? | UAE/MENA + global English. | Founder |
| D5 | Do we incorporate now (and where) or operate as sole proprietor through validation? | Defer to legal review. | Founder + Counsel |
| D6 | Public vs. stealth posture during validation? | Stealth + invite-only beta. | Founder |
| D7 | Will we ever offer a managed/discretionary tier? Materially changes legal and ops scope. | No, for now. | Founder |
| D8 | Do we accept or refuse partnerships with influencers/KOLs as part of GTM? | Refuse during validation. | Founder + Brand |

---

## 6. Workstream Task List

Tasks follow the format `[TYPE] [AREA] — Action / Deliverable` with the required fields. Priorities: **P0 = blocking**, **P1 = important**, **P2 = useful**. Horizons: **Now (≤30d)**, **Next (30–90d)**, **Later (90d+)**.

### 6.1 MARKET

#### [RESEARCH][MARKET] — TAM/SAM/SOM for AI crypto futures intelligence
- **Objective:** Quantify the size of the addressable market for paid AI-assisted crypto futures intelligence to inform pricing, GTM scale, and fundraising narrative.
- **Owner:** Strategy / Founder.
- **Dependencies:** None.
- **Inputs:** Public exchange volume reports (Binance, Bybit, OKX), CoinGecko derivatives data, third-party reports (Messari, Kaiko), competitor pricing pages.
- **Output:** 6–10 page memo with sized funnel: total active futures traders → with capital ≥$10k → English-speaking sophisticated → reachable.
- **Acceptance:** Numbers cited with sources; explicit confidence bands; clearly distinguishes retail, prosumer, prop, and small-fund segments.
- **Priority:** P1.
- **Horizon:** Next.

#### [RESEARCH][MARKET] — Competitor landscape map
- **Objective:** Map the 12–20 closest competitors across signal services, copy-trading, AI bots, prop-desk tools, and analytics platforms; identify positioning gaps.
- **Owner:** Strategy.
- **Dependencies:** None.
- **Inputs:** 3Commas, Cryptohopper, Pionex, Coinrule, ChainEdge, Coinglass Pro, Hyblock, LunarCrush Pro, TokenMetrics, Cipher, Velo, Amberdata, etc.
- **Output:** Comparison matrix (features, pricing, target user, risk posture, regulatory posture, weaknesses) + top-3 most threatening rivals memo.
- **Acceptance:** Each competitor has at least one direct artifact (pricing screenshot, public review) cited; weaknesses are specific, not generic.
- **Priority:** P1.
- **Horizon:** Now.

#### [RESEARCH][MARKET] — Regulatory landscape scan (multi-jurisdiction)
- **Objective:** Identify regulatory constraints that bound the product and GTM, by jurisdiction.
- **Owner:** Strategy + Counsel.
- **Dependencies:** D4 (geographic ICP).
- **Inputs:** Jurisdictions: UAE (VARA/SCA), EU (MiCA), US (CFTC/SEC), UK (FCA), Singapore (MAS).
- **Output:** Memo: by-jurisdiction matrix of what's permissible (signals, copy-trading, managed accounts) and what triggers licensing.
- **Acceptance:** Each jurisdiction has explicit citations; conclusions distinguish "allowed", "allowed with disclosure", "licensed only", "prohibited".
- **Priority:** P0.
- **Horizon:** Now.

### 6.2 ICP

#### [RESEARCH][ICP] — Define primary and secondary ICP hypotheses
- **Objective:** Convert founder intuition into a written, testable ICP definition.
- **Owner:** Strategy.
- **Dependencies:** None.
- **Inputs:** Founder's user assumptions, competitor user reviews, public trader communities.
- **Output:** ICP doc: 1 primary persona, 2 adjacent personas, with role, capital range, current tools, top jobs-to-be-done, top fears, current spend.
- **Acceptance:** Each persona includes a "we are not for X" anti-persona; testable assertions explicitly listed.
- **Priority:** P0.
- **Horizon:** Now.

#### [RESEARCH][ICP] — Run 15 problem-discovery interviews
- **Objective:** Validate or kill the ICP hypothesis with primary research before building any GTM motion.
- **Owner:** Founder.
- **Dependencies:** ICP hypothesis doc.
- **Inputs:** Interview guide (open-ended, problem-first, no pitching), recruit list from communities and personal network.
- **Output:** Interview notes (15) + synthesis memo with pattern themes, surprises, and quotes.
- **Acceptance:** No more than 30% of interviewees from founder's first-degree network; synthesis identifies at least 3 patterns ≥6 mentions.
- **Priority:** P0.
- **Horizon:** Next.

#### [DOC][ICP] — ICP card (one-pager) and anti-ICP statement
- **Objective:** Produce a tight artifact every team member, partner, or asset can reference.
- **Owner:** Strategy.
- **Dependencies:** Interview synthesis.
- **Inputs:** ICP doc, interview synthesis.
- **Output:** 1-page ICP card + 1-paragraph anti-ICP statement.
- **Acceptance:** Used as the front matter of all GTM and content briefs.
- **Priority:** P1.
- **Horizon:** Next.

### 6.3 POSITIONING

#### [DOC][POSITIONING] — Positioning statement and message hierarchy
- **Objective:** Lock the public narrative around capital preservation; differentiate from "alpha-promising" signal services.
- **Owner:** Strategy + Brand.
- **Dependencies:** Vision/Mission (locked); ICP card.
- **Inputs:** Vision A doc, competitor positioning matrix.
- **Output:** Positioning statement (≤30 words), 3-tier message hierarchy (lead, support, proof), reasons-to-believe list.
- **Acceptance:** Reads believably to a skeptical prosumer; survives a "this sounds like every other bot" stress test.
- **Priority:** P0.
- **Horizon:** Now.

#### [DOC][POSITIONING] — Differentiation matrix vs. competing signal services
- **Objective:** Make our differences credible and concrete, not slogans.
- **Owner:** Strategy.
- **Dependencies:** Competitor landscape map.
- **Inputs:** Competitor matrix.
- **Output:** Side-by-side: risk policy, validation transparency, audit posture, fee model, what they hide vs. what we publish.
- **Acceptance:** Every cell has a verifiable claim; at least 3 dimensions where we are demonstrably stronger.
- **Priority:** P1.
- **Horizon:** Next.

### 6.4 PRODUCT

#### [BUILD][PRODUCT] — Define readiness criteria for real-capital gate unlock
- **Objective:** Translate "the gate is locked until ready" into a concrete, measurable, falsifiable checklist.
- **Owner:** Founder + Risk.
- **Dependencies:** None — this is the most important blocker on the entire plan.
- **Inputs:** Validation phase data, risk thresholds, current ops MTBF.
- **Output:** A "Production Candidate Criteria" doc covering: (a) signal quality bands, (b) drawdown discipline, (c) latency/slippage, (d) ops MTBF and MTTR, (e) monitoring & alerting coverage, (f) rollback readiness, (g) legal & disclosure prerequisites, (h) capital cap on first live phase.
- **Acceptance:** Criteria are binary or numeric (no "feels stable enough"); each has an owner and a verification method; document is the gate-keeper for any real-capital decision.
- **Priority:** P0.
- **Horizon:** Now.

#### [BUILD][PRODUCT] — Validation phase telemetry & KPI dashboard
- **Objective:** Make the validation phase auditable in real time, not retrospectively.
- **Owner:** Founder.
- **Dependencies:** Engine API endpoints (`/scan`, `/performance`, `/journal`, `/risk-gate`).
- **Inputs:** Endpoint contracts, journal data.
- **Output:** A dashboard surfacing: trade journal, risk-gate hit rate, regime distribution, drawdown curve, signal latency, kill-switch events.
- **Acceptance:** All metrics derived from live engine data; no manual data entry; survives a session restart.
- **Priority:** P0.
- **Horizon:** Now.

#### [DOC][PRODUCT] — Product tier definitions (Intelligence / Co-pilot / Managed)
- **Objective:** Clarify what we build, what we sell, and in what order.
- **Owner:** Strategy + Founder.
- **Dependencies:** D3 (first paid product), D7 (managed tier yes/no).
- **Inputs:** Vision A, ICP card, regulatory memo.
- **Output:** Tier matrix with feature scope, user trust required, regulatory exposure, pricing band, build cost.
- **Acceptance:** Each tier has a clear "do not build until X" gate.
- **Priority:** P1.
- **Horizon:** Next.

#### [BUILD][PRODUCT] — Closed paper-trading beta onboarding flow
- **Objective:** A controlled way to put 10–20 users on the dashboard without exposing them to real capital risk.
- **Owner:** Founder.
- **Dependencies:** ICP card; T&Cs draft; readiness criteria draft.
- **Inputs:** Existing dashboard, Telegram bot, Engine API.
- **Output:** Invite flow → onboarding form → access to dashboard in paper mode → feedback loop (weekly survey + qualitative interview).
- **Acceptance:** Every user explicitly acknowledges paper-mode + risk disclosures before access.
- **Priority:** P1.
- **Horizon:** Next.

### 6.5 PRICING

#### [RESEARCH][PRICING] — Pricing benchmark study
- **Objective:** Anchor pricing in market reality rather than aspiration.
- **Owner:** Strategy.
- **Dependencies:** Competitor landscape.
- **Inputs:** Public pricing pages of 12–20 competitors + indirect signals (Reddit, reviews) on what users actually pay.
- **Output:** Pricing matrix (per-user/month, per-AUM, per-trade, freemium, discount practices) + willingness-to-pay hypotheses.
- **Acceptance:** At least 3 distinct pricing archetypes identified; ours fits one or has a defensible reason to differ.
- **Priority:** P1.
- **Horizon:** Next.

#### [DOC][PRICING] — Initial pricing v0
- **Objective:** Land a v0 price for the closed beta and the first paid tier.
- **Owner:** Founder + Strategy.
- **Dependencies:** Pricing benchmark; product tier doc.
- **Inputs:** Benchmark data, ICP capital range.
- **Output:** v0 price card (free beta → tier 1 monthly → tier 1 annual; optional early-access discount).
- **Acceptance:** Defensible against the question "why this number"; explicit grandfathering policy for beta users.
- **Priority:** P2.
- **Horizon:** Next.

### 6.6 GTM

#### [GTM] — Closed beta cohort design
- **Objective:** Recruit and structure a beta cohort that produces signal, not noise.
- **Owner:** Founder.
- **Dependencies:** ICP card, T&Cs.
- **Inputs:** ICP card, recruit channels (founder network, communities).
- **Output:** Cohort plan: target size 10–20, screening rubric, weekly cadence, exit criteria, what we measure.
- **Acceptance:** No "friends and family" filler; every member matches ICP and signs disclosure.
- **Priority:** P1.
- **Horizon:** Next.

#### [GTM] — Content-led organic GTM motion plan
- **Objective:** Build trust before asking for money. Content is the trust mechanism for capital-preservation positioning.
- **Owner:** Brand + Founder.
- **Dependencies:** Positioning doc.
- **Inputs:** Validation data, risk philosophy, technical writeups.
- **Output:** 90-day editorial plan: ~2 long-form pieces/month + weekly short notes; topics anchored on transparency (validation results, drawdown post-mortems, regime studies).
- **Acceptance:** No "alpha" / "moonshot" / get-rich language anywhere; every piece tied to the positioning hierarchy.
- **Priority:** P1.
- **Horizon:** Next.

#### [GTM] — Outbound playbook for prosumer / micro-fund segment
- **Objective:** A structured outbound motion to a tightly defined segment, not spray-and-pray.
- **Owner:** Founder.
- **Dependencies:** ICP card, positioning, content assets.
- **Inputs:** Target list (≤200), message templates, sequence cadence.
- **Output:** Playbook: list build → personalized opener → 3-touch sequence → call → beta invite.
- **Acceptance:** Reply-rate baseline established within first 50 contacts; content assets do the convincing, not promises.
- **Priority:** P2.
- **Horizon:** Later.

### 6.7 PARTNERSHIPS

#### [PARTNERSHIPS] — Exchange partnership scoping
- **Objective:** Identify whether exchange partnerships (referral, fee rebates, market-maker programs) are viable and worth the integration tax.
- **Owner:** Strategy.
- **Dependencies:** None.
- **Inputs:** Binance, Bybit, OKX, Hyperliquid partner program docs.
- **Output:** Memo: per-exchange offer, ROI estimate, integration complexity, brand-risk implications.
- **Acceptance:** Includes recommendation of which (if any) to pursue in next 6 months, and which to defer.
- **Priority:** P2.
- **Horizon:** Later.

#### [PARTNERSHIPS] — Data vendor SLAs and failure-mode mapping
- **Objective:** Make our provider dependencies a managed risk, not a hidden one.
- **Owner:** Ops.
- **Dependencies:** None.
- **Inputs:** CoinGlass, Tradefeeds, CoinGecko, Binance API docs and terms.
- **Output:** Per-vendor: contract terms, rate limits, observed reliability, fallback path, what breaks if it dies.
- **Acceptance:** Each vendor has a documented "what we do if this vendor goes dark for 24h" plan.
- **Priority:** P0.
- **Horizon:** Now.

#### [PARTNERSHIPS] — Influencer / KOL evaluation framework
- **Objective:** Decide whether and how we use KOL distribution, given that capital-preservation positioning is fragile to bad influencer alignment.
- **Owner:** Brand + Founder.
- **Dependencies:** D8.
- **Inputs:** Brand voice doc, positioning doc.
- **Output:** Evaluation rubric (audience fit, credibility, prior misses) + a default "no" stance for validation phase.
- **Acceptance:** Default is "no"; explicit override criteria documented.
- **Priority:** P2.
- **Horizon:** Later.

### 6.8 OPS

#### [OPS] — Production candidate criteria document
- **Objective:** Single source of truth for what "production-ready" means in this project, ending the temptation to call work production-ready before it is.
- **Owner:** Founder.
- **Dependencies:** Readiness criteria (Product).
- **Inputs:** Readiness criteria doc, ops baselines.
- **Output:** Doc enumerating: SLOs, alerting coverage, rollback procedures, runbooks, on-call definition (even if solo), incident review cadence.
- **Acceptance:** Any future "is this production-ready?" question answered by referring to this doc.
- **Priority:** P0.
- **Horizon:** Now.

#### [OPS] — Incident response runbook
- **Objective:** Predefined response to the most likely failures (engine down, vendor outage, kill switch trip, dashboard down, false signal storm).
- **Owner:** Ops.
- **Dependencies:** Vendor failure-mode mapping.
- **Inputs:** Engine architecture, kill switch behavior, alert channels.
- **Output:** Runbook with severity ladder, paging path, comms templates, post-mortem template.
- **Acceptance:** A first-responder (even the founder at 3am) can resolve the top 5 incidents from the runbook alone.
- **Priority:** P0.
- **Horizon:** Now.

#### [OPS] — Unblock COI-40 VPS deployment
- **Objective:** Resolve the active deployment blocker.
- **Owner:** Founder.
- **Dependencies:** None.
- **Inputs:** COI-40 ticket, current deployment state.
- **Output:** Deployment unblocked + post-mortem of what caused the block.
- **Acceptance:** Engine running on target VPS with monitoring; root cause documented to prevent recurrence.
- **Priority:** P0.
- **Horizon:** Now.

#### [OPS] — User support intake & SLA (beta-grade)
- **Objective:** A minimal, honest support channel for beta users that doesn't overpromise.
- **Owner:** Founder.
- **Dependencies:** Beta cohort design.
- **Inputs:** Telegram, email, status-page tooling.
- **Output:** Single intake (Telegram or email), response SLA (e.g., 24h beta-grade), public status page.
- **Acceptance:** Every beta user knows where to file an issue and what to expect; SLA met for first 4 weeks.
- **Priority:** P1.
- **Horizon:** Next.

### 6.9 SUPPORT

#### [DOC][SUPPORT] — User-facing FAQ and "how the system protects your capital" doc
- **Objective:** Pre-empt the questions that drive trust loss; explain the risk architecture in user-facing language.
- **Owner:** Brand + Founder.
- **Dependencies:** Risk policy doc.
- **Inputs:** Trading rules, risk thresholds, kill switch behavior.
- **Output:** Public-facing FAQ (≤25 entries) + one explainer page on the risk architecture.
- **Acceptance:** A reasonable, skeptical reader can answer "is this safer than a typical bot?" after reading.
- **Priority:** P1.
- **Horizon:** Next.

### 6.10 FINANCE

#### [FINANCE] — 18-month financial model
- **Objective:** Quantify burn, runway, and revenue scenarios; turn "we're bootstrapping" into an actual plan.
- **Owner:** Founder.
- **Dependencies:** Vendor cost map, hosting costs, salary assumptions.
- **Inputs:** Current monthly costs, projected vendor tier upgrades, projected user growth.
- **Output:** Excel/Sheet model with three scenarios (downside / base / upside), monthly cash, breakeven date, hiring trigger points.
- **Acceptance:** Model is interactive; sensitivity to top 3 drivers (price, conversion, churn) visible.
- **Priority:** P0.
- **Horizon:** Now.

#### [FINANCE] — Funding strategy and decision
- **Objective:** Decide on the funding path; document why.
- **Owner:** Founder.
- **Dependencies:** Financial model; D2.
- **Inputs:** Burn, runway, founder personal runway, milestone economics.
- **Output:** 1-page memo: bootstrap / angel / both, with milestones tied to each path.
- **Acceptance:** Decision and rationale captured; revisit date set.
- **Priority:** P1.
- **Horizon:** Next.

#### [FINANCE] — Treasury & runway policy
- **Objective:** Avoid treasury risk in a crypto-adjacent business (no over-exposure to volatile assets, clear separation of personal and business cash).
- **Owner:** Founder.
- **Dependencies:** Entity decision.
- **Inputs:** Bank options, stablecoin custody options.
- **Output:** Policy doc: where cash sits, currency mix, runway floor (e.g., 9 months stays in fiat).
- **Acceptance:** Policy is followed for the next deposit.
- **Priority:** P2.
- **Horizon:** Next.

### 6.11 LEGAL

#### [LEGAL] — Entity & jurisdiction structure
- **Objective:** Pick a structure that does not block the realistic 12–24 month roadmap.
- **Owner:** Founder + Counsel.
- **Dependencies:** Regulatory memo; D5.
- **Inputs:** Founder location, target user geographies, banking access.
- **Output:** Recommendation: where to incorporate, what entity type, when to do it.
- **Acceptance:** Counsel sign-off; recommendation accommodates a future co-pilot product.
- **Priority:** P0.
- **Horizon:** Now.

#### [LEGAL] — Terms of Service, Privacy Policy, Risk Disclosure
- **Objective:** Stop operating without binding user agreements before any user touches the product.
- **Owner:** Counsel + Founder.
- **Dependencies:** Entity decision.
- **Inputs:** Existing comparable T&Cs, data handling map.
- **Output:** ToS, Privacy Policy, Risk Disclosure document (the latter is the most important — it must explicitly disclaim guaranteed performance, describe testnet status, and explain capital loss risk).
- **Acceptance:** No user can access the dashboard without explicit acceptance; counsel-reviewed.
- **Priority:** P0.
- **Horizon:** Now.

#### [LEGAL] — Securities/CFTC/MiCA analysis (no-investment-advice posture)
- **Objective:** Make sure the product, marketing, and signal language do not constitute investment advice or unregistered solicitation in target jurisdictions.
- **Owner:** Counsel.
- **Dependencies:** Entity decision; jurisdiction memo.
- **Inputs:** Product description, sample marketing copy, signal output examples.
- **Output:** Memo: red lines (what we cannot say or do), yellow lines (require disclosures), green lines (safe).
- **Acceptance:** Brand and content teams have a checklist they can apply without re-asking counsel.
- **Priority:** P0.
- **Horizon:** Now.

### 6.12 RISK

#### [RISK] — Product risk register
- **Objective:** Surface and rank the top 20 risks across product, ops, market, legal, partner, and reputational categories.
- **Owner:** Founder.
- **Dependencies:** Vendor failure mapping, regulatory memo.
- **Inputs:** All workstream artifacts above.
- **Output:** Living register: risk → likelihood × impact → mitigation owner → status.
- **Acceptance:** Reviewed monthly; no item sits in "open" without a mitigation.
- **Priority:** P0.
- **Horizon:** Now.

#### [RISK] — User capital protection policy
- **Objective:** Codify the rules that protect users from us as well as from the market.
- **Owner:** Founder.
- **Dependencies:** Risk thresholds (already defined: max DD 10%, daily loss 5%, etc.).
- **Inputs:** Trading rules, kill switch behavior, position-sizing logic.
- **Output:** Public-facing policy + internal version with implementation references.
- **Acceptance:** Policy is referenced from ToS and Risk Disclosure.
- **Priority:** P1.
- **Horizon:** Next.

#### [RISK] — Validation phase exit/extension criteria
- **Objective:** Decide in advance under what conditions validation extends, restarts, or exits successfully — to avoid retroactive rationalization.
- **Owner:** Founder + Strategy.
- **Dependencies:** Readiness criteria.
- **Inputs:** 30-day validation plan, observed metrics so far.
- **Output:** Decision tree: pass / extend / restart / kill, each tied to specific metrics.
- **Acceptance:** Written before validation phase ends, not after.
- **Priority:** P0.
- **Horizon:** Now.

### 6.13 BRAND / CONTENT

#### [BRAND] — Brand voice guidelines (capital-preservation tone)
- **Objective:** A voice that is calm, technical, and trust-building, not performative.
- **Owner:** Brand.
- **Dependencies:** Positioning.
- **Inputs:** Vision A doc, sample writing.
- **Output:** Voice doc: do/don't, banned words ("alpha", "moonshot", "guaranteed", "easy"), tone examples.
- **Acceptance:** External copy is reviewable against the doc; reviewer can flag voice violations objectively.
- **Priority:** P1.
- **Horizon:** Next.

#### [CONTENT] — Editorial calendar (validation phase transparency content)
- **Objective:** Use the validation phase itself as the content engine.
- **Owner:** Brand + Founder.
- **Dependencies:** Brand voice; positioning.
- **Inputs:** Validation telemetry, regime studies, post-mortems.
- **Output:** 90-day calendar with topics, formats (long-form, dashboard snapshots, post-mortems), distribution channels.
- **Acceptance:** Every piece is sourced from real engine output, not hypotheticals.
- **Priority:** P2.
- **Horizon:** Next.

### 6.14 METRICS

#### [METRICS] — North Star metric definition
- **Objective:** Pick one metric that, if it goes up, the business is winning. Resist the urge to track everything equally.
- **Owner:** Strategy + Founder.
- **Dependencies:** Product tier doc; ICP.
- **Inputs:** Validation telemetry, draft pricing, tier definitions.
- **Output:** Memo: candidate North Star + rejected alternatives + why. Likely candidate: "weekly active capital under guidance with a non-violated risk policy."
- **Acceptance:** A single, sharable definition; no compound or composite metrics.
- **Priority:** P1.
- **Horizon:** Next.

#### [METRICS] — Validation phase KPI definitions
- **Objective:** Tie validation phase to numbers, not vibes.
- **Owner:** Founder.
- **Dependencies:** Readiness criteria.
- **Inputs:** Engine endpoints, journal data.
- **Output:** KPI doc: signal precision, false-positive rate, drawdown depth and duration, slippage vs. expected, kill-switch trip frequency, ops MTBF.
- **Acceptance:** Every KPI has source, owner, target band, alert threshold.
- **Priority:** P0.
- **Horizon:** Now.

#### [METRICS] — Operational metrics dashboard
- **Objective:** A second dashboard for the business itself (not the engine): users, support load, content engagement, vendor cost burn.
- **Owner:** Strategy.
- **Dependencies:** Beta cohort plan.
- **Inputs:** Stripe (later), email/Telegram engagement, vendor invoices.
- **Output:** A simple weekly view of business KPIs.
- **Acceptance:** Reviewed weekly; deltas explainable.
- **Priority:** P2.
- **Horizon:** Later.

### 6.15 FUNDRAISING (Stub — gated by D2)

#### [FUNDRAISING] — Angel-round narrative pack (only if D2 = raise)
- **Objective:** A clean, defensible deck and data room.
- **Owner:** Founder + Strategy.
- **Dependencies:** Validation report; financial model; positioning.
- **Inputs:** All workstreams.
- **Output:** 12–15 slide deck + 1-page memo + data room (validation report, model, ToS, risk register).
- **Acceptance:** A skeptical angel cannot ask a question that isn't answered in the data room.
- **Priority:** P2.
- **Horizon:** Later.

---

## 7. Workstream Priorities At-a-Glance

| Workstream | P0 (Now) | P1 | P2 |
|---|---|---|---|
| MARKET | Regulatory scan | Competitor map; TAM/SAM/SOM | — |
| ICP | ICP hypothesis; 15 interviews | ICP card | — |
| POSITIONING | Positioning statement | Differentiation matrix | — |
| PRODUCT | Readiness criteria; Validation telemetry | Product tiers; Beta onboarding | — |
| PRICING | — | Pricing benchmark | Pricing v0 |
| GTM | — | Beta cohort; Content motion | Outbound playbook |
| PARTNERSHIPS | Vendor SLAs / failure mapping | — | Exchange partnerships; KOL framework |
| OPS | Production criteria; Runbook; VPS unblock | Support intake | — |
| SUPPORT | — | FAQ / risk explainer | — |
| FINANCE | Financial model | Funding decision | Treasury policy |
| LEGAL | Entity; ToS / risk disclosure; No-advice memo | — | — |
| RISK | Risk register; Validation exit criteria | User capital protection | — |
| BRAND/CONTENT | — | Brand voice | Editorial calendar |
| METRICS | Validation KPI defs | North Star | Ops dashboard |
| FUNDRAISING | — | — | Angel pack (gated) |

---

## 8. Risk Lens on the Plan Itself

A few self-aware risks in this plan — flagging them so they don't get lost:

1. **Founder bandwidth.** Most P0/Now tasks land on one person. Without sequencing discipline, "everything is P0" becomes "nothing is."
2. **Premature GTM.** The biggest temptation is to start outbound before validation closes. The plan deliberately holds GTM at `Next`.
3. **Soft readiness criteria.** If the readiness criteria aren't binary, the gate will be unlocked under social pressure, not evidence. Hardening them is the single highest-leverage task in the plan.
4. **Legal procrastination.** The instinct will be to defer legal until users exist. That's backwards — we cannot expose any user (even a free beta one) without a risk disclosure and ToS.
5. **Provider concentration.** Five vendors carry the entire P1 stack. A 24h CoinGlass outage during validation could distort results. Mitigation lives in the vendor SLA task.

---

## 9. Immediate Next 5 Tasks

These are the tasks to start this week. Everything else queues behind them.

1. **[BUILD][PRODUCT] — Define readiness criteria for real-capital gate unlock** (P0, Now). Without this, the validation phase has no exit and the rest of the plan has no anchor.
2. **[OPS] — Unblock COI-40 VPS deployment** (P0, Now). Active blocker; resolves a known operational risk to validation.
3. **[LEGAL] — ToS, Privacy Policy, Risk Disclosure draft** (P0, Now). Required before any user — including a free beta user — touches the dashboard.
4. **[RESEARCH][MARKET] — Regulatory landscape scan (multi-jurisdiction)** (P0, Now). Feeds the entity, ToS, and product-tier decisions.
5. **[RISK] — Validation phase exit/extension criteria** (P0, Now). Decide pass/fail rules before validation ends, not after.

---

## 10. Open Items for the Next Review

- Founder confirmation of D1–D8.
- Whether we want a parallel "co-pilot product spec" track to start in `Next`, or hold strictly until validation closes.
- Whether we want to commission a third-party code/risk review of the engine before any real-capital decision (recommend: yes).
