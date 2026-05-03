# §3 ICP and Customer Segmentation

**Status:** v1 LOCKED. Sub-persona cards (Re-cut E), anti-personas, segment matrix, interview plan, and soft-cohort validation strategy all committed. Cards remain inference-labeled until §3.7 + §3.8 empirical data publishes v1.1. Downstream sections (§4, §5, §6, §7, §9, §11, §15) proceed against v1.
**Last updated:** 2026-05-01
**Disclaimer:** Inference-based personas. Each card is labeled as inference until soft-cohort data validates or refines it.

---

## 3.0 Assumptions

- **Locked primary ICP** (per `_decisions/decision-log.md`, 2026-05-01): disciplined retail futures trader, $5k–$250k account, MENA + global EN, self-directed.
- **Locked secondary persona:** prop-firm-funded traders (served, not led with).
- **Locked anti-ICP:** US-resident retail, sub-$5k accounts, copy-traders / signal-group buyers, fund LPs.
- **Cut axis (re-cut E):** *origin and motivation* for Personas 1 and 2; *scale and book complexity* for Persona 3. The mixed axis is intentional and explained in §3.1.

### Documented concerns (carried forward from re-cut review)

- **TAM breadth on Persona 1.** The Self-Taught Methodist may be a flattering archetype that under-counts disciplined-by-habit traders (disciplined through experience and pattern recognition rather than deliberate study). §3.7 interview plan must surface unprompted whether discipline-by-habit is a meaningful adjacent segment. If yes, broaden Persona 1's origin definition rather than adding a fourth persona.
- **Possible fourth archetype — disciplined intuitive trader.** Same caveat as above; tracked here so §3.7 explicitly tests for it.
- **Persona 3 regulatory line.** Inherited by §12 risk register: Solo PM operating an informal partner book sits in a fuzzy regulatory zone in many jurisdictions. CoinScopeAI does not advise on fund formation; Desk-tier marketing copy must not position the product as a fund-formation alternative.
- **Persona 2 buy-vs-build pricing constraint.** Inherited by §6 pricing: Trader-tier price must compete with "six months of personal build time" because the Engineer Trader is doing the math.

---

## 3.1 Why three sub-personas, why this re-cut

The first cut (Burned Survivor / Engineer Trader / Aspiring Pro) had two structural weaknesses: Persona 1 was cycle-dependent (anchored on 2021–2022 trauma), and Persona 3 overlapped with the locked secondary persona (prop-firm-funded). Re-cut E corrects both:

- **Persona 1 → The Self-Taught Methodist.** Disciplined from the start through deliberate study, not from recovery. Less cycle-fragile, larger TAM, durable across bull and bear legs.
- **Persona 2 → The Engineer Trader.** Unchanged. Still the strongest persona of the three, cleanly mapped to Force 2.
- **Persona 3 → The Solo PM.** Manages own capital plus a small partner/family book ($200k–$1M aggregate). Sits at the top of the self-serve ceiling and creates a natural Trader → Desk progression story for §5. Distinct from the secondary persona (Solo PM is *not* prop-firm-funded; they manage close-circle capital).

The cut axis is now mixed — origin/motivation for Personas 1 and 2, scale/book-complexity for Persona 3. This is **intentional**: Persona 3's defining feature is that they are **already disciplined** (so origin doesn't discriminate them) but they operate at a scale and complexity that creates fundamentally different feature priorities (multi-account, reporting, seats). Forcing them onto the origin axis would produce a card that reads as "Methodist with a bigger account" — collapsing the distinction.

Force-to-persona alignment under Re-cut E:

- Persona 1 ↔ Force 1 (demand shift) — the durable version, not the recovery-trauma version.
- Persona 2 ↔ Force 2 (AI cost-collapse) — unchanged.
- Persona 3 ↔ Force 1 + Force 3 — split alignment; Solo PMs are themselves Force-1 evidence and disproportionately MENA-resident, anchoring Force 3.

The 1↔1, 2↔2, 3↔3 mapping the original cut produced is gone. We trade clean §15 arithmetic for sharper persona distinctions.

---

## 3.2 Sub-persona cards

Each card: identity, origin, job-to-be-done, pains, triggers, channels, objections, feature priorities, anti-fit signals, force alignment.

---

