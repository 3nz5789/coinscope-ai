# §11 Financial Model — Assumptions Document

**Status:** v1 markdown LOCKED. All sub-sections (§11.0–§11.7) committed. Phase 3b sensitivity ran six inputs; audit applied six flags as framing/documentation (no number changes). xlsx (`11a-financial-model.xlsx`) **PENDING** — final deliverable.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active; pricing locked at §6 v1 but no actuals exist yet. All inputs tagged by source. Numbers are inference-based until soft cohort produces observed data.

---

## 11.0 Assumptions framework and inheritance

### Source taxonomy

Every quantitative input in §11 is tagged:

- **`A` — assumed.** Inference without external evidence. Most v0 inputs sit here. Refined to `O` once soft-cohort or post-launch data lands.
- **`O` — observed.** Measured from CoinScopeAI's own data (validation cohort, soft cohort, public-launch actuals). None at v0; the count grows as we ship.
- **`B` — benchmarked.** Drawn from comparable industry data — comp set per §6.1, public SaaS benchmarks, prop-firm and quant-tool retention literature.

### Inherited from locked decisions

- **§6 v1 pricing** (the revenue side):
    - Trader: $79/mo, $790/yr, founder-cohort $59/mo
    - Desk Preview: $399/mo, $3,990/yr, founder-cohort $299/mo
    - Desk Full v2: $1,199/mo, $11,990/yr, founder-cohort $899/mo
    - Per-seat: $149 partner read-only, $249 analyst
    - Annual ~17% off; founder-cohort ~25–30% off, 60-day window post-public-launch
- **§5.4 phase map** (timeline anchor):
    - P0 M0 (May 2026) — validation
    - P1 M1–M2 (Jun–Jul 2026) — soft launch (40-user cap)
    - P2 M3–M4 (Aug–Sep 2026) — v1 public launch
    - P3 M5–M7 (Oct–Dec 2026) — v1 stabilization
    - P4 M8–M9 (Jan–Feb 2027) — v2 prep
    - P5 M10–M12 (Mar–May 2027) — Desk Full launch + v2 stabilization
- **§3.8 soft-cohort mix:** 50% P2 / 30% P1 / 20% P3 (target).
- **§6.9 sensitivity flags:** per-seat density, Free→Trader conversion, annual/monthly mix, Desk Preview→Desk Full v2 migration, Trader→Desk Preview conversion, founder-cohort effective ARPU.
- **§14 launch sequencing:** validation pass + 30-day soft-cohort floor; pricing locks for ≥6 months post-validation.
- **§15 raise posture:** no investor-funded burn assumed in base case (founder-cost only).
- **§5.4.7 execution-resource flag:** P4 (Jan–Feb 2027) is the highest-risk phase for solo execution; §11 must model two cost scenarios (solo vs. solo + 1–2 contractors for ~3 months).

### Currency

- **Primary:** USD.
- **Reporting view:** AED (peg-converted at USD/AED 3.673; not market-rate).
- **VAT step-function trigger:** AED 375,000 (~$102k) annual revenue. Below threshold = no collection.

### Scenario structure

Three scenarios per §16 (drafted later):

- **Base case:** central assumptions, target outcome.
- **Bull case:** favorable but plausible — conversion rates at upside, retention strong, P3 cohort fills.
- **Bear case:** unfavorable but plausible — conversion at downside, P3 cohort thin, validation produces marginal cohort behavior.

Phase 1 documents base case only. Bull and bear are derived in Phase 3 (sensitivity + scenarios).

---

## 11.1 Top-of-funnel and signup model (base case)

### Soft cohort — P1 (M1–M2)

- **Cap:** 40 paid users (per §14, capped at 25–50; we plan to fill upper).
- **Mix:** target 50/30/20 P2/P1/P3 per §3.8 → ~20 P2 + 12 P1 + 8 P3.
- **Tier distribution:** P1 → Trader; P2 base layer → Trader; ~10% of P2 self-select as power-users → Desk Preview; P3 → Desk Preview.
    - Estimated soft-cohort tier split: **30 Trader + 10 Desk Preview** at founder-cohort pricing. (12 P1 + 18 P2 base → Trader; 2 P2 power-users + 8 P3 → Desk Preview.)
- **Founder-cohort pricing applies:** Trader $59/mo, Desk Preview $299/mo.
- **Soft-cohort recurring revenue:** 30 × $59 + 10 × $299 = $1,770 + $2,990 = **$4,760/mo** during P1. **`A`**

### Waitlist + public-launch onboarding (M3 onwards)

