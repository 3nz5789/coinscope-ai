# CoinScopeAI — Risk Disclosure (Founder Draft v0)

**Status:** Founder draft for counsel review and revision.
**Author:** Mohammed (Founder), with Strategy Chief of Staff (Scoopy).
**Date drafted:** 2026-05-01.
**Audience:** This draft is for engaged counsel. It is **not** ready for user click-through. Sections marked **[COUNSEL]** are explicitly counsel territory.
**Voice goal:** Plain language. The user must finish reading this and *understand* the risk, not just nod through it.

---

## 0. Document Purpose

When you sign up for CoinScopeAI, you will see this disclosure and be asked to accept it. You cannot use the product without accepting it.

Please read it carefully. **Trading crypto futures can lose all of your money.** This disclosure explains why, and what CoinScopeAI does and does not do to help.

---

## 1. The Short Version (Read This Even If You Skip Everything Else)

- **You can lose all of your money trading crypto futures.** Sometimes very fast.
- **CoinScopeAI is an information service, not a broker, not a fund manager, and not your financial adviser.** We provide signals, dashboards, regime detection, and a risk-policy framework. We do not place trades on your behalf today, we do not hold your money, and we do not assess whether trading is suitable for you personally.
- **Real-capital trading through CoinScopeAI is currently disabled.** The engine runs on Binance Futures Testnet only. There is a structural lock on real-capital execution (we call it the "§8 gate"), and it is not unlocked.
- **If and when real-capital trading is enabled in the future,** you will see a separate, more detailed disclosure and consent flow. This document does not authorize real-capital trading.
- **Past performance — including testnet performance, paper-trading results, and any numbers shown on `trust.coinscope.ai` — does not predict future results.**
- **Our capital-preservation policy is a policy, not a promise.** It describes how the engine *attempts* to manage exposure. It does not promise you will not lose money.
- **By accepting this disclosure, you confirm that you understand these risks** and that you alone are responsible for your trading decisions, your exchange account, and your taxes.

---

## 2. What CoinScopeAI Is

CoinScopeAI is a **subscription software product** that:

- Runs an automated engine that analyzes crypto futures markets across multiple exchanges and produces trading signals with a confluence score.
- Classifies the current market regime as Trending, Mean-Reverting, Volatile, or Quiet.
- Applies a documented risk-policy framework (drawdown limits, leverage caps, position-heat ceiling) to decide whether a signal is allowed to result in a trade in the engine's *paper-trading* environment.
- Publishes a methodology page describing how the engine works.
- Publishes performance snapshots from the engine's paper-trading activity on a public Trust dashboard (`trust.coinscope.ai`), with cryptographic signatures that allow third parties to verify the snapshot has not been altered.
- Provides a dashboard, a Telegram bot, and an API for paying subscribers.

**That is what CoinScopeAI is.** What follows is what it is *not*.

---

## 3. What CoinScopeAI Is Not

- **CoinScopeAI is not your investment adviser.** We do not assess your financial situation, your risk tolerance, your investment objectives, or whether trading crypto futures is suitable for you. Nothing on the platform — including signals, regime classifications, methodology pages, or performance snapshots — is a personal recommendation to you.
- **CoinScopeAI is not a broker or exchange.** We do not match orders. We do not custody your assets. We do not transmit your money.
- **CoinScopeAI does not currently execute real trades on your behalf.** The engine runs on Binance Futures Testnet only. Even if you connect a real exchange API key in the future, real-capital trading is structurally locked behind a gate we call the §8 gate, which is not currently open.
- **CoinScopeAI is not a guarantee, a forecast, or a prediction.** Signals are software outputs based on historical patterns and current market data. They can be wrong. They have been wrong. They will be wrong again.
- **CoinScopeAI does not provide tax, legal, or regulatory advice.** You are responsible for your own tax obligations and your own compliance with the laws of your jurisdiction.

---

## 4. Risks of Trading Crypto Futures (In General, Not Specific to CoinScopeAI)

