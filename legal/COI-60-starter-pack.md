# COI-60 — Starter Pack

**Issue:** P1.5 — ToS and Risk Disclosures (signed acceptance gate)
**Linear:** https://linear.app/coinscopeai/issue/COI-60
**Status:** Backlog → moving to Todo
**Date:** 2026-04-29

---

## What "starting" means here

The legal language is drafted (`/CoinScopeAI/legal/tos-and-disclosures-DRAFT.md`). What's missing is (1) counsel review to make it actually defensible, (2) the placeholders filled with real entity/jurisdiction info, and (3) the Auth-middleware wiring that gates API access on signed acceptance.

Validation phase rule (no engine code changes) means the wiring step waits. The other two start now.

---

## Sequenced milestones

### M1 — Counsel selection (this week)

Pick a lawyer / firm. Three viable paths:

- **Specialized crypto-trading-platform counsel** (US or EU) — best for a globally-targeted SaaS. Examples to evaluate: Cooley, Latham, Anderson Kill (US); Bird & Bird, Osborne Clarke (EU). Cost: $5k–$15k for a ToS + Risk Disclosures review at the founder-stage pricing. Turnaround: 2–4 weeks.
- **Jordan-local counsel + crypto specialist on retainer** (cheaper) — local lawyer for entity / Jordan-specific issues, plus a crypto specialist for the trading-platform-specific clauses. Cost: $2k–$5k combined. Turnaround: 3–5 weeks.
- **Online-platform legal services** (Clerky, Stripe Atlas legal, LegalZoom, AngelList) — cheapest, lowest-touch. Acceptable for a placeholder ToS pre-revenue but not for real-capital launch. Cost: $300–$1,500. Turnaround: same week.

**Recommendation:** start with #3 to get a counseled-but-not-bespoke draft live in two weeks. Move to #1 or #2 before the real-capital gate flips.

### M2 — Placeholder fill (parallel with M1)

Decisions Mohammed needs to make before counsel can finalize:

- [ ] **Legal entity name** — incorporate where? (Delaware C-Corp? Jordan LLC? UAE free-zone?) Affects everything downstream.
- [ ] **Jurisdiction of governing law** — typically matches incorporation. Affects which courts handle disputes.
- [ ] **Dispute resolution mechanism** — binding arbitration (cheaper, faster, opaque) or courts (slower, transparent, public)? Recommend arbitration with a US-based provider (AAA or JAMS) for cross-border SaaS.
- [ ] **Restricted jurisdictions** — start with the OFAC SDN comprehensive list. Decide whether to also exclude all of mainland China, Russia, Belarus, Venezuela, Myanmar.
- [ ] **Legal contact email** — `legal@coinscope.ai` recommended. Set up the alias before publishing.
- [ ] **Liability cap dollar amount** — current draft says $1k. Counsel may push to remove or raise. Discuss before review.
- [ ] **Fee refund policy** — current draft says "all sales final, refunds at sole discretion." Confirm or soften.

### M3 — Auth wiring (post-validation)

Engineering work, gated on COI-41 validation completing:

- Add `tos_accepted_version` and `tos_accepted_at` columns to `users` table
- Auth middleware reads `tos_accepted_version` from JWT claims; refuses any non-`/auth/*`, non-`/billing/*` route if version mismatches current published version
- 403 response includes a `Link: </legal/terms>; rel="tos-accept"` header and a JSON body with the acceptance URL
- Signup flow shows ToS + Risk Disclosures, captures click + IP + timestamp, writes acceptance to user record
- ToS version bump triggers re-acceptance: deploy publishes new version string, all users 403 until they re-accept
- All acceptances recorded in `audit_log_tos_acceptance` table for evidentiary purposes

Estimated 2–3 days of focused work once unblocked.

### M4 — Public publication

After M2 done and M3 deployed:

- Push final ToS to `/legal/terms` on coinscope.ai
- Push Risk Disclosures to `/legal/risk-disclosures`
- Push methodology summary to `/legal/methodology` (linked from COI-63)
- Push current-status page to `/legal/status` (linked from COI-63)
- Footer link from marketing site
- Footer link from app dashboard
- Update version string in app config; trigger initial acceptance for any existing users

---

## Counsel-engagement brief (use this when contacting lawyers)

> **Subject:** ToS + Risk Disclosures review — pre-revenue crypto-trading SaaS
>
> We're CoinScopeAI, a pre-revenue SaaS that produces algorithmic crypto-derivatives trading signals and (in higher tiers) executes trades on connected exchanges on the user's behalf. We're founder-stage, currently in 30-day testnet validation, no real capital is being traded yet.
>
> We need:
> 1. Review and revision of attached starter ToS (~3,500 words) and Risk Disclosures (~1,500 words)
> 2. Recommendation on legal-entity / jurisdictional structure for a globally-targeted product (founder is based in Jordan, target users US/EU/global)
> 3. Standard sanctions-list and KYC/AML guidance — what's the minimum we need to have published before we sign a paying customer
> 4. Disclaimer-language around past-performance and backtest-result presentation
>
> Out of scope (for now): securities-law analysis, regulated-advisory-status counsel, EU MiCA-specific licensing assessment.
>
> Timeline: 2–4 week turnaround. We're flexible on price; quote against the 4-document deliverable. Would prefer fixed-fee for this scope.
>
> Drafts attached: tos-and-disclosures-DRAFT.md (with `[TBD]` placeholders).

---

## Acceptance criteria (from the Linear issue)

- [ ] ToS + Risk Disclosures committed to `/CoinScopeAI/legal/`
- [ ] Auth middleware enforces signed-acceptance on protected routes (M3, post-validation)
- [ ] `/legal` renders both documents (M4)
- [ ] New user signup flow forces acceptance before first API call (M3)
- [ ] ToS version stored on User; bump triggers re-acceptance (M3)

---

## Companion docs

- Drafted language: `/CoinScopeAI/legal/tos-and-disclosures-DRAFT.md`
- Architecture v5 (Compliance rail): `/CoinScopeAI/architecture/architecture.md`
- Strategy memo: `/CoinScopeAI/strategy/strategic-memo-2026-04-29.md`
- Sister issues: COI-63 (public /legal page), COI-64 (audit log retention)
