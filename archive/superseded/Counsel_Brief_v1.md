# CoinScopeAI — Counsel Engagement Brief v1.0

**Date:** 2026-05-01
**Status:** Draft for Founder Review (then transmittal to Counsel)
**Prepared by:** Strategy Chief of Staff (Scoopy)
**Founder:** Mohammed (`abu3anzeh@gmail.com`)
**Engagement scope:** Phase A — ToS, Privacy Policy, Risk Disclosure, No-Investment-Advice Memo. Phase B and C scoped for context.

> This brief is the artifact handed to engaged counsel. It does **not** itself create legal advice; it gives counsel the factual basis to do so. Where facts are uncertain, items are marked **[CONFIRM WITH FOUNDER]**.

---

## 0. Engagement at a Glance

| Field | Value |
|---|---|
| Engagement type | Initial fixed-scope: Phase A documents + advisory memo |
| Primary jurisdictions to advise on | UAE (VARA/SCA), EU (MiCA/GDPR), US (CFTC/SEC/state), UK (FCA), Singapore (MAS) — confirm counsel can cover or refer |
| Target Phase A delivery | 4–6 weeks from engagement start |
| Most time-sensitive item | **Risk Disclosure** (gates user access via API auth ToS-gate) |
| Founder availability | High; sole operator |
| Budget envelope | **[CONFIRM WITH FOUNDER]** |

---

## 1. Company & Product Summary

### 1.1 Entity status

CoinScopeAI is a pre-revenue / early-revenue crypto-futures intelligence software product. The operating entity is **[CONFIRM WITH FOUNDER — likely not yet incorporated]**. Founder is based in **[CONFIRM WITH FOUNDER — assumption: UAE]**.

This brief presumes that one of counsel's first deliverables will be a recommendation on entity formation jurisdiction (see §6.5).

### 1.2 What CoinScopeAI does today

- A **read-only intelligence subscription product**: a user pays a recurring fee to access a dashboard, signal feed, regime detection, risk-gate explanations, methodology pages, and a Telegram bot for status / positions / signals / kill commands.
- An ML-driven engine that scans crypto futures markets and outputs trading signals with a confluence score, a regime classification, and a risk-gate decision.
- A "Trust" surface (`trust.coinscope.ai`) that publishes signed, tamper-evident performance snapshots from the engine.
- Subscription billing through Stripe, with four tiers ($19 / $49 / $99 / $299).
- ToS-gated authentication: the product's API will refuse requests from any user who has not signed the Terms of Service.

### 1.3 What CoinScopeAI does NOT do today

This list is at least as important as §1.2. Counsel should be aware that **none** of the following occurs through the platform today:

- Trading with real customer capital. **The engine is configured for Binance Futures Testnet only.**
- Custody of customer funds. The platform never holds, receives, or transmits customer fiat or crypto.
- Discretionary trading on behalf of customers. The user does not delegate execution; today, no execution occurs.
- Personalized investment advice. The product publishes signals and methodology; it does not assess any individual user's financial situation.
- KYC / AML pipeline activation. KYC is architected (Sumsub or Persona) but gated to a future "Team" tier and not currently in use.

A real-capital gate exists in the system architecture and is **explicitly locked** (the architecture marks it `§8 gate locked`). Unlocking the gate is governed by a separate Production Candidate Criteria document (provided in §7 references). Counsel should advise as if real-capital trading is **not coming online during the Phase A engagement**, and treat any future unlock as a Phase C scope item.

### 1.4 Target users

- Geographic focus (initial, beta cohort): **[CONFIRM WITH FOUNDER — assumption: UAE/MENA + global English-speaking]**.
- Profile: sophisticated retail / "prosumer" crypto futures traders and small trading desks. Not first-time investors.
- The product is **not** marketed to US persons until counsel advises on the CFTC/SEC posture (see §3.4). A jurisdictional gate at signup is in scope as part of Phase B.

### 1.5 Architectural facts that affect legal scope

The following architecture decisions are *already deployed* and bear on legal scope:

| Architectural fact | Legal implication |
|---|---|
| ToS-gate enforced at API auth (refuse if ToS unsigned) | ToS is a hard precondition for any user interaction. Must be in place before any non-founder user touches the dashboard. |
| Stripe subscription billing live, 4 tiers | Consumer subscription law applies (auto-renewal, refunds, cancellation, taxes, applicable consumer-protection regimes). |
| Per-user keys, per-user portfolios, per-user thresholds | Multi-tenant data model. Privacy regime applies per-user. |
| Audit log retention: 7-year trade / 1-year auth / 90-day request | This is a regulatory-grade commitment. Counsel should confirm 7-year is appropriate for target jurisdictions and does not conflict with any privacy-deletion obligation. |
| Public performance dashboard (`trust.coinscope.ai`), signed snapshots | Marketing-claims regime; some jurisdictions regulate publication of trading performance. |
| Vendor sub-processors: Stripe, Anthropic, Binance, CoinGlass, Tradefeeds, CoinGecko; future: Sumsub or Persona | Privacy disclosure obligations and data-transfer compliance. |
| Operator-side platforms: MemPalace, Notion, Linear, GitHub, Google Drive (one-way operator sync; never reads back into engine) | Data-residency exposure for operator-side data even though it's not user-facing. |

### 1.6 Validation phase context

The product is in a **30-day validation phase** ending ~2026-05-09. The phase's purpose is to verify engine behavior matches documented risk policy under live market conditions. The validation phase is engine-only; legal documentation is the parallel track that this engagement opens.

---

## 2. Why this engagement, why now

Three specific business decisions are gated on counsel's input:

1. **The closed beta cannot open without ToS, Privacy Policy, and Risk Disclosure in force.** The API auth layer enforces this structurally — not a policy preference, an architectural one. Without these three documents, no non-founder user can use the product.
2. **The "no investment advice" posture must be defensible in marketing copy and the Trust dashboard.** The Trust rail publishes live PnL with signed snapshots; this is a magnet for an "investment recommendation" classification in some jurisdictions. The brand depends on getting this presentation right.
3. **The entity / jurisdiction decision is gating downstream work** (banking, Stripe production scaling beyond test mode, beta user routing). Founder needs a recommendation, not a survey of options.

---

## 3. Specific Phase A Deliverables

### 3.1 Terms of Service (the contract)

**Form:** A standard SaaS subscription ToS adapted to a crypto-data-and-analytics product. Click-through assent at signup. Versioned; retained per user, signed and timestamped.

**Substantive content counsel should cover:**

- Definition of the service. Critically, the service is defined as **information and software access**, not investment management or brokerage.
- Subscription terms: pricing (4 tiers), billing cadence, taxes, auto-renewal, cancellation, refunds. Counsel should advise on compliance with consumer-subscription regimes in target jurisdictions (e.g., EU "right to withdraw" / 14-day reflection period, UAE consumer protection, US state auto-renewal laws).
- Service availability disclaimers. The system runs on third-party infrastructure (Binance, vendor APIs, cloud hosting); availability is best-effort, not guaranteed.
- IP ownership (CoinScopeAI retains all rights to signals, methodology, dashboard).
- Acceptable use. Specifically: no scraping, no resale of signals, no use in jurisdictions counsel identifies as prohibited.
- Limitation of liability. Counsel to advise on caps; the standard "fees-paid-in-prior-12-months" cap is intended.
- Indemnification.
- Dispute resolution + governing law (depends on entity decision, see §6.5).
- Force majeure (especially relevant given vendor-dependency risks).
- Modification clause + notice period.
- Termination (for cause and convenience).
- A clear "no investment advice" recital (also reinforced in the Risk Disclosure).

**Specific drafting requests:**

- A short, plain-language summary on the click-through page above the full ToS link.
- Versioning and re-acceptance flow for material changes.

### 3.2 Privacy Policy

**Form:** A privacy notice covering all jurisdictions where users may sign up, with regional addenda where required.

**Data inventory counsel will need (founder to populate completely):**

