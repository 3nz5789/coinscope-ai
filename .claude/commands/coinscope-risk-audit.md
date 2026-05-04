---
name: coinscope-risk-audit
description: Audit current risk configuration against canonical caps and PCC v2 — per-symbol leverage, account-level DD/daily-loss/positions/heat, override flags, and any silent bypasses. Use to verify nothing has drifted from the canonical numbers in CLAUDE.md and the v1 framework.
triggers:
  - "audit our current risk settings"
  - "check configs against PCC v2"
  - "are any symbols bypassing the 10x rule?"
  - "risk configuration sanity check"
  - "is anything drifting from canonical?"
allowed-tools: Bash(python3 *), Read, Grep
inputs:
  required:
    - none           # auto-discovers configs in repo
  optional:
    - target_paths   # default: engine/**, services/**, .env*, configs/**
phase_constraint: Read-only audit. Any config change routes through `coinscopeai-premortem` + decision log; this command produces remediation diffs as proposals, not commits.
---

# CoinScopeAI — Risk Configuration Audit

Catches the kind of drift that produced the 20x → 10x slip. Pairs with `drift-detector` (which audits canonical docs); this audits **runtime configs**.

## Canonical caps (single source of truth — CLAUDE.md)

| Cap | Value | Reference |
|---|---|---|
| Max leverage | **10x** | PCC v2 §8 Capital Cap, locked 2026-05-01 |
| Max drawdown | **10%** | account hard stop |
| Daily loss limit | **5%** | 24h rolling, halts trading |
| Max open positions | **5** | concurrent, revised 2026-05-03 |
| Position heat cap | **80%** | per position, blocks new entries |

If any config exceeds, weakens, or silently bypasses any of these → flag as drift.

## Steps

### 1. Discover configs
Search for risk-related settings in:
- `.env`, `.env.example`
- `engine/**/*.py`, `engine/**/*.yaml`, `engine/**/*.toml`
- `services/**/config*`
- `configs/**`
- Any DB seed file under `db/` or `migrations/` referencing risk caps

Patterns to grep for: `leverage`, `LEVERAGE`, `max_drawdown`, `daily_loss`, `max_positions`, `heat`, `MAX_POS`, `cap`.

### 2. Normalize into one table
Build a synthetic table — one row per (scope, cap) pair:

```
| scope          | cap              | declared | canonical | status |
| global         | max_leverage     | 10x      | 10x       | OK     |
| BTCUSDT        | max_leverage     | 12x      | 10x       | DRIFT  |
| global         | max_drawdown     | 0.10     | 10%       | OK     |
| global         | daily_loss_limit | 0.07     | 5%        | DRIFT  |
| global         | max_positions    | 3        | 5         | STALE  |  ← old value, not a bypass but should be reconciled
| global         | heat_cap         | 0.80     | 80%       | OK     |
```

Statuses:
- **OK** — matches canonical.
- **DRIFT** — exceeds or weakens canonical (action required).
- **STALE** — within canonical but using the older value (e.g., 3 positions when canonical revised to 5).
- **OVERRIDE** — flag-gated (whitelist, debug, test_mode); document it explicitly.
- **MISSING** — cap not declared at all (silent bypass risk).

### 3. Edge-case scan
Look for:
- "debug", "whitelist", "test_mode", "internal_only" flags that could bypass caps.
- Per-symbol overrides that exceed global caps.
- Conditional code paths where caps only apply on some branches.
- Mock-mode configs that disable caps for testing — must be unreachable in production builds.

### 4. Propose remediation
For each DRIFT or MISSING row:
- Concrete diff: file, line, current → proposed value.
- Severity: HIGH (DRIFT or MISSING) / MEDIUM (STALE) / LOW (OVERRIDE with documentation gap).
- Phase impact: HIGH must be addressed during validation phase even though the engine is frozen — this is a config issue, not engine-code, and is in scope.

### 5. Optional: CI guard
Propose a CI/boot check that re-runs this audit on every deploy:
- Fails build on any HIGH (DRIFT or MISSING).
- Warns on MEDIUM (STALE) or LOW (OVERRIDE).

Drop the script under `scripts/risk_config_audit.py` mirroring the `drift_detector.py` pattern.

## Output format

```
RISK AUDIT — {YYYY-MM-DD}
phase: P0 (validation cohort)
canonical source: CLAUDE.md (v3, 2026-05-04)

SUMMARY
{x} OK | {y} DRIFT | {z} STALE | {w} OVERRIDE | {v} MISSING

CONFIG TABLE
{the normalized table from step 2}

ISSUES (ranked)
HIGH
  1. {file:line} max_leverage 12x on BTCUSDT — exceeds 10x cap.
  2. ...
MEDIUM
  ...
LOW
  ...

REMEDIATION (ordered patch list)
1. {file:line} → change `12` to `10`
2. ...

OPTIONAL: CI GUARD
Propose `scripts/risk_config_audit.py` mirroring `drift_detector.py`.

NOTE
Engine code is frozen during validation phase, but config corrections are in scope for HIGH issues. Any cap-value change routes through `coinscopeai-premortem` and the decision log.
```

## Anti-patterns

- Auto-applying remediations without going through the decision log for cap-value changes.
- Treating STALE rows as DRIFT — they're misalignment, not bypass.
- Ignoring `mock_mode` / `test_mode` flags — those are the most common silent bypass vector.
- Auditing only `.env` — many configs live in code or DB seeds.
- Calling the audit "complete" without checking per-symbol overrides.

## Cross-references

- Sister audit (canonical docs): `skills_src/drift-detector/SKILL.md`
- Caps: `skills/coinscopeai-trading-rules/SKILL.md`
- Premortem (gate for cap-value changes): `skills/coinscopeai-premortem/SKILL.md`
- Risk pre-flight: `skills_src/risk-pcc-pre-flight/SKILL.md`
- Source: CLAUDE.md §Risk thresholds (v3, 2026-05-04)
