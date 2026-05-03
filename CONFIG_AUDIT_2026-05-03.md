# CoinScopeAI — Claude Configuration Audit
**Date:** 2026-05-03
**Auditor:** Claude (Cowork session, Sonnet 4.6)
**Scope:** Master prompt (Scoopy v2) · Memory system · Skills/plugins · MCP integrations
**Mode:** Findings + action plan only — no changes applied
**Reference:** Companion to `architecture/enhancement-audit-2026-05-02.md` (knowledge/skills/workflow gaps); this audit covers the Claude *configuration* layer specifically.

---

## TL;DR

The Scoopy v2 prompt is fundamentally sound — capital-preservation framing, risk numbers as first-class citizens, and the v1 framework reference block all hold up. Five concrete issues pull weight against it:

1. **20x leverage residue** in 9+ live `docs/` files and 1 *active* validation template — drift-detector exists but hasn't been run as gate.
2. **Master prompt cites stale URLs** (`localhost:8001` as primary, `coinscope.ai` as dashboard) — memory says `api.coinscope.ai` and `app.coinscope.ai` are canonical.
3. **Memory hygiene** — 2 orphaned files, 1 expired mandate (Apr 10–30), 1 actively dangerous file (`project_engine_specs.md` — wrong leverage cap, wrong drawdown, wrong daily-loss cap).
4. **Pricing conflict** — `project_current_state.md` memory says canonical pricing is $19/$49/$99/$299; CLAUDE.md + `06-pricing-monetization.md` say $79/$399/$1,199. Memory is stale (legacy Stripe seed data).
5. **Plugin/skill bloat** — Zoom (32 sub-skills), HR (10), parts of Finance, Slack-by-Salesforce, Apollo, and Common Room consume context for capabilities that don't fit a solo founder pre-revenue.

Highest-leverage fixes: (a) wire `scripts/drift_detector.py` into a pre-commit + weekly schedule, (b) prune 4 memory files and re-index, (c) add 5 missing rules to CLAUDE.md, (d) declutter plugin set.

---

## Section 1 — Master prompt (Scoopy v2)

**Source:** `/Users/mac/Documents/Claude/Projects/CoinScopeAI/CLAUDE.md` (5,495 bytes, last modified 2026-05-02 18:02)

### 1.1 What's working
- Identity (Scoopy + @ScoopyAI_bot) is unambiguous.
- 4 voice principles are operational, not vibes — each maps to behavior Scoopy can be evaluated against.
- Risk numbers are first-class and now correctly resolve leverage to 10x with the §8 PCC v2 citation.
- The v1 framework reference block (personas / tier matrix / phase map / authoritative locations) is the single most valuable addition vs. v1.
- Has a Changelog and version stamp — most ad-hoc prompts don't.

### 1.2 Drift / errors

| # | Finding | Evidence | Severity |
|---|---|---|---|
| P-1 | Engine API URL in prompt = `http://localhost:8001` (dev). Memory (`project_current_state.md`) says `api.coinscope.ai` is the production engine, localhost is dev-mode only. Scoopy should know both and which to use when. | CLAUDE.md L33 vs. memory L28 | HIGH |
| P-2 | Dashboard URL in prompt = `https://www.coinscope.ai`. Memory pins `app.coinscope.ai` as the canonical app/dashboard URL since 2026-04-23 — `coinscope.ai` is the marketing site, distinct surface. | CLAUDE.md L34 vs. memory L27 | HIGH |
| P-3 | Phase map skips P3 (Oct–Dec 2026) and P4 (Jan–Feb 2027); jumps P0 → P1 → P2 → P5. Either fill them in or state "intentionally omitted." | CLAUDE.md L72–76 | MED |
| P-4 | "Read project skills (SKILL.md in CoinScopeAI Design System) before any task." — there is no `CoinScopeAI Design System` folder of SKILL.md files locally. The pointer is dangling. | CLAUDE.md L92, no matching path on disk | MED |
| P-5 | No US-block / jurisdictional rule. `project_jurisdictional.md` memory is explicit: US persons blocked at signup until counsel returns the no-investment-advice memo. This is a hard gate that should bind GTM/marketing/sales copy generation. | Missing from prompt | MED |
| P-6 | "30-day validation phase" — no start date, no expected end date. COI-41 is in progress but the prompt has no anchor for "are we still in it?" | CLAUDE.md L29 | MED |
| P-7 | Connector-health rule (from `feedback_connector_health.md`) is not in prompt. Currently only enforced via memory. | Missing from prompt | LOW |
| P-8 | Missing version stamps for satellite docs (brand book v3, architecture v5, design-system manifest v2). Without these, drift-detector has no anchor to compare against. | CLAUDE.md tail | LOW |
| P-9 | Free tier is listed but has no constraints described (signal cap? read-only?). Defers to framework — fine if intentional, but worth noting. | CLAUDE.md L66 | LOW |

