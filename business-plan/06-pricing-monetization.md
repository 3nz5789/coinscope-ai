# §6 Pricing and Monetization

**Status:** v1 LOCKED. All phases committed: foundation (§6.1–§6.4), Free tier scope (§6.5), tier prices (§6.6), currency and jurisdiction (§6.8), policy and refund (§6.7), §11 sensitivity flags (§6.9), anti-overclaim audit (§6.10). §11 financial model can begin drafting against §6 v1 inputs.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active; pricing structure committed at v0; specific dollar amounts are v1 territory. Anti-overclaim discipline applies — pricing must trace to §3 WTP and §5 capability maturity.

---

## 6.0 Assumptions

- **§3 v1 inputs:** WTP scoring per §3.6 — P1 Methodist M, P2 Engineer M, P3 Solo PM H.
- **§5 v1 inputs:** Three tiers (Free / Trader / Desk) with Desk Preview at v1 and Desk Full at v2. Static monthly PDF in Preview. Trader API target ~1 req/sec/endpoint.
- **§5.3 packaging principles:** no lifetime deals, no grandfather discounts, founder-cohort time-bounded, no "Premium/Pro" tier names, no anti-ICP bundling.
- **§11 horizon:** 24-month base + 36-month strategic, USD primary, AED reporting view.
- **§14 launch:** validation pass + 30-day soft-cohort floor; pricing locks for ≥6 months after validation.
- **§3 sub-$5k disciplined:** "we'll be back for you" stance pending §6 Free-tier scope decision (Phase 2).
- **§3 documented concerns:** Trader-tier price must respect P2 buy-vs-build math; Desk-tier copy must avoid fund-infrastructure framing.

---

## 6.1 Comp pricing landscape

Pricing references for comparable products our ICP currently uses or considers. Categories chosen by buyer overlap, not product similarity. All prices are monthly USD as published; some products discount on annual.

| Category | Product | Pricing range | What they offer | Buyer overlap |
|---|---|---|---|---|
| Charting baseline | TradingView | $15 / $30 / $60 | Charts, basic alerts, watchlists | P1, P2 |
| Charting baseline | TrendSpider | $33 / $65 / $99 | Pattern recognition + alerts | P2 |
| Crypto bot platforms | 3Commas | $14 / $37 / $75 | Bot creation, copy-trade, basic risk | P2 (rejects), some P1 |
| Crypto bot platforms | Cryptohopper | $24 / $58 / $107 | Strategy templates, paper-trade, marketplace | P2 (rejects), some P1 |
| Trading journals | Edgewonk | $169/year (~$14) | Journal + analytics + tags | P1 |
| Trading journals | Tradervue | $29 / $49 / $79 | Journal + tags + advanced reports | P1, some P3 |
| Quant/backtest | QuantConnect | $0 / $20 / $50 / $120 | Backtesting + cloud research | P2 |
| Quant/backtest | vectorbt PRO | $99 / $179 / $299 | High-perf Python backtesting | P2 (heavy quants) |
| Crypto data/analytics | Glassnode Studio | $29 / $99 / $399 / $799 | On-chain + market data | P2, some P3 |
| **Crypto on-chain analytics** | **Nansen** | **$99 / $1,500 / $1,800** | Wallet labels, smart-money flows, alerts | P2, P3 — both already paying |
| **Crypto on-chain analytics** | **Arkham Intelligence** | **$99 / $1,500 / $2,400** | Address attribution, on-chain visualization | P2, some P3 |
| **Quant on-chain data** | **CryptoQuant** | **$39 / $99 / $300 / Enterprise** | Exchange flows, miner data, derivatives | P2 — methodology-verifiable |
| **Direct futures analytics** | **CoinGlass Hyper / Pro** | **$29 / $79 / $290** | Liquidations, funding rates, OI heatmaps | P1, P2, P3 — direct functional overlap. **§12 risk note: we consume CoinGlass data on our P1 vendor stack; they sell a direct user-facing tier.** Dual customer-vendor relationship. |
| **Research / newsletter tier** | **Delphi Digital, The Block Pro, Messari** | **$25 / $240 / $1,000** | Research reports, market data, analyst access | P2, P3 — wallet competitor, not feature competitor |
| Signal groups (mid) | Various | $50–$150 | Curated signals, no risk infra | **anti-ICP** for us |
| Signal groups (top) | Whale-curated | $200–$500 | Premium signals + chat | **anti-ICP** for us |
| Prop firm challenges | FTMO, Apex, Topstep | $89–$1,080 challenge + $99–$700/mo subs | Funded accounts, scaling | Secondary persona (locked) |
| Adjacent journaling | TraderSync | $30 / $80 / $150 | Journal + analytics — Tradervue alternative | P1 (parenthetical) |
| Adjacent scanning | Trade Ideas | $84 / $144 / $228 | Real-time scanning + alerts (stocks-focused) | P2 (parenthetical, ceiling reference) |
| Institutional terminals | Bloomberg | ~$2,000+/mo | Comprehensive market terminal | Defines ceiling, out of range |

