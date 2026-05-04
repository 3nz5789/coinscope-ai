---
name: risk-pcc-pre-flight
description: Mandatory pre-flight checklist before changing any of the 5 canonical risk thresholds, any PCC v2 gate criteria (G1-G4 + §8), the leverage cap, the position-concurrency cap, the heat cap, the regime palette, the persona names, or any engine config that touches the validation gate. Codifies the 7-phase reconciliation chain so changes propagate atomically across CLAUDE.md, business-plan/, docs/, .env*, scripts, decision log, claude.ai project Instructions, and Cowork project_instructions. Use BEFORE making the first edit, not after. Capital-preservation-first.
---

# Risk + PCC Pre-Flight

The change you're about to make can affect real-capital behavior. Run this checklist BEFORE editing the first file. Every phase has a verification gate — do not advance until the gate passes.

## When Scoopy should run this

Mandatory before any change to:

| Surface | Examples |
|---|---|
| **Risk thresholds** | `max_leverage`, `max_drawdown`, `daily_loss_limit`, `max_open_positions`, `position_heat_cap` |
| **PCC v2 criteria** | G1 (signal quality), G2 (execution integrity), G3 (real-capital phase 1 unlock), G4 (operational maturity), §8 (Capital Cap & Phased Ramp) |
| **Regime palette** | Any of the 4 regime hex codes or label names |
| **Personas** | Internal IDs P1/P2/P3 or names Omar/Karim/Layla |
| **Engine validation gate** | `coinscope_trading_engine/config.py` thresholds, kill-switch trigger conditions |
| **Framework lock/unlock** | Moving from "v1 LOCKED" to v2, locking a previously-draft section |

Do NOT run for: copy edits, formatting changes, adding new doc sections that don't restate canonical values.

## The 7 phases

### Phase 0 — Confirm trigger (10 seconds)

State out loud (in chat) which surface from the table above you're about to touch and why. If you can't name the surface, this skill probably doesn't apply — escalate to "Is this a canonical change?" before proceeding.

### Phase 1 — Pre-mortem (run the `coinscopeai-premortem` skill)

Per memory `feedback_premortem_required.md`: "4-question verification gate kills 50%+ false positives." Do not skip even if the change feels small — the leverage cap drift that this whole machinery exists to prevent felt small at the time.

Output of pre-mortem must include:
- Worst plausible failure mode of the proposed change
- Smallest reversible test
- Rollback procedure
- Who/what gets impacted (engine? validation cohort? real capital path? brand?)

If pre-mortem surfaces an unresolved risk: STOP. Do not proceed. Return to user with the risk.

### Phase 2 — Identify the canonical token + current value

For each value being changed, fill in:

| Field | Example |
|---|---|
| Canonical token name | `max_open_positions` |
| Current value (from CLAUDE.md) | 5 |
| Proposed new value | 4 |
| Source for new value | decision-log entry / PCC criterion / external review |
| Files where current value appears | (run `grep` to enumerate before editing — DON'T skip this) |

If the canonical token name doesn't appear in CLAUDE.md, this is not a canonical edit — different process applies.

### Phase 3 — Backup CLAUDE.md (per safety rule)

Per `feedback_claude_md_safety.md`: ANY operation that touches CLAUDE.md requires a timestamped backup FIRST.

```bash
cd /Users/mac/Code/CoinScopeAI
cp CLAUDE.md CLAUDE.md.bak.$(date +%Y%m%d-%H%M%S)
wc -c CLAUDE.md   # must be ≥ 4,000 (canonical 5,531)
```

If `wc -c` shows < 4,000: HALT. CLAUDE.md is already corrupted — recover from `~/Code/CoinScopeAI_v2/CLAUDE.md` or `git show HEAD:CLAUDE.md` BEFORE proceeding.

### Phase 4 — Reconciliation chain (the full propagation)

Edit in this order. Do not skip any layer where the token appears.

| # | Layer | What changes |
|---|---|---|
| 1 | `CLAUDE.md` | Master prompt — the canonical value |
| 2 | `business-plan/_decisions/decision-log.md` | Append a dated entry (use `decision-log-appender` skill) |
| 3 | `business-plan/<section>.md` | Any framework section that quotes the token (use `grep -rn '<token>' business-plan/` to enumerate) |
| 4 | `architecture/architecture.md` | If the change is architectural |
| 5 | `architecture/design-system-manifest.md` | If the token is a design / regime / persona token |
| 6 | `docs/**/*.md` | Runbooks, configuration docs, risk-framework, data-flow, etc. (use `grep -rn '<token>' docs/`) |
| 7 | `coinscope_trading_engine/.env`, `.env.example`, `.env.template` | If the token is an engine env var |
| 8 | `coinscope_trading_engine/config.py` | If the token is a Python config constant |
| 9 | `scripts/drift_detector.py` | Update `CANONICAL_TOKENS` dict to the new value |
| 10 | `scripts/risk_threshold_guardrail.py` | Update if applicable |
| 11 | `tests/conftest.py`, `tests/test_*.py` | Update any hard-coded threshold in test fixtures |
| 12 | Root `.env.template`, `ci.yml` | If the token leaks into root-level config |

After EACH layer, re-grep for the OLD value to confirm it's gone. The 2026-05-03 max_open_positions revision missed 6 docs the first time — multi-pass grep is non-negotiable.

### Phase 5 — Run guardrails (gate before claiming done)

```bash
cd /Users/mac/Code/CoinScopeAI
python3 scripts/drift_detector.py            # must exit 0
python3 scripts/risk_threshold_guardrail.py  # must exit 0
```

If either reports findings: fix and re-run until both clean. Do NOT advance to Phase 6 with any open findings.

### Phase 6 — Decision log + commit

6a. If you didn't already in Phase 4 step 2, append a decision-log entry now via the `decision-log-appender` skill. Required fields: date, section ref (§5/§11/§14/§16 cross-ref), area, short name, context, options considered, outcome, rollback, references.

6b. Commit the full set as ONE atomic commit:

```bash
git add -A
git commit -m "risk(<token>): <old_value> → <new_value> per <decision-log-id>

Reconciled across N files. Drift detector + guardrail PASS post-patch.
Decision log: <decision-id>
Pre-mortem: <session-or-doc-reference>"
```

One commit, one decision, one ID. Do not split into multiple commits — that's how layers slip out of sync.

### Phase 7 — Re-paste master prompt to claude.ai project + Cowork

CLAUDE.md is the source of truth, but two external surfaces hold their own STALE copy until you re-paste:

| Surface | How to refresh | Verify |
|---|---|---|
| **claude.ai project Instructions** | Open project → Instructions → ⌘A ⌘V from clipboard (after `pbcopy < CLAUDE.md` — but first back it up per Phase 3 rule). Save. | Open a fresh chat in the project, ask "what's the canonical `<token>` value?" — expect new value. |
| **Cowork project_instructions** | CoinScopeAI project → Settings → Instructions → ⌘A ⌘V from clipboard. Save. | Open a fresh Cowork chat, ask the same question. Expect same answer. |

Both must be done. Doing one and not the other = silent drift between Chat and Cowork answers.

### Phase 8 — VPS engine propagation (if applicable)

If the token is also in the engine's running `.env`, restart is required for `/config` to reflect the new value. Track under COI-40 if VPS deploy is still pending. Runbook: `docs/runbooks/vps-engine-restart.md`.

`/config` endpoint check: `curl -s https://api.coinscope.ai/config | jq .<token>` — should return new value within 60s of restart.

## Anti-patterns (will silently fail)

- ❌ Editing one file at a time and committing each separately. The `git log` tells you the change "happened" but the surfaces are out of sync mid-stream.
- ❌ Skipping the master-prompt re-paste because "the file is updated". The file is updated; the running prompts in claude.ai and Cowork are still stale.
- ❌ Asserting "locked" / "production-ready" / "PCC v2 §8 satisfied" without a documented decision-log entry + drift_detector PASS.
- ❌ Changing a token in CLAUDE.md but not in `scripts/drift_detector.py` CANONICAL_TOKENS dict — drift detector will then KEEP CATCHING the old value and reporting it as drift, until you also update the dict. (This bites every time.)
- ❌ Skipping pre-mortem on a "small" change. Every leverage-cap incident in this project's history started with "this seems straightforward."

## Templates

### Decision log entry skeleton

```yaml
- id: YYYY-MM-DD-<token>-<old>-to-<new>
  date: YYYY-MM-DD
  category: Risk
  status: Accepted
  cross_ref: [§<section>, PCC v2 §<n>]
  context: |
    <Why this change. What surfaced it.>
  options_considered:
    - opt: <new value>; rationale: <...>
    - opt: <alternative>; rationale: <why rejected>
    - opt: <status quo>; rationale: <why rejected>
  outcome: <what was decided + by whom + when>
  reconciled_in_files: [list from Phase 4 grep]
  guardrails_post_patch: drift_detector PASS, risk_threshold_guardrail PASS
  rollback: <single-step revert command + reference to backup>
  references:
    - pre_mortem: <session id or doc>
    - linear: <COI-N>
    - claude_md_backup: CLAUDE.md.bak.YYYYMMDD-HHMMSS
```

### Pickup line for next session if change is in-flight

"Mid-flight on `<token>` change (<old> → <new>). Phases 0-N done; Phase N+1 outstanding. CLAUDE.md backup at `<path>`. Decision-log id `<id>`. Drift detector last status: `<PASS|FAIL+findings>`."

## What this skill explicitly will NOT do

- Decide whether the proposed change is correct (that's the pre-mortem skill + user judgment).
- Push commits to GitHub (user discretion — runs `git commit` only).
- Restart the VPS engine (Phase 8 is a pointer, not an action).
- Skip phases for "obvious" changes. Every shortcut here has cost capital-preservation rigor in the past.

Disclaimer: testnet only, 30-day validation phase, no real capital. This skill exists so that when real-capital phase unlocks, the reconciliation rigor is already automatic.