Crypto futures are among the highest-risk financial instruments available to retail traders. The following risks apply to **any** crypto futures trading, whether or not you use CoinScopeAI:

### 4.1 Total loss is possible.
Leverage amplifies both gains and losses. A small adverse price move can liquidate a leveraged position entirely. You can lose more than your initial position margin in some scenarios, depending on the exchange's margining rules.

### 4.2 Volatility.
Crypto markets can move 10% or more in minutes. Liquidations can cascade. Slippage and execution gaps are common during fast markets.

### 4.3 Funding rates.
Perpetual futures charge or pay a funding rate. Holding a position for a long time can result in significant funding costs that erode profitability even on correct directional calls.

### 4.4 Counterparty / exchange risk.
The exchange you trade on (e.g., Binance) can be hacked, halted, regulated, geographically blocked, or otherwise impaired. Your funds on an exchange are not protected the way bank deposits are protected.

### 4.5 Regulatory risk.
Crypto regulation is evolving in every jurisdiction. Rules in your jurisdiction may change. Activities that are legal today may not be legal in the future.

### 4.6 Custody and key risk.
You are responsible for the API keys you connect to your exchange. Theft, loss, or compromise of your keys is your responsibility, not ours.

### 4.7 Tax complexity.
Crypto futures gains and losses can produce complex tax situations. Reporting obligations vary widely by jurisdiction. We do not advise on or report your tax situation.

---

## 5. Risks Specific to Using CoinScopeAI

Using CoinScopeAI introduces additional risks that are specific to relying on a software product for market intelligence.

### 5.1 Signal accuracy is not guaranteed.
Signals are produced by an ML-driven engine based on historical patterns and current data. The engine has been wrong before and will be wrong again. We do not promise any specific accuracy rate, win rate, profit factor, or risk-adjusted return.

### 5.2 Past results do not predict future results.
Any performance numbers, statistics, or charts shown on the platform — including the Trust dashboard at `trust.coinscope.ai` — describe what the engine has done in the past, in paper-trading on testnet conditions. They do not predict what the engine will do in the future. They especially do not predict what will happen with real capital under live execution conditions.

### 5.3 Testnet results differ from mainnet.
Until the §8 gate is unlocked, the engine operates exclusively on Binance Futures Testnet. Testnet liquidity, slippage, latency, and funding-rate behavior **differ from mainnet** in ways that can favorably bias paper-trading performance. Real-money performance can be materially worse.

### 5.4 Software and operational risks.
The engine, dashboard, Telegram bot, and supporting infrastructure can fail, be slow, return stale data, or be unavailable. Signals can be missed or delayed. The kill switch can fail. We attempt to operate to documented reliability targets but do not guarantee uptime.

### 5.5 Vendor / data-provider risk.
The engine depends on third-party data and infrastructure: Binance for market data, CoinGlass for derivatives data, Tradefeeds for news data, CoinGecko for token data, Anthropic for limited natural-language enrichment, Stripe for billing, our hosting provider, and others. **Any of these providers can fail, change behavior, or be unavailable.** Data you see may be stale, partial, or incorrect because of a vendor issue we have not yet detected.

### 5.6 Methodology disclosure is not a complete specification.
The methodology page on the website describes how the engine works in good faith. It is **not** a complete specification, and the engine evolves over time. Material changes will be reflected in the methodology page, but day-to-day model retraining and parameter adjustments may occur without separate notice.

### 5.7 Risks of relying on automated signals.
Automated signal services can produce a false sense of security or expertise. **You can lose money following good-faith, well-reasoned signals.** No signal — ours or anyone else's — should substitute for your own judgment, your own risk tolerance, and your own decision to participate in any given trade.

---

## 6. Our Capital-Preservation Policy — What It Is and What It Isn't

CoinScopeAI is built around an explicit principle: **capital preservation first, profit generation second.** This is reflected in a documented risk-policy framework that the engine enforces:

- **Maximum drawdown:** the engine attempts to halt new entries if cumulative drawdown reaches **10%** of starting equity.
- **Daily loss limit:** the engine attempts to halt new entries on any day where net loss reaches **5%** of equity.
- **Leverage cap:** the engine restricts effective leverage to a maximum of **10x**.
- **Concurrent position limit:** the engine restricts open positions to a maximum of **3 at any one time**.
- **Position heat cap:** the engine declines entries where the position-heat score exceeds **80%**.
- **Kill switch:** a manual or automatic mechanism that halts new entries entirely.

**This is policy, not promise.** It describes how the engine *attempts* to manage exposure. It does **not** promise:

- That you will not lose money.
- That the policy will operate without failure.
- That the engine will not, due to a bug or a vendor issue, exceed any of these limits.
- That these limits are appropriate for your personal financial situation.

If real-capital trading is enabled in the future and the engine breaches one of these limits, you may suffer losses larger than the policy contemplates.

---

## 7. The §8 Gate (Real-Capital Trading Is Currently Locked)

CoinScopeAI's architecture includes a structural lock — the "§8 gate" — between the engine and real-capital execution. **The gate is currently locked.** No real-capital trade has been or will be placed through the platform until:

- Documented engine readiness criteria are met.
- An external risk reviewer has signed off on the engine's risk path.
- A separate counsel memo on the regulatory implications of real-capital trading has been completed.
- A capped, founder-only Phase 1 has run for the documented minimum duration.

**You are not authorizing real-capital trading by accepting this disclosure.** If and when real-capital trading is enabled, you will see a separate, more detailed disclosure and consent flow that you must accept before any real-capital trade can occur on your behalf.

If you connect a real exchange API key to the platform today, the engine **will not** use it to place real trades. Real-capital execution is structurally disabled, not just by policy.

---

## 8. Your Responsibilities

By using CoinScopeAI, you confirm that you alone are responsible for:

- **Your trading decisions.** Whether to act on any signal, ignore any signal, or trade entirely independent of any signal.
- **Your exchange account.** Account security, API key management, withdrawal addresses, and so on.
- **Your funds.** CoinScopeAI does not custody your funds at any point.
- **Your tax obligations.** Reporting and payment in your jurisdiction.
- **Your legal compliance.** Whether using a crypto futures intelligence service is permitted in your jurisdiction.
- **Your own assessment of suitability.** Whether crypto futures trading is appropriate for your financial situation, risk tolerance, and goals.

If you are not willing or able to accept these responsibilities, **you should not use CoinScopeAI.**

---

## 9. Who Should Not Use CoinScopeAI

You should not use CoinScopeAI if any of the following are true for you:

- You are under 18 years old.
- You cannot afford to lose the capital you intend to deploy in crypto futures trading.
- You are looking for a guaranteed return, a low-risk savings product, or a substitute for professional financial advice.
- You are a person ordinarily resident in a jurisdiction we have identified as restricted at signup. (We currently restrict signup from US persons; the up-to-date list is shown at signup.)
- You are obligated by your employer or by a regulator to seek pre-clearance before engaging in personal trading and have not done so.
- You expect us to make trading decisions for you.

---

## 10. No Advisory Relationship

By using CoinScopeAI, you acknowledge:

- We have **no fiduciary duty** to you.
- We are **not your financial adviser**, broker-dealer, investment manager, fund manager, or commodities trading adviser.
- Nothing on the platform — including signals, regime classifications, methodology, dashboards, performance snapshots, Telegram messages, or email communications — constitutes personalized investment advice.
- You will not represent to anyone — including any regulator, court, or third party — that CoinScopeAI is your investment adviser or that signals from CoinScopeAI are personalized recommendations.

---

## 11. No Guarantees

We do not guarantee:

- The accuracy, completeness, or timeliness of any signal, regime classification, or other data.
- The availability or uptime of the platform, the dashboard, the API, or the Telegram bot.
- The continued availability of any vendor or data source.
- The continued operation of the platform.
- Any specific performance, profit, return, drawdown profile, or other outcome.
- That past behavior of the engine will be replicated in the future.