- **Validation-phase waitlist:** assumed 200 names by M3, drawn from founder network + early outreach + content-driven inbound. **`A`**
- **Waitlist → paid conversion:** assumed 30% in M3, 15% in M4, 5% trickle thereafter. **`A`** (benchmarked against typical SaaS waitlist conversion at ~20–40% in launch month, decaying.)
- **Free signup growth (organic):** assumed M3=50, M4=80, growing 25% MoM through M9, tapering to 15% MoM through M24. **`A`** (Soft growth curve absent paid acquisition.)
- **Free → Trader conversion:** 5% over 90 days base case. **`A`** Per §6.9. Soft cohort observation will validate.
- **Paid acquisition assumption:** off until M5 (per §14 launch — no paid acquisition until public launch is stable). M5+ assumes light paid acquisition at $200 CAC for Trader-tier targeting; ramps based on §11.2 unit economics. **`A`**

### Cohort sizing — base case month by month

Approximate. Actuals will diverge; this is the structural shape, not the locked number.

| Month | Phase | Free signups (cumulative) | Free active | New Trader | Trader cohort active | New Desk Preview | Desk Preview cohort active | New Desk Full v2 | Desk Full active |
|---|---|---|---|---|---|---|---|---|---|
| M1 | P1 soft | 0 | 0 | 30 | 30 | 10 | 10 | — | — |
| M2 | P1 soft | 0 | 0 | 0 | 30 | 0 | 10 | — | — |
| M3 | P2 launch | 50 | 45 | 65 | 93 | 12 | 22 | — | — |
| M4 | P2 launch | 130 | 110 | 35 | 123 | 5 | 26 | — | — |
| M5 | P3 stab | 230 | 180 | 20 | 140 | 4 | 27 | — | — |
| M6 | P3 stab | 350 | 250 | 18 | 152 | 4 | 30 | — | — |
| M7 | P3 stab | 480 | 320 | 16 | 162 | 4 | 32 | — | — |
| M8 | P4 prep | 620 | 380 | 18 | 174 | 5 | 35 | — | — |
| M9 | P4 prep | 770 | 440 | 18 | 184 | 5 | 38 | — | — |
| M10 | P5 launch | 940 | 510 | 22 | 198 | -25 (migrate to Full) | 17 | 25 | 25 |
| M11 | P5 launch | 1,140 | 590 | 25 | 215 | 5 | 20 | 8 | 33 |
| M12 | P6 stab | 1,360 | 670 | 24 | 230 | 6 | 24 | 6 | 39 |

Tags on the table: cohort sizing and conversion rates are all **`A`** (assumed). Absolute numbers are illustrative; the *shape* (S-curve with v2-launch step at M10) is the load-bearing claim.

### Retention curve — base case

Monthly retention assumptions, applied as stable monthly rates after a higher initial-month churn:

- **Trader:** 92% monthly retention after month 1; month-1 churn 15% (typical first-month abandonment). Annualized ≈ 60% retention. **`B`** (mid-market SaaS benchmark.)
- **Desk Preview:** 95% monthly retention after month 1; month-1 churn 10%. Annualized ≈ 70%. **`B`** Higher because P3 has structural switching cost.
- **Desk Full v2:** 96% monthly retention; month-1 churn 5%. Annualized ≈ 80%. **`B`** Highest because partner-money obligations + audit-grade dependencies.

### Annual vs. monthly mix — base case

- **Trader:** 40% annual / 60% monthly. **`A`** P1 disposition mixed; typical SaaS at this price point.
- **Desk Preview:** 60% annual / 40% monthly. **`A`** P3 prefers predictable budget for partner reporting.
- **Desk Full v2:** 75% annual / 25% monthly. **`A`** P3 commits to longer terms when product-market fit lands.

### Per-seat density at Desk Full v2 — base case (time-varying)

The Desk Full v2 cohort evolves from P2-power-user-skewed (early) to pure-P3-skewed (mature). Per-seat density tracks this evolution.

- **Early v2 (M10–M18): 2.0 seats average per account.** Cohort blend ~70% pure P3 + ~30% P2 power-user. Pure P3 averages 2.5 (1 PM + 1.5 partner); P2 power-user averages 1 (PM only). Blend: 0.7 × 2.5 + 0.3 × 1.0 = ~2.0 total seats. **`A`**
- **Mature v2 (M19+): 2.5 seats average per account.** Pure-P3 dominance as relationship-driven acquisition matures and partner-seat utilization saturates. **`A`**
- **Upside:** 4 seats (PM + 2 partner + 1 analyst).
- **Downside:** 1 seat (PM only — no per-seat revenue).

---

## 11.2 Revenue model (base case)

### Standard vs. founder-cohort pricing windows

