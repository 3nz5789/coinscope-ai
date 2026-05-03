# Vendor Spike: Massive vs CCXT Pro

**Date:** 2026-04-29
**Decision needed:** Where (if anywhere) does Massive fit in the rollout?
**TL;DR verdict:** **DROP Massive.** CCXT Pro covers our needs end-to-end at ~7× lower cost, and Tardis.dev is the right Phase 2 backtest source.

---

## Sources

- [Massive · Crypto WebSocket overview](https://massive.com/docs/websocket/crypto/overview)
- [Massive · Crypto REST overview](https://massive.com/docs/rest/crypto/overview)
- [CCXT Pro manual](https://docs.ccxt.com/ccxt.pro.manual)
- [CCXT Pro · GitHub wiki](https://github.com/ccxt/ccxt/wiki/ccxt.pro)
- [Top 5 Crypto WebSocket APIs (2026)](https://www.coingecko.com/learn/top-5-best-crypto-websocket-apis)
- [Crypto API Latency for HFT in 2026](https://coinmarketcap.com/academy/article/crypto-api-latency-for-high-frequency-trading-in-2026)

---

## Side-by-side

| Dimension | CCXT Pro (current) | Massive | Winner |
|---|---|---|---|
| **Base price** | $29/month | $199/month | CCXT Pro (~6.9× cheaper) |
| **Exchange coverage (WS)** | 72 exchanges with WebSocket | "Major exchanges worldwide" — actual count not published | CCXT Pro |
| **Latency** | Direct exchange WebSocket — bound by upstream exchange | < 20ms claimed (aggregated/normalized) | Massive (marginal — depends on geography) |
| **Data unification** | Each exchange surfaces its own schema; CCXT normalizes the common surface (book, trades, ticker) | Aggregates and standardizes feeds across exchanges into one schema | Massive |
| **Execution / order placement** | Yes — unified order placement on 72 exchanges | No — read-only data only | **CCXT Pro (deal-breaker)** |
| **REST + WebSocket parity** | Yes (CCXT base + Pro WS layer) | Yes (REST + WS + flat files) | Tie |
| **Backtest data (historical)** | No native historical layer | Some historical, but Tardis is more battle-tested for institutional backtest | Tardis (P2) |
| **Auth model** | Per-exchange API keys; CCXT brokers the call | Single Massive API key; opaque to exchanges | Tie (different trade-offs) |
| **Open source** | Core CCXT yes, Pro is paid wrapper | Closed-source SaaS | CCXT Pro |
| **Battle-tested at scale** | 10+ years, default in retail crypto-quant | Newer; less production track record visible | CCXT Pro |
| **Vendor lock-in risk** | Low — CCXT is portable, multi-exchange-by-design | High — Massive abstracts the exchanges away from your code | CCXT Pro |
| **Regulatory considerations** | Direct exchange relationship (your keys, your account) | Massive sits between you and the exchange for data; not for orders | CCXT Pro |

---

## The decisive points

**1. Massive does not place orders.** CCXT Pro is the only one of the two that wraps order execution across exchanges. We need that for Tier 04 Order Manager, full stop. Whatever Massive provides, we still need CCXT Pro. So adding Massive is *additional* cost on top of CCXT Pro, not a replacement.

**2. Massive's normalization advantage is duplicated by our Vendor Adapter layer.** The Tier 02 Adapter layer (Architecture v5) already maps vendor-specific schemas into our 10 internal models (`Candle`, `Order`, `Position`, etc.). That's exactly the unification Massive sells. We're paying for it once in our codebase already; paying $199/mo to have a vendor do it externally is double-spending.

**3. The latency advantage is marginal at best for our use case.** Massive claims <20ms; CCXT Pro WebSocket connections route directly to exchanges, which have their own latency profile that depends on geography. For a 10-second scan interval and confluence ≥ 65 signal threshold, the latency floor is set by our scan cadence, not the WS feed. We are not running HFT; sub-100ms feeds are not a value driver for us.

**4. Phase 2 backtest data goes to Tardis.dev, not Massive.** Massive's historical offering is real but Tardis is more institutional-grade and is already in our Phase 2 plan. No reason to introduce a third backtest vendor.

**5. Vendor lock-in cuts the wrong way.** Massive abstracts the exchanges away from the consuming code. CCXT keeps each exchange visible (with normalized helpers). For a system whose mandate is capital preservation, the strictly-more-explicit relationship with each exchange (CCXT) is the safer architecture.

---

## Verdict

**DROP Massive from all phases.**

- Phase 1: keep CCXT Pro (Binance · Bybit · OKX · Hyperliquid)
- Phase 2: add Tardis.dev for historical backtest fuel
- Phase 3: revisit only if a fund-tier customer specifically requires a Massive-backed feed (unlikely)

Update the Vendor Catalog: remove Massive from the TBD section, replace with a one-line note that the spike concluded "drop."

---

## Cost impact of this decision (saving)

| Phase | Without Massive | With Massive | Annual saving |
|---|---|---|---|
| P1 (now) | CCXT Pro $29/mo | CCXT Pro + Massive $228/mo | **$2,388/yr** |
| P2 | + Tardis (priced separately) | + Tardis + Massive $199/mo | **$2,388/yr** |
| P3 | + Coin Metrics (priced separately) | + Coin Metrics + Massive | **$2,388/yr** |

For a pre-revenue platform, ~$2.4k/year of margin matters.

---

## What changes downstream

- **Architecture diagram:** remove the TBD "Massive" entry from the vendor catalog panel; replace with a struck-through line and "spike concluded — dropped."
- **architecture.md vendor catalog:** remove Massive row; document the decision in the open-follow-ups section.
- **Strategic memo:** the "Decide Massive's slot" follow-up is now closed.
- **No code changes required.** Massive was never wired in.

---

## Open question this spike does *not* answer

LunarCrush vs Grok X (xAI) for Phase 2 social-sentiment is still open. Recommend a separate spike when Phase 2 planning starts (gated on Phase 1 validation passing).
