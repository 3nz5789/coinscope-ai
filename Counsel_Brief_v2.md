# CoinScopeAI — Counsel Engagement Brief v2.0

**Date:** 2026-05-01
**Supersedes:** Counsel_Brief_v1.md (2026-05-01)
**Status:** Founder-confirmed values populated; transmittal-ready pending counsel selection (F-9)
**Prepared by:** Strategy Chief of Staff (Scoopy)
**Founder:** Mohammed (`abu3anzeh@gmail.com`)
**Engagement scope:** Phase A — ToS, Privacy Policy, Risk Disclosure, No-Investment-Advice Memo. Phase B and C scoped for context.

> Confirmed values (formerly open items F-1 through F-11) are now in §6. Two assumptions are flagged as **founder-correctable**: F-5 (Stripe live-mode-but-no-real-charges-yet) and F-6 (only founder-controlled test accounts to date). Counsel should verify both at engagement start.

---

## 0. Engagement at a Glance

| Field | Value |
|---|---|
| Engagement type | Initial fixed-scope: Phase A documents + advisory memo |
| Founder home jurisdiction | **United Arab Emirates** |
| Operating entity status | **Sole proprietor — not yet incorporated.** Counsel's first deliverable should include an entity-formation recommendation. |
| Target jurisdictions for counsel coverage | UAE (primary), EU/UK (read-across for European users), US (block-list posture) |
| Target user geographies (closed beta) | UAE / MENA + global English-speaking. **US persons blocked at signup until counsel sign-off.** |
| Phase A target delivery | 4–6 weeks from engagement start |
| Most time-sensitive item | **Risk Disclosure** (gates user access via API auth ToS-gate) |
| Founder availability | High; sole operator |
| Budget envelope | **USD $10,000–$15,000 mid-tier UAE / regional firm** |
| Phase B/C right of first refusal | **Yes — included in engagement letter, no fee commitment** |

---

## 1. Company & Product Summary

### 1.1 Entity status

CoinScopeAI is operated today by Mohammed (UAE-based) as a **sole proprietor**. No operating entity is incorporated. Counsel's first deliverable should include a recommendation on entity formation jurisdiction and timing, given target user geographies and the architectural commitments in §1.5.

### 1.2 What CoinScopeAI does today

- A **read-only intelligence subscription product**: a user pays a recurring fee to access a dashboard, signal feed, regime detection, risk-gate explanations, methodology pages, and a Telegram bot for status / positions / signals / kill commands.
- An ML-driven engine that scans crypto futures markets and outputs trading signals with a confluence score, a regime classification, and a risk-gate decision.
- A "Trust" surface (`trust.coinscope.ai`) that publishes signed, tamper-evident performance snapshots from the engine.
- Subscription billing through Stripe, with four tiers ($19 / $49 / $99 / $299).
- ToS-gated authentication: the product's API will refuse requests from any user who has not signed the Terms of Service.

**Operational state assumptions** (founder to verify with counsel at engagement start):

- Stripe is configured in **live mode but has not received real customer charges yet**. If this is incorrect (real charges have occurred), counsel should be informed immediately — that materially changes Phase A urgency.
- Aside from the founder, **no non-founder user has signed up yet**; only founder-controlled test accounts exist. If non-founder users exist, ToS retroactivity becomes a counsel-scope question.

### 1.3 What CoinScopeAI does NOT do today

This list is at least as important as §1.2.

- Trading with real customer capital. **The engine is configured for Binance Futures Testnet only.**
- Custody of customer funds. The platform never holds, receives, or transmits customer fiat or crypto.
- Discretionary trading on behalf of customers. The user does not delegate execution; today, no execution occurs.
- Personalized investment advice.
- KYC / AML pipeline activation. KYC is architected (Sumsub or Persona) but gated to a future "Team" tier.

A real-capital gate exists in the system architecture and is **explicitly locked**. The architecture marks it `§8 gate locked` — this refers to **Section 8 of the Production Candidate Criteria document** (Capital Cap & Phased Ramp). Unlocking the gate is governed by that document. Counsel should advise as if real-capital trading is **not coming online during the Phase A engagement**, and treat any future unlock as a Phase C scope item.

