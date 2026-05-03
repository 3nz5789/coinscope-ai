# Strategic Memo — CoinScopeAI Business Architecture

**Date:** 2026-04-29
**Author:** Mohammed Abuanza (with Scoopy)
**Audience:** Internal · advisors · prospective co-founder
**Status:** Working draft · circulate for sharpening, not for external distribution
**Length target:** one page (read in 4 minutes)

---

## TL;DR

CoinScopeAI's trading engine is well-engineered for capital preservation and is mid-validation on Binance Testnet. The platform around the engine is underbuilt for multi-customer SaaS at the price tiers we've published ($19 / $49 / $99 / $299). Before we can credibly sell beyond Mohammed's own use, five strategic layers need to land — three of them small enough to ship alongside the current 30-day validation, and two larger ones gated on validation passing. Without these the architecture only supports read-only signals; with them, all four pricing tiers become real, and the path to fund-tier credibility opens.

---

## Where we are

**Engineering posture is strong.** Capital preservation as primary mandate, ADR-004 (no LLM on the order path), Risk Gate halts everything downstream, EventBus journals every signal/gate/order, vendor adapters preventing field-name leakage, real-capital gate as a hardcoded `testnet=true`. These are the right invariants and they're rare in retail crypto.

**Phase 1 vendor surface is locked appropriately small.** CCXT (Binance · Bybit · OKX · Hyperliquid), CoinGlass v4, Tradefeeds, CoinGecko, Claude API minimal tools. The discipline to defer Tardis · CFGI · LunarCrush / Grok · TradingView to Phase 2, and Coin Metrics · CoinMarketCap · Perplexity to Phase 3, avoids the classic over-investment trap.

**Validation is in flight.** COI-41 30-day testnet validation in progress, blocked on COI-40 (DigitalOcean SGP1 droplet provisioning). The 4,955 USDT testnet account exists, the 16-page dashboard is live at `app.coinscope.ai`, the 98-path Engine API is live at `api.coinscope.ai`. The Telegram bot is built but pending VPS.

---

## What's missing strategically

Five gaps, ranked by ROI. None are engineering bugs — they're missing layers of the platform.

**1. Multi-tenancy isn't there.** The engine runs one account. Four-tier pricing implies many users with their own portfolios, risk profiles, journals, exchange keys. Without multi-tenancy, only the read-only signals tier is sellable.

**2. No entitlements / feature-flag layer.** Stripe charges money; it doesn't enforce what each tier can do. Every gated feature is currently a billing footgun.

**3. Compliance is invisible.** Jordan-based founder + global users + crypto = real regulatory weight. ToS, risk disclosures, jurisdictional exclusions, audit-log retention are not optional past Phase 1. KYC/AML is required for any fund-tier work.

**4. No public trust surface.** Trading platforms live or die on trust. At $299/mo Team tier the first sales objection is "show me your live track record." We have the data (Trade Journal in PG); we don't have the public artifact. Competitors with one will out-sell us.

**5. Cost meter / margin protection.** Each paying user costs us in vendor API spend. Without per-user tracking, a chatty Pro user at $49/mo can cost $50/mo in Claude alone. Margins die one user at a time.

---

## Sequenced roadmap

**Phase 1.5 — alongside VPS deploy + validation** *(none touch engine internals; validation rules still hold)*

ToS + Risk Disclosures · Per-User Exchange API Key Vault scaffold · Basic Cost Meter · Public Disclosures Page · Audit Log Retention Policy. Five Linear issues live: COI-60 through COI-64. All S effort. Net effect: we can sign our first paying customer to read-only signals without legal or cost exposure.

**Phase 2 — after validation passes** *(the unlock for paid tiers)*

Multi-Tenant Engine (largest single piece of work in the plan) · Entitlements Service · KYC/AML for Fund Tier · Public Performance Dashboard · Per-User Strategy Configuration. Plus the Phase 2 vendor additions (Tardis · CFGI · LunarCrush *or* Grok · TradingView). All four pricing tiers become sellable. Trust surface goes live. Real-capital gate may flip for Mohammed's own account at small notional after §8 sign-off.

**Phase 3+ — gated on revenue / fund clients**

ML Lifecycle (Registry · Shadow · A/B · Retrain) · Multi-Region HA · Programmatic API for Fund Clients · Customer Support System · Strategy Marketplace · Coin Metrics · Perplexity research. The "institutional-grade" claim now stands up to due diligence.

---

## Recommended go / no-go signals

**Validation pass conditions** (gate from Phase 1.5 → Phase 2): COI-41 completes 30 days, per-provider health green ≥ 7 consecutive days, no engine code changes during the period, all five P1.5 Linear issues closed, ToS + disclosures published. If any fail, hold Phase 2 and fix.

**First paying customer conditions** (read-only signals tier): ToS signed-acceptance gate live, public disclosures page up, Telegram bot operational, basic Cost Meter recording usage, Audit Log Retention enforced. Roughly 4 of 5 P1.5 issues — closable in two weeks alongside the COI-40 unlock.

**Real-capital flip conditions** (Mohammed's own account first, small notional): all six §8 checklist items green, all five incident runbooks authored and rehearsed, Phase 2 Multi-Tenant Engine and Public Performance Dashboard live (so the system is honest about what it's doing). Recommended starting notional ≤ 1% of intended live capital.

**Fund tier readiness signals** (Team tier real selling): KYC/AML pipeline operational, Programmatic API + webhooks shipped, multi-region HA, ML lifecycle in place, six months of public performance history with signed snapshots.

---

## Effort and risk

**Phase 1.5** is roughly two weeks of focused work for one developer. No blockers beyond COI-40. Risk: low (mostly content + middleware + small migrations).

**Phase 2** is the largest investment in the entire plan — likely 8–12 weeks of multi-tenancy work alone, plus parallel work on KYC, Entitlements, and the Trust dashboard. Risk: medium-high (multi-tenancy migrations are scary; budget time for it).

**Phase 3+** is open-ended; size against revenue. Don't start any of it without paying customers.

---

## Critical posture notes

The Claude API endpoint must be `api.anthropic.com`, never `claudeapi.com` (which is a third-party proxy). This is now Invariant #9 in the architecture. The order routing is and remains Binance Testnet only until the §8 gate flips. The validation phase rule (no engine code changes) still applies — every P1.5 item is engineered to sit *around* the engine, not inside it.

---

## Next decisions (for Mohammed)

1. **Approve P1.5 scope as-is** (COI-60..COI-64) → signal to start COI-60 first (legal language) since other items can wait one more week
2. **Lock Phase 2 budget** — 8–12 weeks of focused work; commit or descope before validation completes
3. **Decide Massive's slot** — replace CCXT WS in P1, slot into P2 with Tardis, or drop. Compare cost / latency / coverage in a 30-min spike
4. **Consider co-founder / advisor** — the Phase 2 work plus customer conversations is more than one person can do well in parallel; surface this as a real question now rather than at week 4 of P2

---

**Companion docs**
- Architecture v5: `/CoinScopeAI/architecture/architecture.md`
- Readiness checklist: `/CoinScopeAI/mvp-readiness-checklist.md`
- Vendor catalog (with URLs): inside the architecture doc
- Linear issues: COI-60 through COI-64

**File location:** `/CoinScopeAI/strategy/strategic-memo-2026-04-29.md`