### Persona 1 — The Self-Taught Methodist (working name: "Omar")

**One-line summary.** Built discipline through deliberate study before they ever placed a leveraged trade, and treats trading as a craft with a written plan.

**Identity.** Age range 28–50. Account $20k–$150k typical. Often a professional or self-employed background — lawyer, doctor, business owner, mid-level engineer, consultant. Not necessarily a coder. Owns the canon: Van Tharp's *Trade Your Way to Financial Freedom*, Schwager's *Market Wizards* series, position-sizing literature, possibly Ed Seykota's commentary. Has a written trading plan they have actually followed for 12+ months. Predominantly MENA + global EN.

**Origin.** Approached trading the way they'd approach any serious skill — by reading the canon first, then placing small trades, then sizing up only after the methodology proved out on their own track record. Internalized risk-of-ruin math and expected value before they internalized chart patterns. Discipline is not earned through a recovery story; it is *preparation*. May or may not have taken losses; the rules don't bend either way.

**Job-to-be-done (verbatim flavor).** *"I have my system. What I need is the infrastructure to execute it without lapses. Show me a tool that respects my framework instead of trying to replace it. Help me automate the gating I already do by hand. And if your math is wrong, I will notice."*

**Pains in current setup.**

- Manual gating is tiring and error-prone at edge cases (multiple positions, after-hours setups, news-driven volatility).
- Journal lives in spreadsheets or Notion; performance attribution is painful.
- Already trusts their own methodology — suspicious of products that try to override it rather than augment it.
- Plenty of products exist for chart-pattern traders; few exist for *risk-first methodology* traders. Feels underserved.

**Buying triggers.**

- A peer in a methodology-focused closed community recommends.
- A long-form explainer that demonstrates the product's authors actually understand position-sizing math (not marketing copy *about* it).
- An inflection point in account size where manual processes break — typically ~$50k across multiple positions.
- A drawdown they handled correctly that nonetheless cost them sleep, prompting "I should automate this."

**Channels.**

- Substack — Quantian, Of Dollars And Data, applied-methodology crypto writers.
- Twitter quant-adjacent corners — applied rather than pure-code.
- Books and reading lists — Edgewonk content, prop-trading reading lists.
- Closed Discord/Telegram methodology cliques — smaller, more invitation-driven than survivor groups.
- Podcasts on systematic discretionary trading.

**Objections.**

- "Will your gates conflict with my own rules?" (concern about override, not enforcement.)
- "Can I customize the thresholds?"
- "Do I have to use your full system or can I bring my own framework?"
- "Have you actually read [Van Tharp / Schwager / Tharp's R-multiples]?"

**Feature priorities** (in order).

1. Configurable gates that respect the user's own thresholds, not just CoinScope defaults.
2. Performance journal with rule-violation tagging and R-multiple reporting.
3. Position-sizing math transparency — show the formula, the inputs, the output.
4. Ability to backtest user-defined rules against historical data.

**Anti-fit signals.** If they reject any external constraint and want a tool that does only what they tell it to, they're a solo operator — not our buyer. If they ask "what should I trade today" rather than "how do I size what I'm already trading," they're not Persona 1.

**Force alignment.** Force 1 (demand shift) — the durable version. Persona 1 is evidence that the disciplined-trader preference is a settled preference, not a cycle artifact.

---

### Persona 2 — The Engineer Trader (working name: "Karim")

**One-line summary.** Works in tech/data/quant-adjacent roles by day, treats trading as a system to optimize, and evaluates products by methodology not vibes.

**Identity.** Age range 25–42. Account $50k–$200k typical. Day-job in software, data, fintech, or trading-adjacent engineering. Reads documentation. May have built their own backtest framework in Python; may have looked at QuantConnect, Hummingbot, or vectorbt and decided not to invest the time. Geographically dispersed across MENA + global EN.

**Origin.** Did not necessarily lose in 2021–2022. Came to crypto-perp through the engineering angle: "this market has structure, I want to model it." Treats trading as an extension of professional work. Discipline is native, not earned.

**Job-to-be-done (verbatim flavor).** *"Show me your methodology. If your regime classifier is real, I want to see how it's labeled, what the inputs are, what the false-positive rate looks like. I don't need a black box. I need a framework I can stress-test, plug into my own workflow, and trust because the math holds, not because the marketing copy says so."*

