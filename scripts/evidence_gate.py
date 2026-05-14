#!/usr/bin/env python3
"""Evidence gate — enforces the proof / freeze / release rule.

A PR that touches risk thresholds, execution logic, regime logic, or the
canonical operator/threshold config MUST also touch at least one of the
canonical evidence destinations:

  - docs/validation/p0-evidence-pack.md   (validation proof hub)
  - docs/validation/**.md                 (any other evidence record)
  - README.md                             (Validation Phase Freeze lives here)
  - CHANGELOG.md                          (release record)
  - docs/runbooks/release-checklist.md    (release process record)

This is the codified version of the rule the README's "Start here" block
states in prose. Surfacing without enforcement makes the rule advisory;
this script makes it a hard gate.

Usage
-----
Local::

    # Diff against origin/main (default)
    python3 scripts/evidence_gate.py

    # Diff against a custom base
    python3 scripts/evidence_gate.py --base origin/release/p0

CI::

    python3 scripts/evidence_gate.py --base "origin/${{ github.base_ref }}"

Exit codes
----------
  0 — no sensitive files changed, OR a sensitive change is accompanied
      by at least one evidence touch.
  1 — sensitive files changed with no accompanying evidence. Failure.
  2 — invocation error (bad arguments, git not available, etc.).

Opt-out
-------
The CI workflow honours the `evidence-gate-exempt` PR label. Apply that
label only when a maintainer has confirmed the change is genuinely
evidence-neutral (e.g. a pure rename, a comment-only fix). The label is
auditable in the PR history; the script itself takes no opt-out flag.
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass


# Files that, when changed, require an evidence touch.
# Patterns use fnmatch semantics (** is not recursive — we expand by walking
# the matched path's segments).
SENSITIVE_PATTERNS: tuple[str, ...] = (
    # Risk gate, kelly sizer, regime detector, circuit breakers, kill switch
    "risk_management/*.py",
    "risk_management/**/*.py",
    # Paper-trading kill switch + safety gate + executor
    "services/paper_trading/safety.py",
    "services/paper_trading/kill.py",
    "services/paper_trading/order_manager.py",
    # Live execution adapter
    "engine/exchange/*.py",
    "engine/exchange/**/*.py",
    # Canonical thresholds + operator config
    "coinscope.env.example",
    "configs/environments/*.yaml",
    "configs/environments/*.yml",
    "CLAUDE.md",
    # Regime logic anywhere in the tree (HMM, classifier, regime enrichers)
    "**/regime*.py",
    "**/hmm*.py",
)

# Files that, when changed, satisfy the evidence requirement.
EVIDENCE_PATTERNS: tuple[str, ...] = (
    "docs/validation/*.md",
    "docs/validation/**/*.md",
    "README.md",
    "CHANGELOG.md",
    "docs/runbooks/release-checklist.md",
)

# Paths that are never sensitive even if they match a sensitive pattern.
# Tests are validation evidence themselves; doc-only changes to sensitive
# directories should not require a second doc change.
EXCLUDE_PATTERNS: tuple[str, ...] = (
    "tests/*",
    "tests/**/*",
    "**/test_*.py",
    "**/*_test.py",
    "docs/*",
    "docs/**/*",
    ".github/*",
    ".github/**/*",
)


@dataclass(frozen=True)
class Result:
    sensitive: tuple[str, ...]
    evidence: tuple[str, ...]
    excluded_sensitive: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.sensitive or bool(self.evidence)


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_match(path, p) for p in patterns)


def _match(path: str, pattern: str) -> bool:
    # fnmatch doesn't treat `**` as recursive; emulate it by trying the pattern
    # as-is and also with `**` collapsed to `*` on each segment count.
    if fnmatch.fnmatch(path, pattern):
        return True
    if "**" in pattern:
        # Expand `**` into 0, 1, 2, or 3 wildcard segments.
        for depth in range(4):
            expansion = "/".join(["*"] * depth) if depth else ""
            collapsed = pattern.replace("**", expansion)
            collapsed = collapsed.replace("//", "/").strip("/")
            if fnmatch.fnmatch(path, collapsed):
                return True
    return False


def changed_files(base: str) -> list[str]:
    """Return the list of files changed between ``base`` and ``HEAD``.

    Uses the three-dot form so the diff is taken against the merge base — i.e.
    only files actually touched by this branch, not files that diverged on the
    base side.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("evidence-gate: git not found on PATH", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        print(
            f"evidence-gate: git diff failed (base={base!r}): {exc.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(2)
    return [line for line in out.stdout.splitlines() if line.strip()]


def classify(paths: list[str]) -> Result:
    sensitive: list[str] = []
    evidence: list[str] = []
    excluded: list[str] = []
    for path in paths:
        is_sensitive = _matches_any(path, SENSITIVE_PATTERNS)
        is_excluded = _matches_any(path, EXCLUDE_PATTERNS)
        if is_sensitive and is_excluded:
            excluded.append(path)
            continue
        if is_sensitive:
            sensitive.append(path)
        if _matches_any(path, EVIDENCE_PATTERNS):
            evidence.append(path)
    return Result(
        sensitive=tuple(sensitive),
        evidence=tuple(evidence),
        excluded_sensitive=tuple(excluded),
    )


def report(result: Result) -> None:
    if not result.sensitive:
        print("evidence-gate: no sensitive files changed — gate not required.")
        if result.excluded_sensitive:
            print("evidence-gate: excluded (tests/docs in sensitive dirs):")
            for path in result.excluded_sensitive:
                print(f"  - {path}")
        return

    print("evidence-gate: sensitive files changed:")
    for path in result.sensitive:
        print(f"  - {path}")

    if result.evidence:
        print("evidence-gate: evidence files changed:")
        for path in result.evidence:
            print(f"  - {path}")
        print("evidence-gate: OK — rule satisfied.")
        return

    print()
    print("evidence-gate: FAIL — no evidence touch.")
    print()
    print("This PR changes risk/execution/regime/threshold code but does not")
    print("update any canonical evidence destination. Update at least one of:")
    print()
    print("  - docs/validation/p0-evidence-pack.md   (validation proof hub)")
    print("  - docs/validation/<new-record>.md       (new evidence record)")
    print("  - README.md  (Validation Phase Freeze section)")
    print("  - CHANGELOG.md")
    print("  - docs/runbooks/release-checklist.md")
    print()
    print("If this PR genuinely needs no evidence update (rename, comment fix,")
    print("etc.), a maintainer can apply the `evidence-gate-exempt` label.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence gate enforcer.")
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git revision to diff against (default: origin/main).",
    )
    args = parser.parse_args(argv)

    paths = changed_files(args.base)
    result = classify(paths)
    report(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