### Pricing-band reading

Three bands emerge from the comp landscape that map to our tiers:

- **$0–$30/mo: lead-gen / charting baseline.** TradingView Pro, free 3Commas tier, free QuantConnect. **Maps to our Free tier.**
- **$30–$150/mo: serious retail tools.** TradingView Premium, mid-tier Cryptohopper, Tradervue Gold, QuantConnect mid-tier, mid signal groups. **Maps to our Trader tier.**
- **$200–$800/mo: power-user / pro-adjacent.** Glassnode Studio, top signal groups, prop-firm subscriptions, vectorbt PRO mid-tier. **Maps to our Desk Preview and Desk Full v2.**

We are explicitly **not** competing with the $50–$500 signal-group band (locked anti-ICP) or the $2,000+/mo institutional-terminal band (out of weight class, ceiling reference).

### What our buyer is currently paying

Inferred bundle ranges from the canvases (updated against expanded comp set):

- **P1 Methodist:** TradingView Premium + Tradervue + Edgewonk + occasional CoinGlass Pro = ~$60 + $49 + $14 + $79 = **~$200/mo for partial functionality.** They cobble.
- **P2 Engineer:** TradingView + QuantConnect + Nansen Standard + CryptoQuant + (own time on backtest framework) = ~$60 + $50 + $99 + $99 = **~$300/mo + opportunity cost.** They half-build, and they pay for the data feeds they can't replicate.
- **P3 Solo PM:** TradingView + Tradervue + Nansen Pro or equivalent + CoinGlass Hyper + research-tier subscription + spreadsheet labor = ~$60 + $49 + $1,500 + $290 + $240 = **~$2,100/mo + significant manual effort.** They are paying real money already; the ceiling on what they spend is much higher than P1/P2.

The expanded comp set materially raises the ceiling we can defend at Desk Full v2 — Persona 3 is structurally already at $2k/mo bundles.

Our pricing must compete with what they're already paying, replace what they cobble, and price the time we save.

---

## 6.2 Willingness-to-pay per persona

Calibrating the monthly drag each persona can absorb against their account size.

### Persona 1 — Methodist

- **Account size band:** $20k–$150k typical.
- **Subscription drag tolerance:** **1–3% of account per month.** Casual-retail benchmark is 1–2%, but disciplined-trader buyers pay above casual norms when the product delivers discipline enforcement (their stated value). At $20k account → $20–$60/mo; at $150k → $150–$450/mo. The wider band reflects discipline-as-value rather than entertainment-as-value.
- **Buying frame:** "Does the product replace what I'm cobbling and respect my framework?"
- **Currently paying:** ~$200/mo for cobbled bundle (per expanded comp set).
- **WTP score (§3.6):** M.
- **Trader-tier landing zone:** $40–$150/mo. Beneath the comp-bundle they currently pay (~$200/mo cobbled), with better functionality. Upper end (~$150/mo) is approximately 1% of $15k account or 0.5% of $30k account — comfortably inside band.

### Persona 2 — Engineer Trader

- **Account size band:** $50k–$200k typical.
- **Subscription drag tolerance:** anchored to buy-vs-build math, not pure account percentage. Concrete bands replace the abstract "buy-vs-build" framing:
    - **Trader-tier band: $50–$150/mo.** Compares favorably to ~6 months of personal build time at engineering opportunity cost ($80–$200/hour × 200+ hours).
    - **Desk-power-user band: $200–$400/mo.** Justified when API rate limits become binding and methodology depth justifies the upgrade vs. continuing to half-build.
- **Buying frame:** "Is the methodology credible? Is the API depth sufficient? Is this cheaper than building it myself?"
- **Currently paying:** ~$300/mo for cobbled bundle (TradingView + QuantConnect + Nansen + CryptoQuant) + opportunity cost on personal backtest framework (per expanded comp set).
- **WTP score (§3.6):** M, but with API depth as the upgrade trigger to Desk.
- **Trader-tier landing zone:** $50–$150/mo. Must respect the buy-vs-build math (per §3 documented concern).
- **Trader → Desk power-user trigger:** when API rate limits become binding. Desk-Preview-as-power-user landing zone: $200–$400/mo.