| Data category | Source | Storage | Retention | Sub-processors involved |
|---|---|---|---|---|
| Account identifiers (email, hashed password) | Signup | Postgres | Account lifetime + 1y | Hosting provider (DigitalOcean per "DO env") |
| Subscription / billing data | Stripe checkout | Stripe + minimal mirror | Per Stripe + tax retention | Stripe |
| Per-user portfolio config (symbols, risk profile) | User input | Postgres | Account lifetime | Hosting |
| API exchange keys (per-user, encrypted at rest) | User input | Encrypted vault | Until user deletes | Hosting + KMS |
| Trade journal / signal interactions | Engine | Postgres | **7 years** | Hosting |
| Auth logs | Engine | Logs store | **1 year** | Hosting |
| Request logs | Engine | Logs store | **90 days** | Hosting |
| KYC records (future, Team tier) | User upload | Sumsub / Persona | Per regulator | Sumsub or Persona |
| Public performance snapshots | Engine | `trust.coinscope.ai` | Indefinite, signed | Hosting |
| Operator-side notes about a user (Notion, MemPalace) | Founder | Notion / GDrive | Operator policy | Notion, Google |

**Specific counsel asks:**

- Confirm 7-year trade-journal retention is supportable in EU/UAE (especially against GDPR Art. 17 / UAE PDPL deletion rights). Identify if a "lawful basis" + "legitimate interest" argument suffices, or if anonymization is required after a shorter window.
- Cross-border transfer mechanism (likely SCCs for EU users, or equivalent).
- Data-subject rights flow: access, rectification, erasure, portability, restriction, objection. Operational SLA per jurisdiction.
- Cookies / analytics policy — minimal currently, but anticipate.
- Children's data: explicit minimum-age (18+) gate.

### 3.3 Risk Disclosure

**This is the single most important Phase A deliverable.** It is what every user sees first and what most defends the company in a worst-case dispute.

**Form:** A standalone document (separate from ToS), explicitly accepted at signup with a click-through requiring deliberate scroll-to-accept (not a bundled checkbox).

**Substantive content (founder requests, counsel to dramatically improve):**

- **Plain-language summary at the top.** "You can lose money trading crypto futures. CoinScopeAI does not eliminate that risk and does not guarantee any outcome."
- **Current operating posture:** the engine runs on Binance Futures Testnet. The product today provides intelligence, not execution. Real-capital execution through the platform is **not currently enabled**; if and when it is, a separate, explicit consent and disclosure flow will apply.
- **Limitations of paper trading / testnet conditions.** Slippage, latency, and funding-rate behavior on testnet differ from mainnet. Past testnet performance does not predict mainnet outcomes.
- **Capital-preservation framing is policy, not promise.** The risk policy (max DD 10%, daily loss 5%, max leverage [10x or 20x — see §8 open item], max 3 positions, position heat ≤80%) describes how the *engine* attempts to manage exposure. It does not promise the user will not lose money.
- **Crypto-specific risks:** market volatility, exchange counterparty risk, custody risk on the user's own exchange account (which the platform does not control), regulatory risk, potential for total loss.
- **Vendor risk.** Outages of Binance, CoinGlass, Tradefeeds, etc., can affect signal quality and execution behavior. Documented in vendor failure-mode mapping.
- **No fiduciary, no advisory relationship.** Explicit disclaimer that the product does not assess the user's financial situation, risk tolerance, or suitability.
- **No guarantees of accuracy, completeness, or fitness for purpose** of any signal, regime classification, or methodology.
- **The user is solely responsible** for their own trading decisions, exchange account, and tax obligations.
- **Methodology transparency clause.** The published methodology page describes the approach in good faith but is not a complete specification; the engine evolves.

**Specific counsel asks:**

- Does the Trust dashboard (live PnL, signed snapshots) meet definitions of "communications regarding investment performance" in any of the target jurisdictions, and if so, what disclosures must accompany it on `trust.coinscope.ai`?
- Are testnet-period results "performance" for any regulator's purposes? Recommend explicit framing.
- For each target jurisdiction, the *minimum* disclosure language that must appear (or be linked) on every signal-bearing page.