### 1.3 Recommended prompt edits (drop-in)

Three small inserts close the highest-impact gaps:

```markdown
━━ Key resources ━━
- Engine API (dev): http://localhost:8001 — use locally only
- Engine API (prod): https://api.coinscope.ai — read-only from Scoopy chat
- Primary app/dashboard: https://app.coinscope.ai
- Marketing site: https://coinscope.ai (separate surface — do not conflate)
- GitHub: 3nz5789/coinscope-ai
- Telegram: @ScoopyAI_bot (Chat ID: 7296767446)

━━ Jurisdictional posture (locked 2026-05-01) ━━
- Founder: UAE-based, sole proprietor (no entity yet — pending counsel).
- Target: UAE/MENA + global English. **US persons are blocked at signup** until counsel returns the no-investment-advice memo.
- All GTM/marketing/sales copy must be consistent with the US block. Treat UAE as primary jurisdiction; EU/UK as read-across.

━━ Validation phase ━━
- Started: 2026-04-10  ·  Linear: COI-41  ·  Phase end (target): 2026-05-10
- No core engine changes. No real orders on any exchange.
- Connector health is a first-class concern — verify on touch, audit on health check.
```

Also fix `(SKILL.md in CoinScopeAI Design System)` → `(SKILL.md files under skills_src/ and skills/)` so the pointer resolves to a real path.

---

## Section 2 — Memory system

**Index:** `MEMORY.md` lists 11 entries.
**Files on disk:** 13 `.md` files (12 + index).

### 2.1 Inventory delta

| File | Indexed? | Age | Status | Action |
|---|---|---|---|---|
| `instruction_project_management.md` | ✓ | 22 d | **EXPIRED** — mandate window Apr 10–30 closed; today is May 3 | Delete or rewrite |
| `project_engine_specs.md` | ✗ orphaned | 21 d | **DANGEROUS** — quotes max leverage 5x, max DD 15%, daily loss 5%, max position 10%, max concurrent 5 — none match current PCC v2 | Delete |
| `project_restructure_pass_2026-04-18.md` | ✗ orphaned | 14 d | Still useful (archive policy + freeze rule) | Add to MEMORY.md |
| `project_current_state.md` | ✓ | 9 d | Mostly fresh; **pricing block stale** ($19/$49/$99/$299 conflicts with $79/$399/$1,199 in CLAUDE.md + framework) | Strike pricing block; add note "see business-plan/06-pricing-monetization.md as canonical" |
| `project_vision_mission.md` | ✓ | 10 d | Clean, locked, in use | Keep |
| `project_notion_workspace.md` | ✓ | 9 d | Fresh | Keep |
| `project_phased_rollout.md` | ✓ | 3 d | Fresh | Keep |
| `project_jurisdictional.md` | ✓ | 1 d | Fresh | Keep |
| `project_engine_thresholds.md` | ✓ | 1 d | Fresh, authoritative | Keep |
| `feedback_connector_health.md` | ✓ | 0 d | Fresh, comprehensive | Keep |
| `feedback_design_system_sync.md` | ✓ | 0 d | Fresh | Keep |
| `project_drive_dual_tree.md` | ✓ | 0 d | Fresh | Keep |
| `project_deferred_handoffs.md` | ✓ | 0 d | Fresh; tracks 2 remaining items | Keep |

### 2.2 Hygiene actions