### Persona 3 — Solo PM

- **Account size band:** $200k–$1M aggregate.
- **Subscription drag tolerance — conditional:**
    - **0.3% of book/month if the product replaces their current cobbled bundle.** At $200k → ~$600/mo; at $1M → ~$3,000/mo. This is the *bundle-replacement* WTP — what they'll pay to consolidate Nansen + CoinGlass Pro + research-tier + journal + spreadsheets into one product.
    - **Up to 1% of book/month if the product additionally delivers partner reporting at audit-grade.** At $200k → up to $2,000/mo; at $1M → up to $10,000/mo. The premium reflects that partner reporting is operationally expensive to produce without infrastructure; replacing manual effort + reducing reporting risk justifies higher drag.
- **Buying frame:** "Does this look professional to my partners? Does it justify the cost as a percentage of book? Does it scale with me?"
- **Currently paying:** ~$2,100/mo for cobbled bundle + significant manual effort (per expanded comp set: TradingView + Tradervue + Nansen Pro + CoinGlass Hyper + research-tier).
- **WTP score (§3.6):** H.
- **Desk Preview landing zone:** $250–$500/mo. ~0.05–0.1% of $500k book — comfortably under bundle-replacement tolerance. Preview-priced because v1 delivers bundle replacement but only static-PDF partner reporting (not audit-grade).
- **Desk Full v2 landing zone:** $750–$1,500/mo (excluding per-seat add-ons). 0.15–0.3% of $500k book at base; with per-seat additions, can scale to ~0.5% of book for a 3–5 partner book. Justified by:
    - **Lower bound** ($750/mo): clean 3x step from Desk Preview upper ($500), differentiates the v2 upgrade trigger meaningfully. Roughly 0.375% of $200k book floor — well within bundle-replacement WTP.
    - **Upper bound** ($1,500/mo): replaces P3's currently-paid $2,100/mo cobbled bundle, with switching-friction discount built in.
    - **Per-seat add-ons** push the total higher proportionally with partner count, capturing the audit-grade-reporting premium that justifies up to 1% of book.

### Cross-persona pricing-power asymmetry

P3 carries 5–10x the per-user revenue of P1 at equivalent drag-tolerance. §11 financial model should expect:

- P1 + P2 drive **paid user count.** Volume side.
- P3 drives **revenue per user.** Margin side.
- A balanced cohort across all three is healthier than a P3-heavy cohort (concentration risk) or a P1-heavy cohort (margin compression).

---

## 6.3 Subscription, usage, or hybrid — model decision

Three monetization models considered:

### Model A — Pure tiered subscription

Free / Trader / Desk Preview / Desk Full. Flat monthly fee per tier. Same model as TradingView, Tradervue, Glassnode Studio.

**Pro:** predictable revenue (clean §11 modeling), fits SaaS norms, simple billing, fits §3 P1 buying frame ("predictable monthly cost").

**Con:** does not differentiate between a Persona 3 with 3 partners and a Persona 3 with 8 partners — both pay the same Desk Full price despite different product utilization.

### Model B — Pure usage-based

Per-API-call, per-trade, per-account, per-signal. Same model as cloud infrastructure.

**Pro:** revenue scales with utilization; no tier-overflow (no "I'm paying for features I don't use" friction).

**Con:** Billing variability conflicts with disciplined-buyer expectations. Per-trade pricing creates *adverse incentive* — we'd be rewarded by users trading more, which is anti-ICP. P1 hates surprise billing. P2 may tolerate usage on API but not on the product overall.

**Reject.** The per-trade variant specifically conflicts with capital-preservation positioning. We do not want to be paid more when our user trades more; we want to be paid more when our user *manages a bigger book*.

### Model C — Hybrid (subscription baseline + per-seat for Desk Full)

Free / Trader / Desk Preview as flat subscription. Desk Full v2 as subscription + per-seat charge above the included PM seat (partner read-only seats and analyst seats priced per-seat).

**Pro:** captures Persona 3's variable scale (3-partner book vs. 8-partner book) without per-trade adverse incentive. Matches institutional SaaS norms (Slack, Notion, GitHub all do per-seat). Aligns revenue with the dimension that matters — book size and partner count, not trade volume.

**Con:** slightly more complex billing and pricing-page communication. Requires §10 ops to support per-seat invoicing (light lift; existing billing platforms handle this).

### Recommendation

**Model C — hybrid.** Subscription tiered for Free / Trader / Desk Preview; subscription + per-seat for Desk Full v2.

