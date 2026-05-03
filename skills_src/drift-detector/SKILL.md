---
name: drift-detector
description: Run a consistency check across CoinScopeAI's canonical documents (CLAUDE.md, design-system-manifest, business-plan/*.md, decision-log) and flag drift in risk thresholds, regime palette, persona names, tier prices, and brand-voice rules. Use when any canonical doc has been edited, before merging changes to business-plan/, or as part of a session-start audit.
---

# Drift Detector

A protective check that catches the kind of regression that produced the 20x → 10x leverage slip earlier this project.

## When Scoopy should run this

- **After editing CLAUDE.md** or the design-system manifest
- **Before committing** any change to `business-plan/` or `_decisions/decision-log.md`
- **At session start**, when the user asks for a project health check
- **Before declaring** any document "synced" or "canonical"

## What it checks

Across these 10 files:
- `CLAUDE.md`
- `architecture/design-system-manifest.md`
- `business-plan/00-framework.md`
- `business-plan/01-executive-summary.md`
- `business-plan/05-product-strategy.md`
- `business-plan/06-pricing-monetization.md`
- `business-plan/09-brand-messaging.md`
- `business-plan/12-risk-compliance-trust.md`
- `business-plan/14-launch-roadmap.md`
- `business-plan/_decisions/decision-log.md`

It flags violations of these canonical rules:

| Rule | What it catches |
|---|---|
| `20x_leverage` | Any live mention of 20x (the cap is 10x per PCC v2 §8) |
| `old_pricing_19_49_99_299` | Pre-Track-B prices ($19/$49/$99/$299) |
| `production_ready_no_context` | "production-ready" used without PCC v2 context (warning, not error) |
| `leverage_cap_mismatch` | A line asserting a leverage cap that's not 10x |
| `tier_price_mismatch` | A tier asserted at a price ≠ canonical $79/$399/$1,199 |
| `regime_hex_missing` | A file enumerates regime palette but is missing a canonical hex |

## How it differentiates real drift from valid context

A line counts as **valid context** (skipped) when it contains any of:
- "supersede", "supersedes", "fixed", "→", "previously", "v1 (pre-"
- "anti-overclaim", "never say", "rule:", "disclaimer:"
- "do not", "anything referencing"
- Or it contains a **price range** like `$40–$120` (a band, not an assertion)

This dramatically reduces false positives from changelog notes, rule statements, and competitive market-range tables.

## How to run

```bash
# Default: human-readable, exits 1 if drift found
python3 scripts/drift_detector.py

# Machine-readable JSON
python3 scripts/drift_detector.py --json

# One specific rule
python3 scripts/drift_detector.py --rule tier_price_mismatch

# Different project root (not usually needed)
python3 scripts/drift_detector.py --root /some/other/path
```

## Exit codes

- **0** — No drift found, OR only warnings (use `--json` and inspect manually if you want to be strict on warnings)
- **1** — At least one error-severity finding

## Adding new canonical rules

Edit `CANONICAL_TOKENS` and `FORBIDDEN` at the top of `scripts/drift_detector.py`:

```python
CANONICAL_TOKENS = {
    "max_leverage": "10x",
    # ...
}

FORBIDDEN = {
    "old_pricing_19_49_99_299": (
        r"\$19\s*/\s*\$49\s*/\s*\$99\s*/\s*\$299",
        "Old pricing replaced 2026-05-01.",
    ),
    # ...
}
```

When adding rules: also add a quick test by running the detector on a known-clean state to confirm zero false positives.

## Authoritative locations

- Source: `scripts/drift_detector.py`
- This skill doc: `skills_src/drift-detector/SKILL.md`
- Updates to canonical tokens trigger this skill's manifest version bump.