1. **Delete `project_engine_specs.md`.** It contradicts current canonical thresholds. Risk: if a future Scoopy reads it before `project_engine_thresholds.md`, it could quote 5x leverage / 15% DD as authoritative.
2. **Delete or rewrite `instruction_project_management.md`.** The Apr 10–30 mandate window has closed. If the user wants the standing rule preserved, rewrite as a no-end-date feedback memory.
3. **Add `project_restructure_pass_2026-04-18.md` to MEMORY.md.** Still load-bearing for archive policy + internal-refactor freeze.
4. **Strike the `## Pricing Model (CANONICAL)` block in `project_current_state.md`** — replace with a one-line pointer: *"Pricing: see `business-plan/06-pricing-monetization.md` as canonical (Trader $79 / Desk Preview $399 / Desk Full v2 $1,199 + per-seat)."*
5. **Mark `project_current_state.md` for refresh.** Several "verify before acting" notes (COI-40 status, Linear ticket states) are 9+ days old. Re-pull from Linear next session.

### 2.3 Re-indexed `MEMORY.md` (proposed)

```markdown
# CoinScopeAI Memory Index

- [Notion Workspace](project_notion_workspace.md) — DB IDs, active OS URLs, completed P1/P2 items
- [Current Project State](project_current_state.md) — Phase, blocker (COI-40 VPS), Linear issues, what's next
- [Vision and Mission](project_vision_mission.md) — Locked 2026-04-22: Vision A + Mission 1
- [Phased Vendor Rollout](project_phased_rollout.md) — 3-phase plan; P1 ships narrow
- [Jurisdictional Posture](project_jurisdictional.md) — UAE founder, sole prop; US blocked at signup
- [Engine Thresholds & §8 Gate](project_engine_thresholds.md) — Leverage cap = 10x; §8 = Capital Cap section of PCC v2
- [Repo Restructure Pass 2026-04-18](project_restructure_pass_2026-04-18.md) — Archive-over-delete policy; freeze rule for engine internals
- [Connector Health Standard](feedback_connector_health.md) — Always keep connectors auth-valid; verify on touch
- [Deferred Handoffs](project_deferred_handoffs.md) — 2 user-only items remaining (key revoke, GitHub push)
- [Design System Sync Rule](feedback_design_system_sync.md) — When CLAUDE.md tokens change, update manifest in same response
- [Drive Dual-Tree Setup](project_drive_dual_tree.md) — Curated tree + auto-synced mirror — both intentional
```

(Removed: `instruction_project_management.md`, `project_engine_specs.md`. Added: `project_restructure_pass_2026-04-18.md`.)

---

## Section 3 — Leverage / threshold consistency (PCC v2 sweep)

**Drift-detector** (`scripts/drift_detector.py`) already exists with a `20x_leverage` rule (regex `\b20x\b`). It has never been run as a gate.

### 3.1 Live (non-archived) files still saying 20x

| File | Line | Severity |
|---|---|---|
| `Validation_Phase_Exit_Memo_TEMPLATE.md` | 73 | **CRITICAL** — D3 acceptance criterion reads "0 trades >20x" — would mark a 15x trade as PASS |
| `business-plan/_data/operations/Validation_Phase_Exit_Memo_TEMPLATE.md` | 73 | (mirror) |
| `Vendor_Failure_Mode_Mapping_v1.md` | 14 | HIGH — published "Core invariant" still says leverage 20x |
| `business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md` | 14 | (mirror) |
| `Business_Plan_v1.md` | 29 | HIGH — pitch deck source |
| `README.md` | 136 | HIGH — repo first impression |
| `docs/runbooks/daily-market-scan-runbook.md` | 230, 306 | MED |
| `docs/architecture/data-flow.md` | 113 | MED |
| `docs/risk/risk-framework.md` | 42 | MED — "risk framework" doc |
| `docs/risk/position-sizing.md` | 15, 57 | MED |
| `docs/ml/confidence_scoring_baseline.md` | 81 | MED |
| `docs/backend/configuration.md` | 95 | MED — `MAX_LEVERAGE: 20` (default in env doc, even though code default is 10) |
| `mvp-readiness-checklist.md` | 61 | LOW — says "Running: 10× (ceiling 20×)" — ambiguous since ceiling was lowered |
| `business-plan/_data/operations/mvp-readiness-checklist.md` | 61 | (mirror) |