- **M1–M2 (P1 soft):** founder-cohort pricing applies to all 40 cohort users.
- **M3–M4 (P2 launch):** founder-cohort pricing applies to *new* signups within the 60-day window. Soft-cohort users locked at founder-cohort through their first renewal.
- **M5+ (P3 stab onwards):** standard pricing for new signups. Founder-cohort users convert to standard at next renewal (annual or monthly).

### Effective ARPU per tier — base case

Blended annual + monthly:

- **Trader effective ARPU:** weighted by mix. Annual: $790/yr ÷ 12 = $65.83/mo. Monthly: $79/mo. Blend at 40/60 = 0.4 × $65.83 + 0.6 × $79 = **$73.73/mo / $885/yr.** **`A`**
- **Desk Preview effective ARPU:** Annual $332.50/mo equivalent + Monthly $399. Blend at 60/40 = 0.6 × $332.50 + 0.4 × $399 = **$359/mo / $4,308/yr.** **`A`**
- **Desk Full v2 effective ARPU (base, no per-seat):** Annual $999.17/mo + Monthly $1,199. Blend at 75/25 = 0.75 × $999.17 + 0.25 × $1,199 = **$1,049/mo / $12,594/yr.** **`A`**
- **Desk Full v2 with per-seat (time-varying):**
    - **Early v2 (M10–M18) — 2.0 avg:** $1,049/mo + 1.0 × $149 = **$1,198/mo / $14,376/yr.** **`A`**
    - **Mature v2 (M19+) — 2.5 avg:** $1,049/mo + 1.5 × $149 = **$1,272/mo / $15,267/yr.** **`A`**

Note: analyst seats less common in early v2 cohort; partner read-only is the dominant per-seat type. Time-varying density tracks cohort composition evolution from P2-power-user-skewed to pure-P3-skewed per §3 segment matrix.

### Founder-cohort effective ARPU during the 60-day window

- **Trader founder:** $59/mo monthly equivalent. Per-month revenue × 1.5 month average → ~$88.50 per founder user during the window.
- **Desk Preview founder:** $299/mo. ~$448.50 per founder user during the window.
- **Desk Full v2 founder:** not applicable — Desk Full v2 launches in P5 (M10), well after the 60-day founder-cohort window closes.

### Monthly recurring revenue — base case

Computed from cohort sizing × effective ARPU. All `A`-tagged at v0.1.

| Month | Trader MRR | Desk Preview MRR | Desk Full MRR (with per-seat) | Total MRR | Cumulative ARR run-rate |
|---|---|---|---|---|---|
| M1 | $1,770 | $2,990 | $0 | $4,760 | $57,120 |
| M2 | $1,770 | $2,990 | $0 | $4,760 | $57,120 |
| M3 | $5,820 (mix of founder + standard) | $7,720 | $0 | $13,540 | $162,480 |
| M4 | $7,800 | $9,300 | $0 | $17,100 | $205,200 |
| M5 | $9,500 (founder window closing) | $10,200 | $0 | $19,700 | $236,400 |
| M6 | $10,500 | $11,200 | $0 | $21,700 | $260,400 |
| M7 | $11,400 | $12,200 | $0 | $23,600 | $283,200 |
| M8 | $12,400 | $13,500 | $0 | $25,900 | $310,800 |
| M9 | $13,400 | $14,500 | $0 | $27,900 | $334,800 |
| M10 | $14,500 | $7,000 (post-migration) | $31,800 | $53,300 | $639,600 |
| M11 | $15,800 | $8,200 | $42,000 | $66,000 | $792,000 |
| M12 | $17,000 | $9,800 | $49,600 | $76,400 | $916,800 |

**M12 ARR run-rate (base case): ~$917k.** **`A`**

### M13–M24 base-case shape (without month-by-month detail)

Growth tapers as organic acquisition matures:

- M13–M18: cohort growth ~10% MoM tapering to 5%, MRR reaches ~$120k by M18 (~$1.4M ARR). **`A`**
- M19–M24: growth slows to 5–7% MoM; MRR reaches ~$160k by M24 (~$1.9M ARR). **`A`**

**M24 ARR target (base case): ~$1.9M.** This is the headline number §15 investor narrative inherits.

### M25–M36 strategic arc

Per §11 horizon lock — quarterly milestones only, expressed in §16 scenarios:

- **Bull case M36:** ~$5–7M ARR.
- **Base case M36:** ~$3–4M ARR.
- **Bear case M36:** ~$1.5–2M ARR (cohort retention weaker, slower P3 acquisition).

These are placeholder ranges. §16 scenarios refine.

---

## 11.3 Cost model (Phase 2)

### People cost — Scenario 3 locked (Solo + 2 contractors at P4)

