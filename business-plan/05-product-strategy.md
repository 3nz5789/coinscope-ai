# §5 Product Strategy and Packaging

**Status:** v1 LOCKED. All sub-sections committed. Downstream §6, §7, §9, §11, §13, §14, §15 draft against §5 v1.
**Last updated:** 2026-05-01
**Disclaimer:** Inventory is inference-based against project memory and engine/dashboard/Telegram-bot scope as documented. v1.1 refresh after a real product audit. Validation phase active; nothing labeled "production-ready" until §8 Capital Cap criteria are met.

---

## 5.0 Assumptions

- **Locked inputs:** §3 personas (P1 Methodist, P2 Engineer, P3 Solo PM); §3.6 segment matrix tier mapping (P1 → Trader, P2 → Trader+Desk power-user, P3 → Desk); §4.4 lead VP; §4.5 product-scope fence; §14 launch sequencing; phased vendor rollout (P1 narrow → P2 → P3).
- **Engine reference:** `coinscopeai-engine-api` — endpoints `/scan`, `/performance`, `/journal`, `/risk-gate`, `/position-size`, `/regime/{symbol}`.
- **Risk thresholds (locked):** max drawdown 10%, daily loss 5%, max leverage 10x, max 5 open positions, position heat cap 80%.
- **Regime labels (v3 ML):** Trending, Mean-Reverting, Volatile, Quiet.
- **Validation posture:** Binance Testnet only; no real orders; 30-day cohort active.
- **Phase-0 lock:** Tier 1 delivery surface = dashboard canonical, Telegram companion, email transactional only.

### Maturity legend (used throughout §5.1)

- **VTN** — validated on testnet (works against §8 criteria-eligible behavior).
- **STN** — shadow-tested on testnet (running in shadow mode; not yet validated).
- **IB** — in-build (under active development, not in production).
- **RM** — roadmap (planned, not started).

No capability is labeled "production-ready." That label is gated by §8 Capital Cap criteria and remains forward-locked across §5.

---

## 5.1 Capability inventory

### 5.1.1 Engine — quant signal generation and risk control

| Capability | Maturity | Description | Primary persona served |
|---|---|---|---|
| Multi-symbol scanner (`/scan`) | VTN | Scans USDT-perpetual pairs; ranks by 0–12 confluence score (RSI, EMA, ATR, Volume, CVD, entry timing) | P1, P2 |
| Regime classifier v3 ML (`/regime/{symbol}`) | VTN | Labels per-symbol regime as Trending / Mean-Reverting / Volatile / Quiet with confidence score | P1, P2 |
| Risk gate (`/risk-gate`) | VTN | Evaluates a proposed trade against drawdown / daily-loss / leverage / open-position / heat thresholds. Returns pass/fail + reason. | P1, P2, P3 |
| Position sizer (`/position-size`) | VTN | Computes position size per user-configured risk-per-trade and current account state | P1, P2, P3 |
| Performance journal (`/journal`) | VTN | Logs each scored signal, gate decision, position, and outcome with attribution | P1, P3 |
| Performance reporter (`/performance`) | VTN | Aggregates journal into rolling cohort and per-account metrics | P1, P3 |
| Kill switch | STN | Halts trading when daily-loss limit or drawdown ceiling triggered | P1, P3 |
| Multi-timeframe confirmation | STN | Cross-checks signals against higher timeframes | P2 (transparency) |
| Custom-rule backtester | RM | User-defined rule backtesting against historical data | P1 (Canvas A v0.1 listed; clarified to roadmap in §4.5.4) |

### 5.1.2 Dashboard — canonical user surface

Hosted at `app.coinscope.ai`. Per the locked Tier 1 delivery decision, the dashboard is the source of truth for journal, performance, settings, gate config, regime visualization, cohort metrics, and billing.

| Capability | Maturity | Description | Primary persona served |
|---|---|---|---|
| Live signal feed | IB | Renders `/scan` output with confluence score, regime label, gate decision | P1, P2 |
| Regime visualization | IB | Color-coded per locked palette (mint / neutral / amber / muted) with confidence | P1, P2 |
| Risk gate configurator | IB | UI to set personal thresholds (drawdown, daily loss, leverage, heat) | P1 (configurable gates), P3 (LP-style gates) |
| Performance journal UI | IB | Per-trade journal with gate decision, regime label, R-multiple, rule-violation tagging | P1 |
| Cohort drawdown chart | IB | Aggregate cohort metric — surface for "you're not alone" framing | P1 |
| Multi-account dashboard | RM | Per-account + aggregate book view for Desk tier | P3 |
| Static monthly PDF report | IB | Single-template monthly statement generated from journal; PDF only; PM emails to partners | P3 |
| Audit-grade journal export | RM | Configurable-period statements (CSV + PDF), real-time exports, tax-ready formatting | P3 |
| Role-based access (seats) | RM | Read-only partner view, analyst seat | P3 |
| Tax-ready exports | RM | Structured period reports for tax-professional review | P3 |
| Arabic-language UI | RM | Post-v1 per §3.6; English-first for launch | P3 (regional) |