Reasoning: aligns revenue with book size and partner count (P3's actual scale dimension), preserves predictable subscription cleanliness for P1 / P2 / Preview, avoids the per-trade adverse incentive that would conflict with capital-preservation positioning, and matches the SaaS norms our P3 buyers (often coming from financial-services or tech operator backgrounds) recognize.

**Per-seat structure for Desk Full v2:**

- 1 PM seat included in base subscription.
- Partner read-only seats: priced per-seat per month, low-touch (ideally 10–25% of base subscription per seat).
- Analyst seats: priced per-seat per month, slightly higher than partner read-only because analyst seats have write privileges.

Specific seat pricing locks in Phase 2 alongside tier prices.

---

## 6.4 Phase 1 close — what's locked, what opens to Phase 2

**Locked at v0.1:**

- Comp pricing landscape mapped to tier bands.
- WTP per persona quantified against §3.6 matrix.
- Monetization model: Model C (hybrid subscription + per-seat for Desk Full v2).
- Pricing-band landing zones per tier (ranges, not specific prices).

**Opens to Phase 2:**

- Free tier scope decision (open per §3 documented concerns).
- Specific tier prices v1 (USD + AED) within the landing-zone bands.
- Per-seat pricing structure for Desk Full v2.
- Currency and jurisdiction handling.

---

## 6.5 Free tier scope

### Locked scope: account-verified entry tier with "we'll be back" messaging

Free tier is **account-verified, no paid-feature exceptions, with personalized "we'll be back" messaging for sub-$5k disciplined users.**

### What Free includes (locked)

- Account verification at signup — verified exchange account at any size.
- Read-only access to curated top-5 signal list, daily refresh, delayed.
- Per-symbol regime label without confidence score.
- Demo-trade view of risk gate behavior (no personal trade data).
- Engine methodology documentation (per §5.3.1, public regardless of tier).
- Validation phase status disclosure (per §5.3.1).
- "What CoinScopeAI does not do" reference page (per §5.3.4).
- Capital-preservation primitives operating on demo trades (kill switch, drawdown ceilings — §5.3.1).
- **Personalized "we'll be back" messaging** for sub-$5k disciplined verified users: framing that positions Trader tier as the destination when account crosses the $5k floor.

### What Free excludes (locked)

- Personal performance journal (§5.3.2 paid feature; no exception for sub-$5k).
- Real-time / full-fidelity signal feed (§5.3.2).
- Configurable risk gate (§5.3.2).
- Telegram bot (§5.3.2).
- API access (§5.3.2).
- Any execution-adjacent capability.

### Why Scope B over alternatives

- **Fulfills §3.5 "we'll be back" stance through messaging**, not through §5.3.2 packaging-principle exception. Brand-voice alignment is real without compromising the locked principle.
- **Account verification sets up §7 funnel cleanly.** Sub-$5k Free users are the recruiting pool — we recognize them and prompt them at the $5k threshold without manual intervention.
- **Support load stays low.** No paid-feature obligations for non-paying users.
- **Upgrade path is simple.** §3.7 interview data may show sub-$5k disciplined would convert at meaningfully higher rates with journal access; if so, extending Scope B → Scope C (journal exception) is a clean post-validation decision.

### Specific "we'll be back" messaging requirements

Sub-$5k verified users see persistent in-product copy that:

- Acknowledges them as future-ICP, not as second-class users.
- Frames Trader tier as the destination, not as a paywall.
- Offers a wishlist / "notify me when account crosses floor" subscription.
- Surfaces the capital-preservation primitives they *do* get on demo trades as evidence we treat their discipline seriously.

§9 messaging matrix inherits this requirement; no slogan-tier "upgrade now" pressure copy on Free for sub-$5k users.

### What this unlocks

- **§6.6 tier prices v1** can now treat Free as $0 with no further scope ambiguity.
- **§7 GTM funnel** has a defined sub-$5k recruiting pool that converts at the $5k threshold.
- **§3.5 anti-persona stance fulfilled at product layer**, not just marketing layer.
- **§11 cost model** can model Free as zero-revenue, low-support segment with explicit conversion-trigger metric (account size crosses $5k).

---

## 6.6 Tier prices v1 (USD)

### Locked v1 prices — Candidate B mid-band anchored

| Tier | Monthly | Annual (paid yearly) | Founder cohort* |
|---|---|---|---|
| **Free** | $0 | $0 | $0 |
| **Trader** | **$79/mo** | **$790/yr** ($65/mo equiv, ~17% off) | $59/mo |
| **Desk Preview** | **$399/mo** | **$3,990/yr** ($332/mo equiv) | $299/mo |
| **Desk Full v2** | **$1,199/mo** | **$11,990/yr** ($999/mo equiv) | $899/mo |
| Desk Full — per partner read-only seat | **$149/mo** | $1,490/yr | $99/mo |
| Desk Full — per analyst seat | **$249/mo** | $2,490/yr | $179/mo |

*Founder cohort pricing locked for first 60 days post-public-launch (P2 phase per §5.4 roadmap). Auto-converts to standard pricing at the next renewal date after the 60-day window closes. Per §5.3.3, no grandfather discount — founder-cohort price is time-bounded, not legacy.

### Pricing rationale per tier

**Trader at $79/mo.** Mid-band of locked $40–$150 zone. Beneath P1's ~$200/mo cobbled-bundle estimate (60% savings to switch). At this price, $948/yr is below ~10 hours of senior engineering time — making P2's buy-vs-build math harder to defend. Annual paid-yearly at $790 (~17% discount) drives retention.

**Desk Preview at $399/mo.** Mid-band of locked $250–$500 zone. Roughly 5x Trader monthly, recognizable Preview-tier step-up. Well under P3's $200k-floor bundle-replacement WTP (~$600/mo at 0.3% drag). Justifies the multi-account view + static monthly PDF combination at v1.

**Desk Full v2 at $1,199/mo.** Mid-band of locked $750–$1,500 zone (excluding per-seat). 3x step from Desk Preview ($399 → $1,199). 0.24% of $500k book at base — comfortable bundle-replacement drag. Plus 2–3 partner seats ($149 each) reaches ~$1,500–$1,800/mo total — replaces P3's currently-paid $2,100/mo cobbled bundle with switching-friction discount.

**Per-seat $149 partner read-only.** ~12% of Desk Full base subscription per seat — within the locked 10–25% per-seat band. Light enough that adding partners is frictionless; substantial enough to capture the audit-grade-reporting premium that justifies up to 1% of book at full partner count.

**Per-seat $249 analyst.** ~21% of Desk Full base per seat — higher than partner read-only because analyst seats have write privileges and more functional access.

### Annual billing discount logic

All paid tiers offer ~17% discount on annual prepay (10 months for the price of 12). Reasons:

- **Cash flow.** Annual prepay smooths revenue and reduces working-capital needs at the founder/operator scale modeled in §11.
- **Retention.** Annual commitment reduces involuntary churn and gives §13 cohort retention metrics cleaner monthly cohorts.
- **Anchor.** Monthly price is the reference; annual is the discount. Avoids signaling that monthly is overpriced.

### Founder-cohort pricing logic

Founder-cohort discount is **~25–30% off standard pricing**, applied to **first 60 days post-public-launch**. Reasons:

- **Soft-launch conversion incentive.** Soft-cohort users (per §14) and the first wave of public users get a meaningful early-supporter discount.
- **Time-bounded per §5.3.5.** No "lifetime" promise. Locked through one renewal cycle (annual or monthly) starting at signup; converts to standard at the next renewal after 60 days.
- **Anchored to public-launch date, not validation pass.** Validation phase users are not "founder cohort" — they are validation. Founder cohort is the public-launch gift.

### What this unlocks

- **§11 financial model** has revenue-per-paid-user inputs: Trader $79/mo (annualized $790), Desk Preview $399/mo, Desk Full v2 base $1,199/mo + per-seat additions.
- **§7 GTM** can model funnel economics with concrete CAC tolerance per tier.
- **§14 launch comms** can reference exact pricing in launch announcements.
- **§9 messaging matrix** has the price anchor for tier descriptions.

### Open dependency for Phase 3

- **AED conversion** for §6.8 — exchange rate snapshot, AED display strategy, payment processor jurisdiction.
- **Refund policy** for §6.7 — affects effective revenue per cohort.
- **Discount stacking** for §6.7 — can annual + founder-cohort stack? Recommendation: no, founder-cohort applies only to monthly billing within the 60-day window; annual prepay locks at standard discount.

---

## 6.7 Discount, refund, and founder-cohort policy

### Refund policy

- **14-day money-back guarantee** for first-time paid customers. Single-use per account. Applies to monthly and annual subscriptions.
- **No refunds after 14 days.** User can cancel anytime; access remains until end of current billing period.
- **Annual prepay refunds** are pro-rated only within the 14-day window; after day 14, annual is locked through the term.
- **Per-seat refunds** follow the same logic — first-time-seat-add gets 14 days; subsequent additions are non-refundable but cancel at next renewal.
- **Anti-abuse:** the 14-day guarantee is not stackable across re-signups. Account-level enforcement; one refund window per email or payment method, whichever is more restrictive.

### Mid-cycle changes

- **Tier upgrades** (e.g., Trader → Desk Preview): take effect immediately. User charged pro-rated difference for remainder of current billing period.
- **Tier downgrades** (e.g., Desk Preview → Trader): take effect at next renewal. No immediate refund of difference.
- **Per-seat additions:** immediate, pro-rated charge.
- **Per-seat removals:** take effect at next renewal.
- **Annual ↔ monthly switch:** allowed only at renewal boundary, not mid-cycle.

### Founder-cohort policy (full)

- **Eligibility window:** sign-ups during the first 60 days post-public-launch (P2 phase per §5.4 roadmap). Soft-launch users (P1 phase) get founder-cohort pricing automatically.
- **Discount magnitude:** ~25–30% off standard pricing per §6.6 prices table.
- **Lock duration:** founder-cohort price locks through one renewal cycle from signup. For monthly billing → standard pricing applies at the renewal after the 60-day window closes. For annual billing → founder-cohort price locks for the full annual term, then converts to standard at next annual renewal.
- **No stacking with annual prepay discount.** Founder cohort applies to monthly billing within the 60-day window; annual prepay locks at standard 17% discount, not stackable. Users choose one or the other.
- **No grandfather discount.** Per §5.3.3, founder-cohort price is time-bounded, not legacy. Pricing changes apply to all users at next renewal.
- **No "founder-cohort forever" framing.** Marketing copy must use "founding member" or "early-supporter pricing" language, never "lifetime" or "permanent."

### Promotions outside founder cohort

- **Case-by-case approval.** No standing discount programs at v1.
- **Maximum discount:** 25% off standard pricing for any approved promotion. Avoids race-to-the-bottom signaling.
- **Maximum duration:** 30-day promotional window with auto-revert to standard.
- **Anti-ICP guard:** no co-marketing or bundled promotions with signal groups, copy-trade products, leverage-maximizer content, or any anti-ICP product. Per §5.3.3.
- **Partnership-driven discounts** (e.g., prop-firm partnership per §8 — when applicable): structured as fixed-amount or percentage discount with explicit time-bounded terms; no permanent affiliate-driven discount classes.

### Cancellation and reactivation

- **Cancel anytime.** Effective at end of current billing period.
- **Reactivation within 90 days** restores prior tier and pricing. After 90 days, user re-onboards as new account at current standard pricing — founder-cohort is *not* re-extended.
- **Account data retention** post-cancellation: journal and configuration retained for 90 days for reactivation; permanently deleted thereafter unless user requests longer hold (§10 ops).

### Edge cases

- **Failed payment:** retry 3 times over 7 days. Account moves to "past due" state with read-only access until resolved. After 14 days past due → suspended; data retained per cancellation policy above.
- **Chargebacks:** account immediately suspended pending review. Chargeback abuse triggers permanent ban.
- **Refund-then-resubscribe pattern:** anti-abuse enforcement caps refunds at one per account lifetime.

---

## 6.9 LTV/CAC sensitivity flags for §11

§11 financial model consumes the following inputs from §6 v0.7. Sensitivities ranked by impact on base-case unit economics.

### Inputs §11 consumes from §6

- **Tier prices** (from §6.6): Trader $79/$790, Desk Preview $399/$3,990, Desk Full v2 $1,199/$11,990, per-seat $149 / $249.
- **Annual vs. monthly mix** (assumption, not yet locked): suggested base case 40% annual / 60% monthly for Trader; 60% annual / 40% monthly for Desk Preview; 75% annual / 25% monthly for Desk Full v2 (P3 expects predictable budget).
- **Founder-cohort effective ARPU during 60-day window:** ~25–30% below standard. Affects first 2 months post-public-launch revenue.
- **Per-seat density assumption for Desk Full v2:** base case 2.5 seats per Desk Full account (1 PM + 1.5 partner read-only on average); upside 4 seats; downside 1 seat (PM-only).
- **Free → Trader conversion rate** (assumption): base case 5% over 90 days; upside 10%; downside 2%.
- **Trader → Desk Preview conversion rate** (assumption): base case 8% over 12 months; upside 15%; downside 4%.
- **Desk Preview → Desk Full v2 migration rate at v2 launch:** base case 70% (most Preview users upgrade); upside 90%; downside 50%.

### Sensitivity ranking — most impactful first

1. **Per-seat density at Desk Full v2.** Each additional seat at $149/mo adds ~$1,800/yr revenue. A book averaging 4 seats vs. 2.5 seats is +$2,700/yr per Desk Full account. P3 cohort revenue is highly leveraged on this.
2. **Free → Trader conversion rate.** Volume side. Base 5% vs. downside 2% means 2.5x difference in Trader cohort size. Direct multiplier on §11 revenue.
3. **Annual vs. monthly mix.** Cash flow + retention math. Higher annual mix improves working capital and reduces involuntary churn but locks in the ~17% discount.
4. **Desk Preview → Desk Full v2 migration rate.** Revenue ramp at v2 launch. Critical for §15 investor narrative — investors will model this directly.
5. **Trader → Desk Preview conversion rate.** Lower volume, higher per-event revenue. Less sensitive than Free → Trader but still material.
6. **Founder-cohort effective ARPU.** Material only in the 60-day window; small effect on 24-month total.

### CAC tolerance per tier (LTV/CAC ≥ 3 floor)

Approximate first-pass numbers for §11 to validate against:

- **Trader CAC tolerance:** Annual ARPU $790 × ~2 year average tenure (assumption) = LTV ~$1,580. CAC ceiling at 3:1 → ~$525. Realistic CAC range $80–$300 for organic + light paid funnel.
- **Desk Preview CAC tolerance:** Annual ARPU $3,990 × ~2.5 year tenure (P3 retention higher per §3.6 matrix) = LTV ~$10,000. CAC ceiling at 3:1 → ~$3,300. Realistic CAC range $300–$1,500 (relationship-driven channels).
- **Desk Full v2 CAC tolerance:** Annual ARPU $11,990 base + ~$5,400 per-seat (avg 3 seats × $1,800) = ~$17,400 × 3-year tenure = LTV ~$52,000. CAC ceiling at 3:1 → ~$17,000. Realistic CAC range $2,000–$8,000.

### Cohort retention assumptions to validate via soft cohort

- **Trader 12-month retention:** assumed 60% (industry benchmark for SaaS at this price point).
- **Desk Preview → Desk Full v2 retention through v2 transition:** assumed 70%.
- **Desk Full v2 12-month retention post-launch:** assumed 80% (high-touch, partner-money obligations create switching cost).

§3.8 soft-cohort behavioral grid is the validation instrument for these assumptions.

### Step-function operational costs to flag in §11

- **VAT registration** at AED 375k (~$102k) annual revenue. Adds tax-collection and remittance overhead.
- **Stripe processing fees:** ~2.9% + $0.30 per transaction for cards; lower for ACH if available; AED conversion adds ~1% FX margin. §11 should model 3.5% blended.
- **Per-seat invoicing complexity:** light at v1 (Stripe handles), but support inquiries scale with seat count.

---

## 6.10 Anti-overclaim audit on §6 v0.7

Audit performed against §6.5, §6.6, §6.7, §6.8 on 2026-05-01. Three flags surfaced. None substantive enough to require pricing changes; all are wording or framing flags for downstream copy.

### Flag 1 — Founder-cohort framing

The 25–30% founder-cohort discount with auto-conversion at next renewal is principled (§5.3.5 time-bounded). But marketing copy implementations could drift toward "founding member discount" patterns that *imply* permanence even when contractually time-bounded.

**Mitigation.** §9 messaging matrix inherits a strict rule: **never use "lifetime," "forever," "always," or "founder discount locked-in" framing for founder-cohort pricing.** Acceptable language: "founding-member pricing — locked through your first renewal cycle, then standard pricing applies." Explicit about the time-bound.

### Flag 2 — "Stabilizing" UI label and pricing tension

Trader tier ships with dashboard IB items labeled "stabilizing in cohort" per §5.2.3. We are charging $79/mo for a tier with "stabilizing" features. Pricing copy must not market the IB items as "shipped at maturity."

**Mitigation.** Pricing-page tier descriptions must visually surface the "stabilizing" status alongside the price. Acceptable: "Trader — $79/mo. Includes engine API + dashboard (stabilizing in cohort during validation phase)." Unacceptable: "Trader — $79/mo. Full dashboard access." §9 inherits this.

### Flag 3 — AED display vs. local-entity implication

The AED conversion display at checkout for MENA users is a courtesy display, not a local-entity registration. We are a UAE sole prop, not a MENA-multi-country entity. AED display must not imply we are tax-registered or legally established in any country other than UAE.

**Mitigation.** AED conversion shown as "Approximate AED equivalent — billed in USD. UAE sole prop (Mohammed). Other GCC users responsible for any local tax obligations." Verbose but honest. §10 ops + §12 risk register inherit this guard.

### What audited clean

- Tier prices traceable to §6.2 WTP bands and §6.3 Model C structure — no overclaim.
- Free tier scope (Scope B) explicitly does not promise journal access — no §5.3.2 exception leak.
- Desk Preview pricing explicitly labeled "Preview" — no "full Desk" framing leak.
- v3-deferred features (LP-style gates, tax-ready exports) absent from any tier description in §6.
- Refund policy and discount stacking rules align with §5.3.3 packaging principles.

### §6 v1 LOCKED

§6.5 / §6.6 / §6.7 / §6.8 / §6.9 / §6.10 all committed. §11 financial model can begin drafting against §6 v1 inputs.

---

## 6.8 Currency and jurisdiction handling

### Locked

- **Pricing-page currency:** USD-primary globally. AED conversion shown alongside at checkout for MENA-region users (region-detected, not user-selected by default — user can switch).
- **Payment processor:** Stripe. UAE entity support, multi-currency native, SaaS-standard.
- **VAT posture for v1:** below UAE registration threshold (AED 375,000 ~$102k annual revenue). No VAT collection until threshold approached.

### USD-primary rationale

- Preserves §11 financial model currency anchor.
- Globally interpretable; doesn't fragment the pricing page across regions.
- AED display at checkout signals MENA-aware without making AED the primary surface.
- Mirrors how the locked comp set (TradingView, Glassnode, Nansen) presents pricing.

### AED conversion display behavior

- Region-detected at first page load (geolocation hint, not blocking).
- AED equivalents displayed at standard exchange rate (USD/AED ≈ 3.673 fixed peg, so conversion is mechanical not market-rate).
- User-toggle option to switch back to USD-only display.
- Annual prices in AED shown as paid-yearly equivalent.

### Stripe configuration

- UAE entity registration supported by Stripe Atlas equivalents and direct merchant accounts.
- Subscription billing native (monthly + annual).
- Per-seat pricing supported via Stripe-native quantity-based subscriptions.
- Founder-cohort pricing implemented as time-bounded promo codes.
- Multi-currency support — USD as account currency, AED display via region-detection layer.

### VAT and tax handling

- **UAE VAT threshold:** AED 375,000 (~$102k USD) annual taxable revenue. Below threshold → not required to register or collect.
- **v1 posture:** below-threshold, no VAT collection. Pricing displayed inclusive (i.e., $79 is the all-in price).
- **Trigger to revisit:** when revenue approaches AED 30k–35k/month (~$8.2k–$9.5k USD), begin VAT-registration preparation. §11 cost model flags this as a step-function operational cost.
- **Non-MENA users:** their local tax obligations are their own (or merchant-of-record's, if we ever migrate to Paddle).
- **Other GCC users:** KSA, Bahrain, Oman have separate VAT regimes; our UAE-resident posture means we collect UAE VAT (if registered) on UAE customers; cross-border GCC VAT rules apply only if specifically registered there. Operational complexity flagged for §12.

### What this unlocks

- §11 financial model uses USD as primary, AED as reporting view, with VAT-step-function flag at the threshold.
- §7 GTM can advertise AED-aware checkout in MENA-region copy without hard-localizing the pricing page.
- §10 ops doesn't need to build multi-jurisdiction tax handling at v1.

### Documented post-v1 considerations (not v1 commitments)

- **Paddle merchant-of-record migration** — revisit if VAT compliance becomes meaningful operational burden post-threshold. Higher cut, lower complexity.
- **Direct AED billing** — currently the AED display is conversion at peg; a future option is direct AED-denominated subscription with bank-transfer support for MENA users who prefer it.
- **Crypto payments** — not v1. Considered, deferred. Adds complexity for testnet-only validation; revisit post-v2.

---



---

## Open questions for the founder (Phase 1 only)

1. **Comp pricing landscape — anything missing?** I included TradingView, 3Commas, Cryptohopper, Tradervue, Glassnode, prop-firm subs, signal groups. Specific tools I should add to the comp set?
2. **WTP drag-tolerance percentages.** Used 1–2% of account/month for P1, 0.3–1% of book/month for P3. These are inference numbers; comfortable with the bands or want to adjust?
3. **Subscription + per-seat (Model C) hybrid choice.** Comfortable with rejecting per-trade and pure usage models, or want a different cut?
4. **Pricing-band landing zones — directionally right, or want to widen/narrow?**
   - Free: $0
   - Trader: $40–$120/mo
   - Desk Preview: $250–$500/mo
   - Desk Full v2: $600–$1,200/mo + per-seat
