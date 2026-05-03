# §7 Go-to-Market Strategy

**Status:** v1 LOCKED. All sub-sections committed: channel-fit matrix, lead-with-channel (Approach 1), GTM time allocation, P3 track concurrent, paid trigger M5+ + CAC<$200, 90-day content calendar, funnel model, community strategy, anti-overclaim audit. §15, §1, §16 draft against §7 v1.
**Last updated:** 2026-05-01
**Disclaimer:** Validation phase active; paid acquisition off until M5+ per §14. CAC bands inherit from §11.5; channel mix decisions are §7 territory.

---

## 7.0 Assumptions and inheritance

### Locked from upstream

- **§3.6 segment matrix** — channel breadth per persona (organic vs. paid vs. relationship-driven).
- **§11.5 channel CAC bands per tier** — Trader $30–$400 across channels; Desk Preview $0–$3,000; Desk Full v2 $0–$8,000.
- **§11.5 blended CAC base case** — Trader $120, Desk Preview $600, Desk Full v2 $2,000.
- **§11.5 implied M1–M12 marketing budget: ~$60k.**
- **§14 launch comms plan** — continuous content cadence (Substack 1–2/mo, X 3–5/wk, Telegram light, LinkedIn monthly); paid acquisition off until M5+.
- **§9 hero copy locked (Set Alpha)** — channel-specific variants ready.
- **§9.3 register handoff per channel** — product-tier vs. social-tier rules per surface.
- **§13 north-star: MAVT** — funnel target metric.
- **§6.5 Free tier scope** — sub-$5k disciplined "we'll be back" recruiting pool.

### What §7 decides

1. The channel-fit matrix — which channels reach which personas at what cost (Phase 1).
2. The lead-with-channel decision — which channel gets primary founder attention and budget (Phase 1).
3. 90-day content calendar tied to validation milestones (Phase 2).
4. Funnel model — visitor → free → paid (Phase 2).
5. Community strategy (Phase 2).
6. Anti-overclaim audit on the GTM plan (Phase 2).

---

## 7.1 Channel-fit matrix

Synthesizes §3.6 persona-channel breadth with §11.5 CAC bands. Each cell represents a {persona × channel} fit.

### Channel coverage per persona