### 5.1.3 Telegram bot — companion alert + light interaction surface

`@ScoopyAI_bot` (Chat ID 7296767446). Per locked Tier 1 delivery: time-sensitive push + light commands; not the system of record.

| Capability | Maturity | Description | Primary persona served |
|---|---|---|---|
| Signal arm push | STN | Pushes scored signals to authorized users | P1, P2, P3 |
| Gate decision push | STN | Notifies on gate pass/fail with reason | P1, P3 |
| Kill-switch alert | STN | Real-time alert when daily-loss / drawdown halts trading | P1, P2, P3 |
| Daily P&L digest | STN | End-of-day summary with key metrics | P1, P3 |
| `/scan` command | STN | On-demand scan request | P2 (light use), P1 (occasional) |
| `/performance` command | STN | Quick performance snapshot | P1 |
| `/risk-gate` command | STN | On-demand gate check on proposed trade | P1 |
| Multi-channel routing | RM | Per-user customized push profiles (which alerts go where) | P2, P3 |

### 5.1.4 Vendor / data integrations — Phase 1 narrow stack

Locked phased vendor rollout: P1 narrow → P2 layer-on → P3 expansion. Inventory below reflects P1 only.

| Vendor | Role | Maturity | Notes |
|---|---|---|---|
| CCXT (4 exchanges) | Market data + execution simulation | STN | Binance, Bybit, OKX, KuCoin (representative; exact list confirms in `coinscopeai-architecture`) |
| CoinGlass | Liquidations, funding rates, open interest | STN | Macro context for regime classifier and risk gate |
| Tradefeeds | News / sentiment data | IB | Lower-priority signal input; integration in progress |
| CoinGecko | Token metadata, market cap, supply | STN | Reference data, not signal-critical |
| Claude (minimal) | Structured reasoning over journal entries; narrative generation | IB | Bounded use; not in trade-decision loop |

P2 layers (deferred): expanded exchange coverage, deeper sentiment, alternative data. P3 layers (deferred): institutional-grade execution venues, compliance tooling.

### 5.1.5 Operational mechanisms (cross-cutting)

| Capability | Maturity | Description |
|---|---|---|
| Validation cohort instrumentation | STN | Tags every signal/trade with cohort membership for §13 KPI tracking |
| Vendor failover | RM | Graceful degradation when a P1 vendor is unavailable |
| Audit log | STN | Append-only log of gate decisions, kill-switch triggers, configuration changes |
| Engine-state replay | RM | Reproduce a historical engine decision from logs (debugging + Persona 2 transparency) |
| API authentication / rate limiting | STN | Per-user keys, tier-based rate limits |

### 5.1.6 What is NOT in inventory (declared gaps)

These are visible-by-omission gaps that §5.2 tier matrix and §5.4 roadmap must address explicitly. Listing them here prevents accidental tier-matrix promises that have no inventory backing.

- **No fund-management or LP-allocation tooling.** Per §4.5 fence.
- **No trade execution without user authorization.** Per §4.5 fence.
- **No alpha-generation product.** Per §4.5 fence.
- **No teaching / coaching / discipline-from-zero content.** Per §4.5 fence.
- **No mobile-native client.** Web dashboard responsive; native mobile not in v1.
- **No multi-asset coverage beyond crypto-perp.** Spot, options, equities, FX explicitly out of scope for v1.
- **No social or community features inside the product.** Telegram is companion, not community-platform.
- **No marketplace / strategy-store / signal-marketplace.** Anti-ICP territory.

---

## 5.2 Tier matrix

### 5.2.1 Locked structure

Three named tiers — **Free**, **Trader**, **Desk**. Desk ships in two states: **Preview (v1)** and **Full (v2)**. No Fund tier (per §4.5 fence + no persona to anchor it).

### 5.2.2 Feature-gate matrix