### 3.4 No-Investment-Advice Memo (Internal — the "red/yellow/green" doc)

**Form:** An internal memo to the founder, brand, and content workstreams. Not user-facing. Used as the standing checklist for marketing copy review.

**Counsel asks:**

A structured **red / yellow / green** classification of language and product behavior across each target jurisdiction:

- **Green:** unambiguously safe. ("Our engine published 12 long signals on BTC last week with average confluence score 7.3.")
- **Yellow:** safe with explicit accompanying disclosure. ("BTC long performed +2.1% on the trust dashboard this week — disclosure: testnet, past results, no future-performance promise.")
- **Red:** prohibited. ("Buy BTC. Our system says it will go up." Anything that could be construed as personalized advice, prediction, or guaranteed performance.)

**Specific framing questions for the memo:**

- At what point does a "Co-pilot" feature (assisted execution where user clicks to confirm) cross into investment advice or brokerage in each jurisdiction? Counsel should give a specific feature-level threshold, not a category-level statement.
- Does publishing live PnL on a public URL constitute solicitation in any target jurisdiction?
- Does a Telegram bot that pushes signals to a user's private channel constitute "communication" subject to financial-promotion rules? In which jurisdictions?
- Are there jurisdictions where the product, *as currently described*, cannot legally be sold to residents? Recommend a signup-time block list.

---

## 4. Phase B and Phase C Scope (For Context, Not for Phase A Engagement)

This is what counsel should know is coming, so the Phase A documents are drafted to accommodate it. **Not part of the Phase A fixed scope.**

### 4.1 Phase B — when validation passes (target: Q3 2026)

- Jurisdictional gating logic at signup (operationalize the Phase A red/yellow/green memo).
- KYC / AML scoping for "Team" tier (Sumsub or Persona): when does Team tier trigger KYC, what regimes apply.
- Marketing-copy review framework (handed to founder + brand workstream).
- Affiliate / referral program legal structure if pursued.

### 4.2 Phase C — before §8 real-capital gate flips

This is the heaviest legal lift; calling it out so counsel knows it exists.

- Whether enabling real-capital trading **through** the platform, even via user-owned exchange API keys, triggers brokerage / investment-management / virtual-asset-service-provider licensing in any target jurisdiction.
- If yes: where to license, where to block, where to restructure.
- Custody analysis (the platform does not custody assets, but holds API keys with trade authority — this is a legal middle ground that needs a clear answer).
- Updated Risk Disclosure for real-capital mode (heavier than testnet-mode disclosure).
- Updated ToS to cover real-capital authorization and revocation.

This Phase is **not** authorized by Phase A engagement. We are asking counsel to scope it as a follow-on, not to do it now.

---

## 5. Materials Counsel Will Receive

On engagement start, the founder will provide:

1. This brief.
2. The Production Candidate Criteria document (§7 of that doc enumerates the L1–L4 acceptance criteria from a product perspective).
3. The Vendor Failure-Mode Mapping document (sub-processor list and operational dependencies).
4. The current architecture diagram (v5).
5. A sample signal output (so counsel can see what we publish).
6. The current methodology page draft.
7. Stripe configuration screenshots (tier names, pricing, billing cadence).
8. The data inventory in §3.2 (with founder-confirmed retention numbers).

Counsel will **not** receive:

- Source code.
- ML model details or feature lists.
- Trading strategy specifics beyond what the methodology page already describes.

---

## 6. Open Items for Founder Confirmation Before Counsel Transmittal

| # | Item | Default if no decision |
|---|---|---|
| F-1 | Confirm founder's home jurisdiction | UAE |
| F-2 | Confirm operating-entity status (none, in progress, formed) | None |
| F-3 | Confirm target user geographies for closed beta | UAE/MENA + global English |
| F-4 | Confirm whether US persons are permitted at signup | Block for now |
| F-5 | Confirm whether Stripe is taking real money today, or in test mode | **Critical for counsel timing** |
| F-6 | Confirm whether any user (other than founder) has ever signed up | If yes, ToS retroactivity is in scope |
| F-7 | Confirm what `§8 gate` refers to | Treat as architectural lock for now |
| F-8 | Confirm leverage cap: engine policy says 20x, v5 architecture diagram shows 10x | Higher of the two until clarified |
| F-9 | Counsel selection / current relationships | Open hire |
| F-10 | Budget envelope for Phase A | TBD |
| F-11 | Whether Phase B and Phase C scope can be written into the engagement letter as "right of first refusal" without committing fees | Recommended yes |