- **Founder cost: $7,000/mo** baseline throughout the 24-month horizon. UAE-resident, currently uncompensated but appears as P&L line item for investor-narrative purposes. **`A`** assumed.
- **Contractor cost at P4: $8,000/mo each × 2 contractors × 3 months (M8–M10) = $48,000 spike.** Front-end engineer (multi-account dashboard) + back-end engineer (audit-grade journal export). Mid-senior in lower-cost region (Eastern Europe / SE Asia / MENA tier-2). **`A`**

**Total people cost over 24 months:** $7k × 24 + $48k = **$216,000.**

### Vendor stack — Phase 1 narrow (locked)

Monthly recurring costs at low-to-moderate scale (early v1 + early v2). All **`A`** unless noted; benchmarked against published pricing where available.

| Vendor | Monthly cost | Notes |
|---|---|---|
| CCXT | $0–$50/mo | Open-source library; cost is engineering time + occasional support. **`B`** |
| CoinGlass (data feed for engine) | $290/mo | Pro tier required for liquidations + funding + OI feed at engine quality. **`B`** |
| Tradefeeds (sentiment) | ~$300/mo | Mid-tier API access estimate; revisit at signup. **`A`** |
| CoinGecko (token metadata) | $129/mo | Pro API tier for higher rate limits. **`B`** |
| Claude API (minimal) | $100–$300/mo | Bounded use per project rules; not in trade-decision loop. Scales with cohort size. **`A`** |
| **Vendor stack total** | **~$820–$1,070/mo** | Mid-point assumption: **$945/mo** |

**24-month vendor cost:** ~$22,700 (mid-point baseline). Slight ramp expected as cohort grows; Phase 2 vendor stack remains narrow per §5.4.3.

### Infrastructure cost

| Item | Monthly cost | Notes |
|---|---|---|
| Hosting (Vercel / Render / Hetzner equivalent) | $100–$200/mo | Dashboard + API + Telegram bot |
| Database + cache (managed Postgres + Redis) | $80–$200/mo | Scales with user count |
| Monitoring + error tracking (Sentry / Datadog-light) | $50–$150/mo | Required per §10 ops runbook |
| Email + transactional (Postmark / SendGrid) | $20–$100/mo | Receipts, password resets, monthly statements |
| Domain, SSL, secrets management | ~$30/mo | Operational overhead |
| **Infra total (excluding Stripe)** | **~$280–$680/mo** | Mid-point: **$480/mo** |
| Stripe processing fees | **3.5% of revenue (blended)** | Per §6.8 — card processing + AED FX margin. **`B`** |

**24-month infra cost (excluding Stripe):** ~$11,500 (mid-point baseline).

**Stripe fees scale with revenue.** At M24 ARR ~$1.9M = $158k/mo MRR → $5.5k/mo Stripe fees. Cumulative Stripe fees through M24: **~$30,000** (estimated against revenue ramp).

### Step-function operational costs

- **VAT registration trigger:** AED 375k (~$102k) annual revenue. **`B`** UAE statutory.
    - **Triggered approximately at:** M9–M10 in the base case (when ARR run-rate crosses ~$100k/year).
    - **Step-function cost:** ~$2k–$5k one-time setup (accountant + registration) + ongoing ~$200–$500/mo VAT-handling overhead. **`A`**
- **Cross-border GCC VAT** (per §12 risk register): operational complexity if customer base spreads across UAE / KSA / Bahrain / Oman with VAT-registered status. Deferred cost; not in v1 base case.

### Other operational

- **Legal + accounting** (UAE sole prop): $200–$500/mo retainer. **`A`** Includes basic bookkeeping + occasional compliance check.
- **Insurance** (E&O / cyber): $100–$300/mo when applicable. **`A`** May not be required at v1 sole-prop scale; revisit at entity restructure.
- **Customer support tooling** (Intercom-light or equivalent): $50–$200/mo. **`A`** Required for §10 ops support tier matrix.
- **Subtotal other operational:** ~$350–$1,000/mo. Mid-point: **$675/mo.**

**24-month other operational cost:** ~$16,200.

### Total cost summary (24-month base case)

| Category | Total over 24 months |
|---|---|
| People (founder + P4 contractor spike) | $216,000 |
| Vendor stack (P1 narrow) | $22,700 |
| Infrastructure (excluding Stripe fees) | $11,500 |
| Stripe processing fees (revenue-scaling) | ~$30,000 |
| Other operational (legal, accounting, support tools) | $16,200 |
| VAT setup + ongoing handling (post-M10 trigger) | ~$5,000 |
| **Total 24-month base-case cost** | **~$301,400** |

### Revenue vs. cost summary