| Capability area | Free | Trader (v1) | Desk Preview (v1) | Desk Full (v2) |
|---|---|---|---|---|
| **Live signal feed** | Read-only, top-5 daily, delayed | Full live `/scan` output | Full + multi-account view | Full + multi-account + multi-strategy isolation |
| **Regime classifier** | Per-symbol label, no confidence | Full label + confidence + history | Same as Trader | Same as Trader |
| **Risk gate** | View-only on demo trades | Full configurable gate, personal account | Configurable + view across accounts | LP-style book-level gates + per-account |
| **Position sizer** | View-only | Full per-trade sizing | Same as Trader, multi-account | Same + book-level allocation logic |
| **Performance journal** | None | Full personal journal + R-multiples + rule-violation tagging | Multi-account read view, single-PM access | Full multi-account + audit-grade + role-based |
| **Performance reporter** | None | Personal cohort metrics | Multi-account aggregate (basic) | Audit-grade monthly statements (PDF + CSV) |
| **Kill switch** | n/a | Personal account | Per-account triggers | Book-level + per-account triggers |
| **Telegram bot** | None | Signal arms, gate decisions, kill alerts, daily digest, light commands | Same as Trader | Same as Trader; **multi-channel routing** |
| **API access** | None | Rate-limited (Trader rates) | Same as Trader | Elevated rate, programmatic multi-account |
| **Multi-account dashboard** | n/a | Single account | View-only across accounts (no role-based access) | Full RBAC + seats |
| **Audit-grade exports** | n/a | Personal CSV journal | Basic CSV multi-account + **static monthly PDF report (single template, PM emails to partners)** | Configurable-period CSV + PDF, real-time exports, tax-ready |
| **Role-based seats** | n/a | n/a | Single PM access only | PM + partner read-only + analyst |
| **Tax-ready exports** | n/a | n/a | n/a | Structured period reports |
| **Custom-rule backtester** | n/a | n/a (RM) | n/a (RM) | RM (post-v2) |
| **Arabic-language UI** | n/a | n/a (RM) | n/a (RM) | RM (post-v2) |

### 5.2.3 Tier-by-tier detail

#### Free

**Purpose.** Lead-gen and the "we'll be back for you" stance from §3.5 for sub-$5k disciplined traders. Not a buyer tier — explicitly a marketing surface that produces value without committing to product use.

**What it includes.**

- Read-only access to a curated top-5 signal list, daily refresh, delayed.
- Per-symbol regime label without confidence.
- Risk gate visualization on demo trades only.
- No personal journal. No Telegram bot. No API.

**What it excludes.** Personal trading data, gate configuration, journal, performance reporter, real-time signals, anything execution-adjacent.

**Scope locked in §6.5 (2026-05-01):** Free is account-verified entry tier with "we'll be back" messaging for sub-$5k disciplined users. No journal exception. See §6.5 for full scope detail.

#### Trader (v1)

**Purpose.** The primary v1 paid tier. Anchored on the six engine API endpoints (VTN) plus dashboard IB capabilities labeled as "stabilizing" rather than "shipped." Serves Persona 1 (Methodist) fully and Persona 2 (Engineer) base layer.

**What it includes.**

- Full `/scan`, `/regime`, `/risk-gate`, `/position-size`, `/journal`, `/performance` access.
- Configurable risk gate per personal thresholds.
- Performance journal with R-multiples and rule-violation tagging.
- Telegram bot integration (push alerts, light commands).
- **API access at single-account integration density.** Target rate limits ~1 req/sec/endpoint, burst 10 — to be finalized through soft-cohort calibration since the underlying rate-limiting capability is at STN. Sufficient for Persona 2 to integrate CoinScopeAI as their primary risk layer in their personal trading system. Multi-account or production-grade integration density requires Desk-tier elevated access.
- Single account.

**Maturity caveats applied to product copy.** Dashboard IB items (live signal feed UI, regime visualization UI, gate configurator UI, journal UI) labeled "stabilizing" inside the product during the soft-cohort window. Once those cross IB → VTN through §3.8 cohort observation, the label drops.

**What it excludes.** Multi-account, role-based seats, audit-grade exports, custom backtester, elevated API.

#### Desk Preview (v1)

**Purpose.** Persona 3 onboarding pathway at v1. Honest about what's incomplete; gives Solo PMs a v1 product instead of a 12-month waitlist; protects the high-ARPU acquisition runway.

**What it includes.**

- Everything in Trader.
- View-only multi-account aggregation across up to **3 accounts** (capped — multi-account dashboard is IB, capping limits load).
- Aggregate basic CSV export across accounts (the IB multi-account view; not the RM audit-grade exports).
- **Static monthly PDF report** — single-template monthly statement generated from the journal. PM emails the PDF to partners. Solves Persona 3's core "partner reporting" pain without requiring partner-side login infrastructure at v1.
- Single-PM access only — partners and analysts cannot have their own logins yet.
- "Preview" labeled prominently in product copy and pricing.

**What it excludes.** Role-based seats, audit-grade monthly statements, tax-ready exports, LP-style book-level gates, multi-strategy isolation, unlimited sub-accounts.