**Pains in current setup.**

- Built or considered building their own system, and it's been six months without finishing.
- Off-the-shelf tools insult their intelligence (signal groups) or hide their math (proprietary terminals).
- Wants API access and is annoyed when products gatekeep it.
- TradingView is fine for charting but doesn't handle execution, gating, or regime classification.

**Buying triggers.** A technically credible explainer of how the engine works. Open documentation. A peer engineer recommending. The realization that "I will not finish my own system in time for this cycle."

**Channels.** X/Twitter quant subculture. Substack and Read.cv. GitHub. Specific YouTube creators who explain methodology rather than show charts. LinkedIn for B2B-ish credibility cues. Reddit `r/algotrading`. Discord communities organized around code, not signals.

**Objections.**

- "Is your engine open or proprietary? Can I see how regime is labeled?"
- "What's the latency? Data cleanliness? Slippage model?"
- "Why should I pay for this when I could build it?"

**Feature priorities** (in order).

1. Engine methodology documentation — regime classifier inputs, gate logic, position-sizer math.
2. API access and programmatic integration.
3. Backtesting transparency — show me the cohort, not just the winners.
4. Regime label depth and confidence scores (not just colors).

**Anti-fit signals.** If they want signals delivered "ready to trade" with no explanation, not Persona 2. If they ask about copy-trade, not Persona 2.

**Force alignment.** Force 2 (AI cost-collapse). Persona 2 is the buyer who validates that we built credibly with a small team.

---

### Persona 3 — The Solo PM (working name: "Layla")

**One-line summary.** Manages own capital plus a close-circle book — 2–5 partners or family — at $200k–$1M aggregate. Presents and onboards as retail; operates like a micro-fund.

**Identity.** Age range 32–50. Aggregate book $200k–$1M (own + partners). Individual account at the top of the self-serve ceiling. Comes from a successful business background, earlier crypto wealth, real estate, or a high-paying career. May have a partnership agreement with friends/family — informal LP-style obligations: annual reports, periodic meetings, expectations of transparency. MENA-heavy; UAE/GCC over-indexed in this persona.

**Origin.** Built capital through business or earlier crypto/equity positions. Now manages own + close-circle money because trusted peers asked. Operates at a scale where Excel-plus-screenshots is breaking, but the formal-fund structure (regulatory, operational, GP/LP) is too heavy. Wants the *infrastructure* of a fund without the *overhead* of one — at least for now.

**Job-to-be-done (verbatim flavor).** *"I'm running a small book for myself and a few people who trust me. I need tools that produce reports my partners can read, risk metrics that justify my decisions, and an audit trail when I have to explain a drawdown. I'm already disciplined. I need infrastructure that scales with me — and the option to graduate from it cleanly if I ever go full fund."*

**Pains in current setup.**

- Excel + manual aggregation breaks past 2–3 accounts.
- Partners ask for monthly performance reports; cobbled together each time.
- No clean separation between "what I traded" and "what we did" in the data.
- Operationally lonely — most peers at this scale have either retreated to retail-only or gone proper-fund. The middle is unserved.
- Trust accountability is high — drawdown is *someone else's* money.

**Buying triggers.**

- The aggregate book hits a complexity threshold (~$300k+ multi-account) where manual reporting fails outright.
- A partner explicitly asks for monthly reporting.
- A drawdown event forces an articulated risk-framework conversation with partners.
- Considering a proper fund structure in 12–24 months and wanting to "act like one" first.

**Channels.**

- LinkedIn — B2B-ish credibility cues for the Solo-PM identity.
- Closed founder/operator networks — Telegram/WhatsApp groups for entrepreneurs.
- MENA family-office and HNW-adjacent introductions — high-trust, low-volume.
- Regional events — Token2049, Dubai Fintech Summit, regional alpha events.
- Substack creators who write about emerging-fund operators and small-PM ops.
- Less reliance on Twitter; more on closed referral networks.

**Objections.**

- "Do you have a Desk tier, or do I need to use Trader?"
- "Can I add seats for my partners or analyst?"
- "What's the audit log? What's the exportability for tax reporting?"
- "Is this regulated where I'm operating?" — UAE/GCC tax and reporting questions.
- "Can my partners get a read-only view?"

