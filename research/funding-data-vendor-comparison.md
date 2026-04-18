# Funding Data Vendor Comparison

**Task:** `[RESEARCH] DATA — Funding Data Vendor Comparison`
**Author:** Scoopy (Claude) on behalf of Mohammed
**Date:** 2026-04-17
**Status:** Draft v1 — pending review
**Scope:** Validation-phase backtest enrichment only. No engine changes.

---

## 1. Context and Scope

CoinScopeAI is mid-way through the 30-day Testnet Validation Phase (COI-41). The engine is frozen. This research evaluates third-party vendors for **historical backfill** of derivatives data to enrich the existing 110K+ candle dataset and regime labeling, not for live signal generation or streaming ingestion (the EventBus already handles that through exchange-native WebSocket streams).

### Data requirements

Full derivatives suite across the four exchanges CoinScopeAI already streams:

| Data type | Use in validation |
|-----------|-------------------|
| Funding rates (historical) | Regime context, carry-adjusted returns |
| Open interest | Positioning signal for regime labels |
| Liquidations | Volatility regime, tail-risk feature |
| Basis (perp vs spot) | Market stress indicator |
| Long/short ratios | Crowd-positioning feature |
| Options skew | Vol regime classifier (Trending/Volatile/Quiet) |

Target exchanges: **Binance, Bybit, OKX, Hyperliquid.**

### Evaluation criteria (weighted)

1. **Cost** (heaviest weight — solo-dev, validation-phase budget)
2. **Hyperliquid coverage** (hardest to source from general vendors)
3. **Bulk historical depth** (batch/CSV download preferred over streaming)
4. **Python SDK** (matches existing codebase)
5. **Auth + rate limits** compatible with overnight backfill scripts
6. **License** permitting internal backtesting + redistribution inside private repo

---

## 2. Vendor Comparison Matrix

Scoring: ✅ confirmed / ⚠️ partial or unconfirmed / ❌ not supported / ❓ not published.

| Vendor | Binance | Bybit | OKX | Hyperliquid | Funding | OI | Liquidations | Basis | LS Ratio | Options Skew | Python SDK | Entry Price | Hist. Depth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Exchange-native APIs** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ infer | ⚠️ compute | ⚠️ Binance only | ❌ | community | Free | Since listing |
| **Coinalyze** | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ❌ | ✅ (unofficial) | Free (40 req/min) | Multi-year |
| **Tardis.dev** | ✅ | ✅ | ✅ | ✅ (since 2024-10-29) | ✅ | ✅ | ✅ | ⚠️ compute | ⚠️ | ❌ | ✅ | Free tier (1 day/mo); paid tiers not published | Since 2019-03-30 |
| **Coinglass** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ (community) | ~$35/mo | Since ~2019 |
| **Laevitas** | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ⚠️ | ❓ | ⚠️ | ❌ (REST only) | Free tier; $50/mo premium; HTTP 402 pay-per-call | Not published |
| **CoinAPI** | ✅ | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ | ✅ | Free dev tier ($25 credit); $79/mo Dev | Derivatives: since 2021 |
| **Kaiko** | ✅ | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ❌ | ✅ (gRPC) | Sales call; not published | Not published |
| **Amberdata** | ✅ | ✅ | ✅ | ❌ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ | ✅ (vol surfaces) | ✅ | Sales call; not published | Years of vol surfaces |
| **CCData** | ✅ | ✅ | ✅ | ❓ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ❌ | Sales call; not published | Full tick history |
| **Glassnode** | ✅ | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ✅ | ⚠️ | ✅ | ❌ | ❌ | Not published (likely enterprise) | BTC/ETH/SOL focus |
| **Velo Data** | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ | ❓ | ❓ | ❓ | ❌ | ❓ | Not published | UI-first |

Legend caveats:
- Hyperliquid coverage was explicitly confirmed for Tardis.dev (starting 2024-10-29), Coinglass, Laevitas, and Glassnode. Every other vendor's Hyperliquid coverage is either unconfirmed or not yet on their exchange list as of April 2026.
- "Compute" entries for basis mean the vendor gives you perp + index/spot ticks; you compute basis yourself. Standard.

---

## 3. Detailed Vendor Notes