**Pricing posture for §6.** Preview-tier pricing should be lower than full Desk would be. Approximate framing: between Trader and projected full-Desk pricing. §6 decides actual numbers; §5.2 establishes that **Preview pricing carries an implicit upgrade pathway** at v2 launch.

#### Desk Full (v2 commitment)

**Purpose.** The Persona 3 destination tier. Multi-account aggregation at scale, audit-grade reporting, role-based access, LP-style gates. Ships when multi-account dashboard, audit-grade journal export, role-based access, and tax-ready exports cross IB → VTN.

**What it adds vs. Desk Preview.**

- Multi-account scaling (≥3 accounts, cap defined by §11 financial-model unit economics).
- Role-based seats: PM + partner read-only + analyst.
- Audit-grade monthly statements (PDF + CSV) — configurable periods, real-time.
- Multi-channel Telegram routing.

**Deferred to v3** (per §5.4 realism-tightening pass): tax-ready period exports, LP-style book-level gates, multi-strategy account isolation. Persona 3 users at v2 launch should not expect these features; v3 planning revisits them after Desk Full stabilizes.

**Trigger to ship Desk Full:** the three P4 RM → IB items (multi-account dashboard, audit-grade exports, role-based seats) cross IB → VTN, and §13 KPIs around Desk Preview cohort behavior validate Persona 3 buying.

### 5.2.4 Validation gates per tier

What must be true at what maturity for each tier to actually ship:

| Tier | Required maturity floor | Specific gating items |
|---|---|---|
| Free | n/a (read-only render of VTN engine output) | Engine endpoints VTN ✓ |
| Trader (v1) | Engine endpoints VTN + dashboard core IB stabilizing | Live feed, regime viz, gate configurator, journal UI all at IB minimum + soft-cohort observation in §3.8 |
| Desk Preview (v1) | Trader floor + multi-account dashboard at IB | Multi-account view-only must reach IB before Preview opens to paid |
| Desk Full (v2) | All Desk-area items VTN | Multi-account dashboard VTN, audit-grade exports VTN, role-based access VTN, tax-ready exports VTN |

**Stop-the-line implication.** If any Trader-floor item fails to clear IB during soft-cohort, Trader does not open to public per §14. If Desk Preview multi-account dashboard does not clear IB by v1 launch, Desk Preview is held — Trader still ships.

### 5.2.5 Tier progression and upgrade pathway

**Free → Trader.** Account size threshold ($5k floor per locked anti-ICP) is the structural gate. Free → Trader conversion event: user verifies an exchange account at or above the floor and opts into Trader.

**Trader → Desk Preview.** Triggered by user request *or* by behavioral signal (multi-account setup attempt detected; account size grows past ~$200k). Auto-prompted but not auto-billed — user opts in.

**Desk Preview → Desk Full.** Automatic at v2 launch. Preview users get first-look pricing on Full Desk (incentive to retain through the gap). Desk Preview users do not need to re-onboard.

**Trader → Desk Preview *power-user* path.** Persona 2 power users (multi-strategy multi-account engineers) can join Desk Preview without being Persona 3 — same product surface, different user mental model. §9 messaging matrix addresses both audiences.

### 5.2.6 Anti-overclaim notes for tier marketing copy

Specific phrasings flagged for §9 / §15 review:

- **Never describe Desk Preview as "full Desk."** Preview is Preview. Persona 3 must understand the v1/v2 split before they pay.
- **Never market Trader features at IB maturity as "production-ready."** Use "in active development" or "stabilizing in cohort" — anti-overclaim per §0.2.
- **Never imply Free tier is a permanent home for sub-$5k disciplined traders unless §6 locks that.** Maintain "we'll be back for you" stance until §6 confirms scope.
- **Never market Desk Full features as v1.** Multi-account at scale, role-based seats, audit-grade exports — explicitly v2.
- **Never market v3-deferred features as v2.** Tax-ready period exports, LP-style book-level gates, and multi-strategy account isolation are v3 commitments per §5.4 refinement; v2 marketing copy must not include them.

---

## 5.3 Packaging principles

These are the rules that govern *how* we package — what is always free, what is always paid, what we will never do, and what is always visible. They are inherited by §6 (pricing), §7 (GTM), and §9 (messaging) and constrain those sections from contradicting product-tier voice and risk-first principles.

**Boundary with §6.** §5.3 is about *rules*, not *prices*. Specific dollar amounts, free-tier eligibility scope (e.g., whether sub-$5k disciplined gets a Free tier home), discounting policy, and founder-cohort pricing are §6 territory. §5.3 sets the rails inside which §6 operates.

