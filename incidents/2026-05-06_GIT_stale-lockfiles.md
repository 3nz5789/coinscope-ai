---
incident_id: INC-2026-05-06-01
title: Stale .git lockfiles in canonical repo
opened_by: Mohammed
incident_commander: Scoopy (Claude)
detected_at: 2026-05-06 (during feat/agency-agents-scaffold branch promotion)
resolved_at: 2026-05-06
status: Resolved
severity: SEV3 (development tooling — no engine, trading, or capital impact)
---

## Symptom

`feat/agency-agents-scaffold` branch creation failed on 2026-05-06 with
`Unable to create '.git/HEAD.lock': File exists` and an equivalent error on
`.git/index.lock`. Diagnosis revealed both lock files dated
2026-05-04 10:16:10 UTC — exactly matching the timestamp of commit
`230287e` (the prior tip of `docs/scoopy-v3-skills-2026-05-04`).

## Cause

A git client (GUI or IDE extension — TBD) crashed mid-commit on
2026-05-04 and left the locks behind. No git processes were running at
recovery time (`pgrep -fa git` returned only the diagnostic shell).

## Impact

For ~48 hours, every git **write** operation in this repo failed silently
for any tool that checks for locks (most do). Read-only operations
(`git status`, `git log`, `git diff`) continued working, masking the
issue. No commits were lost — the prior commit completed before the
crash; only the post-commit cleanup of lockfiles was interrupted.

## Recovery

1. Confirmed lock files were empty (0 bytes) and dated two days prior.
2. Confirmed no git processes running in the workspace sandbox.
3. Removed both lock files (`rm -f .git/HEAD.lock .git/index.lock`).
4. Re-ran branch creation and commit. HEAD moved to `d85afc1`.

## Follow-up

- [ ] Identify the crashing client (GUI or IDE extension).
- [x] Audit other local repos for similar stale locks — sandbox-visible
  scope (`~/Code` full mount, `~/Documents/Claude/Projects/CoinScopeAI`
  subtree only) ran clean on 2026-05-06.
- [ ] Run the same audit on the Mac directly to cover the unmounted
  portion of `~/Documents`:
  ```
  find ~/Code ~/Documents -name "HEAD.lock" -o -name "index.lock" 2>/dev/null
  ```
- [ ] If a specific tool is identified as the root cause, add a runbook
  entry for safe-recovery so future stale-lock incidents don't require
  diagnosis from scratch.
