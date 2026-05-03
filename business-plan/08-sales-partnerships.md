# §8 Sales and Partnerships

**Status:** v1 LOCKED. Single-pass draft. Light at v1 — most acquisition self-serve (PLG); founder-led sales for Desk tiers; partnership long-list scoped but few committed deals at v1.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active. §8 reflects v1 sales motion at solo-founder scale; partnership commitments deferred to post-validation per §15 raise posture.

---

## 8.0 Assumptions and inheritance

### Locked from upstream

- **§5.2 tier matrix** — Free / Trader / Desk Preview / Desk Full v2.
- **§6 v1 pricing** — Trader $79/mo, Desk Preview $399/mo, Desk Full v2 $1,199/mo + per-seat.
- **§7 GTM lead-with-channel** — founder-led content primary; closed networks + 1:1 P3 sales as concurrent track.
- **§7.5 community strategy** — founder selectively engages MENA crypto-trader cliques; no paid promotion.
- **§10 support tier matrix** — Sev-1 1h response across all tiers; Desk-tier response 4–12h weekday.
- **§11.5 channel CAC bands** — Desk Preview $0–$3,000 closed networks / events; Desk Full v2 $0–$8,000 partnership-driven.
- **§3 personas** — P1 / P2 / P3 with secondary persona (prop-firm-funded trader).
- **§2.7 competitive positioning** — prop firms parallel category, partnership candidates not rivals.
- **§13 MAVT north-star** — sales motion measures conversion to MAVT, not just signups.

### What §8 decides (new)

- Sales motion per tier (PLG / PLS / sales-led split).
- Desk discovery → demo → close playbook.
- Partnership long-list and scoring methodology.
- Top-3 partnership targets for first 90 days.
- Affiliate program v1 scope and payout model.

---

## 8.1 Sales motion per tier

### Tier-by-tier sales motion

| Tier | Sales motion | Founder time per acquisition | Self-serve eligibility |
|---|---|---|---|
| **Free** | Pure PLG (product-led growth) | None | Yes — anonymous landing-page signup → account verification → onboarding |
| **Trader** | PLG with optional founder support | None typical; Sev-1+ founder-direct | Yes — self-serve signup + payment |
| **Desk Preview** | PLG with founder sales-assist | 0–1 hr discovery call optional | Yes — self-serve, but invitation-friendly via §7 closed networks |
| **Desk Full v2** | Sales-led for new acquisition; self-serve migration from Preview | 2–4 hr discovery + demo + close cycle | Migration: yes (Preview → Full); new acquisition: founder-led |

### Why this split

**PLG dominates Free + Trader.** §11.5 CAC bands for Trader ($30–$120 organic content) only work if sales is light or absent. Founder time spent on individual Trader acquisition kills unit economics.

**Sales-assist optional at Desk Preview.** Persona 3 sometimes wants to talk before paying $399/mo — that conversation is bounded (~1hr) and high-conversion. Self-serve remains the primary path.

