# Runbook — Mirror v1 framework deltas to CoinScopeAI_v2

**Task #75** · closes deferred handoff #2 from `project_state_2026-05-02.md` · **owner: Mohammed (manual run on Mac)**

## Why this exists

Five v1 working-tree files were authored on 2026-05-03 but were never tracked in v1's git history — they belong canonically in `3nz5789/CoinScopeAI_v2`. The v2 repo's HEAD is still `3d6362d` (yesterday) and needs to advance.

Cowork can't push because the sandbox has no GitHub credentials. This script runs on your Mac, where your SSH key reaches both the v1 working tree and the local v2 clone.

## Files mirrored

| Path (v1-relative)                                                      | Bytes  | SHA1 (captured 2026-05-03 17:50) |
| ----------------------------------------------------------------------- | -----: | -------------------------------- |
| `Business_Plan_v1.md`                                                   | 34,634 | `92fbcfb8…cd27`                  |
| `Vendor_Failure_Mode_Mapping_v1.md`                                     | 11,664 | `36bf1a13…3ed6`                  |
| `business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md`      | 11,664 | `36bf1a13…3ed6` *(same content)* |
| `business-plan/05-product-strategy.md`                                  | 37,379 | `5bebe7a0…c01a`                  |
| `scripts/drift_detector.py`                                             | 12,577 | `c66e05a3…324a`                  |

The drift_detector delta is the new `MINIMUM_SIZES_BYTES` file-size tripwire (catches CLAUDE.md-style accidental clobbers like the 144-byte and 58-byte ones from 2026-05-03). v2 inherits that protection by virtue of receiving the file.

## Pre-flight (do this once, on your Mac)

The v2 clone must exist and be clean.

```bash
# Confirm the clone is there, on its default branch, with a clean working tree
cd ~/Documents/Claude/Projects/CoinScopeAI_v2
git status                # should show "nothing to commit, working tree clean"
git symbolic-ref --short HEAD     # confirm branch name (likely main)
git rev-parse --short HEAD        # should print 3d6362d (per 05-02 state snapshot)
```

If the v2 clone doesn't exist:

```bash
git clone git@github.com:3nz5789/CoinScopeAI_v2.git \
  ~/Documents/Claude/Projects/CoinScopeAI_v2
```

If the v2 working tree is dirty, resolve first — the script will refuse to proceed otherwise (intentional).

## Run

```bash
cd ~/Documents/Claude/Projects/CoinScopeAI
./scripts/mirror-v1-deltas-to-v2.sh
```

Override `V1` / `V2` env vars if your paths differ from the defaults.

## What the script does (7 phases)

1. **Preflight v1** — verifies all 5 source files exist and SHA1-match the captured values. Bails if anything has drifted since this script was generated.
2. **Preflight v2** — confirms the v2 clone exists, is on a branch (not detached HEAD), is clean, and `git pull --ff-only`s.
3. **Copy** — `cp` the 5 files into v2 (with `mkdir -p` for missing parents).
4. **Verify** — re-SHA the v2 copies; must match v1.
5. **Stage** — `git add` only the 5 files.
6. **Commit** — `GIT_EDITOR=true git commit -m …` (no vim drop-in).
7. **Push + drift detector** — push to `origin/<branch>`, then run `scripts/drift_detector.py` from v1 to confirm canonical files still pass.

## Lessons baked in (do not regress)

- `GIT_EDITOR=true` forces non-interactive commit — even if a future merge sneaks in.
- No `grep -c` inside `&&` chains. `grep -c` on a no-match returns 0, which `set -e` treats as failure and aborts the chain. The script uses `wc -l` after assignment instead.
- Pre-flight SHA1 check on v1 sources — fails closed if the script's idea of "today's deltas" no longer matches reality.
- Idempotent — re-running after a successful push exits 0 at Phase 5 ("nothing to commit").

## After it's pushed

Update memory:

```bash
# project_state_2026-05-02.md should record:
#   v2 HEAD: 3d6362d → <new short SHA>
# and remove deferred handoff #2 from the outstanding list.
```

If the v1 working tree has unrelated unfinished merge state (it does, as of 2026-05-03 evening), that's a **separate** concern not addressed by this runbook — Task #75 only covers the v2 mirror.

## Failure modes

| Exit code | Meaning                                                     | Recovery                                                  |
| --------: | ----------------------------------------------------------- | --------------------------------------------------------- |
|         2 | v1 directory missing                                        | Re-check `V1` path                                        |
|         3 | v1 source SHA1 mismatch (sources drifted)                   | Inspect diff manually; regenerate script if intentional   |
|         4 | v2 clone missing                                            | Clone per Pre-flight section                              |
|         5 | v2 in detached HEAD                                         | `git checkout main` (or whichever branch) and re-run      |
|         6 | v2 working tree dirty                                       | Resolve (`git stash`, commit, or revert) and re-run       |
|         7 | Post-copy SHA mismatch                                      | Filesystem issue; check disk/permissions                  |
|         8 | drift_detector.py FAIL                                      | Investigate canonical-file drift — separate from mirror   |

## Known gotchas

- **Read-only destinations in `business-plan/_data/operations/`.** All files in this directory in the v2 clone were observed at mode `0400` (`-r--------`) on 2026-05-03. Plain `cp` fails on read-only destinations with "Permission denied". Script uses `cp -f` to unlink + recreate; you must own the file (you do, `mac:staff`). No xattrs / Drive-sync involved — just restrictive perms baked in by some prior generation step.
- **Partial-state recovery.** If a run aborts mid-Phase-3, the files that did copy land as untracked (`??`) in v2. The next run's Phase 2 dirty check will refuse. Clean with `cd ~/Documents/Claude/Projects/CoinScopeAI_v2&& git status --short` then `rm -f` the listed `??` paths.