### 5.3.1 What we never charge for — capital-preservation primitives

Capital preservation is the locked operating principle. Every primitive that protects user capital is never tier-gated; the *configurability* of those primitives is gated, but the **protection itself** is never withheld.

- **Kill switch.** Operates on any account at any tier, including Free-tier demo trades. Daily-loss and drawdown ceiling enforcement does not become a paid feature.
- **Drawdown and daily-loss alerts.** Surfaced visibly in any tier where trading data is present. Trader-tier and above get configurable thresholds; the alerts themselves are universal.
- **Anti-overclaim disclaimers.** Always paired with numerical claims, performance metrics, and tier descriptions. The disclaimer is not promotional copy — it is a brand obligation, paid or free.
- **Engine methodology documentation.** The *how it works* (regime classifier inputs, gate logic, position-sizer math) is publicly available. The *engine itself* is paid. Documentation is a trust artifact, not a paywall feature.
- **Validation status disclosure.** Every product surface — Free, Trader, Desk Preview, Desk Full — carries the validation-phase disclaimer until §8 Capital Cap criteria are met.

### 5.3.2 What is always behind a paywall — the paid value

What makes Trader and Desk worth paying for. These are the gated capabilities; without them, Free is a marketing surface that converts.

- **Real-time, full-fidelity signal feed.** Free gets top-5 daily delayed; Trader and above get the live `/scan` output. Speed and depth are paid.
- **Configurable risk gate.** Any user setting their own thresholds (vs. seeing the engine defaults) is paying. Gate visibility is universal; gate configuration is paid.
- **Personal performance journal.** Per-user trade history, R-multiples, rule-violation tagging. Paid because it accumulates value over time and represents the user's own analytical asset.
- **Multi-account aggregation.** Locked Desk-tier feature. Persona 3's structural need is paid because it is structurally expensive to build.
- **API access at any meaningful density.** Free has none; Trader has rate-limited single-account density; Desk has elevated rate. API is paid.
- **Audit-grade and tax-ready exports.** v2 Desk Full only. Static monthly PDF (Desk Preview) is paid but limited; configurable-period and tax-ready formats are the v2 paid value.

### 5.3.3 What we never do — brand discipline rules

Packaging decisions we explicitly will not make, regardless of revenue impact. These are flagged because they are tempting at low-revenue moments and damaging long-term.

- **No lifetime deals.** Lifetime pricing traps us in legacy obligations and signals weak unit economics. Founder-cohort pricing (§6) is time-bounded; "lifetime" is not a class we sell.
- **No "free forever" tier without account verification.** Sub-$5k anti-ICP signups would consume support load with no revenue path. Free is real but signup-verified.
- **No bundling with anti-ICP products.** No signal-group partnerships, no copy-trade integrations, no leverage-maximizer content. Locked anti-ICP is a packaging boundary, not just a marketing one.
- **No "Premium" or "Pro" tier names.** Tier names describe what the user *does* (Trader, Desk), not what they *are*. "Premium" carries the wrong register; "Pro" implies professionalism we cannot vet.
- **No tier features that contradict §4.5 fence.** Auto-execution-as-paid-feature, signal-streams-as-paid-feature, fund-management-as-paid-feature, capital-custody-as-paid-feature — all explicitly excluded.
- **No grandfather discounts for tier price changes.** When pricing adjusts, all users pay the new price at next renewal. Avoids the legacy-pricing drag that founder cohorts otherwise create.

### 5.3.4 What is always visible — transparency principles

What every user sees regardless of tier, because hiding any of it conflicts with risk-first / methodical voice.

- **Tier feature comparison.** Honest, side-by-side, including Desk Full v2 commitments labeled as v2.
- **Maturity labels in the product.** IB items shown to users with "stabilizing in cohort" framing. Does not surface internal labels (VTN/STN/IB/RM) but communicates the same idea in user-readable language.
- **Engine methodology docs.** Public, indexed, kept current.
- **Risk threshold defaults.** Documented even when configuration is gated (Free users see "Trader-tier users can configure these thresholds; engine defaults are X, Y, Z").
- **Validation phase status.** Persistent banner or footer wherever performance numbers are shown.
- **Full-cohort backtest disclosures.** Backtest results published as distributions, including failure modes, not cherry-picked headline numbers. Persona 2's buying criterion of methodology trust depends on this transparency. Inherits from §4.1 Canvas B pain reliever — full-cohort disclosure is a §5 commitment, not just §4 framing.
- **What CoinScopeAI does not do.** §4.5 fence renders into a "What CoinScopeAI is not" page in the product, public-facing.

### 5.3.5 Validation-phase packaging principles