**Feature priorities** (in order).

1. Multi-account aggregation and reporting.
2. Audit-grade journaling and exportable performance reports.
3. Configurable gates that match LP-style commitments ("no leverage above Xx until cohort drawdown <Y").
4. Seats / role-based access for partners or analysts.
5. Tax-ready exports and structured period reporting.

**Anti-fit signals.** If they're a *true* fund — regulated, GP/LP structure, files with regulators — they're out of our serviceable market for v1. If they're solo with no partners, they may be a high-account Persona 1 or 2, not Persona 3.

**Force alignment.** Force 1 (demand shift, durable form) + Force 3 (MENA hub). Split alignment is intentional — Solo PMs are Force-1 evidence at scale and disproportionately MENA-resident, anchoring both pulls.

---

## 3.3 Cross-persona observations

- **Account size separates Persona 3 from 1 and 2.** Persona 3 is structurally larger and operates a *book*, not an account. Personas 1 and 2 overlap heavily on account size ($20k–$200k); they are distinguished by *how they evaluate* a product, not how much they have.
- **All three reject signal-group buying.** That commonality is the locked anti-ICP boundary.
- **Channel mix differs sharply.** Persona 1 lives in methodology-focused Substack and closed Discord/Telegram. Persona 2 lives in X quant subculture and GitHub-adjacent communities. Persona 3 lives in LinkedIn, closed founder networks, and regional events. §7 channel strategy must allocate against this mix, not pick a single channel.
- **Willingness-to-pay rises with persona number.** Persona 1 will start at Free or Trader and convert on rule-respect evidence. Persona 2 will jump to Trader and ask for API access (Desk-tier feature). Persona 3 starts at Desk or asks for it on day one.
- **The Trader → Desk progression story comes from Persona 3.** §5 tier matrix can defend a Desk tier specifically because Persona 3 exists and is unserved by Trader tier alone.

---

## 3.4 What this section unlocks

Once the re-cut sub-personas are confirmed, the next pass produces:

- **§3.5 Anti-persona cards** — 2 cards for the locked anti-ICP groups with explicit "what they say, why we're wrong for them" framing.
- **§3.6 Segment matrix** — quantitative scoring across persona × dimensions (size, sophistication, jurisdiction, willingness-to-pay, channel reach).
- **§3.7 Interview / observation plan** — protocol for soft-cohort and external interviews to validate or refine.
- **§3.8 Soft-cohort validation strategy** — how the §14 soft-cohort window doubles as the persona-validation instrument.

---

## 3.5 Anti-persona cards

The locked anti-ICP groups are: US-resident retail, sub-$5k accounts, copy-traders / signal-group buyers, and fund LPs. Two of those carry **active messaging risk** — they may show up in our funnel, share our channels, or mimic our ICP language at first glance. The other two are infrastructure-enforced (US residency at signup) or referent-only (fund LPs are a §15 narrative concern, not a product-funnel concern). The two cards below address the messaging-risk anti-personas. The remaining two get a brief operational note.

---

### Anti-Persona A — The YOLO Gambler

**One-line summary.** Wants alpha, treats leverage as the product, sees risk discipline as friction, and shares a Telegram chair next to our ICP.

**Why they look like ICP at first glance.** They are crypto-perp traders. They're in the same Telegram and X feeds as Personas 1 and 2. They sometimes use the language of discipline ("I'm working on my risk management") without the substance.

**Signature behaviors that disqualify.**

- First-conversation question is "what's the highest leverage I can use" or some variant.
- Frames a losing trade as bad luck rather than a rule violation.
- Stacks signals from multiple groups; can't articulate their own framework.
- Asks how to bypass the gate or override the position heat cap.
- Account often <$5k *and* uses 50x+ leverage — the locked sub-$5k anti-ICP boundary intersects here.

**Why we're wrong for them.** Our risk gate will reject the majority of their setups, the heat cap will block the size they want to take, and the regime label will tell them to wait when they want to enter. They will churn within two weeks and post negative reviews framed as "this product is too restrictive." Every retention metric they touch they degrade.

**What we do.**

