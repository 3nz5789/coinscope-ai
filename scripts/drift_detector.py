#!/usr/bin/env python3
"""
CoinScopeAI Drift Detector
==========================

Cross-checks canonical token consistency across:
  - CLAUDE.md (master prompt, source of truth)
  - architecture/design-system-manifest.md
  - business-plan/*.md (16 framework sections)
  - business-plan/_decisions/decision-log.md

Catches the kind of regression that produced 20x → 10x slip.

Usage:
    python3 scripts/drift_detector.py            # exits 1 if any drift
    python3 scripts/drift_detector.py --json     # machine output
    python3 scripts/drift_detector.py --rule risk_thresholds   # one rule

Run pre-commit, in CI, or whenever Scoopy edits anything canonical.
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CANONICAL_TOKENS = {
    # Risk thresholds — these are LOCKED in CLAUDE.md and must match everywhere.
    "max_leverage": "10x",
    "max_drawdown": "10%",
    "daily_loss_limit": "5%",
    "max_open_positions": "5",  # revised 2026-05-03 — supersedes earlier 3-cap
    "position_heat_cap": "80%",
    # Regime palette (v3 ML)
    "regime_trending_hex": "#00FFB8",
    "regime_meanrev_hex": "#A3ADBD",
    "regime_volatile_hex": "#F5A623",
    "regime_quiet_hex": "#5B6472",
    # Personas (internal IDs only)
    "persona_p1_name": "Omar",
    "persona_p2_name": "Karim",
    "persona_p3_name": "Layla",
    # Tier prices (Track B canonical)
    "tier_trader_price": "$79",
    "tier_desk_preview_price": "$399",
    "tier_desk_full_price": "$1,199",
    # Per-seat
    "per_seat_partner": "$149",
    "per_seat_analyst": "$249",
}

# Files to scan for canonical consistency.
SCAN_TARGETS = [
    "CLAUDE.md",
    "architecture/design-system-manifest.md",
    "business-plan/00-framework.md",
    "business-plan/01-executive-summary.md",
    "business-plan/05-product-strategy.md",
    "business-plan/06-pricing-monetization.md",
    "business-plan/09-brand-messaging.md",
    "business-plan/12-risk-compliance-trust.md",
    "business-plan/14-launch-roadmap.md",
    "business-plan/_decisions/decision-log.md",
]

# File-size tripwire — catches accidental file collapse. Two CLAUDE.md clobbers
# happened on 2026-05-03 (144 bytes and 58 bytes), both from pbcopy/heredoc snippets
# that the user inadvertently wrote AS the file rather than reading FROM it.
# Threshold is ~70% of the canonical size; a file shrinking below this means data loss
# or a paste/redirect went the wrong way. The minimum is intentionally generous so that
# a normal edit pass (adding/removing a section) doesn't trip it.
MINIMUM_SIZES_BYTES = {
    "CLAUDE.md": 4000,                                # canonical 5,531 (v2 from 3d6362d)
    "CONTEXT_PRIMER.md": 4000,                        # canonical 5,549
    "architecture/architecture.md": 7000,             # canonical 10,346
    "architecture/design-system-manifest.md": 4500,   # canonical 6,464
    "business-plan/00-framework.md": 20000,           # canonical 32,036
    "business-plan/_decisions/decision-log.md": 80000, # canonical 105,275
    "scripts/drift_detector.py": 7000,                # canonical 10,523
    "scripts/risk_threshold_guardrail.py": 3000,      # canonical 4,790
}

# Forbidden tokens — values that have been superseded but might still lurk.
FORBIDDEN = {
    "20x_leverage": (
        r"\b20x\b",
        "20x leverage was superseded by 10x via PCC v2 §8 on 2026-05-01. "
        "If you find this in a 'supersedes' / changelog / historical context, that's fine.",
    ),
    "old_pricing_19_49_99_299": (
        r"\$19\s*/\s*\$49\s*/\s*\$99\s*/\s*\$299",
        "Old pricing tier ($19/$49/$99/$299) replaced by Track B ($0/$79/$399/$1,199) on 2026-05-01.",
    ),
    "production_ready_no_context": (
        r"\bproduction[- ]ready\b",
        "Brand voice rule: avoid 'production-ready' unless explicitly tied to PCC v2 §8 sign-off. "
        "Allowed only in changelogs, pre-PCC-v2 historical context, or explicit gate references.",
    ),
}


@dataclass
class Finding:
    rule: str
    severity: str  # "error" | "warning" | "info"
    file: str
    line: int | None
    excerpt: str
    note: str


HISTORICAL_MARKERS = (
    "supersede", "supersedes", "earlier", "previously", "v1 (pre-",
    "changelog", "old:", "deprecated", "→", "->", "fixed",
    "pcc v2", "10x", "anti-overclaim", "never say", "never describe",
    "avoid \"production", "label is gated", "no claim", "rule:",
    "no \"production", "disclaimer:", "do not use", "do not",
    "anything referencing", "until §8", "until pcc", "anything mentioning",
)


def is_price_band(line: str) -> bool:
    """A line that lists a tier with a price RANGE (e.g. '$40–$120') is a
    band, not an assertion of canonical pricing. Skip drift check on it."""
    return bool(re.search(r"\$[\d,]+\s*[–—\-/]\s*\$[\d,]+", line))


def is_meta_or_historical(line: str) -> bool:
    """Detect lines that discuss the rule itself or note a historical change.
    These mentions don't constitute live drift."""
    low = line.lower()
    return any(marker in low for marker in HISTORICAL_MARKERS)


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not path.exists():
        findings.append(
            Finding(
                rule="missing_file",
                severity="error",
                file=str(path.relative_to(PROJECT_ROOT)),
                line=None,
                excerpt="",
                note="Expected file does not exist.",
            )
        )
        return findings

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    # Forbidden tokens check (line-by-line, skip historical/meta context)
    for rule, (pattern, note) in FORBIDDEN.items():
        for i, line in enumerate(lines, start=1):
            if re.search(pattern, line, re.IGNORECASE):
                if is_meta_or_historical(line):
                    continue
                findings.append(
                    Finding(
                        rule=rule,
                        severity="warning" if rule == "production_ready_no_context" else "error",
                        file=str(path.relative_to(PROJECT_ROOT)),
                        line=i,
                        excerpt=line.strip()[:120],
                        note=note,
                    )
                )

    # Leverage assertion check: any line that ASSERTS a leverage value should say 10x.
    for i, line in enumerate(lines, start=1):
        # Patterns that look like the file is stating a current leverage cap value.
        if re.search(r"(?:max[\s_-]*leverage|leverage\s*cap|leverage\s*=)\s*[:\s]*[\d.]+\s*x", line, re.IGNORECASE):
            if not re.search(r"10\s*x", line, re.IGNORECASE):
                if is_meta_or_historical(line):
                    continue
                findings.append(
                    Finding(
                        rule="leverage_cap_mismatch",
                        severity="error",
                        file=str(path.relative_to(PROJECT_ROOT)),
                        line=i,
                        excerpt=line.strip()[:120],
                        note="Live assertion of a leverage cap must use 10x (PCC v2 §8).",
                    )
                )

    # Tier-price check: only flags a file if a tier appears WITH A DIFFERENT price.
    # i.e. "Trader $49" would flag, but "Trader" alone would not.
    tier_canonical = {
        r"\b(trader)\b\s*(?:tier)?\s*[—\-:]?\s*\$(\d+)": ("$79", 79),
        r"\b(desk\s*preview)\b\s*[—\-:]?\s*\$(\d+)": ("$399", 399),
        r"\b(desk\s*full(?:\s*v?2?)?)\b\s*[—\-:]?\s*\$([\d,]+)": ("$1,199", 1199),
    }
    for pattern, (expected_str, expected_int) in tier_canonical.items():
        for i, line in enumerate(lines, start=1):
            m = re.search(pattern, line, re.IGNORECASE)
            if m:
                if is_meta_or_historical(line) or is_price_band(line):
                    continue
                num = int(m.group(2).replace(",", ""))
                if num != expected_int:
                    findings.append(
                        Finding(
                            rule="tier_price_mismatch",
                            severity="error",
                            file=str(path.relative_to(PROJECT_ROOT)),
                            line=i,
                            excerpt=line.strip()[:120],
                            note=f"{m.group(1).strip()} canonical price is {expected_str} per Track B (locked 2026-05-01).",
                        )
                    )

    # Regime palette: only checks files that ACTUALLY enumerate the palette
    # (have all 4 regime labels AND at least one hex code somewhere in the file).
    palette = {
        "Trending": "#00FFB8",
        "Mean-Reverting": "#A3ADBD",
        "Volatile": "#F5A623",
        "Quiet": "#5B6472",
    }
    has_all_regimes = all(label in text for label in palette)
    has_any_hex = bool(re.search(r"#[0-9A-Fa-f]{6}", text))
    if has_all_regimes and has_any_hex:
        for label, hex_value in palette.items():
            if hex_value.lower() not in text.lower():
                findings.append(
                    Finding(
                        rule="regime_hex_missing",
                        severity="warning",
                        file=str(path.relative_to(PROJECT_ROOT)),
                        line=None,
                        excerpt=f"({label} canonical hex {hex_value} not found)",
                        note=f"File defines the regime palette but is missing {label}'s canonical color {hex_value}.",
                    )
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="CoinScopeAI canonical drift detector.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--rule",
        default=None,
        help="filter findings to rule name (e.g., '20x_leverage', 'tier_price_mismatch')",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=PROJECT_ROOT,
        help=f"project root (default: {PROJECT_ROOT})",
    )
    args = parser.parse_args()

    all_findings: list[Finding] = []

    # File-size tripwire — runs first; catches catastrophic file collapse before
    # any content-level checks can be misleading.
    for rel, min_bytes in MINIMUM_SIZES_BYTES.items():
        path = args.root / rel
        if not path.exists():
            continue
        size = path.stat().st_size
        if size < min_bytes:
            all_findings.append(
                Finding(
                    rule="file_size_collapse",
                    severity="error",
                    file=rel,
                    line=None,
                    excerpt=f"file size = {size} bytes (minimum {min_bytes})",
                    note=(
                        f"{rel} has shrunk below its safety threshold. "
                        "This likely indicates an accidental overwrite — recover from "
                        "archive/_backups/, Drive, or git before continuing."
                    ),
                )
            )

    for rel in SCAN_TARGETS:
        path = args.root / rel
        all_findings.extend(scan_file(path))

    if args.rule:
        all_findings = [f for f in all_findings if f.rule == args.rule]

    if args.json:
        print(json.dumps([asdict(f) for f in all_findings], indent=2))
    else:
        if not all_findings:
            print("✓ No drift found across", len(SCAN_TARGETS), "canonical files.")
            return 0
        # Group by file
        print(f"✗ {len(all_findings)} drift finding(s) across canonical files:\n")
        by_file: dict[str, list[Finding]] = {}
        for f in all_findings:
            by_file.setdefault(f.file, []).append(f)
        for file, finds in by_file.items():
            print(f"--- {file} ---")
            for f in finds:
                marker = "ERR " if f.severity == "error" else "WARN"
                line = f"L{f.line}" if f.line else "    "
                print(f"  [{marker}] {line}  {f.rule}")
                if f.excerpt:
                    print(f"            > {f.excerpt}")
                print(f"            note: {f.note}")
            print()

    errors = [f for f in all_findings if f.severity == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
