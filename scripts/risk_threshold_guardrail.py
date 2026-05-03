#!/usr/bin/env python3
"""
Risk Threshold Guardrail
========================

A focused subset of the drift detector: specifically guards against any new
code referencing risk thresholds with values that DON'T match the canonical
hard ceilings.

Wider scope than drift_detector.py (which only scans canonical .md files).
This one scans the entire codebase including .py, .yml, .json, .toml, .env*.

Use as a pre-commit hook or in CI.

Canonical ceilings (per CLAUDE.md v2):
  max_leverage         = 10x
  max_drawdown         = 10%
  daily_loss_limit     = 5%
  max_open_positions   = 5  (revised 2026-05-03 — supersedes 3)
  position_heat_cap    = 80%
"""

from __future__ import annotations
import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CODE_GLOBS = ["**/*.py", "**/*.yml", "**/*.yaml", "**/*.json", "**/*.toml", "**/*.env*"]
EXCLUDE_DIRS = {
    "archive", "node_modules", ".git", "__pycache__", ".venv", "venv",
    "pytest-cache-files-lw31l5ev", "manus_setup", "manus_upload",
    "legacy_2026-04",
}

# (rule_name, regex, fixer_message)
RULES = [
    (
        "leverage_cap_above_10x",
        re.compile(r"\bmax_leverage\b\s*[:=]\s*([\d.]+)", re.IGNORECASE),
        lambda m: float(m.group(1)) > 10.0,
        "max_leverage must be ≤ 10 per PCC v2 §8 (locked 2026-05-01).",
    ),
    (
        "drawdown_above_10pct",
        re.compile(r"\bmax_drawdown(?:_pct)?\b\s*[:=]\s*([\d.]+)", re.IGNORECASE),
        lambda m: float(m.group(1)) > 10.0,
        "max_drawdown ceiling is 10% (account hard stop).",
    ),
    (
        "daily_loss_above_5pct",
        re.compile(r"\b(?:max_)?daily_loss(?:_pct|_limit)?\b\s*[:=]\s*([\d.]+)", re.IGNORECASE),
        lambda m: float(m.group(1)) > 5.0,
        "daily_loss_limit ceiling is 5% (24h rolling halt).",
    ),
    (
        "open_positions_above_5",
        re.compile(r"\bmax_open_positions\b\s*[:=]\s*(\d+)", re.IGNORECASE),
        lambda m: int(m.group(1)) > 5,
        "max_open_positions ceiling is 5 (revised 2026-05-03 — supersedes earlier 3).",
    ),
    (
        "heat_cap_above_80pct",
        re.compile(r"\b(?:position_)?heat(?:_cap|_pct)?\b\s*[:=]\s*([\d.]+)", re.IGNORECASE),
        lambda m: float(m.group(1)) > 80.0,
        "position_heat_cap ceiling is 80%.",
    ),
]


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    excerpt: str
    note: str


def is_excluded(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & EXCLUDE_DIRS)


def scan(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    seen: set[Path] = set()
    for glob in CODE_GLOBS:
        for path in root.glob(glob):
            if path in seen or is_excluded(path) or not path.is_file():
                continue
            seen.add(path)
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, start=1):
                # Skip comments and quoted strings — risk_thresholds in those are documentation, not assertions.
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                for rule_name, pattern, predicate, note in RULES:
                    m = pattern.search(line)
                    if m:
                        try:
                            if predicate(m):
                                violations.append(
                                    Violation(
                                        file=str(path.relative_to(root)),
                                        line=i,
                                        rule=rule_name,
                                        excerpt=line.strip()[:120],
                                        note=note,
                                    )
                                )
                        except (ValueError, IndexError):
                            continue
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Risk threshold guardrail.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    violations = scan(args.root)
    if not violations:
        print(f"✓ Risk thresholds clean across all scanned code in {args.root}")
        return 0

    print(f"✗ {len(violations)} risk-threshold violation(s):\n")
    for v in violations:
        print(f"  {v.file}:{v.line}  [{v.rule}]")
        print(f"    > {v.excerpt}")
        print(f"    note: {v.note}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