- **Marketing copy excludes them by tone.** No "alpha," no "dominate the market," no "10x your account." The product-tier voice does this naturally.
- **Onboarding screens them.** A signup question — "what's your typical leverage range?" — flags >25x as a soft warning with educational content. We do not block, but we set expectations explicitly.
- **First-week behavior surfaces them.** If gate-rejection rate >50% in week 1 paired with repeated override attempts, customer-success follow-up offers a refund and a fit-check.

**Connected anti-ICP groups absorbed by this card:** copy-traders / signal-group buyers (their question is "where do the signals come from"), sub-$5k high-leverage accounts.

---

### Anti-Persona B — The Fund LP / Allocator

**One-line summary.** Wants to invest *in* a fund, mistakes our Solo-PM-tier copy for a fund product, and asks "what are your returns."

**Why they look like ICP at first glance.** They surface in the same MENA family-office and HNW networks as Persona 3 (Solo PM). They speak fluently about allocation, performance reporting, and audit trails. Their language overlaps with Persona 3's — but their *role* is the inverse.

**Signature behaviors that disqualify.**

- First question is "how do I invest" or "what are your returns / track record / AUM."
- Asks for a fact sheet, monthly NAV, or attribution report.
- References "your fund" or "your strategy" rather than "your tool."
- Wants to see a manager bio, not a methodology doc.

**Why we're wrong for them.** We tool managers; we don't manage capital. We do not run pooled investment vehicles, take fiduciary responsibility, or report performance as a fund. Engaging this persona as a customer creates regulatory and expectations risk that pays no upside.

**What we do.**

- **Copy discipline.** Persona 3 / Desk-tier copy must say "infrastructure for the operator," never "fund infrastructure." Avoid "track record" framing; use "tooling" framing. §9 messaging matrix inherits this constraint.
- **Routing.** Inbound LP-style inquiries get a polite redirect: "We don't manage capital. We make the tools the managers use. If you'd like an introduction to operators on our platform, we're not in a position to do that either, but here's a list of professionally licensed funds in your jurisdiction." Decline gracefully.
- **§15 carve-out.** Investor narrative explicitly states we are a software business, not a fund. This avoids both regulatory ambiguity and the worst-case scenario where a venture investor confuses us with a fund-management thesis.

---

### Brief notes on the other two anti-ICP groups

**US-resident retail.** Infrastructure-enforced, not messaging-enforced. Signup geo-block and KYC declaration handle this. No anti-persona card needed because they cannot complete signup. §10 ops runbook owns the technical enforcement.

**Sub-$5k accounts.** Largely absorbed into Anti-Persona A (YOLO Gambler) where leverage is high. The remaining slice — disciplined sub-$5k traders — are a *future* ICP we do not serve in v1 because of unit economics, not because they are wrong-fit. §6 pricing footnote: revisit a sub-$5k tier post-Series-A or once free-tier ARPU economics support it. Keep an explicit "we'll be back for you" stance in marketing copy rather than dismissing them.

---

## 3.6 Segment matrix

Quantitative scoring across the three sub-personas on the dimensions that drive §5 (product), §6 (pricing), §7 (GTM), §11 (financial model), and §15 (investor narrative). Scoring is **L / M / H** with a brief justification per cell. Scores are inference-based and revisited after §3.7 interview data lands.

| Dimension | P1 — Methodist (Omar) | P2 — Engineer (Karim) | P3 — Solo PM (Layla) |
|---|---|---|---|
| **Account size — typical** | $20k–$150k (M) | $50k–$200k (M-H) | $200k–$1M aggregate (H) |
| **Sophistication — methodology** | H — applied | H — technical | H — operational |
| **Sophistication — code/API** | L | H | M |
| **Geo concentration — MENA** | M | M | H |
| **Geo concentration — global EN** | M | H | L-M |
| **Willingness-to-pay** | M | M | H |
| **Channel breadth — paid acquisition viability** | M | H | L (relationship-driven) |
| **Channel breadth — organic content** | H (Substack, books) | H (X, GitHub) | L-M (LinkedIn, closed) |
| **Conversion likelihood** (signup → paid Trader) | M-H (will trial Free first) | M (buy-vs-build math) | H (need is structural) |
| **ARPU potential** | M (Trader tier) | M-H (Trader + API add-on) | H (Desk tier) |
| **Retention expectation** | H — discipline is settled | H — sunk-cost on methodology | H — partner-accountability lock-in |
| **Tier mapping** | Trader | Trader → Desk (power-user) | Desk |
| **Force alignment** | F1 (durable) | F2 | F1 + F3 (split) |
| **Soft-cohort recruitment difficulty** | M | M-L | H (high-trust networks only) |
| **Refund / churn risk** | L (deliberate buyer) | L-M (buy-vs-build regret possible) | L (switching cost is high) |

