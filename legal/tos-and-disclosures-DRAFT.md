# CoinScopeAI — Terms of Service & Risk Disclosures

> ⚠ **STARTER LANGUAGE — REQUIRES COUNSEL REVIEW BEFORE USE**
>
> This document is drafted by the operator (with AI assistance) to capture intent and structure. It is not legal advice and must not be used in production without review and revision by qualified legal counsel familiar with crypto-trading-platform law in the relevant jurisdictions (at minimum: Jordan, the United States, the European Union, and the United Kingdom).
>
> Do not link this document publicly until counsel has reviewed it.
>
> **Document version:** 0.1 (draft)
> **Drafted:** 2026-04-29
> **Status:** PRE-COUNSEL — internal review only
> **Companion:** `/CoinScopeAI/legal/data-retention.md` (P1.5, COI-64)

---

## Part 1 — Terms of Service

### 1. Who we are and what this is

CoinScopeAI ("the Service," "we," "our," "us") is a software platform that produces algorithmic trading signals and, depending on subscription tier, executes trades on behalf of users on connected cryptocurrency-derivatives exchanges. The Service is operated by **[Legal entity name — TBD]**, registered in **[jurisdiction — TBD]**.

These Terms of Service ("Terms") govern your access to and use of the Service. By signing up, accessing, or using the Service, you agree to these Terms. If you do not agree, do not use the Service.

### 2. Eligibility

You must be at least 18 years of age (or the age of majority in your jurisdiction, whichever is higher) to use the Service. By using the Service you represent that:

- You are not a resident of, or located in, any jurisdiction subject to comprehensive sanctions administered by the United Nations, the United States Office of Foreign Assets Control (OFAC), the European Union, or the United Kingdom — including but not limited to Cuba, Iran, North Korea, Syria, the Crimea, Donetsk, and Luhansk regions, and any other restricted territory designated from time to time
- You are not on any restricted-persons list (OFAC SDN, EU consolidated, UK HMT, UN, or equivalent)
- Cryptocurrency derivatives trading is lawful where you reside and where you access the Service
- You have the legal capacity to enter into binding contracts

We may refuse service, suspend, or terminate access at any time if eligibility is not met or cannot be verified.

### 3. The Service is not investment advice

The Service produces algorithmic outputs (signals, scores, regime labels, suggested positions, simulated backtests, performance reports) for informational and operational purposes. **Nothing produced by the Service constitutes investment advice, financial advice, tax advice, legal advice, or a recommendation to buy, sell, or hold any asset.**

You alone are responsible for your trading decisions. The Service is a tool, not an advisor. We are not registered as an investment advisor, broker-dealer, commodity trading advisor, or in any analogous capacity in any jurisdiction, unless and until expressly stated on `coinscope.ai/legal/registrations` (currently: none).

### 4. Past performance does not predict future results

Any performance metric, backtest result, simulated track record, or historical signal output displayed by the Service:

- Is for informational purposes only
- Does not represent actual trading results unless explicitly labeled as such with a verified date range
- Backtest and simulated results have inherent limitations including but not limited to: hindsight bias, overfitting risk, the absence of real-execution friction (slippage, latency, partial fills, market impact), the absence of psychological factors, and the use of historical data that may not represent future market conditions
- **Past performance is not indicative of, nor a guarantee of, future results**
- Live performance metrics are reported on a best-efforts basis and may be subject to revision

You should expect that real-money trading using the Service will experience worse outcomes than backtests display, often substantially worse.

### 5. Validation phase disclosure

As of the version of these Terms in effect, the Service is in a validation phase operating exclusively against testnet (paper trading) environments. **No real capital is being traded by the Service on behalf of users.** When and if real-capital execution becomes available, it will be announced explicitly on `coinscope.ai/legal/status`, gated behind further explicit user opt-in, and accompanied by an updated risk disclosure that you will be required to re-acknowledge.

### 6. Subscription tiers, fees, and billing

The Service is offered in subscription tiers (Starter, Pro, Elite, Team) with prices and feature scopes displayed on `coinscope.ai/pricing` at the time of subscription. By subscribing you authorize recurring charges to your payment method via Stripe.