**Sales-led at Desk Full v2 new acquisition.** Persona 3 paying $1,199/mo + per-seat for partner-money infrastructure usually wants validation through conversation. Founder-led discovery → demo → close. Migration from Preview is self-serve (Preview users who upgrade at v2 launch don't need re-onboarding).

### Founder time allocation (per §7 GTM allocation)

Per §7.2 locked allocation: 25% of GTM time on P3 track during P3 onwards. Within P3 track:

- Closed networks + warm intros: ~50% of P3 time.
- 1:1 sales calls (discovery + demo + close cycles): ~30% of P3 time.
- Partnership outreach + relationship-building: ~20% of P3 time.

At ~5 hrs/week total P3 track during P3 phase, that's ~1.5 hrs/week on 1:1 sales — supports 1–2 active Desk Full v2 sales cycles concurrently. Bounded but real.

---

## 8.2 Discovery → demo → close playbook for Desk

### Stage 1 — Discovery (30 min)

Qualify the prospect against Persona 3 fit:

- **Book size:** $200k–$1M aggregate? Solo PM with partners?
- **Partner count + structure:** 2–5 partners typical; informal vs. formalized partnership?
- **Current toolset:** what cobbled bundle (TradingView + Tradervue + Nansen + spreadsheet labor)?
- **Decision criteria:** capital preservation / partner reporting / regulatory comfort / book scaling?
- **Timeline:** evaluating now? Q? Funded book waiting on infrastructure?

Disqualify if:

- Looking for fund-formation tooling (per §4.5 fence — direct redirect).
- Manages institutional capital (regulated fund) — out of v1 ICP.
- US-resident retail (per §4.5 — explicit rejection).

### Stage 2 — Demo (45 min)

Walk-through Desk Preview surface:

- Multi-account aggregation (3-account view, single PM access).
- Performance journal across accounts (R-multiples + rule-violation tagging).
- Static monthly PDF report generation (the partner-reporting pain solver at v1).
- Risk-gate configuration with LP-style book-level mention as v3-deferred (per §5.2.6 anti-overclaim).
- Telegram-companion bot integration (alerts + commands).

Anchor expectations:

- "Preview is Preview — multi-account view-only, single PM access, static PDF report. Full Desk ships v2 with multi-account at scale + audit-grade exports + role-based seats."
- "v3-deferred features (LP-style gates, tax exports, multi-strategy isolation) won't appear in v2."

### Stage 3 — Trial decision

Two trial paths:

- **Direct paid:** sign up at Desk Preview pricing ($399/mo) with 14-day money-back guarantee per §6.7.
- **Invitation:** if Desk Preview soft-cohort still has open slots and prospect is high-fit, offer founder-cohort pricing ($299/mo) within the 60-day window.

### Stage 4 — Close

- Sign up via Stripe checkout; account-verification at Stripe.
- Onboarding session within 48h: setup multi-account configuration, configure gates, verify journal access.
- Founder-direct contact for first 30 days; transition to standard support tier per §10.1 after onboarding stabilizes.

### Discovery → close cycle metrics

- **Target conversion rate:** 30–40% of qualified Desk-fit prospects close within 21 days of first call. Anchored against §11.5 founder-led-sales CAC bands.
- **Cycle time:** 7–21 days typical for Persona 3 (Solo PMs make decisions slowly per §3 canvas).
- **Disqualification rate:** ~30% of inbound sales conversations disqualify (anti-ICP, fund-LP confusion, US-resident, etc.).

---

## 8.3 Partnership long-list and scoring

### Long-list categories

| Category | Examples | Why interesting |
|---|---|---|
| **Exchanges** | Binance, Bybit, OKX, KuCoin, Bitget — MENA-region focus | Largest user-overlap pool; MENA-specific exchange teams interested in MENA-built infrastructure |
| **Prop firms** | FTMO, Apex, Topstep, MyForexFunds-equivalent | Locked secondary persona overlap; potential bundle: "FTMO funded traders get 30% off CoinScopeAI Trader" |
| **Crypto data / research** | Glassnode, Messari, CryptoQuant, The Block Pro | Same wallet, different value layer; co-marketing potential |
| **MENA founder networks / accelerators** | Sanabil Investments, MEVP, Wamda, Flat6Labs, Antler MENA | Ecosystem integration; founder-network introductions |
| **Education / methodology brands** | Edgewonk, methodology-focused Substack writers, Tradervue | Cross-promotion; methodology-aligned audiences |
| **Crypto influencers (MENA + global)** | MENA-region X / YouTube / Telegram operators | Distribution amplification; selective, methodology-aligned only (not signal-group adjacent) |
| **Software platforms** | Stripe (already vendor), Notion, Linear (already used) | Mainly procurement; partnership unlikely at this scale |

### Scoring methodology — Reach × Fit × Deal complexity

Each candidate scored on three dimensions:

- **Reach:** estimated ICP-overlap audience size. Low / Medium / High.
- **Fit:** alignment with locked positioning + pillars. Low / Medium / High. Anti-ICP-adjacent = disqualified outright.
- **Deal complexity:** what it takes to close. Low (warm-intro chat) / Medium (multi-meeting deal) / High (legal + integration work).

### Selected scoring (illustrative)

| Candidate | Reach | Fit | Deal Complexity | Notes |
|---|---|---|---|---|
| Bybit MENA region (referral deal) | High | High (MENA-aligned) | Medium | Direct revenue impact + MENA distribution |
| FTMO (funded-trader bundle) | High | High (secondary persona) | Medium-high (legal terms) | Partnership long-list anchor |
| Sanabil / MEVP (ecosystem intro) | Medium | High (founder network) | Low | Relationship-driven; founder-led |
| Glassnode (co-marketing) | Medium | Medium (P2 overlap) | Low | Methodology-aligned; light partnership |
| Edgewonk (cross-promotion) | Medium | High (P1 overlap) | Low | Methodology-aligned; minimal commitment |
| MENA crypto influencer X (named TBD) | Medium-high | Medium (must vet) | Low-medium | Selective; methodology-aligned only |
| Anti-ICP signal-group operator | High | **Disqualified** | n/a | §5.3.3 prohibition |

---

## 8.4 Top-3 partnership targets for first 90 days

Selected from long-list based on scoring + founder-time-realistic execution.

### Target 1 — Bybit MENA region referral partnership

**Why:** Bybit's MENA team is actively building infrastructure relationships. CCXT supports Bybit on our P1 stack. Direct user-acquisition path through their MENA user base. Most material reach.

**Approach:** Warm intro via founder network (Mohammed's MENA contacts) → BD team conversation → referral-deal scoping.

**Deal shape (scoping):** Bybit MENA users get founder-cohort pricing on Trader; CoinScopeAI references Bybit as preferred-venue for MENA-focused users. No equity, no integration beyond CCXT (which exists).

**Timeline:** initial conversation by M3; deal scoping M4–M5; possible signing M6.

### Target 2 — FTMO partnership (or comparable prop firm)

**Why:** §3 secondary persona (prop-firm-funded trader) overlap is structural. FTMO is largest by reach; deal complexity manageable.

**Approach:** Founder warm intro + product walkthrough → BD conversation → bundle-deal scoping ("FTMO funded traders get 30% off CoinScopeAI Trader").

**Deal shape:** Affiliate-style commission OR fixed-discount bundle. FTMO retains primary relationship; we get user-acquisition path.

**Timeline:** initial outreach M3–M4; scoping M5; possible launch M7.

### Target 3 — Sanabil / MEVP ecosystem introduction

**Why:** MENA founder-network access for Persona 3 acquisition + warm-intro pipeline for §15 investor narrative post-validation.

**Approach:** Founder-led; relationship-building during validation phase. Light. Not a transactional partnership — ecosystem positioning.

**Deal shape:** Not a "deal" — relationship + introductions + advisor potential.

**Timeline:** ongoing; founder maintains contact throughout P0–P3.

### Why not exchanges other than Bybit at v1

Binance, OKX, KuCoin all on the list. But (a) Binance is the largest and the most institutional — relationship-building takes longer than 90 days; defer to post-validation. (b) OKX and KuCoin have less MENA-specific BD presence — lower priority for v1 90-day window. (c) Founder time bounded — 1 exchange partnership at v1 is realistic; multiple is not.

---

## 8.5 Affiliate program v1

### Scope

- **Open to:** existing paying users (Trader, Desk Preview, Desk Full v2) who refer new paying users.
- **Not open at v1:** general-public affiliate signup (deferred to post-launch when economics validated).

### Commission structure

- **Commission rate:** 20% of first 12 months of MRR per converted referral.
- **Cookie window:** 30 days from referral click.
- **Self-referral disallowed** — affiliate cannot refer themselves.
- **Anti-abuse:** account-level enforcement; one-time-use referral codes; suspicious patterns (e.g., 5+ referrals from same IP cluster) flagged for review.

### Stacking rules

- **Cannot stack with founder-cohort pricing.** Affiliate referrals during the founder-cohort window go through founder-cohort, not affiliate commission.
- **Can stack with annual prepay discount.** Affiliate commission applies to the standard annual rate; the user gets the 17% discount, the affiliate gets 20% of the discounted MRR.
- **Cannot stack with case-by-case promotional codes.** One discount path per user.

### Payout

- **Frequency:** monthly via Stripe payout.
- **Threshold:** minimum $50 accumulated commission before payout (avoids per-transaction fees).
- **Tax:** affiliate responsible for own tax obligations in their jurisdiction; CoinScopeAI does not provide tax advice.

### Trigger to launch

- **Not at v1 launch.** Affiliate program goes live at M5–M6 if §11.5 unit economics validate (Trader CAC <$200 organic + paid acquisition criteria met). If unit economics don't validate, affiliate program deferred to post-v2.

### Anti-ICP guard

- **No bundling with anti-ICP products.** Affiliates promoting CoinScopeAI alongside signal groups, copy-trade products, or leverage-maximizer content disqualified.
- **§9.3 register handoff applies:** affiliate-content register must respect product-tier (no slogan-tier "alpha" framing; no v3-deferred features marketed as v2).

---

## 8.6 Anti-overclaim audit on §8

Audit performed against §8.0 through §8.5 on 2026-05-01.

### Flags applied

**Flag 1 — Partnership "targets" are scoping, not commitments.**

Top-3 partnership targets (Bybit MENA, FTMO, Sanabil) are *scoping conversations*, not announced deals. §15 investor narrative must frame as "partnership pipeline" not "partnership wins" until contracts signed.

*Mitigation:* §8.4 explicit "scoping" language; §15.5 deck does not list named partnerships in traction slide unless contracts signed.

**Flag 2 — Affiliate commission stacking rules locked.**

§8.5 stacking rules prevent ambiguity. Founder-cohort + affiliate stacking would erode pricing power; one-discount-path-per-user maintains discipline.

*Mitigation:* Stacking rules embedded in Stripe promo-code logic; documented in §10 support templates.

**Flag 3 — Sales motion at Desk Full requires founder time at v2 launch.**

§5.4 P5 (Desk Full launch M10–M12) is also when contractor support tapers. Founder must balance Desk Full sales (2–4 hrs per cycle) with v2 stabilization needs.

*Mitigation:* §7 GTM allocation already accounts for P5 founder time (50% content / 30% P3 track / 10% community / 10% GTM ops); P5 is highest founder-time-on-P3-track at 30%.

### What §8 audited clean

- Sales motion per tier traceable to §5.2 + §11.5 CAC bands.
- Discovery → close cycle anchored against §3 Persona 3 canvas + §11.5 founder-led-sales CAC.
- Partnership long-list excludes anti-ICP categories (signal groups, copy-trade).
- Top-3 partnership targets realistic for 90-day founder-time bounds.
- Affiliate program scope respects §5.3.3 anti-ICP prohibition + §9.3 register handoff.
- §15 due-diligence Q&A inherits partnership pipeline framing without overclaim.

### §8 v1 LOCKED

§8.0 through §8.6 all committed. Framework sections 1–16 now all v1 LOCKED.