### 3.2 Engine code is correct
- `coinscope_trading_engine/config.py` L157: `max_leverage: int = Field(10, ge=1, le=125, ...)` ✓
- `tests/conftest.py` L37 + `tests/test_risk.py` L65: 10 ✓
- `tests/test_ws_replay_consistency.py` L58: 10 ✓
- `risk/position_sizer.py` reads from settings ✓

### 3.3 Action plan

1. **Run `python scripts/drift_detector.py` now** — get the full ground-truth list.
2. **Sweep-fix in one PR.** All 14 files above. Use `sed -i 's/20x/10x/g'` carefully (review diff — some occurrences in archived/superseded files should remain).
3. **Wire drift-detector into pre-commit** (`.pre-commit-config.yaml`) blocking on `20x_leverage` rule. The script is built for this.
4. **Wire drift-detector into a weekly scheduled task** so silent drift is caught even without commits.
5. **Update `Validation_Phase_Exit_Memo_TEMPLATE.md` D3 row first** — this is the only one with operational consequences (it gates the validation pass/fail decision).

---

## Section 4 — Skills & plugins audit

**Total available skills:** ~190 (counted from `<available_skills>`).

### 4.1 KEEP — directly project-relevant (always-on)

| Bundle | Skills | Why |
|---|---|---|
| **CoinScopeAI core** | architecture, engine-api, mempalace-ops, platform-sync, task-naming-standard, trading-rules, market-scanner, binance-futures-api | Project DNA |
| **Doc creation** | pdf, docx, xlsx, pptx | Business plan, decks, financial model |
| **Skill/MCP authoring** | skill-creator, mcp-builder | You're building skills (drift-detector, daily-status, etc.) |
| **Engineering** | code-review, debug, system-design, architecture, deploy-checklist, testing-strategy, documentation, incident-response, runbook | Solo-dev essentials |
| **Design** | design-system, accessibility-review, design-handoff, ux-copy, design-critique | Manifest + dashboard work |
| **Brand/marketing** | brand-voice (3), brand-guidelines, draft-content, campaign-plan, content-creation, brand-review | Aligns with v3 brand book |
| **Data** | analyze, sql-queries, statistical-analysis, build-dashboard, create-viz, explore-data | Backtesting + validation analysis |
| **PM** | write-spec, brainstorm, roadmap-update, metrics-review, synthesize-research | Solo PM work |
| **Operations** | runbook, status-report, risk-assessment, change-request, process-doc | Operational SOPs |
| **Productivity meta** | task-management (TASKS.md) | Compatible with TodoList |
| **Schedule** | schedule | Powers daily-status / weekly digest |
| **Theming** | theme-factory, canvas-design, web-artifacts-builder | Artifact polish |

### 4.2 LIKELY-PRUNE — high context cost, low CoinScopeAI fit

| Bundle | Skills | Reason | Action |
|---|---|---|---|
| **zoom-plugin** | 32 sub-skills | No video-call workflow; consumes most context budget of any single bundle | **Disable entirely** until a Zoom integration is on the roadmap |
| **human-resources** | 10 skills (org-planning, perf-review, comp-analysis, recruiting…) | No employees yet (sole prop) | Disable until first hire |
| **slack-by-salesforce** | 6 skills + 2 reference skills | Workspace doesn't appear Slack-based | Disable unless Slack is in use |
| **finance** (subset) | sox-testing, audit-support, sox-testing variants | Pre-revenue sole prop is not at SOX scale | Keep `journal-entry`, `reconciliation`, `variance-analysis`, `financial-statements`; disable SOX/audit |
| **common-room** | 7 skills | Pre-launch — no sales motion yet | Disable until P1+ |
| **apollo** | 3 skills | Same — pre-launch | Disable until P1+ |
| **customer-support** | 5 skills | No customers yet (cohort opens P0/May) | Re-enable May 2026 when cohort starts |
| **pdf-viewer** | 4 skills | Niche; you can use Read on PDFs directly | Disable unless PDF annotation is a workflow |
| **legal** | 9 skills | Some value (NDA triage, contract review for vendor agreements) — but low frequency | Keep but acknowledge as low-frequency |

### 4.3 Skills to BUILD (from `enhancement-audit-2026-05-02.md`, still pending)