### Reading the matrix

**Persona 3 wins on ARPU and retention; loses on volume.** The funnel narrows dramatically as you go P1 → P2 → P3 in raw addressable count. §11 financial model should expect P1 + P2 to drive *paid user count* and P3 to drive *revenue per user*.

**Channel allocation falls out of the matrix directly.** §7 GTM:

- Paid acquisition: weight toward P2 (highest paid-acquisition viability).
- Organic content / Substack: weight toward P1.
- Relationship-driven / closed networks: weight toward P3 — this is not a paid-marketing channel, it's a founder-led activity.

**Buy-vs-build risk concentrates on P2.** This is the documented Concern 3 from §3.0. The Trader-tier price must respect that P2 is doing the math.

**Tier strategy is justified by the matrix.** Trader tier serves P1 + the entry-level slice of P2. Desk tier serves P3 + the power-user slice of P2. There is no persona that justifies a lower tier than Trader (sub-$5k is anti-ICP; Free tier is lead-gen, not a buyer-tier).

**Geo split argues for dual-language posture eventually.** P3's MENA concentration combined with P2's global-EN concentration means we maintain English-first for v1 with an Arabic-language layer flagged for post-launch — an option, not a v1 commitment.

---

## 3.7 Interview / observation plan

The persona cards above are inference-based. Before public launch, we run a structured research pass to **validate, refine, or replace** the inferences with real ICP voice. The plan below is the protocol.

### Goals

The research must answer five things:

1. Do the three sub-personas exist as cleanly as drafted? Or are there two, four, or different cuts?
2. Does discipline-by-habit (Concern 1 / Concern 4) appear as a meaningful adjacent segment that should broaden Persona 1's origin, or is the Methodist framing sufficient?
3. Does the Force 1 demand-shift language surface *unprompted* in 30%+ of interviews? (This is the Force 1 kill-trigger from §2.4.)
4. When a MENA respondent is offered both a MENA-founded and a US/EU-founded equivalent, do they default to the latter? (This is the Force 3 kill-trigger from §2.4.)
5. What language do real buyers use to describe their problem? §4 problem/value-prop drafts inherit verbatim quotes.

### Sample size and recruitment

**Target:** 18 interviews total — 6 per persona — over a 21-day window in parallel with the validation phase. Realistic for a solo founder; tight enough to complete before soft launch.

**Recruitment paths per persona:**

- **P1 — Methodist (Omar):** Substack readership of methodology-focused crypto writers, closed methodology Discord/Telegram cliques (request introductions), founder personal network in trading-disciplined circles. Recruit incentive: early access to Trader tier + 1:1 methodology-feedback session.
- **P2 — Engineer (Karim):** X/quant subculture replies, GitHub activity on adjacent OSS quant repos, Substack tech-quant writers, founder personal network in tech. Recruit incentive: API early-access + technical methodology document.
- **P3 — Solo PM (Layla):** Closed founder/operator networks, MENA family-office introductions through trusted intermediaries, regional event attendees (Token2049, Dubai Fintech Summit). Recruit incentive: Desk-tier preview + reporting-template feedback session. **This persona is the hardest to recruit; expect 4 of the 6 to come from the founder's direct network and warm intros.**

### Interview structure

Format: semi-structured, 30–45 minutes, video call, recorded with explicit consent, transcribed.

**Open-ended block (first 15 minutes — do not lead):**

- "Walk me through how you currently trade — what's your week look like."
- "Tell me about the last time you broke your own rules. What happened, what did you do after?"
- "What products or tools have you bought or tried for trading? Which ones did you keep?"
- "If a tool could do exactly one thing for you, what would it be?"
- "How do you think about risk when you're sizing a position?"

**Targeted block (next 15 minutes — explicit testing):**