### 1.4 Target users

- Geographic focus (initial, beta cohort): **UAE / MENA + global English-speaking**.
- Profile: sophisticated retail / "prosumer" crypto futures traders and small trading desks. Not first-time investors.
- **US persons blocked at signup** until counsel returns the no-advice memo and the jurisdictional gate is wired.

### 1.5 Architectural facts that affect legal scope

The following architecture decisions are *already deployed* and bear on legal scope:

| Architectural fact | Legal implication |
|---|---|
| ToS-gate enforced at API auth (refuse if ToS unsigned) | ToS is a hard precondition for any user interaction. Must be in place before any non-founder user touches the dashboard. |
| Stripe subscription billing live, 4 tiers | Consumer subscription law applies (auto-renewal, refunds, cancellation, taxes, applicable consumer-protection regimes). |
| Per-user keys, per-user portfolios, per-user thresholds | Multi-tenant data model. Privacy regime applies per-user. |
| Audit log retention: 7-year trade / 1-year auth / 90-day request | This is a regulatory-grade commitment. Counsel should confirm 7-year is appropriate for target jurisdictions and does not conflict with any privacy-deletion obligation. |
| Public performance dashboard (`trust.coinscope.ai`), signed snapshots | Marketing-claims regime; some jurisdictions regulate publication of trading performance. |
| Engine system leverage cap = 10x | Tighter than industry-standard retail futures leverage; supports the capital-preservation positioning. |
| Vendor sub-processors | Stripe, Anthropic, Binance, CoinGlass, Tradefeeds, CoinGecko; future: Sumsub or Persona. Privacy disclosure obligations and data-transfer compliance. |
| Operator-side platforms | MemPalace, Notion, Linear, GitHub, Google Drive (one-way operator sync; never reads back into engine). Data-residency exposure for operator-side data. |

### 1.6 Validation phase context

The product is in a **30-day validation phase** ending ~2026-05-09. The phase's purpose is to verify engine behavior matches documented risk policy under live market conditions. The validation phase is engine-only; legal documentation is the parallel track that this engagement opens.

---

## 2. Why this engagement, why now

Three specific business decisions are gated on counsel's input:

1. **The closed beta cannot open without ToS, Privacy Policy, and Risk Disclosure in force.** The API auth layer enforces this structurally — not a policy preference, an architectural one.
2. **The "no investment advice" posture must be defensible in marketing copy and the Trust dashboard.** The Trust rail publishes live PnL with signed snapshots; this is a magnet for an "investment recommendation" classification in some jurisdictions.
3. **The entity / jurisdiction decision is gating downstream work** (banking, Stripe production scaling, beta user routing). Founder needs a recommendation, not a survey of options.

---

## 3. Specific Phase A Deliverables

### 3.1 Terms of Service (the contract)

**Form:** A standard SaaS subscription ToS adapted to a crypto-data-and-analytics product. Click-through assent at signup. Versioned; retained per user, signed and timestamped.

**Substantive content counsel should cover:**

- Definition of the service. Critically, the service is defined as **information and software access**, not investment management or brokerage.
- Subscription terms: pricing (4 tiers — $19/$49/$99/$299), billing cadence, taxes, auto-renewal, cancellation, refunds. Counsel should advise on compliance with consumer-subscription regimes in UAE, EU, UK.
- Service availability disclaimers. The system runs on third-party infrastructure (Binance, vendor APIs, cloud hosting); availability is best-effort, not guaranteed.
- IP ownership (CoinScopeAI retains all rights to signals, methodology, dashboard).
- Acceptable use. Specifically: no scraping, no resale of signals, no use in jurisdictions counsel identifies as prohibited (US persons currently blocked).
- Limitation of liability. Counsel to advise on caps; "fees-paid-in-prior-12-months" cap is intended.
- Indemnification.
- Dispute resolution + governing law (depends on entity decision).
- Force majeure (especially relevant given vendor-dependency risks).
- Modification clause + notice period.
- Termination (for cause and convenience).
- A clear "no investment advice" recital (also reinforced in the Risk Disclosure).

