#!/usr/bin/env bash
# mirror-v1-deltas-to-v2.sh
# ─────────────────────────────────────────────────────────────────────────────
# Task #75 — mirror today's v1 framework deltas into the local CoinScopeAI_v2
# clone, commit, and push to 3nz5789/CoinScopeAI_v2.
#
# Closes deferred handoff #2 from project_state_2026-05-02.md.
#
# Lessons baked in (do not regress):
#   • GIT_EDITOR=true on the commit  → no vim drop-in if -m is missed downstream
#   • No `grep -c` inside `&&` chains → grep -c returning 0 aborts under set -e
#   • Pre-flight v1 SHA1 check        → fails closed if the sources have moved
#                                       under us since the script was generated
#   • File-size sanity on copies      → catches an empty cp before commit
#
# Generated 2026-05-03 by Scoopy (Cowork session). Re-run safe (idempotent).
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

# ── Configuration ────────────────────────────────────────────────────────────
V1="${V1:-$HOME/Documents/Claude/Projects/CoinScopeAI}"
V2="${V2:-$HOME/Documents/Claude/Projects/CoinScopeAI_v2}"
EXPECTED_OLD_HEAD="3d6362d"   # v2 HEAD per 05-02 state snapshot

COMMIT_SUBJECT="framework: mirror v1 deltas (Business_Plan_v1, Vendor_Failure_Mode_Mapping_v1 ×2, 05-product-strategy, drift_detector tripwire)"
COMMIT_BODY="Refs Task #75 / deferred handoff #2 from project_state_2026-05-02.md.

Mirrored verbatim from the v1 working tree:
  - Business_Plan_v1.md (root)
  - Vendor_Failure_Mode_Mapping_v1.md (root)
  - business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md
  - business-plan/05-product-strategy.md
  - scripts/drift_detector.py (now includes MINIMUM_SIZES_BYTES tripwire)

drift_detector.py CANONICAL_FILES NOT retargeted — v2 receives the file as-is so
the two repos stay byte-identical. The scanner still walks v1-relative paths."

# Files to mirror (v1-relative paths).
FILES=(
  "Business_Plan_v1.md"
  "Vendor_Failure_Mode_Mapping_v1.md"
  "business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md"
  "business-plan/05-product-strategy.md"
  "scripts/drift_detector.py"
)

# Expected v1 SHA1s captured 2026-05-03 17:50 UTC. If a source has changed since
# then we want to know BEFORE we copy garbage into v2.
EXPECTED_SHA1=(
  "92fbcfb8093d10a04d4568b7ca9cfc0a2fe2cd27"
  "36bf1a1360a7607f0f60a5a59ac21beb7dd03ed6"
  "36bf1a1360a7607f0f60a5a59ac21beb7dd03ed6"
  "5bebe7a0e7d6e87709e86a1e0d2c03d86849c01a"
  "c66e05a3a117b1125ef694520a877bc92294324a"
)

# ── Output helpers ───────────────────────────────────────────────────────────
log() { printf '\033[1;36m[mirror]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[mirror!]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[mirror×]\033[0m %s\n' "$*" >&2; }
hr() { printf '\033[2m──────────────────────────────────────────────────────────\033[0m\n'; }

sha1_of() {
  # macOS uses `shasum`, linux usually has `sha1sum`. Both ship with macOS.
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 1 "$1" | awk '{print $1}'
  else
    sha1sum "$1" | awk '{print $1}'
  fi
}

# ── Phase 1 — preflight v1 sources ──────────────────────────────────────────
hr; log "Phase 1 / 7 — preflight v1 sources at $V1"
[ -d "$V1" ] || { err "v1 tree not at $V1"; exit 2; }

mismatch=0
for i in "${!FILES[@]}"; do
  f="${FILES[$i]}"
  exp="${EXPECTED_SHA1[$i]}"
  if [ ! -f "$V1/$f" ]; then
    err "MISSING v1: $f"
    mismatch=1
    continue
  fi
  got=$(sha1_of "$V1/$f")
  if [ "$got" != "$exp" ]; then
    warn "SHA1 mismatch for $f"
    warn "  expected: $exp"
    warn "  got:      $got"
    mismatch=1
  fi
done
if [ "$mismatch" != "0" ]; then
  err "v1 sources have drifted from the captured SHA1s. Inspect before re-running."
  err "If the new content is correct, regenerate this script (or override EXPECTED_SHA1 inline)."
  exit 3
fi
log "v1 sources verified — 5 / 5 SHA1 match"

