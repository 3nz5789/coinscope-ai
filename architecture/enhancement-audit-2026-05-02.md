# CoinScopeAI Enhancement Audit — 2026-05-02

**Scope:** Knowledge + skills + workflows + consistency. Audit-and-recommend mode (no files built without approval).

---

## 1. Current state inventory

| Surface | Count | Notes |
|---|---|---|
| Claude.ai project knowledge | 23 files | 17 framework + decision-log + architecture v5 + design-system-manifest + 3 Claude Code playbooks |
| Local `docs/` markdown files | **49 files** | Highly organized: architecture, runbooks, risk, ml, ops, decisions, onboarding, testing — *most NOT in Claude.ai project knowledge* |
| Engine module skills (`skills/*.skill`) | 7 zips | market_scanner_v2, position_sizer, risk_gate, regime_detector, performance_analyzer, trade_journal, market_scanner (legacy) |
| Persona skills (`coinscopeai-skills/*.skill`) | 7 zips | binance-api-specialist, telegram-bot-specialist, technical-indicator-expert, ai-security-risk, python-trading-architect, realtime-scanner-designer, crypto-futures-expert |
| Available CoinScopeAI-specific Skill-tool skills | 8 | architecture, engine-api, mempalace-ops, platform-sync, task-naming-standard, trading-rules, market-scanner, binance-futures-api |
| Memory wings | 12 files | Coverage solid (project state, vision, rollout, jurisdictional, thresholds, connector health, deferred handoffs, design-system sync, drive dual-tree, etc.) |
| Incidents archive | 2 postmortems | Apr 18 — duplicate orders + redis drift |
| ADRs in `docs/decisions/` | 3 | FastAPI/Uvicorn, Redis/Celery, LLM-off-hot-path |

**Big finding:** `docs/` is rich and well-organized but barely indexed in Claude.ai project knowledge. That's the highest-leverage gap.

---

## 2. Gap analysis — 4 focus areas

### A. Knowledge gaps (Claude.ai project + memory)

| # | Gap | Why it matters | Severity |
|---|---|---|---|
| A1 | `docs/risk/*` (4 files: risk-framework, risk-gate, failsafes-and-kill-switches, position-sizing) NOT in project knowledge | These define the operational risk system. Master prompt references "risk-first" but Scoopy can't cite specifics. | **HIGH** |
| A2 | `docs/runbooks/*` (8 files: daily-market-scan, daily-ops, troubleshooting, release-checklist, local-dev, cloud-deploy, digitalocean-deploy, ws-disconnect-incident) NOT in project knowledge | Operational SOPs for routine work and incident response. | **HIGH** |
| A3 | `docs/ml/*` (3 files: regime-detection, confidence_scoring_baseline, ml-overview) NOT in project knowledge | Explains the v3 regime ML referenced in CLAUDE.md. Scoopy describes regimes but can't ground the description. | MED |
| A4 | `docs/decisions/adr-0001..0003` NOT in project knowledge | Complement the decision-log; ADRs for FastAPI/Uvicorn, Redis/Celery, LLM-off-hot-path. | MED |
| A5 | `docs/onboarding/glossary.md` NOT in project knowledge | Terms used across codebase. Cheap to add. | LOW |
| A6 | `docs/ops/*` (5 files: binance-adapter, stripe-billing, telegram-alerts, exchange-integrations, stripe-billing-runbook) NOT in project knowledge | Vendor integration specifics. | MED |
| A7 | `incidents/*` postmortems NOT in project knowledge | Past incident context for ops decisions. | LOW |
| A8 | `docs/repository-map.md` + `docs/repo-audit.md` NOT in project knowledge | Engine codebase navigation. | MED |
| A9 | `docs/architecture/*` (4 files: component-map, data-flow, future-state-roadmap, system-overview) NOT in project knowledge | Companion to the canonical `architecture.md`. | MED |
| A10 | No `legal/` docs in project knowledge | Counsel Brief v2 + ToS draft are at root locally, not exposed to Scoopy. | MED |

### B. Skills / sub-agents

**Existing skills cover well:** scanning, sizing, gating, regime detection, performance, journaling, plus 7 persona skills (binance, telegram, indicators, security, etc.).