- Fees are charged in advance for each billing period
- All sales are final; refunds at our sole discretion, generally not granted after the first billing cycle
- We reserve the right to adjust pricing with 30 days' notice; existing paid periods are honored at the original price
- You may cancel at any time; access continues through the end of the paid period, then ceases
- We reserve the right to enforce per-tier feature limits, including API call rate limits, scanned-symbol limits, backtest depth limits, and execution limits

### 7. Your account and security

You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account. You agree to:

- Use a strong, unique password
- Enable two-factor authentication when offered
- Notify us immediately of any unauthorized access
- Provide accurate and current information; keep it updated

If your subscription tier permits exchange-execution functionality, you may provide read-only or trade-scoped exchange API keys through the Service's encrypted vault. We:

- Encrypt your keys at rest using industry-standard cryptography
- Never display the secret portion back to you after entry
- Do not access exchange accounts beyond the scope you grant
- Recommend you enable IP allowlisting and withdrawal-disabled flags on the exchange side

You bear sole responsibility for the security of the exchange accounts you connect.

### 8. Acceptable use

You agree not to:

- Use the Service in violation of any law or regulation in any applicable jurisdiction
- Reverse-engineer, decompile, or attempt to extract the source code, models, or proprietary algorithms of the Service
- Resell, sublicense, or commercially redistribute the Service or its outputs without a written commercial agreement
- Use the Service to manipulate markets (including wash trading, spoofing, layering, pump-and-dump schemes)
- Attempt to circumvent rate limits, tier restrictions, or access controls
- Use the Service to launder money or finance any unlawful activity
- Probe, scan, or test the vulnerability of any system or network we operate without written authorization

### 9. Suspension and termination

We may suspend or terminate your access at any time, with or without notice, for any reason, including breach of these Terms, suspected fraud, or required compliance action. Upon termination:

- Your right to use the Service ceases immediately
- We may retain your account data per the Data Retention Policy (linked at `/legal/data-retention`)
- Outstanding fees remain payable; pre-paid amounts are non-refundable except at our sole discretion

### 10. Intellectual property

The Service, including its software, models, signals, scores, dashboards, documentation, and all trademarks, is owned by us and our licensors. We grant you a limited, non-exclusive, non-transferable, revocable license to use the Service for your personal account during your active subscription. Outputs (signals, reports, scores) are licensed for your own trading and decision-making use; redistribution requires separate authorization.

### 11. Disclaimers and limitation of liability

The Service is provided "as is" and "as available" without warranties of any kind, express or implied, including merchantability, fitness for a particular purpose, accuracy, or non-infringement.

**To the maximum extent permitted by applicable law:**

- We are not liable for any trading losses, missed gains, opportunity cost, or consequential damages arising from your use of the Service
- We are not liable for downtime, latency, vendor outages, exchange outages, model errors, or signal inaccuracies
- Our aggregate liability for any claim is capped at the lesser of (a) the fees you paid us in the twelve months preceding the claim, or (b) USD 1,000

Some jurisdictions do not allow exclusions of certain warranties or limitations of certain damages; in such jurisdictions our liability is limited to the maximum extent permitted by law.

### 12. Indemnification

