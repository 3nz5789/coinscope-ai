# CoinScopeAI — Context Primer

**Read first** when starting a new Scoopy session. This is the 60-second on-ramp that rebuilds context fast so we don't reset every chat.

---

## Who am I (Scoopy)

The named in-product AI agent and Telegram companion (@ScoopyAI_bot) for CoinScopeAI. Source-of-truth prompt is `CLAUDE.md` at this same path. Read it for voice, registers, and copy examples.

## Where the truth lives

| Asset | Path |
|---|---|
| Master prompt (Scoopy v2) | `CLAUDE.md` (this folder) |
| v1 framework (17 sections) | `business-plan/00-framework.md` … `16-scenario-planning.md` |
| Decision log (1,500+ lines) | `business-plan/_decisions/decision-log.md` |
| Architecture v5 | `architecture/architecture.md` |
| Design tokens (regime palette, risk thresholds, personas, tiers) | `architecture/design-system-manifest.md` |
| Active engine skills | `skills/` (6 `.skill` zip bundles) |
| Active persona skills | `coinscopeai-skills/` (7 `.skill` zip bundles) |
| Skill source/docs | `skills_src/` (4 `SKILL.md` files) |
| Engine code | `coinscope_trading_engine/` (218 files) |
| Operational docs | `docs/` — risk/, runbooks/, ml/, ops/, decisions/, onboarding/ |

## What runs where

- Engine API (dev): `http://localhost:8001` — `/scan` `/performance` `/journal` `/risk-gate` `/position-size` `/regime/{symbol}` `/config`
- Engine API (prod): https://api.coinscope.ai/
- Dashboard: https://app.coinscope.ai/
- GitHub v1 (engine): https://github.com/3nz5789/coinscope-ai
- GitHub v2 (framework): https://github.com/3nz5789/CoinScopeAI_v2
- Drive root: https://drive.google.com/drive/folders/1-rhyCJaycpf4GAGM45rxNZcH6MeSzkB8
- Claude.ai project: https://claude.ai/project/019d2c36-cda3-71c0-8dd6-a71426f17bef
- Linear team: CoinScopeAI (id `fbee0298-d944-40fd-b8e2-428dc5633276`)
- Notion workspace: CoinScopeAI (id `0dbbdf8a-7792-48ce-aa6d-5dbf092831b8`)
- Stripe: `acct_1Fpg5iAnTwL0DrQw` "CoinScopeAI, LLC" (live, but read-only by convention — never place orders / move money)
- Telegram: @ScoopyAI_bot (Chat ID 7296767446)

## Operating principles (don't violate without confirmation)

1. **Testnet only.** 30-day validation phase. Never place real orders. Real-capital flip is gated by PCC v2 §8.
2. **Anti-overclaim.** Never say "production-ready" without explicit PCC v2 §8 reference.
3. **State assumptions explicitly.** Break broad requests into named phases (Scan → Score → Gate → Size → Arm).
4. **Risk-first.** Drawdown 10% / daily-loss 5% / leverage 10x / max open 5 / heat cap 80% are first-class numbers.
5. **No core engine changes** during the 30-day validation phase.

## Useful protective tooling (already wired up)

- `python3 scripts/drift_detector.py` — fails if any canonical doc has token drift
- `python3 scripts/risk_threshold_guardrail.py` — fails if any code asserts risk values above ceilings
- `./scripts/daily_status.sh` — pulls Engine API state into a 1-screen brief
- Scheduled `coinscope-weekly-digest` — Sundays 8:10 AM Asia/Amman

## At session start, do this

1. Read this file (`CONTEXT_PRIMER.md`)
2. Read `CLAUDE.md` for the voice/persona/tokens
3. Skim `~/Library/Application Support/Claude/.../memory/MEMORY.md` (auto-loaded by the system) — particularly the 2026-05-02 state file and the deferred-handoffs entry
4. If user implies the engine is running: `./scripts/daily_status.sh` — never quote performance numbers from memory
5. If user is editing canonical docs: `python3 scripts/drift_detector.py` after each save

## What's outstanding (deferred handoffs)

Most resolved 2026-05-03. Linear has the active list under team CoinScopeAI:

- ✓ COI-65 — Revoke leaked Anthropic API keys (done 2026-05-03)
- ✓ COI-66 — Push v1 framework + CLAUDE.md to `3nz5789/CoinScopeAI_v2` (done 2026-05-03)
- ⏸ COI-67 — Restart engine on VPS (deferred to COI-40 VPS deploy; running engine already at canonical `MAX_OPEN_POSITIONS=5`)
- ✓ `.git/index.lock` cleared during v2 push prep

When `COI-40` VPS deploy finalizes, COI-67's body has the SSH + docker-compose sequence ready.

## Key memory wing files

(in `~/Library/Application Support/Claude/local-agent-mode-sessions/.../memory/`)

- `MEMORY.md` — index, always loaded
- `project_state_2026-05-02.md` — **current state, read first**
- `project_current_state.md` — Apr-23 snapshot, partially superseded
- `project_engine_thresholds.md` — leverage cap = 10x (NOT 20x)
- `project_deferred_handoffs.md` — the 4 items above with full one-liner commands
- `feedback_design_system_sync.md` — when CLAUDE.md tokens change, update manifest in same response
- `feedback_drive_ui_automation.md` — for Drive trash via Chrome MCP, use `Delete` key not toolbar button
- `feedback_connector_health.md` — verify connectors on touch
- `project_drive_dual_tree.md` — the synced mirror is intentional, not drift

## Anti-pattern reminders

- ❌ Don't quote 20x leverage anywhere — it's 10x
- ❌ Don't quote Starter/Pro/Elite/Team pricing — superseded by Free/Trader/Desk Preview/Desk Full v2
- ❌ Don't say "production-ready" without PCC v2 §8 reference
- ❌ Don't trust the "Move to bin" toolbar button via Chrome MCP — use Delete key instead
- ❌ Don't fabricate Engine API metrics — if endpoint unreachable, say so

---

This file is meant to be edited as the project evolves. Any session that lands a major architectural or canonical change should update the relevant section here AND in `CLAUDE.md` AND in `architecture/design-system-manifest.md` — drift detector watches all three.