### 3.1 Exchange-native APIs (free baseline)

All four target exchanges publish funding rate history, open interest, and partial long/short data for free. This is the baseline you compare every paid vendor against.

| Exchange | Funding | OI | Liquidations | LS Ratio | Rate limit |
|---|---|---|---|---|---|
| Binance Futures `/fapi` | `/fundingRate` | `/openInterest`, `/openInterestHist` | ❌ (infer from aggTrades) | `/globalLongShortAccountRatio`, `/topLongShortAccountRatio` | 2400 weight/min |
| Bybit v5 | `/v5/market/funding/history` | `/v5/market/open-interest` | ❌ (third-party aggregation) | ❌ | 600 req/5s |
| OKX v5 | `/api/v5/public/funding-rate-history` (since Mar 2022) | `/api/v5/public/open-interest` | ❌ | Limited | 20 req/2s per endpoint |
| Hyperliquid | `fundingHistory` (info endpoint) | Available via info endpoints | ⚠️ third-party (hyperliquid-stats) | ❌ | Generous; no published cap |

**Verdict:** The exchange-native APIs cover funding + OI + LS ratios (Binance only) for free across all four targets. They don't give you clean liquidations or basis out of the box, and there's no unified schema — you write four collectors. For a validation-phase budget of $0, this is the floor. Every paid vendor has to beat "four free collectors plus a few hours of glue code."

### 3.2 Coinalyze — best free aggregator

- **Why it wins the free tier:** One API, unified schema, covers Binance/Bybit/OKX with funding, OI, liquidations, and long/short ratios. Python wrapper exists on PyPI.
- **Gap:** Hyperliquid not explicitly confirmed in their docs as of April 2026. Plan to combine Coinalyze with the Hyperliquid public info endpoint to cover all four.
- **Gotchas:** 40 requests/minute per API key is tight for bulk backfill. Paginate and run overnight. No published SLA — it's a community-grade free product.
- **Verdict:** Strong default for Binance/Bybit/OKX. Fill the Hyperliquid gap with the exchange API directly.

### 3.3 Tardis.dev — best for reproducibility if you need tick-level

- **Why it's interesting:** Tick-level replay going back to 2019-03-30 on major exchanges; explicit Hyperliquid coverage since 2024-10-29; official Python client with batch CSV download.
- **Cost:** Free tier is limited to the first day of each month per exchange — not useful for real backfill. Paid tiers (Academic, Solo, Pro, Business) are not publicly priced. Community estimates put "Solo" in the $100–250/mo range but this is unverified.
- **Gap:** Options skew not a first-class product.
- **Verdict:** Over-specced for validation-phase analytics. Worth revisiting post-validation if the ML Signal Engine v4 wants tick replay for feature engineering.

### 3.4 Coinglass — best paid fit for the options-skew requirement

- **Why it's interesting:** The only sub-$50/month vendor that explicitly covers all four target exchanges, all required data types, including options skew, with a Python client.
- **Cost:** $35/month entry tier. Tier limits (exchanges/symbols per tier) need verification against the live pricing page before committing.
- **Gotchas:** Tier limits on symbols/exchanges aren't fully transparent; some community Python clients are on the v3 API and need porting to v4. Confirm tier scope before paying.
- **Verdict:** If options skew is actually required for the v4 regime classifier, this is the cheapest route. If options skew is optional, skip it.

### 3.5 Laevitas — niche, Hyperliquid-native

- Unified API over Binance/Bybit/OKX/Hyperliquid. HTTP 402 USDC micropayments is an interesting low-lock-in model.
- No Python SDK. Rate limits not published. Historical depth not published.
- **Verdict:** Worth a spike only if you want Hyperliquid-first unified access without a Tardis subscription. Not the default.

### 3.6 Enterprise tier (Kaiko, Amberdata, CCData)

- All three require a sales call, none publish pricing. Typical institutional floor is $2–5K/month. Redistributable licensing is their pitch — not relevant for a solo-dev validation phase with a private repo.
- **Verdict:** Out of scope for validation. Re-evaluate only if CoinScopeAI goes to a funded/multi-seat setup.

### 3.7 Coverage caveats worth flagging

