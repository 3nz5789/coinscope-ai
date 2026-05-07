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

- [x] Identify the crashing client.
  - **Ruled out:** GUI git client (Tower / GitKraken / Fork / Sourcetree /
    GitHub Desktop) and IDE git integrations (VS Code / Cursor /
    JetBrains) — none installed.
  - **Confirmed timing detail:** lockfile mtime (2026-05-04 10:16:10 UTC)
    matches the author timestamp of commit `230287e` exactly. The commit
    itself landed cleanly in history, so the locks were not left by a
    failed commit. They were re-acquired by a subsequent operation that
    was interrupted before releasing them.
  - **Inference (not confirmed):** the most plausible class of culprit is
    an agent-driven git session that was terminated between operations
    in a multi-step flow. Candidates include any of the agents installed
    on this machine that drive git on the user's behalf (Claude/Cowork,
    Manus, ChatGPT Atlas, Comet, Jasper). No log evidence currently
    available identifies which agent or whether an agent was involved at
    all; a Terminal-direct `git` session ended by sleep/force-quit/
    network failure remains a possibility.
  - **Status:** root cause not definitively established. Detection and
    recovery procedures (below) cover the failure mode regardless of
    which actor caused it.
- [x] Audit other local repos — clean across ~/Code and ~/Documents.
- [ ] Add runbook entry for safe-recovery from stale .git locks. Cover
  agent-session interruptions and Terminal-direct interruptions as
  distinct trigger classes, with the same recovery steps.