---

## 12. Limitation of Liability

**[COUNSEL: standard limitation-of-liability clause, calibrated to the engagement entity's jurisdiction. Intended cap: greater of fees paid in the prior 12 months or USD $100. Carve-outs as required by applicable law (gross negligence, willful misconduct, fraud, etc.). Consider whether to align with the limitation in the ToS or to keep this disclosure-specific.]**

---

## 13. Indemnification

**[COUNSEL: indemnification provision for user misuse, third-party claims arising from user trading activity, user breach of this disclosure, etc. Consider whether to consolidate with the ToS indemnification or to keep this disclosure-specific.]**

---

## 14. Governing Law and Dispute Resolution

**[COUNSEL: governing law, venue, and dispute-resolution mechanism. Decision pending entity formation.]**

---

## 15. Changes to This Disclosure

We may update this disclosure as the product evolves, regulatory expectations change, or material new risks emerge. If we make a material change, you will be required to re-accept the updated disclosure before continuing to use the platform.

A version history of this disclosure is published at **[COUNSEL: insert URL once decided — recommend `coinscope.ai/legal/risk-disclosure/history` or similar].**

---

## 16. Revoking Your Acceptance

You may revoke your acceptance of this disclosure at any time by closing your account. Closing your account terminates your subscription and your access to the platform. Some data retention obligations (such as the 7-year trade-journal retention) will continue to apply even after account closure, as described in the Privacy Policy.

---

## 17. Acknowledgment

**By clicking "I accept," you confirm:**

1. You have read this Risk Disclosure in full.
2. You understand the risks described in §4 and §5.
3. You understand that CoinScopeAI is an information service and not your investment adviser, broker, or fund manager.
4. You understand that real-capital trading through CoinScopeAI is currently disabled, and that accepting this disclosure does not authorize real-capital trading.
5. You understand that past performance — including any performance shown on the Trust dashboard — does not predict future results.
6. You understand that the capital-preservation policy is a policy, not a promise.
7. You accept sole responsibility for your trading decisions, your exchange account, your funds, your taxes, and your legal compliance.
8. You are not a person identified in §9 as someone who should not use CoinScopeAI.

If you cannot confirm any of the above, **do not click "I accept." Close this page. Do not use CoinScopeAI.**

---

## Version Notes

- v0 (2026-05-01) — Founder draft for counsel review.

---

## Drafter's Note to Counsel

A few things worth flagging about this draft:

- **The plain-language priority is intentional.** The first thing the user reads (§1) is the entire disclosure compressed into bullet points. The detailed sections expand each point. This reflects research that users simply do not read long legal documents; if the most important information is buried, it is functionally invisible.
- **The §8 gate language (§7) is core to the brand promise.** Please preserve the structural-lock framing rather than softening it to a policy claim. The architecture genuinely enforces it.
- **The Trust dashboard mention (§5.2) is deliberate.** Counsel may want to expand this section into a separate "what `trust.coinscope.ai` is and is not" call-out, given regulatory sensitivity around publishing trading performance.
- **Sections 12, 13, 14 are explicitly counsel territory.** I have not attempted to draft them; the placeholders identify the substance to cover.
- **The "Who should not use" list (§9) is intentionally direct.** I'd recommend keeping it that way rather than softening to "consult a professional before using." The brand position is capital-preservation; the disclosure should be allowed to refuse the wrong user.
- **Click-through design** is a separate question from disclosure content. Recommend scroll-to-accept (deliberate scroll required before button enables) rather than a bundled checkbox at signup. That design decision should be made jointly with counsel.
- **Versioning and re-acceptance flow** (§15) is a product question as much as a legal one. The current architecture supports it (per the v5 Customer Layer); please confirm what the trigger threshold for re-acceptance should be (any change vs. material change vs. specific-section change).
