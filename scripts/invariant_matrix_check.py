#!/usr/bin/env python3
"""Invariant-matrix integrity check.

Parses the Markdown table inside ``docs/validation/invariant-matrix.md`` —
delimited by the HTML comments ``<!-- matrix:begin -->`` and
``<!-- matrix:end -->`` — and verifies every cited file path resolves to a
real file on disk at this revision.

Why
---
The matrix is the bridge between the proof hub and the code that protects
each invariant. If a protector file is renamed or deleted without updating
the matrix, the bridge silently rots: PRs continue to merge while the
matrix points at thin air. This script makes that rot fail CI.

What it does
------------
* Reads ``docs/validation/invariant-matrix.md``.
* Extracts the rows between the matrix markers.
* For each row, pulls every backtick-quoted token from the four path
  columns (Source, Code, Test/Script, Evidence).
* Strips any ``::Class::method`` suffix to recover the file path.
* Verifies the file exists at ``REPO_ROOT/<path>``.
* Reports any unresolved paths with the row's invariant ID.

A row with status ``🔴`` (red) is permitted to cite missing paths — that
is the documented meaning of red. ``🟢`` and ``🟡`` must resolve fully.

Exit codes
----------
* 0 — every cited path resolves (or the row is red and exempt).
* 1 — at least one cited path is missing.
* 2 — the matrix file is malformed (markers missing, columns wrong, etc.).

Usage
-----
::

    python3 scripts/invariant_matrix_check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_FILE = REPO_ROOT / "docs" / "validation" / "invariant-matrix.md"

BEGIN_MARKER = "<!-- matrix:begin -->"
END_MARKER = "<!-- matrix:end -->"

# Order must match the table header in invariant-matrix.md.
HEADER = ("ID", "Invariant", "Status", "Source", "Code", "Test/Script", "Evidence", "Notes")
PATH_COLUMNS = ("Source", "Code", "Test/Script", "Evidence")
RED = "🔴"

# Tokens wrapped in backticks. Path-like tokens are extracted by stripping
# any pytest-style ``::Class::method`` suffix.
BACKTICK_RE = re.compile(r"`([^`]+)`")


class MatrixError(Exception):
    """Raised when the matrix file cannot be parsed."""


def _extract_block(text: str) -> str:
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        raise MatrixError(
            f"matrix markers not found or out of order in {MATRIX_FILE.relative_to(REPO_ROOT)}"
        )
    return text[start + len(BEGIN_MARKER) : end]


def _table_rows(block: str) -> list[str]:
    rows = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        raise MatrixError("matrix table has fewer than 3 rows (header + separator + at least 1 row)")
    return rows[2:]  # skip header + separator


def _cells(row: str) -> list[str]:
    cells = [c.strip() for c in row.split("|")]
    # Outer pipes produce empty leading/trailing entries.
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _paths_in_cell(cell: str) -> list[str]:
    """Return cleaned-up file paths cited in a cell.

    Each cell may contain multiple backtick-quoted tokens. Pytest-style
    suffixes (``::Class::method``) are stripped to recover the file path.
    Non-path tokens (e.g. plain identifiers) are tolerated — they will
    simply fail the existence check if the row is non-red, which is the
    correct outcome.
    """
    out: list[str] = []
    for token in BACKTICK_RE.findall(cell):
        if "::" in token:
            token = token.split("::", 1)[0]
        token = token.strip()
        if token:
            out.append(token)
    return out


def check() -> int:
    try:
        text = MATRIX_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"matrix-check: ERROR — {MATRIX_FILE.relative_to(REPO_ROOT)} not found", file=sys.stderr)
        return 2

    try:
        block = _extract_block(text)
        rows = _table_rows(block)
    except MatrixError as exc:
        print(f"matrix-check: ERROR — {exc}", file=sys.stderr)
        return 2

    errors: list[str] = []
    seen_ids: set[str] = set()
    row_count = 0

    for raw_row in rows:
        cells = _cells(raw_row)
        if len(cells) != len(HEADER):
            errors.append(
                f"row has {len(cells)} cells, expected {len(HEADER)}: {raw_row[:80]}…"
            )
            continue

        record = dict(zip(HEADER, cells))
        rowid = record["ID"]
        status = record["Status"]
        row_count += 1

        if not rowid:
            errors.append("row with empty ID")
            continue
        if rowid in seen_ids:
            errors.append(f"{rowid}: duplicate ID")
        seen_ids.add(rowid)

        if status == RED:
            # Red rows are documented gaps; do not enforce path resolution.
            continue

        for column in PATH_COLUMNS:
            for path in _paths_in_cell(record[column]):
                # Skip self-references (e.g. "this file") that aren't backticked.
                target = REPO_ROOT / path
                if not target.exists():
                    errors.append(
                        f"{rowid}: cited path missing in column '{column}': {path}"
                    )

    if row_count == 0:
        print("matrix-check: ERROR — table has zero data rows", file=sys.stderr)
        return 2

    if errors:
        print("matrix-check: FAIL\n")
        for err in errors:
            print(f"  - {err}")
        print(
            "\nFix the matrix at "
            f"{MATRIX_FILE.relative_to(REPO_ROOT)}: rename or remove broken citations,\n"
            "or mark the row 🔴 if the protector is genuinely missing on this branch."
        )
        return 1

    print(f"matrix-check: OK — {row_count} invariant rows, all cited paths resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(check())