---

## 7. Reference Documents

These exist in the project repo and should be transmitted alongside this brief once the founder confirms F-1 through F-11:

- `Business_Plan_v1.md` — strategic context.
- `Production_Candidate_Criteria_v1.md` — full criteria L1–L4 are in §3.7.
- `Vendor_Failure_Mode_Mapping_v1.md` — sub-processor list and dependencies.
- `OPS_Linear_Tickets_v1.md` — execution backlog (for counsel awareness; not for legal action).
- v5 architecture diagram.

---

## 8. Specific Questions Counsel Should Address in the First Engagement Call

A short list — counsel should not need to read every reference doc to answer these:

1. Given the founder's jurisdiction and target user geographies, **what is the recommended entity formation jurisdiction**, and is there a meaningful difference between forming now versus after the closed beta opens?
2. Given the architectural ToS-gate, **is a single ToS sufficient across target jurisdictions**, or do we need regional ToS variants from day one?
3. Given the Trust dashboard's signed-snapshot performance reporting, **what disclosures must accompany it** to remain on the right side of marketing-communications regimes in each target jurisdiction?
4. **Is the product, as described in §1.2 and §1.3, a regulated activity** in any target jurisdiction at the current scope (intelligence subscription, no execution, no custody)? If yes, which, and with what threshold of activity does regulation apply?
5. **What is the minimum Risk Disclosure language** that should appear on every signal-bearing page, regardless of jurisdiction?
6. **At what feature threshold** would a future Co-pilot product trigger investment-advice / brokerage classification, in each target jurisdiction?
7. **Is the 7-year trade-journal retention defensible** against deletion-rights regimes in the target jurisdictions, and what's the operational pattern (anonymization, legitimate-interest carve-out, etc.)?

---

## 9. Engagement Timeline (Proposed)

| Week | Milestone |
|---|---|
| 0 | Engagement letter signed; founder transmits this brief + reference docs. |
| 1 | First call (questions in §8); counsel returns scoping memo + price quote for Phase A. |
| 2–3 | First drafts: Risk Disclosure (priority), ToS, Privacy Policy. |
| 4 | No-investment-advice memo; founder review of Phase A drafts. |
| 5 | Counsel revisions; second-round review. |
| 6 | Phase A documents finalized; click-through flows wired; legal sign-off captured in repo. |

The Risk Disclosure is the gating item; if counsel can deliver it in week 2, the closed beta unblocks even before ToS and Privacy Policy hit final.

---

## 10. Founder Sign-off

Before this brief is transmitted to counsel, the founder confirms:

- [ ] All open items in §6 are resolved (F-1 through F-11).
- [ ] The factual descriptions in §1 are accurate.
- [ ] The "what we do not do" list in §1.3 is exhaustive — no omissions.
- [ ] Counsel selection complete (or hiring process initiated against this brief).
- [ ] Budget envelope set.

Signed: _____________________ (Mohammed) Date: _________

---

## Appendix A — Background Facts Counsel May Find Useful

- The product is built around an explicit **capital-preservation-first** principle. This is the brand. Marketing copy is constrained to be consistent with this; counsel's no-advice memo should treat this as a feature, not a vulnerability.
- The architecture isolates the real-capital execution path behind a gate (`§8 gate locked`). This is structural, not procedural.
- The validation phase (April 10 – May 9, 2026) is governed by a separate Production Candidate Criteria document. Validation outcomes do not unlock real-capital trading — they only unlock the closed beta of the read-only intelligence product.
- The product team is currently the founder, plus a strategic chief of staff agent (Scoopy). All counsel correspondence routes through the founder.