**Specific drafting requests:**

- A short, plain-language summary on the click-through page above the full ToS link.
- Versioning and re-acceptance flow for material changes.

### 3.2 Privacy Policy

**Form:** A privacy notice covering all jurisdictions where users may sign up, with regional addenda where required (UAE PDPL, GDPR for EU users, UK GDPR).

**Data inventory:**

| Data category | Source | Storage | Retention | Sub-processors involved |
|---|---|---|---|---|
| Account identifiers (email, hashed password) | Signup | Postgres | Account lifetime + 1y | Hosting (DigitalOcean) |
| Subscription / billing data | Stripe checkout | Stripe + minimal mirror | Per Stripe + tax retention | Stripe |
| Per-user portfolio config (symbols, risk profile) | User input | Postgres | Account lifetime | Hosting |
| API exchange keys (per-user, encrypted at rest) | User input | Encrypted vault | Until user deletes | Hosting + KMS |
| Trade journal / signal interactions | Engine | Postgres | **7 years** | Hosting |
| Auth logs | Engine | Logs store | **1 year** | Hosting |
| Request logs | Engine | Logs store | **90 days** | Hosting |
| KYC records (future, Team tier) | User upload | Sumsub / Persona | Per regulator | Sumsub or Persona |
| Public performance snapshots | Engine | `trust.coinscope.ai` | Indefinite, signed | Hosting |
| Operator-side notes about a user | Founder | Notion / GDrive | Operator policy | Notion, Google |

**Specific counsel asks:**

- Confirm 7-year trade-journal retention is supportable in EU (GDPR Art. 17) and UAE (PDPL deletion rights). Identify if a "lawful basis" + "legitimate interest" argument suffices, or if anonymization is required after a shorter window.
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
- **Capital-preservation framing is policy, not promise.** The risk policy (max DD 10%, daily loss 5%, max leverage 10x, max 3 positions, position heat ≤80%) describes how the *engine* attempts to manage exposure. It does not promise the user will not lose money.
- **Crypto-specific risks:** market volatility, exchange counterparty risk, custody risk on the user's own exchange account, regulatory risk, potential for total loss.
- **Vendor risk.** Outages of Binance, CoinGlass, Tradefeeds, etc., can affect signal quality and execution behavior. Documented in vendor failure-mode mapping.
- **No fiduciary, no advisory relationship.** Explicit disclaimer that the product does not assess the user's financial situation, risk tolerance, or suitability.
- **No guarantees of accuracy, completeness, or fitness for purpose** of any signal, regime classification, or methodology.
- **The user is solely responsible** for their own trading decisions, exchange account, and tax obligations.
- **Methodology transparency clause.** The published methodology page describes the approach in good faith but is not a complete specification.

**Specific counsel asks:**

- Does the Trust dashboard (live PnL, signed snapshots) meet definitions of "communications regarding investment performance" in any of UAE / EU / UK, and if so, what disclosures must accompany it on `trust.coinscope.ai`?
- Are testnet-period results "performance" for any regulator's purposes? Recommend explicit framing.
- For each target jurisdiction, the *minimum* disclosure language that must appear (or be linked) on every signal-bearing page.

### 3.4 No-Investment-Advice Memo (Internal — the "red/yellow/green" doc)

**Form:** An internal memo to the founder, brand, and content workstreams. Not user-facing. Used as the standing checklist for marketing copy review.

**Counsel asks:**

A structured **red / yellow / green** classification of language and product behavior across UAE, EU, UK, and (for go/no-go decisions) US:

- **Green:** unambiguously safe.
- **Yellow:** safe with explicit accompanying disclosure.
- **Red:** prohibited.

**Specific framing questions:**