Already scoped in the prior audit, repeated for completeness:
- **`drift-detector`** (B3) — script exists; needs SKILL.md polish + pre-commit wiring
- **`daily-status`** (B1) — Engine API roll-up
- **`kill-switch-protocol`** (B2) — codifies failsafes
- **`pcc-v2-gate-inspector`** (B6) — G1–G4 status
- **`vendor-health-check`** (B7) — pings P1 vendor stack
- **`regime-explainer`** (B4) — `/regime/{symbol}` plain-English
- **`decision-log-appender`** (B5) — structured decision-log entries

---

## Section 5 — MCP integrations

### 5.1 Connected MCPs (inventoried from deferred tools)

| MCP | Purpose | Status | Action |
|---|---|---|---|
| Linear (`25a383a6…`) | Issues, projects, docs | KEEP | Healthy |
| Notion (`7cf401c0…`) | Workspace + DBs | KEEP | Healthy per memory |
| Google Drive (`9a046c08…`) | File storage, dual-tree | KEEP | Healthy per memory |
| Google Calendar (`9446971d…`) | Scheduling | KEEP | Healthy per memory |
| Gmail (`b0fe8cac…`) | Email | KEEP | Healthy per memory |
| Stripe (`f1a38a81…`) | **LIVE account** | KEEP — **read-only by convention** | Confirm no write tools called during validation |
| Crypto.com Exchange (`4bce9142…`) | Order book, ticker | KEEP — **read-only by convention** | Memory rule applies |
| Blockchain explorer (`3d788b90…`) | ~90 chains | KEEP | Useful for crypto research |
| LunarCrush (`b2b75e8f…`) | Sentiment | KEEP per founder decision | Paywalled — flag in responses, don't disconnect |
| Chrome (`Claude_in_Chrome`) | Browser DOM | KEEP | Healthy |
| Chrome (`Control_Chrome`) | Browser tabs | **REDUNDANT** with above | **Disable** — pick one Chrome MCP |
| computer-use | Desktop control | KEEP | Healthy |
| PowerPoint / Word (Anthropic) | Office docs | KEEP | Useful for deck export |
| pdf-viewer | PDF annotation | LOW USE | Disable per §4.2 |
| cowork / cowork-onboarding | Cowork meta | KEEP cowork; cowork-onboarding is one-shot | — |
| mcp-registry | Plugin discovery | KEEP | — |
| scheduled-tasks | Cron-like jobs | KEEP — **needed for weekly digest** | — |
| visualize | Diagrams/charts | KEEP | Useful for dashboards |
| workspace (bash) | Sandbox shell | KEEP | — |

### 5.2 Gaps (MCPs you'd benefit from)

| Missing | Why it'd matter |
|---|---|
| **GitHub** | You push to `3nz5789/coinscope-ai` constantly. Today this requires bash + SSH on user's Mac. A GitHub MCP would let Scoopy open issues, read PR diffs, and check workflow status from chat. |
| **Telegram** | @ScoopyAI_bot is a critical alert channel. No MCP means you can't verify alert delivery from chat — only the user can confirm. |
| **Binance Testnet** | The engine talks to Binance directly, but Scoopy can't query the testnet account state (balance, open positions, fills) from chat. Live positions check requires hitting `/journal` via Engine API only. |
| **DigitalOcean** | COI-40 VPS deployment is the active blocker. A DO MCP would let Scoopy check droplet status without browser pivots. |

### 5.3 Risk callouts

1. **Stripe is LIVE** (`acct_1Fpg5iAnTwL0DrQw "CoinScopeAI, LLC"`). With no real customers in validation phase, every Stripe write tool (`create_customer`, `create_price`, `create_invoice`, `cancel_subscription`, `create_refund`, etc.) is high-risk. Memory enforces read-only-by-convention; consider hardening this with a connector-allowlist if Cowork supports it.
2. **Crypto.com Exchange MCP** has `get_book / get_trades / get_tickers` only — no write surface visible. ✓ structurally read-only.
3. **Two Chrome MCPs** is unusual and likely accidental. Prune one to reduce ambiguity for future tool selection.

---

## Section 6 — Prioritized action plan

Ordered by leverage / risk-reduction.

### P0 — Do this week (capital-preservation critical)

