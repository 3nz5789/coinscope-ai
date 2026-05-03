# §4 Problem Statement and Value Proposition

**Status:** v1 LOCKED. All sections committed: canvases (§4.1), register-handoff (§4.2), problem statement (§4.3), lead value proposition (§4.4), what we do not solve (§4.5), anti-overclaim audit (§4.6). Canvas content remains inference-labeled until §3.7 interview data publishes v1.1; problem statement and lead VP wording is final. Downstream sections (§1, §5, §7, §9, §15) draft against v1.
**Last updated:** 2026-05-01
**Disclaimer:** Canvas content draws on inferred persona JTBDs from §3 v1. Verbatim language from §3.7 interviews will refine §4 to v1.1.

---

## 4.0 Assumptions

- **§3 v1 inputs:** three locked sub-personas (Self-Taught Methodist / Omar, Engineer Trader / Karim, Solo PM / Layla); locked anti-personas; §3.6 segment matrix; §3.2 JTBD verbatim flavor blocks.
- **§2 v0.5 inputs:** three structural forces, capital-preservation-first principle, anti-overclaim discipline.
- **Format:** value-prop canvas (Strategyzer-style) — Jobs / Pains / Gains on the customer side; Products / Pain Relievers / Gain Creators on the value-map side.
- **Constraint:** every claim respects the validation phase. No "production-ready" framing. Capital preservation positioned first; alpha generation second.

---

## 4.1 Value-prop canvases