- At what point does a "Co-pilot" feature (assisted execution where user clicks to confirm) cross into investment advice or brokerage in each jurisdiction? Counsel should give a specific feature-level threshold, not a category-level statement.
- Does publishing live PnL on a public URL constitute solicitation in any target jurisdiction?
- Does a Telegram bot that pushes signals to a user's private channel constitute "communication" subject to financial-promotion rules?
- Confirm the US-block posture and identify any other jurisdictions that should join the block list.

---

## 4. Phase B and Phase C Scope (For Context, Not for Phase A Engagement)

This is what counsel should know is coming, so the Phase A documents are drafted to accommodate it. **Not part of the Phase A fixed scope.** The engagement letter should include a **right of first refusal** for Phase B/C without committing fees.

### 4.1 Phase B — when validation passes (target: Q3 2026)

- Jurisdictional gating logic at signup.
- KYC / AML scoping for "Team" tier (Sumsub or Persona).
- Marketing-copy review framework.
- Affiliate / referral program legal structure if pursued.

### 4.2 Phase C — before the §8 gate flips (real-capital enable)

This is the heaviest legal lift; calling it out so counsel knows it exists.

- Whether enabling real-capital trading **through** the platform, even via user-owned exchange API keys, triggers brokerage / investment-management / virtual-asset-service-provider licensing in UAE / EU / UK.
- If yes: where to license, where to block, where to restructure.
- Custody analysis (the platform does not custody assets, but holds API keys with trade authority).
- Updated Risk Disclosure for real-capital mode (heavier than testnet-mode disclosure).
- Updated ToS to cover real-capital authorization and revocation.

---

## 5. Materials Counsel Will Receive

On engagement start, the founder will provide:

1. This brief.
2. The Production Candidate Criteria v2 document (§7 of that doc enumerates the legal acceptance criteria; §8 defines the real-capital gate that this engagement explicitly does not unlock).
3. The Vendor Failure-Mode Mapping document (sub-processor list and operational dependencies).
4. The current architecture diagram (v5).
5. A sample signal output (so counsel can see what we publish).
6. The current methodology page draft.
7. Stripe configuration details (tier names, pricing, billing cadence, current live-mode status).
8. The data inventory in §3.2.

Counsel will **not** receive:

- Source code.
- ML model details or feature lists.
- Trading strategy specifics beyond what the methodology page already describes.

---

## 6. Confirmed Values (Formerly Open Items F-1 to F-11)

| # | Item | Confirmed Value | Notes |
|---|---|---|---|
| F-1 | Founder home jurisdiction | UAE | |
| F-2 | Operating entity status | Sole proprietor — not yet incorporated | Counsel to recommend formation jurisdiction and timing |
| F-3 | Target user geographies (closed beta) | UAE / MENA + global English-speaking | |
| F-4 | US persons at signup | Blocked until counsel sign-off | |
| F-5 | Stripe state today | Assumption: live mode, no real charges yet | **Founder to verify with counsel at engagement start** |
| F-6 | Non-founder users today | Assumption: only founder-controlled test accounts | **Founder to verify with counsel at engagement start** |
| F-7 | `§8 gate` reference | Section 8 of Production Candidate Criteria (Capital Cap & Phased Ramp) | |
| F-8 | System leverage cap | 10x | Project rules string mentioning 20x is stale and being phased out |
| F-9 | Counsel selection | **Open — founder running fit conversations with UAE-fluent firms** | Candidate firms in §9 |
| F-10 | Phase A budget envelope | USD $10,000–$15,000 (mid-tier UAE / regional) | |
| F-11 | Phase B/C right of first refusal | Yes, in engagement letter, no fee commitment | |

---

## 7. Specific Questions Counsel Should Address in the First Engagement Call