1. **Run `scripts/drift_detector.py`** end-to-end. Capture findings.
2. **Fix `Validation_Phase_Exit_Memo_TEMPLATE.md` D3 line** (the "0 trades >20x" criterion). Single most consequential leverage residue.
3. **Sweep-fix the other 13 files** with stale 20x. Diff-review carefully.
4. **Delete `project_engine_specs.md` from memory.** Stale leverage cap is dangerous if recalled.
5. **Patch CLAUDE.md** with the 3 inserts from §1.3 (URLs, jurisdictional posture, validation phase dates).

### P1 — Do this sprint (config hygiene)

6. **Wire drift-detector into pre-commit** + a weekly scheduled task.
7. **Re-index `MEMORY.md`** per §2.3.
8. **Strike pricing block from `project_current_state.md`**, replace with framework pointer.
9. **Disable zoom-plugin, human-resources, slack-by-salesforce, common-room, apollo, customer-support** plugins.
10. **Disable one of the two Chrome MCPs.**
11. **Delete or rewrite `instruction_project_management.md`** (mandate expired).

### P2 — Next 2 weeks (capability expansion)

12. **Build `daily-status` skill** (Engine API roll-up — top of `enhancement-audit-2026-05-02.md` list).
13. **Build `kill-switch-protocol` skill.**
14. **Connect GitHub MCP.**
15. **Connect Telegram MCP** (or document the workaround clearly).

### P3 — Defer until P0/P1 phase exit

16. Re-enable customer-support plugin when P0 cohort opens.
17. Re-evaluate apollo/common-room when sales motion starts.
18. LunarCrush upgrade decision (P2 vendor scope).

---

## Appendix A — File:line index of stale 20x leverage references

(Live, non-archived. Run drift-detector for the canonical authoritative list.)

```
Validation_Phase_Exit_Memo_TEMPLATE.md:73
business-plan/_data/operations/Validation_Phase_Exit_Memo_TEMPLATE.md:73
Vendor_Failure_Mode_Mapping_v1.md:14
business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md:14
Business_Plan_v1.md:29
README.md:136
docs/runbooks/daily-market-scan-runbook.md:230,306
docs/architecture/data-flow.md:113
docs/risk/risk-framework.md:42
docs/risk/position-sizing.md:15,57
docs/ml/confidence_scoring_baseline.md:81
docs/backend/configuration.md:95
mvp-readiness-checklist.md:61
business-plan/_data/operations/mvp-readiness-checklist.md:61
```

## Appendix B — Master prompt diff (proposed)

```diff
 ━━ Environment rules ━━
 - Python 3.11+ with a virtual environment.
 - Binance Testnet only. Never place real orders.
-- Currently in 30-day validation phase. No core engine changes.
+- Validation phase: started 2026-04-10 · COI-41 · target end 2026-05-10. No core engine changes during validation.
+- Connector health is a first-class concern — verify on touch, audit on health check.

 ━━ Key resources ━━
-- Engine API (dev): http://localhost:8001
-  Endpoints: /scan, /performance, /journal, /risk-gate, /position-size, /regime/{symbol}
-- Primary dashboard: https://www.coinscope.ai
+- Engine API (dev): http://localhost:8001 — local only
+- Engine API (prod): https://api.coinscope.ai — read-only from chat
+  Endpoints: /scan, /performance, /journal, /risk-gate, /position-size, /regime/{symbol}, /config, /circuit-breaker
+- Primary app/dashboard: https://app.coinscope.ai (canonical 2026-04-23)
+- Marketing site: https://coinscope.ai (separate surface — do not conflate)
 - GitHub: 3nz5789/coinscope-ai
 - Telegram: @ScoopyAI_bot (Chat ID: 7296767446)

+━━ Jurisdictional posture (locked 2026-05-01) ━━
+- Founder: UAE-based, sole proprietor (no entity yet — pending counsel).
+- Target: UAE/MENA + global English. **US persons blocked at signup** until counsel returns the no-investment-advice memo.
+- All GTM/marketing/sales copy must be consistent with the US block.

 ━━ Operating principles ━━
-- Read project skills (SKILL.md in CoinScopeAI Design System) before any task.
+- Read project skills (SKILL.md files under skills/ and skills_src/) before any task.
+- Before editing any canonical surface (CLAUDE.md, framework, manifest, decision-log), run `scripts/drift_detector.py` and address findings.
```

---

**End of audit.**