- **Glassnode** is on-chain first. Its derivatives coverage for Hyperliquid is genuinely strong (they publish OI share) but for funding rates and OI across Binance/Bybit/OKX at tick granularity it's not the right tool.
- **Velo Data** looks UI-first. Programmatic access is not well documented as of April 2026. Skip for a code-driven backfill pipeline.
- **CoinAPI** has the broadest exchange list (400+) but Hyperliquid support isn't confirmed on their exchange list. Don't pay for their $79/mo Developer plan until that's verified with their sales.

---

## 4. Recommendation for Validation Phase

### Recommended architecture — two-tier, ~$0–35/month

**Tier 1 — Free baseline (mandatory):**
- Exchange-native APIs for all four exchanges. Funding + OI + (partial) LS ratios out of the box.
- Hyperliquid: `fundingHistory` from the info endpoint for funding; `hyperliquid-stats` aggregation for liquidations.

**Tier 2 — Coinalyze (free tier):**
- Unified aggregator for Binance/Bybit/OKX. Removes the need to write four separate collectors for funding + OI + liquidations + LS ratios.
- Hyperliquid falls through to Tier 1.

**Tier 3 — Coinglass ($35/month), conditional:**
- Add only if the v4 regime classifier research confirms it needs options skew. For pure regime labels (Trending/Mean-Reverting/Volatile/Quiet) derived from price + funding + OI, options skew is a nice-to-have, not required.

**Do not adopt during validation:**
- Tardis.dev, Kaiko, Amberdata, CCData, CoinAPI Developer. All are either over-specced or priced above what the validation phase budget justifies. Revisit post-validation when the v4 feature set is defined.

### Estimated monthly cost

| Component | Cost |
|---|---|
| Exchange-native APIs | $0 |
| Coinalyze (free tier) | $0 |
| Coinglass (optional, options skew) | $0 or $35 |
| **Total** | **$0–35/month** |

### Caveats and open questions

1. **Hyperliquid via Coinalyze** — unconfirmed. If they add it during the validation window, the architecture simplifies to a single aggregator. Flag for re-check in 2 weeks.
2. **Coinglass tier limits** — the $35 tier's symbol/exchange caps need verification against the live pricing page before committing. Do not pay without reading the tier sheet.
3. **Rate limits during bulk backfill** — Coinalyze's 40 req/min is tight. Budget an overnight job, not a fast replay.
4. **License review** — confirm Coinalyze and Coinglass terms allow internal backtesting inside a private GitHub repo. Standard commercial TOS usually permits this but explicit confirmation is cheap.
5. **Engine freeze** — this research is informational during validation. No data-path code lands until COI-41 completes and the v4 feature freeze opens.

---

## 5. Next Steps

1. **Verify Coinglass $35 tier scope** against the live pricing page. [Issue]
2. **Prototype a Coinalyze backfill script** for BTCUSDT funding + OI over the last 90 days. Measure wall-clock time and rate-limit margin before claiming viability. [Spike, 1 hour]
3. **Confirm Hyperliquid info-endpoint funding history** returns dense data for the validation symbols list. [Spike, 30 min]
4. **File decision in Notion 12 Meetings & Decision Log** once the two spikes are in. [Doc]

None of the above requires engine changes. All work sits in a new `scripts/backfill/` directory and writes to the existing data store under a clearly-labeled `external_vendor` namespace.

---

## 6. Sources

All pricing and coverage claims reflect public vendor pages as of 2026-04-17. Verify before committing spend.

- Coinalyze API docs — https://api.coinalyze.net/v1/doc/
- Tardis.dev docs — https://docs.tardis.dev/
- Laevitas — https://laevitas.ch/
- Coinglass pricing — https://www.coinglass.com/pricing
- CoinAPI pricing — https://www.coinapi.io/products/market-data-api/pricing
- Kaiko derivatives risk indicators — https://www.kaiko.com/products/analytics/derivatives-risk-indicators
- Amberdata derivatives — https://www.amberdata.io/ad-derivatives
- Glassnode derivatives — https://docs.glassnode.com/basic-api/endpoints/derivatives
- Binance funding rate history — https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History
- Bybit v5 funding history — https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- OKX v5 historical data — https://www.okx.com/en-us/historical-data
- Hyperliquid info endpoint — https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