- **Cumulative 24-month revenue (base case, Phase 1 model):** approximately $1.5M (rough integration of monthly MRR ramp from $4,760 to $158k).
- **Cumulative 24-month cost (base case):** ~$301k.
- **Implied 24-month cumulative gross margin:** approximately **80%.** Strong unit economics if base-case assumptions hold.
- **Net cumulative cash position by M24** (pre-tax, founder-cost included): approximately **+$1.2M** before reinvestment / hiring expansion. Strong bootstrap position; supports v3 scope expansion without external capital if base case lands.

These numbers are illustrative and refined in Phase 3 sensitivity. Bull case improves dramatically (per-seat density at upside, conversion rates higher); bear case narrows margin but stays positive if base assumptions don't break by >40%.

### Cost model anti-flags (carried into Phase 3 audit)

- **Vendor pricing is benchmarked, not negotiated.** Real pricing may differ; CoinGlass Pro tier and CoinGecko Pro pricing are public. Tradefeeds is least confirmed; treat as `A`.
- **Founder cost at $7k/mo is illustrative.** Real cash compensation may be lower at v1 (founder absorbs); model surfaces it for investor narrative honesty.
- **Stripe fees blended 3.5% may underestimate** if AED conversion rate compresses or if customer base skews to non-US cards (international card fees can run higher).
- **VAT timing trigger is calendar-approximate.** Real trigger depends on rolling 12-month revenue; M9–M10 estimate could shift.
- **No paid acquisition cost line item yet.** §11 Phase 3 LTV/CAC pass adds CAC by channel; Phase 2 cost model assumes organic-only.

---

## 11.5 LTV/CAC by tier and channel (Phase 3a)

### LTV per tier — base case

Computed from §6.6 prices, blended annual/monthly ARPU per §11.2, retention curves per §11.1, and tenure assumptions benchmarked against SaaS norms.

| Tier | Effective ARPU/yr | Annual retention | Avg tenure (yrs) | LTV |
|---|---|---|---|---|
| Trader | $885 | 60% | ~1.78 | **~$1,575** |
| Desk Preview | $4,308 | 70% | ~2.32 | **~$10,000** |
| Desk Full v2 (mature, 2.5 seats) | $15,267 | 80% | ~3.4 | **~$52,000** |
| Desk Full v2 (early, 2.0 seats) | $14,376 | 80% | ~3.4 | **~$48,800** |

Tenure assumptions are **`B`** benchmarked: Trader ~24-month median tenure for similar-priced SaaS; Desk Preview longer because partner-money switching cost; Desk Full longest because audit-grade obligation lock-in.

### CAC ceilings — LTV/CAC ≥ 3 floor

Per §6.9 sensitivity flags, LTV/CAC ≥ 3 is the unit-economics floor. CAC ceiling per tier:

- **Trader:** $1,575 / 3 = **$525.**
- **Desk Preview:** $10,000 / 3 = **$3,333.**
- **Desk Full v2 (mature blend):** $52,000 / 3 = **$17,333.**
- **Desk Full v2 (early blend):** $48,800 / 3 = **$16,267.**

These are *ceilings* — actual realized CAC should run well below.

### Channel mix and CAC bands per channel

Channel allocation derived from §3.6 segment matrix and §3.2 persona-channel cards.

#### Trader tier — channels and CAC

| Channel | Estimated CAC | Buyer fit | Volume potential | Notes |
|---|---|---|---|---|
| Founder content (X, Substack, posts) | $30–$120 | P1, P2 | Medium | Highest leverage; founder time is the cost |
| Telegram community (organic + light) | $20–$80 | P1, P2, secondary persona | Medium-high | MENA-strong; matches Telegram-companion delivery surface |
| Referrals (soft-cohort and Trader users) | $20–$100 | All | Low-medium | Highest-quality, lowest-cost — but limited volume |
| Light paid acquisition (X ads, Google) | $150–$400 | P1, P2 | High | Test from M5+; defer until §11.6 sensitivity confirms unit economics |
| Affiliate program (post-launch §8) | $50–$200 | P1, P2 | Medium | Commission-based; per §8 v0.1 pending |
| Methodology-focused content collabs | $50–$200 | P1 | Low | High-trust, low-volume (Substack guest posts) |

**Trader blended-CAC base case:** **~$120/mo per acquisition.** Mix: 40% organic content + 25% Telegram + 15% referral + 15% paid + 5% affiliate.

#### Desk Preview tier — channels and CAC

| Channel | Estimated CAC | Buyer fit | Volume potential | Notes |
|---|---|---|---|---|
| Closed founder networks (warm intros) | $0–$200 (founder time) | P3 | Low | Highest-fit, lowest-volume — concentrated MENA |
| LinkedIn organic | $200–$800 | P3 | Low-medium | Operator-network discovery |
| Regional events (Token2049, Dubai Fintech) | $1,000–$3,000 | P3 | Low | High-cost-per-lead but high-conversion |
| Trader → Desk Preview upgrade | $0 | P2 power-user | Medium | Internal funnel; CAC is incremental product cost |
| Soft-cohort referrals | $50–$300 | P3 | Low | Word-of-mouth from validated P3 users |