- Validate Concern 1 / 4: "Some traders learn discipline from books and frameworks. Others learn it from experience and watching the market. Where do you fall?"
- Validate Force 3 kill trigger: "If you had to choose between two tools — one founded in the UAE and one founded in San Francisco, equal features, equal price — what's your gut reaction?"
- Persona-specific feature probe: show 3 mock screens of CoinScopeAI's gate visualization, regime label, and journal. Ask which they'd use, which they wouldn't, and what's missing.

**Wrap-up block (last 5–10 minutes):**

- "What would make you sign up tomorrow vs. wait three months?"
- "What's a price for this where you'd say 'yes' without thinking? Where you'd think hard? Where you'd walk away?"
- "Who else should I talk to?"

### Passive observation channels

In parallel with active interviews, surface real voice from public conversations. **Read-only, no engagement, no scraping.**

- Telegram crypto-trader communities: monitor frequency of discipline-related vs. signal-related conversation.
- X/Twitter: quant-tag and risk-management-tag activity.
- Substack comments on methodology-focused writers.
- Reddit `r/algotrading` and `r/bitcoinmarkets` post-mortem threads.
- LinkedIn posts from MENA-region operator networks.

Track for 30 days. Output: a short observation log in `_data/icp-observations.md` with anonymized verbatim quotes by category.

### Validation criteria — what makes a persona "real"

Each persona is **validated** if:

- ≥4 of 6 interviews self-describe in language consistent with the persona's job-to-be-done block.
- ≥3 of 6 interviews surface the persona's signature objection or pain unprompted.
- ≥2 of 6 say they would pay for the persona's top-3 feature priorities.

Each persona is **refined** if validation fails on one criterion but not all three. The card gets edited; the cuts hold.

Each persona is **replaced** if validation fails on all three criteria. The card is dropped and the §3 cuts are re-evaluated.

### Timing

- **Days 1–5:** recruit and schedule 18 interviews. Set up passive observation logs.
- **Days 6–18:** conduct interviews, transcribe, tag.
- **Days 19–21:** synthesize. Update §3.2 cards from inference to validated. Write §3.6 matrix update with empirical adjustments.
- **Output:** `03-icp-segmentation.md` v1.1 with persona cards labeled "validated" or "refined" and any replacements documented.

This plan runs **in parallel with the validation phase**, not after it. The 21-day window completes inside the existing validation window so §3 v1.1 is ready before the soft-cohort launch gate per §14.

---

## 3.8 Soft-cohort validation strategy

The §14 soft-cohort window (validation pass + 30-day floor, capped at 25–50 paid users) does double duty: it hardens ops and billing, **and** it validates the personas under real-money behavior — something interviews cannot do. This section defines how the cohort is composed, instrumented, and read.

### Composition strategy

**Target cohort mix: 50% P2 / 30% P1 / 20% P3.**

Reasoning, not equal-weighting:

- **P2 over-weighted.** Engineer Traders are the easiest to recruit, the most likely to surface bugs, and the most articulate about engine internals. Cohort hardening benefits most from this profile.
- **P1 mid-weighted.** Methodists are the persona most directly testing Force 1 (the durable demand shift). We need enough of them to read retention signal cleanly.
- **P3 under-weighted.** Solo PMs are the hardest to recruit, have the highest setup cost (multi-account, partner reporting), and are not the right early-adopters to throw at a still-stabilizing product. We deliberately under-recruit them in the soft cohort and ramp them in post-public-launch.

**Cohort cap: 40 users** at the upper end of the §14 25–50 floor. Roughly: 20 P2 + 12 P1 + 8 P3.

**Recruitment source:** primarily the §3.7 interview pool (interviewees who self-elect into paid soft-cohort access), supplemented by founder network warm-intros for any persona shortfall.

### Instrumentation — tagging at signup

At soft-cohort signup, each user is tagged with an inferred persona based on:

- Self-reported account size band.
- Self-reported trading background (free-text, parsed for keywords: "self-taught," "engineer," "partners," "fund," etc.).
- Inferred from referral source (P1 from Substack referrals; P2 from X/GitHub; P3 from founder network).
- **Manual founder review** for the first 40 — automated tagging does not handle ambiguity well at this scale.

The persona tag is **not** customer-facing. It exists in the back-office for cohort analysis only.

### Behavioral signals — what confirms or refutes each persona

