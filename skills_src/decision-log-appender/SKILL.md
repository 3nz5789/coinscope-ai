---
name: decision-log-appender
description: Append a structured entry to business-plan/_decisions/decision-log.md. Use when the user says "log this decision", "add to the decision log", "record that we decided", "note: we're going with X", or in any situation where a non-trivial scope/architecture/threshold/pricing call has been made and should be preserved as an audit trail. The decision log is the project's source-of-truth for *why* — entries are immutable additive history (never edit prior entries; supersede via new entries).
---

# Decision Log Appender

The decision log (`business-plan/_decisions/decision-log.md`) is the canonical "why" record for CoinScopeAI. As of 2026-05-02 it has 64+ entries spanning vision, pricing, leverage cap, regime ML, GTM, validation phase, and more. Entries are append-only — never edit; supersede via a new entry.

## Trigger phrases

- "log this decision"
- "add to the decision log"
- "record that we decided"
- "note: we're going with X"
- "for the record, …"
- "let's lock in X"
- After any scope/architecture/threshold/pricing/strategy call that the user signals as locked

If you're unsure whether a discussion qualifies — ask the user "should I log this?" rather than logging silently.

## Entry template

Every entry uses this structure:

```markdown
---

## <YYYY-MM-DD> — <short-name>

**Status:** LOCKED | DRAFT | SUPERSEDED-BY-<later-entry>
**Decision area:** <vision | pricing | risk | architecture | gtm | ops | branding | other>
**Decided by:** Mohammed (founder)
**Discussed with:** Scoopy / <other>

### Decision

<One paragraph stating the decision in plain English. Be specific —
quote dollar amounts, dates, percentages, named entities.>

### Why

<Why this and not the alternative. What forced the call.>

### Supersedes

<Any prior decision-log entries this replaces, by date + short-name.
"None" if it's a net-new decision.>

### Cascades into

<Other documents / decisions that should reflect this.
Pattern: §<section> of <file>, plus a one-line action.>

### Notes

<Optional. Edge cases, follow-ups, "revisit if X".>
```

## Hard rules for appending

1. **Append-only.** Place new entries at the END of `decision-log.md` (after the last `---` separator). Never edit prior entries.

2. **Date and short-name.** Date is today (UTC date). Short-name is kebab-case, ≤ 5 words, descriptive. Example: `2026-05-02 — design-system-manifest-canonical`.

3. **Status.** Almost always `LOCKED`. Use `DRAFT` only if the user is still deciding. Use `SUPERSEDED-BY-<date>-<short-name>` only when adding a new entry that replaces this one.

4. **Cascades section is mandatory.** A decision with no downstream impact probably doesn't belong in the log. If you genuinely can't think of cascades, write "None — terminal note." and reconsider whether it should be logged.

5. **Quote canonical values.** If the decision references leverage cap, tier prices, regime hexes, persona names, etc., quote them exactly per CLAUDE.md. The drift-detector skill will fail otherwise.

6. **Run drift detector after.** Always:
   ```bash
   python3 scripts/drift_detector.py
   ```
   If the entry introduced drift, fix the entry (don't just remove it — that's a lossy edit).

## How to append

The cleanest path: `cat` the new entry onto the end of the log file. From the project root:

```bash
cat >> business-plan/_decisions/decision-log.md <<'EOF'

---

## YYYY-MM-DD — <short-name>

**Status:** LOCKED
**Decision area:** <area>
**Decided by:** Mohammed (founder)

### Decision

<paragraph>

### Why

<paragraph>

### Supersedes

<entries or "None">

### Cascades into

- §<section> of <file> — <action>
- <other>

EOF
```

Heredoc preserves backticks and special characters cleanly.

## Example entries to mimic

The existing log has good models. Reference patterns:

- **Pricing decision** (Trader/Desk Preview/Desk Full v2 lock — line 245+ of current log): structured, multiple cascades, supersedes prior $19/$49 series.
- **Leverage cap decision** (10x via PCC v2 §8): tight, single-purpose, references the gating doc.
- **Regime label v3 ML** (entry from Apr 22): notes the v2→v3 supersession.

When in doubt, copy the shape of one of those.

## Common mistakes to avoid

- ❌ Writing in the middle of the log to "fit chronologically." It's append-only.
- ❌ Editing the Status of an old entry. Add a new entry with `SUPERSEDED-BY-...` instead.
- ❌ Logging routine ops as decisions. The log is for non-obvious calls.
- ❌ Vague language. "We're going with the better option" is useless. State the option.
- ❌ Forgetting cascades. Every locked decision should have ≥ 1 cascade.

## See also

- `business-plan/_decisions/decision-log.md` — the log itself
- `business-plan/00-framework.md` — locking taxonomy (LOCKED / DRAFT / SUPERSEDED)
- `skills_src/drift-detector/SKILL.md` — runs after every append to catch token violations