You agree to indemnify and hold us, our officers, directors, employees, and agents harmless from any claim, loss, liability, expense, or demand (including reasonable attorneys' fees) arising from your use of the Service, your breach of these Terms, or your violation of any law or third-party right.

### 13. Governing law and dispute resolution

These Terms are governed by the laws of **[jurisdiction — TBD]** without regard to conflict-of-laws principles. Any dispute will be resolved by **[binding arbitration / courts of jurisdiction — TBD]**. You waive any right to participate in a class action against us.

### 14. Changes to these Terms

We may update these Terms at any time. Material changes will be announced by email and require re-acceptance before continued use. The current version is always available at `coinscope.ai/legal/terms`.

### 15. Contact

Legal inquiries: **[legal@coinscope.ai — TBD]**
General contact: see `coinscope.ai/contact`

---

## Part 2 — Risk Disclosures

### Required acknowledgment

By accepting these Terms you acknowledge that you have read, understood, and accept the following risks. Trading cryptocurrency derivatives is highly speculative and may not be suitable for every investor. **You may lose some or all of your invested capital, and you may incur losses exceeding your initial deposit when using leveraged products.**

### A. Market risk

Cryptocurrency markets are extremely volatile. Price movements of 10% or more in a single hour are common. Liquidity can disappear in stressed markets, leading to rapid drawdowns and potential liquidation of leveraged positions. The market can move against you faster than the Service or any human operator can react.

### B. Leverage risk

If your subscription tier permits leveraged trading, you understand that leverage magnifies both gains and losses. A small adverse price movement can result in the total loss of margin and, on some exchanges and instruments, additional liabilities. The Service enforces internal leverage caps, but those caps do not eliminate the underlying risk; they only bound it.

### C. Technology risk

The Service depends on networks, servers, third-party APIs, exchanges, and software. Any of these may fail, be delayed, be hacked, or behave unexpectedly. Specific failure modes you accept include but are not limited to:

- WebSocket disconnections producing stale data
- Exchange API outages preventing order placement, modification, or cancellation
- Order rejections, partial fills, fills at unexpected prices
- Slippage between signaled and executed price
- Latency-induced missed entries or exits
- Software bugs producing incorrect signals or sizing
- Dependency-vendor outages (CCXT, CoinGlass, Tradefeeds, CoinGecko, Anthropic / Claude API)

### D. Model risk

The Service's signals and scores are produced by machine-learning and rule-based models. Models can be wrong. Specific model risks you accept:

- Overfitting to historical patterns that do not recur
- Regime shifts (the model was trained on a market that no longer exists)
- Data drift (input distributions change over time)
- Latent feature failures (a vendor changes a field; the model degrades silently)
- LLM tool outputs (sentiment, news context) being inaccurate or hallucinated

The Service applies an architectural boundary (ADR-004) ensuring large-language-model outputs do not directly cause orders. This reduces but does not eliminate model risk.

### E. Operational risk

The Service is operated by a small team. Risks you accept:

- Single points of failure in deployment (single VPS region during validation)
- Limited 24/7 coverage; alerts may be delayed during off-hours
- Human error in deployment, configuration, or incident response

### F. Counterparty and exchange risk

When the Service connects to an exchange to place orders on your behalf, you bear all counterparty risk associated with that exchange, including but not limited to: insolvency, withdrawal freezes, hacking, exchange-side errors, regulatory action against the exchange, and changes to the exchange's terms or fee structure. We are not the custodian of your funds.

### G. Regulatory risk

Cryptocurrency regulation is evolving in every jurisdiction. New laws or interpretations may make some or all uses of the Service illegal in your jurisdiction without notice. You are responsible for compliance with the laws applicable to you. We may be required to suspend or terminate service to specific jurisdictions or users at any time.

### H. Tax risk

Trading activity, gains, losses, and even the receipt of in-kind tokens may have tax consequences in your jurisdiction. **The Service does not provide tax advice.** You are solely responsible for tracking your trading activity, computing your tax liability, and filing accurately.

### I. Custody and key risk

If you provide exchange API keys, you remain solely responsible for those credentials and for the security of the exchange accounts they grant access to. We recommend never granting withdrawal scope to any third party, including us.

### J. No guarantee

**Nothing in the Service is a guarantee of profit, accuracy, or availability.** Even when all systems function correctly, market conditions can produce losses. Even when historical performance has been favorable, future performance can be unfavorable.

---

## Acceptance

By clicking "I accept" during signup, you acknowledge that you have read these Terms and Risk Disclosures in full, understand them, and agree to be bound by them. Your acceptance is recorded by the Service with a timestamp, version number, and IP address as evidence of agreement.

If you cannot accept these terms, do not use the Service.

---

**Document control**

- Version: 0.1 (draft)
- Drafted: 2026-04-29
- Status: PRE-COUNSEL — internal only — do not publish
- Companion: COI-60 (signed-acceptance gate), COI-63 (public /legal page), COI-64 (audit log retention)
- File: `/CoinScopeAI/legal/tos-and-disclosures-DRAFT.md`
