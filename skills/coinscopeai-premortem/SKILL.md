---
name: coinscopeai-premortem
description: Risk-first pre-mortem using Tiger / Paper Tiger / Elephant taxonomy with a mandatory 4-question verification gate. Operationalizes the anti-overclaim and risk-first principles into a checkable artifact. Use before locking any framework section, moving any PCC gate (G1-G4), changing any canonical risk threshold (drawdown, daily loss, leverage, max positions, heat cap), or shipping any decision that touches engine config (.env, CLAUDE.md, master-prompt-v2.md). Triggers on "premortem", "what could go wrong", "risk check before", "tigers and elephants", "verify before flagging", "before we lock", "before we ship".
---

# CoinScopeAI Pre-Mortem

Adapted from Gary Klein / Shreyas Doshi premortem with a verification gate that kills false-positive risk flags. Output is YAML, persisted to `business-plan/_premortems/`, cross-referenced from the decision log.

## When to use

- Before locking any framework section (`00-framework.md` through `16-scenario-planning.md`)
- Before moving any PCC gate (G1 → G2, etc.)
- Before changing any canonical risk threshold (max drawdown 10%, daily loss 5%, max leverage 10x, max open positions 5, heat cap 80%)
- Before shipping any decision that touches engine config (`.env`, `.env.example`, `master-prompt-v2.md`, `CLAUDE.md`)
- Before opening a Linear issue marked "irreversible" or "production-affecting"
- Before any change to the validation cohort (cap 40, P0, May 2026)

## When NOT to use

- Routine code review — use `engineering:code-review` instead
- Engine code changes during validation phase — engine is frozen, no premortem needed because no change should happen
- Documentation typos, copy edits, formatting fixes — overhead exceeds value
- Personal scratch work in `_scratch/` — not production-affecting

## Process

### Step 1 — Pattern-match (Pass 1, raw)

Scan the artifact (plan, code, threshold change, framework section, gate move). List every risk that pattern-matches as concerning. Do NOT filter yet.

Output goes into the `potential_risks:` list of the YAML.

### Step 2 — Verification gate (Pass 2, mandatory)

For each finding in `potential_risks`, answer 4 questions BEFORE promoting to tiger:

| Question | Pass condition |
|----------|----------------|
| `context_read` | Did I read ±20 lines around the finding? |
| `fallback_check` | Is there a try/except, `if exists()`, or else branch I missed? |
| `scope_check` | Is this in scope for the current change? |
| `dev_only_check` | Is this in `__main__`, `tests/`, or dev-only code? |

**If ANY answer is "no" or "unknown" → NOT a verified tiger.**

Demote to:
- `paper_tigers:` — cite the mitigation that EXISTS, with file:line
- `false_alarms:` — cite the reason it was cleared

### Step 3 — Required evidence per tiger

Every entry under `tigers:` MUST include `mitigation_checked:` — explicit text describing what you looked for and did NOT find. If you cannot fill this field with specific evidence, it is not a verified tiger.

### Step 4 — Categorize

| Category | Definition |
|----------|------------|
| **Tiger** | Verified threat. Will hurt if not addressed. Has `mitigation_checked` evidence. |
| **Paper Tiger** | Looked threatening, but mitigation exists. Cite the mitigation location. |
| **Elephant** | Unspoken concern. The thing nobody wants to raise. Often process or scope. |

### Step 5 — Decision

For each HIGH-severity tiger, present via AskUserQuestion:

- `accept_with_log` — record in `business-plan/_decisions/decision-log.md` with rationale
- `mitigate_first` — update plan, re-run premortem
- `research_options` — spawn research, return with 2-4 mitigation options
- `discuss` — specific risk conversation

### Step 6 — Persist

Write YAML to `business-plan/_premortems/YYYY-MM-DD_HH-MM_topic.yaml` using `business-plan/_premortems/_template.yaml` as the skeleton.

If tied to a decision, cross-reference from `business-plan/_decisions/decision-log.md`.

If tied to a session, cross-reference from the session handoff under `business-plan/_handoffs/`.

## Severity policy

| Severity | Blocking? | Action |
|----------|-----------|--------|
| HIGH | Yes | Must address or explicitly accept in decision log |
| MEDIUM | No | Inform user, recommend addressing |
| LOW | No | Note for awareness |

## Anti-patterns

- **Don't flag based on pattern-matching alone.** Run the verification gate.
- **Don't skip `mitigation_checked`.** No evidence → not a tiger.
- **Don't use this for routine review.** Use `engineering:code-review` for normal PR review.
- **Don't run on the engine during validation phase.** Engine is frozen until the 30-day cohort closes.
- **Don't run premortem inside a premortem.** No recursive analysis — escalate to user instead.

## Output contract

Always YAML. Always under `business-plan/_premortems/`. Always with the verification gate applied. Always with explicit `mitigation_checked` for every tiger. Always categorized into tigers / elephants / paper_tigers / false_alarms.

## Cross-references

- Template: `business-plan/_premortems/_template.yaml`
- Handoff template: `business-plan/_handoffs/_template.yaml`
- Decision log: `business-plan/_decisions/decision-log.md`
- Source pattern: parcadei/Continuous-Claude-v3 `.claude/skills/premortem/SKILL.md` (extracted 2026-05-04)
- Reference: Gary Klein (HBR 2007), Shreyas Doshi pre-mortems framework