| Channel | P1 Methodist | P2 Engineer | P3 Solo PM | Notes |
|---|---|---|---|---|
| Substack (long-form) | **High** | Medium | Low | Methodology-focused writers + audience overlap |
| X / Twitter (quant subculture) | Medium | **High** | Low | Engineer-trader native habitat |
| GitHub / dev-adjacent | Low | **High** | Low | Engine-methodology trust signal |
| LinkedIn | Low | Medium | **High** | Operator/founder-network channel |
| Closed founder networks | Low | Low | **High** | High-trust, low-volume, MENA-heavy |
| Regional events (Token2049, Dubai Fintech) | Low | Low | **High** | Persona 3 acquisition; high cost, high fit |
| Telegram-public channel (own) | Medium | Medium | Low | MENA distribution; aligned with §3 jurisdictional posture |
| Telegram crypto-trader communities (others') | **High** | Medium | Low | Disciplined-survivor cliques exist; leverage cautiously |
| Reddit (`r/algotrading`, `r/bitcoinmarkets`) | Medium | Medium | Low | Methodology + post-mortem audience |
| Founder personal network | Medium | Medium | **High** | Direct intros; founder time is the cost |
| Trader → Desk upgrade (internal funnel) | n/a | (P2 power-user) | n/a | Internal funnel; CAC effectively zero |
| Affiliate program | Medium | Low | Low | Post-launch §8; commission-based |
| Paid acquisition (X ads, Google) | Medium | Medium | Low | Off until M5+; tested cautiously |

### Channel volume × cost summary

| Channel | Volume potential | CAC per Trader | CAC per Desk Preview | CAC per Desk Full v2 |
|---|---|---|---|---|
| Founder content (Substack + X) | Medium-high | $30–$120 | n/a (light) | n/a |
| Telegram community (organic) | Medium | $20–$80 | n/a | n/a |
| Closed founder networks | Low | n/a | $0–$200 (founder time) | $0–$500 (founder time) |
| LinkedIn organic | Low-medium | $200 (light) | $200–$800 | n/a |
| Regional events | Low | n/a | $1,000–$3,000 | $2,000–$5,000 |
| Trader → Desk Preview upgrade | n/a | $0 internal | $0 internal | n/a |
| Desk Preview → Desk Full migration | n/a | n/a | n/a | $0 internal |
| Founder-led sales (1:1) | Low | n/a | $1,500–$3,000 | $1,500–$5,000 |
| Paid acquisition (X ads, Google) | High | $150–$400 | n/a (light) | n/a |
| Affiliate program | Medium | $50–$200 | n/a | n/a |
| Partnership-driven (prop-firm, exchange) | Low-medium | n/a | n/a | $2,000–$8,000 |

### Reading the matrix

- **No single channel reaches all three personas.** Substack reaches P1 strongly; X reaches P2 strongly; LinkedIn + closed networks reach P3 strongly. A multi-channel mix is structurally required.
- **Paid acquisition is mid-fit at best.** Per §14, off until M5+. Even after M5+, paid is supplementary not primary because CAC at $400 fails the unit-economics test for Trader unless conversion lifts above 20%.
- **Founder time is the dominant cost lever.** Closed networks ($0–$200 founder time), founder-led sales ($1,500–$3,000 founder time for Desk tiers), and founder content (founder time) all have founder time as the primary cost. §11 founder cost ($7k/mo) implicitly funds these.
- **Internal funnel (Trader → Desk Preview, Preview → Full) is the highest-margin channel** — CAC effectively $0. §13 KPIs prioritize Trader → Preview migration tracking.

---

## 7.2 Lead-with-channel decision

The choice of *which channel gets primary founder attention and budget* at v1 launch. Four candidates; one wins.

### Candidate Approach 1 — Founder-led content (Substack + X) primary

**The play.** Founder posts methodology-focused Substack 1–2/mo and X 3–5/wk. Telegram own-channel and closed networks are supplementary. Paid acquisition stays off until M5+ as §14 specifies.

**Pro:** Highest LTV/CAC margins; reaches P1 + P2 directly via their primary habitats; founder time is the cost (bootstrap-friendly); builds Pillar 3 (methodology transparency) which is P2's buying criterion. Lands cleanly with §13 north-star (MAVT) because content drives engaged users, not just signups.

**Con:** Slower volume ramp than paid would produce. Reaches P3 less directly; P3 acquisition requires complementary closed-networks effort. Founder time is finite — sustained content cadence is operationally demanding alongside engineering.

**Volume profile:** Medium-high over 12 months; compounding.

### Candidate Approach 2 — Telegram community primary

**The play.** Founder runs an own Telegram channel; engages disciplined-trader cliques in MENA + global EN; uses Telegram bot integration as a value demo. Substack/X are supplementary.

**Pro:** Lowest CAC ($20–$80 Trader); MENA distribution leverage; aligned with locked Tier 1 delivery surface (Telegram-companion bot). Fast feedback cycles through chat.

**Con:** Telegram is a chat surface, not an analysis surface — hard to convey methodology depth. Risks attracting anti-ICP (signal-group-adjacent users wandering in). Pillar 2 (framework respect) hard to express in chat-tier register. Lower trust artifact density.

**Volume profile:** Medium; community-quality dependent.

### Candidate Approach 3 — Closed networks + LinkedIn primary (P3-focused)

**The play.** Founder time goes into MENA founder networks, regional events, LinkedIn operator-content, and 1:1 sales for Desk-tier candidates. Content + community supplementary.

**Pro:** Highest ARPU per acquisition (Desk Full $1,199–$1,500 + per-seat); §3 P3 is high-value persona. MENA distribution structural advantage. Builds long-term relationship moat.

**Con:** Lowest volume ramp; doesn't acquire P1 or P2 at scale; concentrated risk (single channel underperforming = catastrophic). Founder-time intensive without scaling levers.

**Volume profile:** Low (high-quality, low-quantity).

### Candidate Approach 4 — Paid acquisition primary

**The play.** Allocate the $60k M1–M12 marketing budget toward X ads + Google search targeting Trader-tier acquisition. Content + community supplementary.

**Pro:** Predictable volume; scales with spend; doesn't depend on founder time for distribution.

**Con:** Unit economics unvalidated pre-launch; CAC $150–$400 vs. base-case $120 ceiling means margin tightens; bootstrap-unfriendly (60k is most of marketing budget); §14 explicitly says paid off until M5+; conflicts with locked posture.

**Volume profile:** High but expensive.

### My recommendation

**Approach 1 — Founder-led content primary.**

Reasoning, in three parts:

**Best fit for the locked validation-phase posture.** §14 says paid off until M5+; bootstrap reserves are tight; founder time exists to spend; content accumulates value. Paid acquisition is a Phase 4+ scale lever, not a launch lever.

**Reaches the two-thirds of personas that drive volume.** P1 (Substack-native) + P2 (X-native) cover the majority of paid-user volume in §11 base case (~230 of ~270 acquisitions M1–M12). P3 acquisition is a complementary track running alongside, not requiring its own primary commitment.

**Highest brand-voice alignment.** Methodology-focused content is Pillar 3 in action. Substack long-form lets us *show* the engine internals — full-cohort backtests, regime classifier inputs, gate logic. X threads compress the same into shareable form. The brand voice is methodical and evidence-led; content lives that voice publicly.

**Concrete v1 channel allocation under Approach 1:**

- **Founder time (primary):** ~50–60% of weekly capacity goes to content (Substack + X) and engagement. Sustained cadence enforced by §14 launch comms plan.
- **Founder time (P3 track):** ~15–20% of weekly capacity goes to closed networks + LinkedIn + 1:1 P3 sales. Concurrent track, not subordinate.
- **Founder time (community):** ~10% to Telegram own-channel + MENA crypto-trader engagement.
- **Founder time (operations):** balance for support tickets, soft-cohort interactions, etc.
- **Paid acquisition:** off until M5+. After M5+, light experimental allocation ~$2k–$5k/mo if Trader CAC validated below $200.

### Three confirmable alternatives

1. **Approach 1 — Founder-led content primary (recommended).**
2. **Approach 2 — Telegram community primary.**
3. **Approach 3 — Closed networks + LinkedIn primary (P3-focused).**
4. **Approach 4 — Paid acquisition primary.**

---

## 7.3 90-day content calendar (M0 → M3)

90-day window = May 2026 (M0 validation) → July 2026 (M2 end of soft cohort) → August 2026 (M3 public launch). Content cadence per locked Approach 1 + GTM time allocation.

### Cadence by channel

| Channel | M0 cadence | M1–M2 cadence | M3 cadence |
|---|---|---|---|
| Substack | 1 post (validation methodology overview) | 2 posts (1/mo) — soft-cohort observations + risk-gate methodology | 2 posts — public-launch announcement + cohort-behavior synthesis |
| X / Twitter | 2–3 posts/wk (validation-phase methodology threads) | 3–4 posts/wk (soft-cohort observations + product context) | 5 posts/wk (launch announcement amplification + ongoing) |
| LinkedIn | 1 post (operator-network introduction) | 1 post per month | 1 post (launch announcement, P3-flavored) |
| Telegram own-channel | Phase milestone announcements only | Soft-launch milestone + founder-cohort window open | Public launch milestone + founder-cohort pricing surface |

### Topic themes by month

**M0 — Validation phase (May 2026).**

- *Substack:* "How we validate the engine: a 30-day cohort under §8 capital-cap criteria." Methodology-first; demonstrates anti-overclaim discipline.
- *X threads:* regime classifier inputs explained; gate logic walkthroughs; cohort drawdown framing. Pillar 3 dominant.
- *LinkedIn:* founder introduction + "what we're building, why MENA, what disciplined retail actually wants." Pillar 4 reinforce + Pillar 1 lead.

**M1–M2 — Soft launch (June–July 2026).**

- *Substack post 1:* "Soft cohort week 1: what 40 disciplined traders did with the gate." Observed-data piece. Pillar 1 + Pillar 3.
- *Substack post 2:* "Position-sizing math, demystified: the formula behind the position sizer." Pillar 3 deep dive. P2-targeted.
- *X threads:* soft-cohort behavior observations (anonymized aggregate); methodology Q&A; gate-rejection patterns. 3–4 posts/wk.
- *LinkedIn (1 each month):* P3-flavored — "Running a small book? Here's the infrastructure gap we noticed." Closed-network amplification.
- *Telegram own-channel:* soft launch open milestone; founder-cohort eligibility window.

**M3 — Public launch (August 2026).**

- *Substack post 1:* "Public launch: methodology, gates, and what we're calibrated for." Public-facing version of validation summary. Pillar 1 + 3.
- *Substack post 2:* "Cohort behavior in 90 days: what disciplined crypto-perp traders actually do with infrastructure." Observed-data piece, M0–M2 synthesis.
- *X:* launch announcement thread (lead with hero copy "Trade smarter. Your discipline, enforced."); ongoing methodology cadence.
- *LinkedIn:* launch announcement, operator-targeted, MENA-flavored.
- *Telegram own-channel:* public launch announcement + founder-cohort pricing surface.

### Topic backlog (M4 onwards, drafted as direction not commitment)

- Regime classifier deep dive (per-regime behavior patterns).
- Risk-gate threshold tuning (how Persona 1 configures, how Persona 2 reads the math).
- Cohort retention analysis (when soft-cohort + public-launch data lands).
- Persona 2-targeted: API integration walkthrough; backtest disclosure methodology.
- Persona 3-targeted: multi-account aggregation workflow (when Desk Preview ships); LP-style reporting principles (v3-deferred but direction surface).

### Content-production discipline

- **Per §9.3 register handoff:** Substack title social-tier OK, body product-tier; X full social-tier; LinkedIn headline social-tier OK, body product-tier; Telegram own-channel light-product-tier.
- **Per §9 audit:** every claim traces to §4 canvases or §5 capabilities at correct maturity.
- **Anti-overclaim sweep:** spot-check pattern weekly (per §13.5 weekly internal report).

---

## 7.4 Funnel model — visitor → free → paid

### Stage definitions and base-case conversion rates

| Stage | Source | Base-case conversion to next stage | Inheritance |
|---|---|---|---|
| **Visitor** | Substack readers + X impressions + LinkedIn views + Telegram-public + waitlist landing page | ~3–8% sign up for Free (typical SaaS landing page conversion) | `A` assumed |
| **Free signup** | Account-verified entry tier per §6.5 | 5% to paid Trader within 90 days | Inherited from §6.9 / §11.1 (locked) |
| **Trader (paid)** | First-time paid users | 8% to Desk Preview within 12 months | Inherited from §11.1 |
| **Desk Preview** | Persona 3 + P2 power-users | 70% to Desk Full at v2 launch (M10) | Inherited from §11.1 |
| **Desk Full v2** | Post-v2 launch | 80% retention 12-mo post-launch | Inherited from §11.1 retention curves |

### Funnel volumes — base case M1–M12

Reconciled with §11.1 cohort sizing table.

- **M3 visitor volume estimate:** ~1,500–3,000 unique visitors (combination of waitlist conversions + organic content + early X traction).
- **M3 Free signups:** 50 (per §11.1 cumulative).
- **M3 visitor → Free conversion:** roughly 2–4% (lower than typical because we account-verify; signup friction is real).
- **M3 Trader cohort:** 95 (cumulative; mix of soft-cohort carry-over + waitlist conversion + first organic conversions).
- **M3 Desk Preview cohort:** 22.

### Conversion-rate sensitivity (cross-link to §11.6)

§11.6 sensitivity flags Free → Trader as the highest-leverage input (±$700k M24 ARR variance). §7 funnel model inherits this — content calendar success is largely measured by Free → Trader conversion lift.

### Funnel measurement — §13 KPI alignment

- **Top-of-funnel:** weekly visitor count by source (Substack readers, X impressions, LinkedIn views).
- **Conversion-stage:** Free signups, Free → Trader conversion at 30/60/90 days, Trader → Preview at 6/12 months.
- **MAVT contribution:** §13 north-star measures who's *active* among paid; funnel measures who *enters paid*.
- **Persona segmentation:** funnel metrics segmented by persona where signup data permits inference (channel-of-origin × account-size proxy).

---

## 7.5 Community strategy

### Telegram own-channel (CoinScopeAI broadcast)

- **Cadence:** light. Phase milestones + occasional methodology snippets.
- **Register:** social-tier acceptable per §9.3.
- **Anti-ICP guard:** moderation pattern explicitly excludes signal-sharing, copy-trade promotion, and leverage-maximizing content. Channel description includes our locked positioning so anti-ICP self-deselects on join.
- **Subscriber growth target:** 100–300 by M3 (organic from content + soft-cohort referrals); 500–1,000 by M12.
- **Engagement: not a chat surface.** Broadcast-only by default; replies routed to product support via dashboard.

### MENA crypto-trader engagement (selective, founder-led)

- **Goal:** participation in disciplined-trader cliques; brand-builds Pillar 4 (MENA-rooted) authentically.
- **Method:** founder participates in 2–3 high-trust closed Telegram/WhatsApp groups; never spams, never sells. Posts methodology content selectively.
- **Anti-ICP guard:** founder declines to engage in groups whose primary content is signal-sharing or leverage-maximizing.

### Closed founder networks (P3 acquisition)

- **Goal:** P3 acquisition through warm introductions in MENA founder/operator circles.
- **Method:** founder attends regional events (Token2049, Dubai Fintech Summit when scheduled) at modest cost; participates in MENA founder-network Telegram/WhatsApp groups; LinkedIn 1:1 outreach to operator-network connections.
- **Tracking:** introductions logged in lightweight CRM; founder-time spent per acquisition tracked weekly.

### Discord — explicitly out of scope at v1

Per §0.5 framework lock: "Telegram-first community; Discord deferred." Reaffirmed here. Discord adds a parallel community surface that fragments founder time without proportional reach for our personas. Revisit post-v2 if §3.7 interview data shows P2 (Engineer) cohort meaningfully prefers Discord.

### Reddit — light, content-only

`r/algotrading` and `r/bitcoinmarkets` for methodology post-mortem cross-posts (when Substack content is publishable on Reddit). Founder doesn't actively engage in Reddit threads; cross-posts are one-way.

---

## 7.6 Anti-overclaim audit on §7

Audit performed against §7.0 through §7.5 on 2026-05-01.

### Flags applied

**Flag 1 — Channel-fit matrix CAC bands inherit from §11.5 without re-validation.**

§7.1 reproduces §11.5 CAC bands (Trader $30–$120 founder content, $20–$80 Telegram, etc.). These are still `A` assumed; soft-cohort observation produces the first observed values.

*Mitigation:* §7 inherits §11.5 disclaimer — bands are pre-validation; refined post-soft-cohort.

**Flag 2 — Content cadence is operationally demanding alongside engineering at solo-founder scale.**

60% of GTM time on content × 50% of total founder time on GTM = ~12 hrs/week sustained content cadence. Realistic for Mohammed if validation phase engineering demand drops; aggressive if engineering demand stays high.

*Mitigation:* §13 weekly reporting templates track content cadence actual vs. plan. If actual lags by >30% for 2 consecutive weeks, GTM allocation reviews against engineering load.

**Flag 3 — "MENA-rooted" claims in §7.5 community strategy must be substantiated, not stated.**

Pillar 4 (regulatory-conservative + MENA-rooted) is real per §3 + §11 + §15, but community-strategy copy says "MENA founder networks" generically. The claim is true; the substantiation comes from actual relationships, not assertion.

*Mitigation:* §7.5 community strategy text grounded in specific named events (Token2049, Dubai Fintech) rather than generic "MENA networks." §15 investor narrative requires named MENA contacts/intros to support Pillar 4 claim in due diligence.

### Three flags considered and dismissed

- **"Founder-led content" implies single-source dependency.** True but unavoidable at solo-founder scale; §15 narrative addresses this through §5.4.7 contractor support optionality (engineering, not GTM).
- **Funnel model conversion rates may be optimistic.** §11.6 sensitivity already runs 3% / 5% / 8% Free → Trader scenarios; downside captures conservative case.
- **Discord deferral may surface persona pushback.** §3.7 interview plan probes channel preference; if data shows Discord meaningful, reopens the decision.

### What §7 audited clean

- Lead-with-channel decision (Approach 1) traces to §3.6 + §11.5 + §14 paid-off-until-M5 lock.
- Content calendar topics align with §9 pillar weighting per persona.
- Funnel model conversion rates inherit cleanly from §11.1 / §11.6 / §6.9 — no new claims.
- Community strategy respects locked anti-ICP; explicit Discord deferral matches §0.5.
- §7.4 stage definitions match §13 north-star (MAVT) measurement scope.

### §7 v1 LOCKED

§7.0 through §7.6 all committed. §15 investor narrative, §1 executive summary, §16 scenarios draft against §7 v1.

---


---

## Open questions for the founder (Phase 1 only)

1. **Lead-with-channel** — Approach 1 (founder content), Approach 2 (Telegram), Approach 3 (closed networks/LinkedIn), or Approach 4 (paid)? My recommendation: 1.
2. **Founder time allocation** — proposed 50–60% content / 15–20% P3 track / 10% community / balance ops. Comfortable, or want to adjust?
3. **P3 track concurrency** — running P3 acquisition concurrent (not subordinate) to content track means founder is wearing two GTM hats. Realistic at v1, or want to defer P3 active acquisition until v2?
4. **Paid acquisition trigger** — locked at M5+ pending Trader CAC validation. Comfortable with the trigger, or want a different threshold?