Specific to the current 30-day validation phase and the soft-cohort window. These principles sunset when validation closes.

- **All tier descriptions carry the validation disclaimer.** "Testnet only. 30-day validation phase. No real capital." Inherited from custom instructions, surfaced at every paid-tier touchpoint.
- **Founder-cohort pricing is time-bounded.** §6 sets the price; §5.3 commits that it ends at a defined date or at validation pass + soft-cohort completion, whichever is later. No "founder-cohort forever" promises.
- **Soft-cohort users do not get a permanent free pass.** They pay (per locked §14 soft-launch posture) but at Preview pricing where applicable. They are not retroactively given Desk Full when v2 ships; they convert at v2 Preview-pricing-incentive rates.
- **Tier prices lock after validation.** Once validation closes and §8 Capital Cap criteria are met, tier prices stabilize for ≥6 months. Users get pricing predictability; we get retention math we can model in §11.

---

## 5.4 12-month product roadmap

The roadmap is **phase-driven, not calendar-locked.** Each phase has approximate month boundaries anchored to today (2026-05-01), but the gates that move us between phases are condition-driven (validation pass, IB → VTN graduations, cohort behavioral signals, §14 stop-the-line triggers). Calendar dates are estimates; phase gates are the real schedule.

### 5.4.1 Phase map

| Phase | Approximate window | Gate to enter | Gate to exit |
|---|---|---|---|
| **P0 — Validation phase** (current) | M0 (May 2026) | Already active | §8 Capital Cap criteria met; cohort behavior within tolerance |
| **P1 — Soft launch (Trader)** | M1–M2 (Jun–Jul 2026) | Validation pass | 30-day floor + §14 stop-the-line clean + IB items at "stabilizing-acceptable" maturity |
| **P2 — v1 public launch** | M3–M4 (Aug–Sep 2026) | Soft-cohort exit conditions met | Trader stable in market; first §3.7/§3.8 data lands; Desk Preview opens |
| **P3 — v1 stabilization** | M5–M7 (Oct–Dec 2026) | v1 public open | All Trader-floor IB items cross to VTN; §3 publishes v1.1; §11 financial model reconciles to actuals |
| **P4 — Desk Full preparation** (reduced v2 scope) | M8–M9 (Jan–Feb 2027) | v1 stabilization complete | Multi-account dashboard, role-based seats, audit-grade exports — cross RM → IB. **Tax-ready exports and LP-style book-level gates deferred to v3.** |
| **P5 — Desk Full launch** | M10–M12 (Mar–May 2027) | P4 RM → IB items cross IB → VTN | Desk Full opens to public; Preview users migrate; full Persona 3 acquisition opens |
| **P6 — v2 stabilization** (extends beyond 12-month horizon if needed) | post-M12 | Desk Full open | All v2 commitments stable; Vendor Phase 2 integration begins; ready for next planning horizon |

### 5.4.2 What ships when (capability flow)

| Capability area | P0 Validation | P1 Soft | P2 v1 public | P3 stab | P4 v2 prep | P5 v2 launch | P6 v2 stab |
|---|---|---|---|---|---|---|---|
| Engine API endpoints | VTN | VTN | VTN | VTN | VTN | VTN | VTN |
| Kill switch, multi-TF confirm | STN | STN→IB | IB | IB→VTN | VTN | VTN | VTN |
| Dashboard IB items (signal feed, regime viz, gate config, journal UI) | IB observation | IB stabilizing | IB stabilizing | IB→VTN | VTN | VTN | VTN |
| Cohort drawdown chart | IB | IB | IB→VTN | VTN | VTN | VTN | VTN |
| Telegram bot (push + commands) | STN | STN→IB | IB | IB→VTN | VTN | VTN | VTN |
| Static monthly PDF report (Preview) | — | IB build | IB ship | IB→VTN | VTN | VTN | VTN |
| Multi-account dashboard | RM | RM | RM (Preview cap=3) | RM (Preview cap=3) | RM→IB | IB→VTN | VTN |
| Audit-grade journal export | RM | RM | RM | RM | RM→IB | IB→VTN | VTN |
| Role-based access (seats) | RM | RM | RM | RM | RM→IB | IB→VTN | VTN |
| Tax-ready exports | RM | RM | RM | RM | RM | RM | RM (v3) |
| Custom-rule backtester | RM | RM | RM | RM | RM | RM | RM (v3) |
| Arabic-language UI | RM | RM | RM | RM | RM | RM | RM (v3) |
| Engine-state replay | RM | RM | RM | RM | RM | RM | RM (v3) |
| LP-style book-level gates | RM | RM | RM | RM | RM | RM | RM (v3) |

### 5.4.3 Phased vendor rollout alignment