1. Given the founder is UAE-based with no entity yet, **what is the recommended entity formation jurisdiction**, and is there a meaningful difference between forming now versus after the closed beta opens?
2. Given the architectural ToS-gate, **is a single ToS sufficient across UAE / EU / UK**, or do we need regional ToS variants from day one?
3. Given the Trust dashboard's signed-snapshot performance reporting, **what disclosures must accompany it** to remain on the right side of marketing-communications regimes?
4. **Is the product, as described in §1.2 and §1.3, a regulated activity** in UAE / EU / UK at the current scope? If yes, with what threshold of activity does regulation apply?
5. **What is the minimum Risk Disclosure language** that should appear on every signal-bearing page, regardless of jurisdiction?
6. **At what feature threshold** would a future Co-pilot product trigger investment-advice / brokerage classification in UAE / EU / UK?
7. **Is the 7-year trade-journal retention defensible** against deletion-rights regimes in UAE PDPL / GDPR, and what's the operational pattern (anonymization, legitimate-interest carve-out, etc.)?

---

## 8. Engagement Timeline (Proposed)

| Week | Milestone |
|---|---|
| 0 | Engagement letter signed; founder transmits this brief + reference docs. |
| 1 | First call (questions in §7); counsel returns scoping memo + price quote for Phase A. |
| 2–3 | First drafts: Risk Disclosure (priority), ToS, Privacy Policy. |
| 4 | No-investment-advice memo; founder review of Phase A drafts. |
| 5 | Counsel revisions; second-round review. |
| 6 | Phase A documents finalized; click-through flows wired; legal sign-off captured in repo. |

The Risk Disclosure is the gating item; if counsel can deliver it in week 2, the closed beta unblocks even before ToS and Privacy Policy hit final.

---

## 9. Counsel Selection Shortlist (Founder to Run Fit Conversations)

These are firms known to handle crypto / fintech work in the relevant jurisdictions. **Not endorsements** — fit conversations needed.

| Firm | Strengths | Notes |
|---|---|---|
| Al Tamimi & Co. | Largest regional firm; deep VARA / SCA experience; full UAE + GCC reach | Higher rate card; well-known to UAE regulators |
| BSA Ahmad Bin Hezeem | Crypto / fintech track record in UAE; mid-tier rate | Often pragmatic on early-stage matters |
| DLA Piper Middle East | Global firm with UAE office; EU/UK read-across in-house | International rate card; useful if EU coverage matters |
| Reed Smith UAE | Crypto-specialist partners; UAE + UK reach | Strong on financial promotion regimes |
| Charles Russell Speechlys (UAE) | UK-anchored with UAE presence; capital markets experience | Good for entity-formation advice |

**Selection criteria to apply during fit conversations:**

- Has the firm advised on a crypto-data product (not just an exchange or token issuance)?
- Can the firm cover UAE primary + EU/UK read-across without farming out the EU question?
- Does the partner-of-record understand the difference between an information product and a brokerage product?
- Will the firm commit to the Phase A timeline (4–6 weeks)?
- Is the budget envelope ($10k–$15k Phase A) realistic for that firm's quality?

---

## 10. Founder Sign-off

Before this brief is transmitted to counsel, the founder confirms:

- [x] Items in §6 reflect founder confirmations on F-1 through F-11.
- [ ] The factual descriptions in §1 are accurate.
- [ ] The "what we do not do" list in §1.3 is exhaustive — no omissions.
- [ ] **F-5 and F-6 assumptions are correct, OR the corrected values are flagged before transmittal.**
- [ ] Counsel selection complete (or hiring process initiated against this brief).
- [ ] Budget envelope confirmed.

Signed: _____________________ (Mohammed) Date: _________

---

## Appendix A — Background Facts Counsel May Find Useful

- The product is built around an explicit **capital-preservation-first** principle. This is the brand. Marketing copy is constrained to be consistent with this.
- The architecture isolates the real-capital execution path behind a structural lock at the Order Manager. The lock is the §8 gate defined in Section 8 of the Production Candidate Criteria.
- The validation phase (April 10 – May 9, 2026) is governed by the Production Candidate Criteria document. Validation outcomes do not unlock real-capital trading — they only unlock the closed beta of the read-only intelligence product.
- The system leverage cap is 10x — tighter than industry-standard retail futures leverage. Counsel may find this useful for the Risk Disclosure framing.
- The product team is currently the founder, plus a strategic chief of staff agent (Scoopy). All counsel correspondence routes through the founder.