Each canvas pairs a **customer profile** (what the persona is trying to accomplish, what's painful about doing it now, what good looks like) with a **value map** (what CoinScopeAI offers and how it specifically relieves pains and creates gains).

---

### Canvas A — Persona 1 / The Self-Taught Methodist (Omar)

**Customer profile**

*Jobs*

- **Functional:** Execute a personally-authored trading framework consistently across changing market conditions. Size positions according to position-sizing math. Maintain a journal that captures rule violations. Track performance in R-multiples. Stop trading when their own rules say to stop.
- **Social:** Be the disciplined trader in their methodology-focused community; not the one who blew up.
- **Emotional:** Trust their own framework even after a losing streak. Sleep through drawdown.

*Pains*

- Manual gating is tiring; rules get bent at edges (multi-position, after-hours, news-driven).
- Journal lives in spreadsheets or Notion; performance attribution is laborious.
- Products try to *replace* their framework rather than *augment* it.
- Position-sizing math is correct on paper, sloppy in execution.
- Most "risk management" tools are signal groups in disguise.

*Gains*

- Automated gating that respects their thresholds, not vendor defaults.
- A journal that flags rule violations automatically and tags trades with R-multiples.
- Position-sizing math that runs on every entry without intervention.
- Backtests of their own rules against historical data.
- A product whose authors visibly understand position-sizing literature.

**Value map**

*Products & services CoinScopeAI offers Persona 1*

- Configurable risk gate (user sets thresholds; we enforce them).
- Performance journal with rule-violation tagging and R-multiple reporting.
- Position sizer with transparent math (formula visible, inputs labeled).
- Custom-rule backtester (v3 feature per §5.4 roadmap; v1 ships with engine-default backtests; v2 does not add a custom-rule backtester).

*Pain relievers*

- **Manual gating fatigue → automated configurable gates.** User declares thresholds; the gate enforces. The point is not that we override their judgment; the point is that they don't have to remember at 2 a.m.
- **Spreadsheet journal → structured journal.** Entries auto-populated, rule violations flagged, R-multiples computed. Exports to CSV for users who want to keep their own analysis.
- **Framework override anxiety → framework respect.** Defaults exist, but every threshold is user-configurable. We do not silently apply our values to their book.

*Gain creators*

- **Methodology transparency.** Every gate decision shows its inputs. Every regime label shows its confidence score. Position-sizer math shows the formula and the values that produced the output.
- **Discipline enforcement they trust.** Because the gate runs *their* rules, the enforcement feels like an extension of their framework, not an override.
- **Authors who read the canon.** Documentation cites R-multiples, expectancy, risk of ruin. Persona 1 notices.

**Force alignment.** F1 (durable demand shift). Persona 1 buying signals validate Force 1 directly.

---

### Canvas B — Persona 2 / The Engineer Trader (Karim)

**Customer profile**

*Jobs*

- **Functional:** Run an automated or semi-automated trading workflow. Test hypotheses about market regimes. Integrate trading data with broader engineering work. Validate that a system behaves the way the docs say it does.
- **Social:** Be taken seriously by quant peers; ship a working pipeline rather than another half-finished side project.
- **Emotional:** Avoid the engineer's regret of "I could have built this myself" when paying for a tool.

*Pains*

- Personal build has stalled at 60% for six months.
- Off-the-shelf products either insult intelligence (signal groups) or hide their math (proprietary terminals).
- API access is gatekept behind enterprise pricing on most products.
- Backtest results are presented as cherry-picked best-cases, not full-cohort distributions.
- Regime detection is marketed as a feature without methodology disclosure.

*Gains*

- An engine they can trust *because the math holds*, not because the marketing says so.
- API access at the depth that matters (regime label query, gate evaluation, position-size calculation).
- Backtest transparency including the failures, not just the wins.
- Regime confidence scores numerically, not just colors.
- A way to plug CoinScopeAI into existing tooling without rewriting their workflow.

**Value map**

*Products & services CoinScopeAI offers Persona 2*

- Engine methodology documentation: regime classifier inputs, gate logic, position-sizer math.
- API access (Trader-tier with rate limits; Desk-tier with elevated access).
- Cohort backtest disclosures (full distribution, not selected wins).
- Regime label depth (label + confidence score + inputs).

*Pain relievers*

- **Buy-vs-build regret → buy-vs-build math respected.** Trader-tier price calibrated against six months of personal build time. Documentation good enough that the buy decision is defensible to themselves.
- **Black-box frustration → engine internals exposed.** Methodology docs cover what the regime classifier is, how it labels, what its known false-positive rate is.
- **Cherry-picked backtest skepticism → full-cohort backtest disclosure.** We publish distributions, not just headline numbers.

*Gain creators*

- **API depth that matters.** Programmatic access to the things engineers actually want — gate logic, regime queries, sizing math — not just balance and order endpoints.
- **Confidence scores.** Regime labels carry numeric confidence so the user can model uncertainty in their own pipeline.
- **Workflow integration.** CoinScopeAI fits *into* existing tooling; it does not require replacing it.

**Force alignment.** F2 (AI cost-collapse). Persona 2 buying signals validate that we built credibly with a small team.

---

### Canvas C — Persona 3 / The Solo PM (Layla)

**Customer profile**

*Jobs*

- **Functional:** Manage own + close-circle partner capital ($200k–$1M aggregate). Produce monthly performance reports for partners. Justify risk decisions when a drawdown happens. Maintain audit-grade records. Configure risk parameters that match the obligations they've made to partners.
- **Functional / regulatory:** Maintain regulatory awareness around the line between informal partner-book and fund-registration territory. Use tools that *do not make that exposure worse* — no marketing-as-fund, no implied advisory relationship, no claims that should require a license they don't have.
- **Social:** Look professional to partners, peers in MENA founder/operator networks, and any future fund-formation conversation. Be the operator, not the hobbyist.
- **Emotional:** Sleep through partner-money drawdowns. Have the documentation ready *before* a partner asks. Feel like the infrastructure scales with them.

*Pains*

- Excel + manual aggregation breaks past 2–3 accounts.
- Partner reports are cobbled together each month.
- No clean separation between "what I traded" and "what we did" in the data.
- Operationally lonely — peers at this scale have either retreated to retail-only or gone proper-fund. The middle is unserved.
- Trust accountability is high; drawdown is *someone else's* money.
- Tools either treat them as retail (and break at scale) or as a fund (and require licensure they don't have yet).
- Products marketed *as* fund infrastructure raise the regulatory question they've been carefully avoiding.

*Gains*

- Multi-account aggregation with clean per-partner accounting.
- Audit-grade journaling that exports cleanly to tax and compliance formats.
- Configurable gates that map to partner-level commitments (e.g., "no leverage above 5x while cohort drawdown >5%").
- Role-based access so partners or an analyst can read without write privileges.
- A graduation path — if they ever do go proper-fund, the existing data structure migrates cleanly.

**Value map**

*Products & services CoinScopeAI offers Persona 3*

- Multi-account dashboard with per-account and aggregate views (Desk Preview v1: 3-account cap, view-only; Desk Full v2: full).
- Audit-grade journaling with monthly statement generation (Desk Preview v1: static monthly PDF; Desk Full v2: configurable-period CSV + PDF).
- Role-based seats — PM only at Preview; full PM + partner read-only + analyst at Desk Full v2.

*v3-deferred per §5.4 roadmap (not v1, not v2):*

- LP-style configurable gates (book-level + per-account).
- Tax-ready exports.

*Pain relievers*

- **Excel breaking → multi-account aggregation native.** Per-account isolation, aggregate roll-up, partner-level views.
- **Cobbled partner reports → monthly statements one click away.** Generated from the journal; same data the PM saw all month, in a format the partner can read.
- **Loneliness in the middle → middle-tier infrastructure exists.** Desk tier built specifically for this scale, not a stripped-down fund product or an inflated retail product.

*Gain creators*

- **Professional aesthetics.** Dashboard looks like a desk, not an app. Partners feel the operator is running real infrastructure.
- **Regulatory-conservative positioning.** Product is marketed as ops infrastructure for the operator, never as fund infrastructure. Layla's regulatory posture is not made worse by using us.

*v3-deferred gain creator (per §5.4 roadmap):*

- **LP-style gates.** Risk parameters set against partner commitments and triggered at the book level. Not a v2 capability; revisit at v3 planning.

*Future capability — flagged for v2, not v1*

- **Graduation path to fund formation.** A clean data-structure migration to a regulated fund operating system if Layla decides to go full-fund in 12–24 months. Scoped as a v2 commitment so §4 does not promise migration tooling §5 has not built. §15 narrative may reference this as roadmap, not as v1 deliverable.

**Force alignment.** F1 (durable demand shift, at scale) + F3 (MENA hub — Persona 3 is disproportionately MENA-resident).

---

## 4.2 Cross-canvas observations

- **Capital preservation appears in all three canvases as a *gain*, never as a marketing slogan.** Persona 1 wants discipline enforcement; Persona 2 wants methodology transparency that proves the math; Persona 3 wants book-level risk parameters tied to partner obligations. The same principle, three concrete expressions.
- **The most-shared pain is "tools don't respect what I'm already doing."** Persona 1 has a framework, Persona 2 has a methodology, Persona 3 has a book. All three are skeptical of products that override rather than augment.
- **Each persona's gain creators map to a different §5 tier emphasis.** P1 gains live in Trader. P2 gains span Trader and Desk (API in Desk). P3 gains live primarily in Desk. The tier matrix design must reflect that.
- **No persona's gain creators include "more signals" or "higher leverage."** The locked anti-ICP is reinforced empirically through these canvases — the ICP doesn't ask for what the anti-ICP wants.

### Register handoff to §9 and §15

§4 holds gain-creator language at the **analytical** register — concrete, verifiable, anti-overclaim-clean. This is correct for the customer-profile foundation. Downstream sections inherit content from §4 but operate in different registers and therefore have **broader permission** to expand gain-creator language into more aspirational territory when their context calls for it:

- **§9 GTM hero copy** may translate "methodology transparency" into "the discipline you've built, enforced consistently" — slogan-register acceptable.
- **§15 investor opening** for MENA family-office audience may translate "regulatory-conservative positioning" into "capital preservation as the operating principle" — emotional-resonance register acceptable.
- **§9 messaging matrix** may produce three different copy expressions per persona × stage × pillar combination — broader range acceptable inside the matrix discipline.

Drafters of §9 and §15 should treat §4 canvases as the *truth source* (what we actually do) and reach for the register that matches their context. If a §9 or §15 claim cannot trace back to a §4 canvas pain or gain, it is overclaim by construction and gets flagged in anti-overclaim sweep.

---

## 4.3 Problem statement

> **Disciplined retail and small-fund crypto-perp traders have built their own risk frameworks; the tools they're offered either replace those frameworks or ignore them entirely. Manual discipline breaks at scale, and the cost of failure is account capital.**

The problem is built from three locked inputs:

- **Cross-canvas pain (§4.2):** "tools don't respect what I'm already doing." All three personas are skeptical of products that override rather than augment.
- **Locked operating principle (§2):** capital preservation first, profit generation second. The cost of failure being *account capital* states this in customer terms.
- **Locked ICP (§3):** the buyer is *already* disciplined. The problem statement reflects that — it does not blame the buyer for lacking discipline; it identifies that their discipline doesn't scale without infrastructure.

This statement is the canonical version. §1 executive summary, §7 GTM copy, §9 messaging matrix, and §15 investor narrative all derive from it via register adjustments, not rewrites. Any §9 / §15 wording that does not trace back to this statement is overclaim by construction (per §4.2 register-handoff rule).

---

## 4.4 Lead value proposition

> **AI-driven capital-preservation infrastructure that enforces the discipline you've already built.**

Twelve words carrying all three load-bearing positioning elements:

- **"AI-driven"** — Force 2 alignment (the cost-collapse that lets us build credibly).
- **"Capital-preservation infrastructure"** — locked operating principle, as a noun.
- **"Enforces the discipline you've already built"** — framework-respect (cross-canvas central pain), and the explicit non-override stance.

This sentence travels across §1 / §7 / §15 with only register changes. §1 executive summary uses it verbatim. §7 hero copy may translate to social tier ("Trade smarter. Your discipline, enforced.") without losing the meaning. §15 investor opening keeps the analytical phrasing for global VCs and may shift to emotional resonance for MENA family offices — but the underlying claim is unchanged.

**Audit flag for §4.6:** the word "infrastructure" requires anti-overclaim pressure-test. We are closer to a product than to true infrastructure (which other things plug into) at v1. The audit pass decides whether "infrastructure" stands as aspirational-but-defensible or shifts to "system" / "platform" / "tooling."

---

## 4.5 What we explicitly do not solve

This section is the **fence** around §4.4. It exists to prevent overclaim leak into §1, §7, §9, and §15 by making explicit what the locked lead VP does *not* promise. §4.6 anti-overclaim audit checks every downstream claim against the boundaries declared here.

### 4.5.1 Trading functions we do not perform

- **Alpha generation as primary deliverable.** Capital preservation is first; profit generation is second. Users whose buying frame is "show me the alpha" or "10x my account" are anti-ICP. Our value is in the gating, sizing, and regime-awareness that make a disciplined trader's existing edge survive — not in supplying the edge.
- **Signals or copy-trade.** We do not deliver actionable trade calls or copy-tradable streams under any tier. This is the locked anti-ICP boundary, made explicit at the product-fence layer.
- **Autonomous execution without user authorization.** The engine *arms*; the user *authorizes*. Auto-execute without explicit user consent is not a CoinScopeAI capability. Future scope will be evaluated against the same risk-first principles; users seeking fully-autonomous bots are not our buyer.
- **Capital custody.** Capital remains in the user's exchange account at all times. We do not hold, move, or commingle user funds. This is a software relationship, not a fiduciary one.
- **Discipline-from-zero.** We enforce the discipline a user has already built. We are not a teaching or coaching product — traders developing their methodology are better served by other resources. Disciplined-from-the-start is the §3 ICP filter, restated here as a product-scope boundary.

### 4.5.2 Customer types we do not serve

Rendered from the locked §3 anti-ICP. Repeated here so §4.5 is self-contained as the fence.

- **US-resident retail.** Signup-blocked at the infrastructure layer. Regulatory posture, not preference.
- **Sub-$5k accounts in v1.** Unit-economics floor. Future-ICP framing per §3.5 ("we'll be back for you") — not an adversarial exclusion.
- **Copy-traders, signal-group buyers, leverage-maximizers.** Locked anti-ICP per §3.5 Anti-Persona A.
- **Fund LPs.** We tool the manager, not the allocator. Per §3.5 Anti-Persona B: inbound LP-style inquiries get a polite redirect, not an onboarding flow.

### 4.5.3 Adjacent services we do not provide

- **Tax advice.** Reports CoinScopeAI generates are designed to be exportable for review by qualified tax professionals in the user's jurisdiction. We do not provide tax determinations.
- **Legal or regulatory advice.** We do not opine on jurisdictional fit, fund-registration requirements, virtual-asset advisory licensure, or partner-book classification. Layla's regulatory question (§4.1 Canvas C functional/regulatory job) is *acknowledged*, not *answered*, by our product.
- **Fund formation.** No GP/LP structuring, no entity setup, no migration tooling at v1. This is the §15 audit fence.
- **Performance guarantees.** We do not promise specific returns, "no-loss" outcomes, or drawdown limits beyond what the user themselves configures via the gate. Our operating principle is "capital preservation first" — *first*, not *only*. Drawdowns inside user-configured thresholds are an expected outcome, not a product failure.

### 4.5.4 Future capabilities — flagged as roadmap, not v1

- **Custom-rule backtester.** Listed as a product in Canvas A v0.1. Clarified scope: engine ships with **default** backtests in v1; user-defined-rule backtesting is roadmap, not v1.
- **Fund-formation graduation path.** Canvas C v2-flagged. Data structure designed to be migration-friendly; the migration *tooling* is not built.
- **Arabic-language UI.** §3.6 matrix flagged this as post-v1. English-first for launch. Arabic layer revisited based on cohort demand and economics.
- **Sub-$5k tier.** §3.5 flagged post-Series-A or post-economics-improvement. Marketing maintains the "we'll be back" stance.

### 4.5.5 Why §4.5 exists

The fence is the precondition for the lead VP being trustworthy. Without explicit declarations of what we do *not* solve, downstream copy in §1, §7, §9, and §15 will reflexively expand the value prop into territory the product does not occupy. Anti-overclaim discipline lives in §0.2 of the framework; §4.5 makes that discipline operational by giving the audit a concrete checklist.

Any claim in §1, §7, §9, or §15 that contradicts §4.5 is overclaim by construction, regardless of how well it reads.

---

## 4.6 Anti-overclaim audit

Audit performed against §4.3, §4.4, and §4.5 on 2026-05-01. Four flags surfaced; three resulted in wording changes; one resulted in an audit-defended retention.

### Flags applied (wording changes committed)

- **§4.3 — universal-claim softening.** "Try to replace those frameworks" → "either replace those frameworks or ignore them entirely." The original framing overreached against tool categories that are silent on discipline-enforcement (TradingView, Edgewonk, etc.) rather than substituting. The corrected version captures both failure modes.
- **§4.5.1 autonomous execution — version-bound implication removed.** "Not part of v1 scope" → "not a CoinScopeAI capability. Future scope will be evaluated against the same risk-first principles." Removes the implied v2 commitment. Boundary is now categorical, not version-bound.
- **§4.5.1 discipline-from-zero — gatekeeping tone neutralized.** "Users who do not have one" → "Traders developing their methodology are better served by other resources." Names the product scope without judging the users we don't serve.

### Flag retained — defended

- **§4.4 — "infrastructure".** Pressure-tested. "Infrastructure" implies a foundational layer others plug into; that fits Persona 3's use case (multi-account, partner reports, audit trails — partners and audit logs do depend on the system as infrastructure) but is aspirational for Persona 1 / Persona 2 in Trader-tier. **Retained as written** with the explicit understanding that the lead VP describes the fully-expressed product (Desk-tier configuration), not the entry-level use case. The aspirational reach is defensible because Persona 3's literal use case is infrastructure. Alternative wording considered: "system" (safer, slightly weaker), "platform" (similar overclaim risk), "tooling" (precise, slightly diminishing).

### What §4.6 audit produces downstream

The audit becomes the canonical reference for §1, §7, §9, and §15 anti-overclaim sweeps. Specifically:

- Any §1 / §7 / §9 / §15 wording must trace to §4.3 / §4.4 / §4.5 *as audited*, not as initially drafted.
- Any future change to §4.3 / §4.4 / §4.5 wording requires a new audit pass and a decision-log entry; downstream sections inherit the change automatically.
- The "infrastructure" word retains an audit-defended status; if downstream copy stretches it further (e.g., "global trading infrastructure"), the audit reasoning ceases to apply and the new claim must be re-audited.

---

## Open questions for the founder (this pass only)

1. Do the **three canvases** capture the persona's pain/gain pattern accurately, or do you want any specific job, pain, or gain re-cut?
2. **Capital-preservation-as-gain framing** — comfortable that we treat capital preservation as a customer *outcome* rather than a marketing slogan, and let the three personas express it differently?
3. **Pain relievers vs. gain creators emphasis** — current draft weights pain relievers heavier (we relieve more than we create). Right balance, or do you want gain creators expanded to position the product more aspirationally?
4. **Cross-canvas observations** — useful as a synthesis layer for §9 messaging matrix, or feels redundant once the canvases exist?