The locked phased vendor rollout (P1 narrow → P2 layer-on → P3 expansion) maps to roadmap phases as:

- **Vendor Phase 1** (active throughout P0–P5): CCXT (4 exchanges), CoinGlass, Tradefeeds, CoinGecko, Claude minimal. Composition fixed; integrations mature inside the validation cohort and through Desk Full launch.
- **Vendor Phase 2** (evaluation in P3; integration deferred to P6): expanded exchange coverage (more CCXT venues), deeper sentiment data, alternative data sources. Evaluation is cheap (reading and scoping); integration is expensive and would compete with Desk Full build during P4–P5. Deferring integration to P6 protects the critical-path engineering capacity.
- **Vendor Phase 3** (post-P6, no v2 commitment): institutional-grade execution venues, compliance tooling, advanced data feeds. Only initiated after Desk Full stabilizes and there is empirical demand.

**Vendor rollout is not roadmap pacing.** The phased rollout is the *order* in which we expand vendor footprint; the *timing* depends on cost, persona data, and execution capacity. Vendor Phase 2 evaluation in P3 is cheap; integration during P4–P5 would double the engineering load at the most fragile moment. Deferring integration to P6 is the conservative call.

### 5.4.4 Stop-the-line triggers and rollback positions per phase

Each phase has explicit reversion conditions. These join the locked §14 stop-the-line list.

- **P0 → P1 gate:** §8 Capital Cap criteria not met → P0 extends; P1 does not start. No paid soft launch.
- **P1 → P2 gate:** §14 stop-the-line condition fires → P1 extends or reverts. Specific to product-strategy lens: cohort gate-rejection acceptance <50% with structural ICP-mismatch root cause → revert to validation-phase product copy and pause public-launch comms.
- **P2 → P3 gate:** persona invalidation per §14 condition 6 → §3 v1.1 messaging rewrite forced; Trader copy halts paid acquisition until repaired.
- **P3 → P4 gate:** Trader-floor IB items fail to cross VTN → P3 extends; P4 prep starts only when Trader is structurally stable.
- **P4 → P5 gate:** any of the three P4 RM → IB targets (multi-account dashboard, audit-grade exports, role-based seats) slips → Desk Full launch slips; Desk Preview continues at v1 cap until ready. We do not launch Desk Full with IB-status core features.
- **P5 → P6 gate:** Desk Full cohort behavior signals indicate Persona 3 fit failure → revert to Preview-only Desk; rework Desk Full feature set; do not retire Preview tier until Full is validated.

### 5.4.5 Open dependencies surfaced by the roadmap

Items that need locks elsewhere to keep the roadmap on track:

- **§6 pricing locks for v1 tiers** must close before P2 (no public launch with unset prices).
- **§6 Desk Preview pricing + v2 Desk Full pricing pathway** must close before P5 (cannot run Preview-to-Full migration without locked pricing trajectory).
- **§7 GTM v1 launch comms** must close before P2.
- **§9 messaging matrix locks** must close before any paid acquisition opens (P2).
- **§11 financial model v1** must close before P2 (revenue cohort modeling drives P3 expectations).
- **§13 KPI red-lines** must close before P1 (soft cohort needs the metrics it's evaluated against).
- **§14 launch comms plan** must close before P2.

### 5.4.6 What is explicitly *not* on this roadmap (and what is v3, not v2)

**Not on the plan at all** — per §4.5 fence and §5.1.6 declared gaps:

- No fund-formation tooling at any phase.
- No autonomous-execution feature in any phase.
- No alpha-generation product in any phase.
- No mobile-native client in any phase (web responsive remains).
- No multi-asset coverage (spot, options, equities, FX) in any phase.
- No social/community/marketplace features.

These are not in this roadmap not because they are deferred — they are not on the *plan* at all. Adding them requires re-litigating §4.5.

**Deferred to v3** — items previously considered for v2 but pushed out under the realism-tightening pass:

- **Tax-ready exports.** Originally targeted v2 in P4–P5 RM → IB → VTN flow. Deferred to v3 to reduce P4 capability load.
- **LP-style book-level gates.** Same — originally v2, deferred to v3.
- **Custom-rule backtester.** Persona 1's Canvas A originally listed; clarified to roadmap in §4.5.4 and now explicit v3.
- **Arabic-language UI.** Always post-v1; explicit v3 framing.
- **Engine-state replay.** Persona 2 transparency feature; v3.

**v3 is the planning horizon beyond M12.** §5.4 does not commit v3 timing; that is a future planning conversation after Desk Full stabilizes.

### 5.4.7 Execution-resource flag for §11

The roadmap implicitly assumes Mohammed executes all of P1–P6 solo. This is the riskiest assumption in §5.4 and is surfaced here so §11 financial model can address it explicitly.

**Highest-risk phase for solo execution: P4 (Desk Full preparation).** Pulling three RM items (multi-account dashboard, audit-grade exports, role-based seats) through RM → IB concurrently is the heaviest engineering load in the plan. Solo execution at this phase is plausible but tight; a slip cascades into P5 ship date.

**Recommended §11 input:** model two cost scenarios for P4 — solo-founder execution and solo-founder-plus-contractor execution. The contractor scenario should evaluate whether 1–2 specialized contractors (front-end engineer for multi-account dashboard, back-end engineer for audit-grade journal export) for ~3 months would meaningfully de-risk P4 → P5 transition.

**Not a §5 decision.** Whether to hire or contract is a §11 cost/runway decision and a §10 ops decision. §5.4.7 only flags that the roadmap as drafted assumes solo execution and that this assumption deserves explicit modeling.

---

## 5.5 Risk review

Audit performed against §5.1, §5.2, §5.3, §5.4 on 2026-05-01. Five flags surfaced; all five resulted in changes. §5 v1 lock follows.

### Flags applied

- **Flag 1 — §5.2.3 Desk Full feature list cleaned.** Tax-ready exports, LP-style book-level gates, and multi-strategy account isolation removed from v2 scope; explicitly relabeled as v3 deferrals per §5.4 refinement. Fixes a direct contradiction with the just-locked roadmap.
- **Flag 2 — Multi-strategy account isolation deferred to v3.** Removed from §5.2.3; not added to roadmap capability flow. It was an unmoored claim — a Persona 2 power-user nice-to-have without a real timing commitment. Defers cleanly to v3.
- **Flag 3 — Trader API rate limits reframed as targets.** §5.2.3 Trader description updated: rate limits are now framed as "target ~1 req/sec/endpoint, burst 10, finalized through soft-cohort calibration" rather than committed numbers. Honest about underlying STN status of the rate-limiting capability.
- **Flag 4 — §5.2.6 anti-overclaim notes extended.** Added a fifth bullet protecting against marketing v3-deferred features (tax-ready exports, LP-style book-level gates, multi-strategy isolation) as v2.
- **Flag 5 — §5.4.4 P4 → P5 gate text tightened.** "Any P4 RM → IB target" → "any of the three P4 RM → IB targets (multi-account dashboard, audit-grade exports, role-based seats)." Reflects the post-refinement scope reality.

### What audited clean (no flags)

- §5.1 capability inventory after Rule A downgrade — all labels and descriptions defensible.
- §5.3 packaging principles — every principle traces to brand voice and §4.5 fence; no contradictions surfaced.
- §5.4.1 phase map and §5.4.2 capability flow after refinement — internally consistent.
- §5.4.6 v3 deferrals and "not on the plan" distinction — clean.
- §5.4.7 execution-resource flag — clean.

### Audit reference for downstream sections

§5.5 becomes the canonical reference for §6 / §7 / §9 / §15 anti-overclaim sweeps with respect to product capabilities and packaging. Any downstream copy must trace to §5 *as audited*, not as initially drafted. Specifically:

- Tier marketing copy must respect §5.2.6 anti-overclaim notes (now five bullets).
- Capability claims must match §5.1 maturity labels (not pre-Rule-A labels).
- Roadmap commitments in §15 investor narrative must match §5.4 phase map and capability flow as audited (no v3 features marketed as v2).
- Packaging principles in §5.3 are inherited as constraints by §6, §7, §9 — drafters of those sections cannot relax them.

### §5 v1 LOCKED

All sub-sections committed. Downstream §6 (pricing), §7 (GTM), §9 (messaging), §11 (financial model), §13 (KPIs), §14 (launch), §15 (investor) draft against §5 v1.

---

## Open questions for the founder (this pass — capability inventory)

1. **Maturity-label accuracy.** Anything I labeled VTN that is actually STN, IB, or RM? The labels drive what can ship in v1 tiers vs. what gets roadmap-flagged. Errors here cause overclaim downstream.
2. **Capability omissions.** Anything in the engine, dashboard, or Telegram bot that I missed? I drafted from project memory and `coinscopeai-engine-api`; a real audit would surface anything I don't have in context.
3. **Vendor stack accuracy.** P1 narrow stack listed as CCXT (4-ex), CoinGlass, Tradefeeds, CoinGecko, Claude. Confirm composition and any Phase-1 capability I missed.
4. **Declared gaps in §5.1.6.** Right list, or do you want to add an explicit "we don't do X" item that becomes a product-scope boundary in §5.2 tier matrix design?