| # | Missing skill | What it does | Severity |
|---|---|---|---|
| B1 | `daily-status` | Pulls `/performance` + `/risk-gate` + `/journal` from Engine API + recent journal entries → 1-screen daily brief. The thing you'd want Scoopy to do every morning. | **HIGH** |
| B2 | `kill-switch-protocol` | When to halt + how to halt + who to alert (per `docs/risk/failsafes-and-kill-switches.md`). Capital preservation = mission-critical. | **HIGH** |
| B3 | `drift-detector` | Cross-checks leverage cap, regime colors, persona names, tier matrix across CLAUDE.md / manifest / framework / decision-log. Catches regressions like the 20x→10x slip we just fixed. | **HIGH** |
| B4 | `regime-explainer` | Calls `/regime/{symbol}`, translates the v3 ML output into plain English with bias interpretation. | MED |
| B5 | `decision-log-appender` | Structured `_decisions/decision-log.md` entry with template (date, decision, rationale, supersedes). | MED |
| B6 | `pcc-v2-gate-inspector` | Shows which of the 4 PCC gates (G1–G4) are green/yellow/red. The thing you'd ask before considering capital flip. | MED |
| B7 | `vendor-health-check` | Pings each connected vendor (CCXT, CoinGlass, Tradefeeds, CoinGecko, Claude API), reports green/yellow/red. Hits the connector-health standard. | MED |
| B8 | `backtest-summary` | Interpret backtest reports. Defer until backtest pipeline exists (P2). | LOW |

### C. Workflow automation

| # | Missing workflow | Trigger | Severity |
|---|---|---|---|
| C1 | **Weekly digest** | Schedule task (Sunday 8am) → recap of decisions, code reviews, performance, risk events | **HIGH** |
| C2 | **Validation-phase checkpoint** | Daily during P0 cohort, surfaces metrics + gate status + journal-since-last-checkpoint | **HIGH** during P0 |
| C3 | **Pre-edit drift check** | Runs drift-detector (B3) before any CLAUDE.md or framework commit | MED |
| C4 | **Session start protocol** | Scoopy's opening routine: connector health + active tasks + memory sync. (Partial in mempalace-ops skill — could be tighter.) | MED |
| C5 | **Code-review template** | Given PR/diff, applies engineering:code-review standards + the 9 architecture invariants | LOW (generic skills cover most) |
| C6 | **Decision-log appender** (also B5) | Triggered by "we decided …" phrases in chat | MED |

### D. Quality / consistency

| # | Missing guardrail | What it catches | Severity |
|---|---|---|---|
| D1 | **Drift detector** (= B3) | Token consistency across canonical surfaces | **HIGH** |
| D2 | **Risk-threshold guardrail** | Any new code referencing leverage uses 10x not 20x; new code referencing daily-loss uses 5% not other; etc. Pre-commit grep + assertion. | **HIGH** |
| D3 | **Anti-overclaim linter** | Flags "production-ready" / "live" / "deployed" use without PCC v2 §8 context. Brand voice principle #1. | MED |
| D4 | **Naming-standard linter** | Task titles per `coinscopeai-task-naming-standard`. | LOW |
| D5 | **Regime-color audit** | Hex values match canonical mint/neutral/amber/muted across docs + designs. | LOW |

---

## 3. Recommended additions — prioritized

### TOP 5 (highest leverage, do first)

| Rank | Item | Effort | Why |
|---|---|---|---|
| 1 | **A1 + A2: Upload risk + runbook docs (12 files) to Claude.ai project knowledge** | S (drag-drop) | Closes biggest gap. Scoopy gains operational depth instantly. Daily impact. |
| 2 | **B3 / D1: Build `drift-detector` skill** | M | Protects every canonical doc from regression. Would have caught 20x→10x slip auto. |
| 3 | **B1: Build `daily-status` skill** | M | Most-used routine. Single-call morning brief. |
| 4 | **B2: Build `kill-switch-protocol` skill** | S | Capital preservation. Codifies what's currently tribal. |
| 5 | **C1: Weekly digest workflow** | S (uses schedule plugin) | High-signal, low-cost recurring report. |

### QUICK WINS (S effort, useful)

- **A4:** Add 3 ADRs to project knowledge
- **A5:** Add `glossary.md` to project knowledge
- **D2:** Risk-threshold guardrail (one grep + CI assertion)
- **B5/C6:** Decision-log appender skill

### DEFER (low priority or blocked on prerequisite)

- **B8:** backtest-summary (need backtest pipeline first — P2)
- **C5:** code-review template (engineering:code-review skill already covers ~80%)
- **D4/D5:** Naming + regime-color linters (drift-detector covers most)

---

## 4. How to approve

Reply with the items you want me to build, e.g.:

- *"Build top 5"* — I do A1+A2, B1, B2, B3, C1
- *"Top 5 + quick wins"* — adds A4, A5, B5, D2
- *"Just the drift detector and daily status"* — only B3 + B1
- *"Full top-5 + show me the drift-detector design first"* — staged approval
- *"Skip A1+A2, do B1-B3 + C1"* — pick any subset

For each item I'll:
1. Show the approach in 2–3 lines before I start
2. Build it
3. Verify it works
4. Update memory + sync rules

The audit doc itself is saved at `~/Documents/Claude/Projects/CoinScopeAI/architecture/enhancement-audit-2026-05-02.md` for future reference.