# ── Phase 2 — preflight v2 clone ────────────────────────────────────────────
hr; log "Phase 2 / 7 — preflight v2 clone at $V2"
if [ ! -d "$V2/.git" ]; then
  err "v2 clone not at $V2 (no .git directory)."
  err "Clone first:  git clone git@github.com:3nz5789/CoinScopeAI_v2.git \"$V2\""
  exit 4
fi

cd "$V2"
v2_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
v2_head_before=$(git rev-parse --short HEAD)
log "v2 branch:       $v2_branch"
log "v2 HEAD before:  $v2_head_before  (snapshot expected $EXPECTED_OLD_HEAD)"

if [ "$v2_branch" = "DETACHED" ]; then
  err "v2 is in detached-HEAD state. Check out a branch (e.g. main) and re-run."
  exit 5
fi

# Working tree must be clean — never commit on top of unfinished work.
# We assign first, then check — never put `git status` inside an && chain because
# its exit code on "clean" is still 0 either way and the branch logic is brittle.
v2_dirty=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$v2_dirty" != "0" ]; then
  err "v2 working tree is not clean. Resolve before mirroring:"
  git status --short
  exit 6
fi

# Pull latest. ff-only so we never silently merge.
log "Pulling latest from origin/$v2_branch (ff-only)"
git pull --ff-only origin "$v2_branch"

# ── Phase 3 — copy ──────────────────────────────────────────────────────────
# Use `cp -f` so read-only destinations (mode 0400, common in business-plan/_data/
# operations/) get unlinked + recreated rather than triggering "Permission denied".
# Discovered the hard way 2026-05-03 19:03 — first run aborted at file 3/5 because
# v2/business-plan/_data/operations/Vendor_Failure_Mode_Mapping_v1.md was -r--------.
# `cp -f` only requires that the parent dir be writable + we own the file, both true.
hr; log "Phase 3 / 7 — copy files into v2 working tree (cp -f, handles read-only destinations)"
for f in "${FILES[@]}"; do
  parent="$(dirname "$f")"
  if [ ! -d "$V2/$parent" ]; then
    log "  mkdir -p $parent"
    mkdir -p "$V2/$parent"
  fi
  cp -f "$V1/$f" "$V2/$f"
  log "  copied $f"
done

# ── Phase 4 — post-copy SHA verify ──────────────────────────────────────────
hr; log "Phase 4 / 7 — verify v2 copies match v1 SHA1"
for i in "${!FILES[@]}"; do
  f="${FILES[$i]}"
  exp="${EXPECTED_SHA1[$i]}"
  got=$(sha1_of "$V2/$f")
  if [ "$got" != "$exp" ]; then
    err "post-copy SHA mismatch for v2/$f — copy did not land cleanly"
    err "  expected: $exp"
    err "  got:      $got"
    exit 7
  fi
done
log "All 5 v2 files match v1 SHAs"

# ── Phase 5 — stage ─────────────────────────────────────────────────────────
hr; log "Phase 5 / 7 — stage"
git add -- "${FILES[@]}"

# Assignment-style count — safe under set -e even when 0.
staged=$(git diff --cached --name-only | wc -l | tr -d ' ')
log "Staged $staged file(s)"

if [ "$staged" = "0" ]; then
  log "v2 already had identical content — nothing to commit. Exiting clean."
  exit 0
fi

git diff --cached --stat

# ── Phase 6 — commit (no vim) ───────────────────────────────────────────────
hr; log "Phase 6 / 7 — commit (GIT_EDITOR=true to skip vim)"
GIT_EDITOR=true git commit -m "$COMMIT_SUBJECT" -m "$COMMIT_BODY"
v2_head_after=$(git rev-parse --short HEAD)
log "v2 HEAD after commit:  $v2_head_after"

# ── Phase 7 — push & verify drift detector ─────────────────────────────────
hr; log "Phase 7 / 7 — push to origin/$v2_branch and verify drift detector"
git push origin "$v2_branch"
log "Pushed origin/$v2_branch  $v2_head_before → $v2_head_after"

# Run the canonical scanner from v1 (where CANONICAL_FILES is rooted).
cd "$V1"
log "Running scripts/drift_detector.py from v1…"
if python3 scripts/drift_detector.py; then
  log "drift_detector.py: PASS"
else
  err "drift_detector.py: FAIL — investigate. Mirror itself was clean; problem is in canonical files."
  exit 8
fi

hr
log "Mirror complete."
log "  v2 HEAD: $v2_head_before → $v2_head_after"
log "  Files mirrored: ${#FILES[@]}"
log "  Next: update project_state_2026-05-02.md memory with new v2 HEAD; drop deferred handoff #2."