**Desk Preview blended-CAC base case:** **~$600/mo per acquisition.** Mix: 50% closed networks + 20% upgrade-from-Trader + 15% LinkedIn + 10% events + 5% referral.

#### Desk Full v2 tier — channels and CAC

| Channel | Estimated CAC | Buyer fit | Volume potential | Notes |
|---|---|---|---|---|
| Desk Preview → Desk Full v2 migration | $0 | P3, P2 power-user | High at v2 launch | Internal upgrade — base case 70% Preview→Full |
| Founder-led sales (1:1) | $1,500–$5,000 (founder time) | P3 | Low | Highest-quality, lowest-volume |
| Closed founder networks (warm intros) | $0–$500 | P3 | Low | Inherits Desk Preview channel |
| Partnership-driven (prop-firm, exchange) | $2,000–$8,000 | P3 | Low-medium | §8 partnerships still pending |

**Desk Full v2 blended-CAC base case:** **~$2,000/mo per acquisition.** Mix: 60% Preview→Full migration (CAC ~$0) + 25% founder sales + 10% closed networks + 5% partnership.

### Payback periods

Time for cumulative gross margin per customer to repay CAC. Standard SaaS target: under 12 months.

| Tier | Effective ARPU/mo | Blended CAC | Gross margin at ~80% | Months to payback |
|---|---|---|---|---|
| Trader | $73.73 | $120 | $59 | **~2.0 months** |
| Desk Preview | $359 | $600 | $287 | **~2.1 months** |
| Desk Full v2 (mature) | $1,272 | $2,000 | $1,018 | **~2.0 months** |

All three tiers have payback periods well under 12 months. **Strong unit economics across tiers.**

### LTV/CAC ratios — base case

| Tier | LTV | Blended CAC | LTV/CAC ratio |
|---|---|---|---|
| Trader | $1,575 | $120 | **13.1×** |
| Desk Preview | $10,000 | $600 | **16.7×** |
| Desk Full v2 (mature) | $52,000 | $2,000 | **26.0×** |

**All three tiers clear the 3× LTV/CAC floor by ~4–9× margin.** This is strong; soft-cohort observation will pressure-test whether base-case CAC assumptions hold.

### Implied marketing budget

For the Phase 1 cohort sizing (M1–M12, base case ~270 paid acquisitions across tiers):

- ~230 Trader × $120 = ~$27,600.
- ~24 Desk Preview × $600 = ~$14,400.
- ~9 net-new Desk Full v2 (post-migration) × $2,000 = ~$18,000.
- **Total M1–M12 marketing/CAC budget: ~$60,000.**

**This is in addition to the $301k 24-month cost in §11.3.** Adjusted total 24-month cost: **~$361k.** Implied gross margin tightens to ~76%.

### What this unlocks

- §11.6 sensitivity now has CAC bands to vary against (downside +50%, upside −30%).
- §15 investor narrative can claim defensible LTV/CAC ratios (>10× across tiers) — strong story.
- §7 GTM channel allocation has economic constraints (paid acquisition at $400/Trader CAC fails the unit economics; organic + community must dominate).
- §11a xlsx model receives explicit CAC line items per channel.

---

## 11.6 Sensitivity analysis

### Top-6 sensitivity inputs

Top-5 from §6.9 plus CAC assumption (added per §11.5 honest-read flag). Each input has a downside / base / upside scenario.

| Input | Downside | **Base** | Upside |
|---|---|---|---|
| Per-seat density (early v2 / mature) | 1.5 / 2.0 | **2.0 / 2.5** | 2.5 / 3.0 |
| Free → Trader conversion (90d blended) | 2% | **5%** | 8% |
| Trader annual mix | 30% | **40%** | 50% |
| Trader → Desk Preview conversion (12mo) | 4% | **8%** | 12% |
| Desk Preview → Desk Full v2 migration | 50% | **70%** | 90% |
| Trader CAC (founder-time honesty) | $300 | **$120** | $60 |

### Single-input sensitivity — M24 ARR impact

Holding other inputs at base, varying one input.