| Signal | P1 confirmed if | P2 confirmed if | P3 confirmed if |
|---|---|---|---|
| Gate-rejection acceptance | Acceptance high; few overrides | Acceptance high; engages with gate logic | Acceptance high; configures custom thresholds |
| API usage | Low | High | Medium |
| Multi-account setup | Single account | Often single, occasionally multi | Multi-account from day 1 |
| Journal review frequency | High (weekly+) | Medium-low (data-export pattern) | High (monthly partner-report cadence) |
| Tier upgrade trigger | Slow, deliberate | API access need | Day-1 Desk request or rapid Trader→Desk |
| Support ticket patterns | Methodology questions | Technical and integration questions | Reporting and aggregation questions |
| Retention at day 30 | High | High | High |
| NPS / qualitative feedback | "Respects my framework" | "I can see how it works" | "Makes me look professional" |

**Persona is refuted if** the cohort member's behavior consistently lands in another persona's column — at which point the inference tag is updated, not the user. Aggregate refute-rate per persona becomes a §3 v1.1 input.

### Decision points during the soft cohort

Three explicit checkpoints inside the 30-day soft window:

- **Day 7 — composition review.** Confirm we hit roughly the target mix. If P3 is at zero (likely), do not delay; record as expected.
- **Day 14 — behavioral signal read.** First pass on whether observed behavior matches inferred persona tags. Flag any persona where >50% of cohort members behave outside their tagged column.
- **Day 21 — persona-validation summary.** Combined output of §3.7 interview validation + §3.8 cohort behavior. Updates §3.2 cards from "inference" to "validated / refined / replaced."

### Public-launch readiness from the §3 lens

The soft cohort feeds **one** §14 stop-the-line condition tied to §3 ICP, and contributes **one §13 KPI red-line** that escalates to §14 only if its root cause is structural.

**§14 stop-the-line addition (sixth condition):**

- **Persona invalidation:** if any persona is *replaced* (not just refined) by §3 v1.1, public launch holds until messaging is rewritten and §9 messaging matrix updates. Replacement implies the locked ICP understanding is wrong; launching with mismatched messaging is brand damage that cannot be undone by ordinary monitoring.

**§13 KPI red-line (with conditional §14 escalation):**

- **Cohort gate-rejection acceptance <50%** across all personas. Investigate cause:
    - If cause is gate-threshold tuning, fix and continue — no §14 escalation.
    - If cause is recruiting drift (anti-personas slipping through), re-screen — no §14 escalation.
    - If cause is UX / onboarding, fix and continue — no §14 escalation.
    - **If cause is fundamental ICP mismatch** (the locked ICP does not in fact behave as gate-respecting), escalate to §14 stop-the-line and trigger a §4 problem-statement re-examination.

This split keeps §14 tight (only structural launch-halters) and uses §13 for the metric-driven monitoring that ordinary product iteration should handle.

### What §3.8 unlocks

After §3.7 + §3.8 run their course inside the validation + soft-cohort windows, §3 publishes as v1.1 with:

- Persona cards labeled validated / refined / replaced.
- Matrix updated with empirical scoring where data supports it.
- Anti-personas confirmed against actual signup-funnel behavior.
- Two new §14 stop-the-line conditions added if the cohort triggers fire.

§4 problem/value-prop, §5 product strategy, §7 GTM, and §9 messaging matrix all wait for §3 v1.1 before locking final language.

---

## Open questions for the founder (this pass — §3 v1)

All four prior questions resolved (sub-persona cuts, working names, P3 force alignment, Desk-tier anchor). The remaining v1-pass questions:

1. **Anti-persona cards** — does folding sub-$5k disciplined traders under "we'll be back for you" framing land right, or do you want a sharper exclusion?
2. **Cohort mix (50/30/20)** — comfortable with under-weighting P3 in the soft cohort, or do you want closer-to-even mix at the cost of recruitment difficulty?
3. **Two new §14 stop-the-line conditions** (persona invalidation, cohort gate-rejection <50%) — accept these as additions to the existing §14 conditions?
4. **§3 v1 lock vs. hold for v1.1** — do we lock §3 at v1 now and wait for §3.7 + §3.8 data to publish v1.1, or hold §3 in draft until empirical data lands?