| Input varied | Downside M24 ARR | Base M24 ARR | Upside M24 ARR | Delta range |
|---|---|---|---|---|
| Per-seat density | ~$1,830k | $1,900k | ~$1,970k | ±$70k |
| Free → Trader conversion | ~$1,200k | $1,900k | ~$2,650k | ±$700k |
| Trader annual mix | ~$1,890k | $1,900k | ~$1,920k | ±$15k (small effect) |
| Trader → Desk Preview conversion | ~$1,750k | $1,900k | ~$2,100k | ±$150–200k |
| Desk Preview → Desk Full v2 migration | ~$1,700k | $1,900k | ~$2,050k | ±$200k |
| Trader CAC | n/a (margin only) | n/a | n/a | Affects gross margin, not revenue |

### Single-input sensitivity — gross margin impact (CAC variant)

| CAC scenario | Trader CAC | M1–M12 marketing budget | Adjusted 24-month cost incl. CAC | Implied gross margin |
|---|---|---|---|---|
| CAC downside (founder-time honest) | $300 | ~$110k | ~$430k | ~71% |
| CAC base | $120 | ~$60k | ~$361k | ~76% |
| CAC upside | $60 | ~$45k | ~$346k | ~77% |

**Gross margin range under CAC variation: 71–77%.** Even pessimistic CAC keeps margin >70%.

### Combined-scenario shape (for §16 hand-off)

§16 scenarios will refine. Rough aggregations:

- **Bear case (most inputs at downside):** M24 ARR ~$1.0M; gross margin ~65%; cumulative cash position by M24 modestly negative or flat. Validates company-survival mode but tight.
- **Base case (all inputs at base):** M24 ARR ~$1.9M; gross margin ~76%; cumulative cash ~+$1.2M. Strong bootstrap position.
- **Bull case (most inputs at upside):** M24 ARR ~$3.0–3.5M; gross margin ~79%; cumulative cash ~+$2.0M. Validates investor narrative for raise.

### Most-impactful sensitivity — Free → Trader conversion

Free → Trader conversion is the single largest driver of M24 ARR variance ($700k swing on a $1.9M base = ±37%). This is **the single most important assumption to validate via soft cohort.**

§3.7 interview plan and §3.8 cohort behavioral grid both surface conversion-related signals; §11.6 sensitivity reinforces the priority of that validation.

### Second-most-impactful — Desk Preview → Desk Full v2 migration

The 70% migration assumption produces ±$200k variance. Critical for the v2 ARR ramp narrative. **§13 KPIs should track Preview-tier intent-to-upgrade signals during P3–P4 ahead of v2 launch.**

### Inputs that don't matter much

- Trader annual mix (small effect on M24 ARR; matters more for cash flow than topline).
- Per-seat density (early-cohort effect dampened by small Desk Full base in early v2).

### What §11.6 unlocks

- **§16 scenarios** can formalize bull/base/bear with concrete input combinations.
- **§13 KPIs** prioritized: Free → Trader conversion + Preview → Full migration are the two highest-leverage metrics to track.
- **§15 investor narrative** can present base case ($1.9M M24) with honest range ($1.0M bear / $3.0M bull). Defensible spread.

---

## 11.7 Anti-overclaim audit on §11

Audit performed against §11.0 through §11.6 on 2026-05-01. Six flags surfaced; all addressable through framing or documentation, no number changes.

### Flags applied or documented

**Flag 1 — LTV/CAC ratios may overstate due to founder-time CAC undervaluation.**

Trader 13.1×, Desk Preview 16.7×, Desk Full v2 26.0× are honest ratios *at base-case CAC assumptions*. The CAC base case ($120/Trader, $600/Preview, $2,000/Desk Full) assumes founder time has nominal cost. Under "founder-time honest" pricing (~$300/Trader, ~$1,500/Preview, ~$5,000/Desk Full), ratios drop to 5.3× / 6.7× / 10.4× — still excellent but more defensible.

**Mitigation.** §15 investor narrative quotes both: "13–26× under base case; 5–10× under pessimistic CAC." Avoids the "too good to be true" reaction; demonstrates honest sensitivity awareness.

**Flag 2 — Tenure assumptions are benchmarked, not observed.**

Trader ~1.78 years, Desk Preview ~2.32, Desk Full v2 ~3.4. Tagged `B`. No CoinScopeAI cohort has run long enough to validate; first observed values come at M12+ for Trader, M30+ for Desk Full.

**Mitigation.** §11 explicitly tags tenure as `B` not `O`; §15 narrative discloses this; soft-cohort observation produces the first refinement at M3+.

**Flag 3 — M24 ARR ~$1.9M is base case; investor narrative must present range.**

Risk: §15 quoting only $1.9M makes the bull/bear case invisible. Investors expect range.

**Mitigation.** §11.6 + §16 hand-off provide the bull ($3.0M) / base ($1.9M) / bear ($1.0M) framing. §15 inherits all three.

**Flag 4 — Founder cost $7k/mo is implicit, not actually drawn.**

The model includes $168k of founder cost over 24 months as a P&L line item. Reality: founder may draw $0–$3k/mo at v1. The implicit cost is for *investor narrative honesty* — investors expect to see "what would this cost if founder was paid market rate."

**Mitigation.** Two views in xlsx: "actual cash burn" (real founder draw) vs. "fully-loaded P&L" (implicit founder cost included). §15 narrative uses fully-loaded for unit economics; cash-burn view used for runway calculation.

**Flag 5 — Cumulative 24-month revenue ~$1.5M is rough integration.**

Computed approximately by integrating monthly MRR over 24 months. Precise number depends on annual prepay timing (some annual revenue lands in upfront chunks, distorts monthly recognition). xlsx will compute precisely.

**Mitigation.** Markdown narrative says "approximately $1.5M cumulative revenue"; xlsx provides exact number. Investor decks use xlsx number, not markdown estimate.

**Flag 6 — CoinGlass dual customer-vendor relationship affects vendor cost defensibility.**

§12 risk register tracks this; §11.3 vendor cost lists CoinGlass at $290/mo. If CoinGlass changes API pricing or terms, the vendor cost line moves and we may need to swap providers (engineering cost not in current budget).

**Mitigation.** §12 tracks; §11 documents the dependency; xlsx adds a "vendor cost variance" sensitivity.

### What §11 audited clean

- Revenue numbers traceable to §6 v1 pricing — no overclaim.
- Cohort sizing assumptions tagged `A` and clearly labeled as inference.
- Gross margin claim (~76% with CAC included) is defensible against the locked cost stack.
- §5.4.7 hiring scenario explicitly modeled (Scenario 3 with $48k contractor spike); investor narrative use-of-funds is honest.
- §16 scenario hand-off produces bull/base/bear range; not a single point estimate.

### §11 markdown LOCKED at v1

§11.0 through §11.7 all committed. xlsx (`11a-financial-model.xlsx`) is the next deliverable — built once founder confirms the audit flags are acceptable.

---

## 11.7 Anti-overclaim audit on §11

PENDING. Phase 3 next pass.

---

## 11.4 What Phases 1 and 2 close vs. open

### Closed (Phase 1 + 2 locked)

- Source taxonomy and inheritance map.
- Top-of-funnel cohort sizing structure (M1–M12 illustrative; M13–M24 directional).
- Effective ARPU per tier blended over annual/monthly mix.
- Per-seat density base assumption (2.5 avg).
- Retention assumptions tagged as benchmarked.
- M24 ARR base-case target: ~$1.9M.

### Phase 2 cost model — drafted in §11.3 (locked)

- People cost: $216k over 24 months (founder $7k/mo + P4 contractor spike $48k).
- Vendor stack: ~$945/mo mid-point ($22.7k over 24 months).
- Infrastructure (ex-Stripe): ~$480/mo ($11.5k over 24 months).
- Stripe fees: 3.5% blended (~$30k cumulative).
- Other operational: ~$675/mo ($16.2k over 24 months).
- VAT trigger ~M9–M10; setup + ongoing ~$5k cumulative.
- **Total 24-month cost: ~$301k.**
- **Implied gross margin: ~80%.**

### Open for Phase 3

- LTV/CAC per channel using §6.9 ceilings.
- Sensitivity table on top-5 inputs (per-seat density, Free→Trader conversion, annual/monthly mix, Preview→Full migration, Trader→Preview conversion).
- Bull/base/bear scenario formal definition (handed to §16).
- Anti-overclaim audit on revenue numbers.

### Open for Phase 3 close

- xlsx live model (`11a-financial-model.xlsx`) — built once §11 v1 markdown locks.

---

## Phase 1 open questions — RESOLVED

All five Phase-1 questions resolved during the §11 v0.1 → v1 progression. Locked answers:

1. **Soft-cohort tier split:** 30 Trader + 10 Desk Preview (modest skew with P2 power-user slice). Soft-cohort recurring revenue $4,760/mo at founder-cohort pricing.
2. **Waitlist size:** 200 names by M3 (Scenario B baseline — passive landing + light content during validation).
3. **Free → Trader conversion:** 5% blended over 90 days; decomposition documented for Phase 3 sensitivity (~7.8% blended-from-segments; locked at 5% for selection-bias absorption).
4. **M24 ARR target:** ~$1.9M base case as natural derivative of locked Phase 1 inputs. Bull ~$3M / bear ~$1.0M per §16.
5. **Per-seat density at Desk Full v2:** time-varying base case — 2.0 early v2 (M10–M18) / 2.5 mature (M19+).

See `_decisions/decision-log.md` entries dated 2026-05-01 for full rationale per question.
