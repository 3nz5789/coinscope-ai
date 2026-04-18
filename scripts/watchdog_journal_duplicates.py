#!/usr/bin/env python3
"""
watchdog_journal_duplicates.py — Phase 1 Watchdog (freeze-compatible)

Purpose
-------
Detects duplicate orders on the CoinScopeAI execution path by polling the
engine's /journal endpoint and flagging journal entries that share the same
(symbol, side, qty) within a configurable time window.

This watchdog lives OUTSIDE the engine. It does not modify engine behavior.
It is the Phase 1 response to:
    [INCIDENT] EXECUTION — Duplicate Orders During Retry (2026-04-18)

Design invariants
-----------------
- Read-only: only calls GET /journal.
- Idempotent: running it twice will not create side effects other than alerts.
- Freeze-compatible: no core engine change, no new dependencies beyond
  the stdlib + requests (already in the repo toolchain).
- Fails safe: if the engine is unreachable, it logs and exits 2. It does not
  assume "no duplicates" when it has no evidence.

Usage
-----
    python3 scripts/watchdog_journal_duplicates.py [--base-url URL] [--window-s SEC]

Exit codes
----------
    0  No duplicates detected.
    1  Duplicates detected (alert fired).
    2  Engine unreachable / evidence incomplete.

Alerting
--------
When a duplicate is detected, writes a structured JSON line to stdout and,
if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars are set, sends a Telegram
message via @ScoopyAI_bot.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(2)


DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_WINDOW_S = 30       # two fills within 30s are suspicious
DEFAULT_TIMEOUT_S = 5


# ----------------------------- Engine calls -----------------------------

def fetch_journal(base_url: str, timeout: float) -> list[dict[str, Any]]:
    """GET /journal and return the data list. Raises on non-2xx or schema drift."""
    url = f"{base_url.rstrip('/')}/journal"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"journal returned non-success status: {payload!r}")
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"journal data is not a list: {type(data).__name__}")
    return data


# ----------------------------- Detection core -----------------------------

def _parse_ts(entry: dict[str, Any]) -> float | None:
    """Parse an entry timestamp into epoch seconds. Returns None if unparseable."""
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        # Accept both "2026-04-08T15:30:00Z" and "...+00:00"
        ts_norm = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_norm).astimezone(timezone.utc).timestamp()
    except (ValueError, TypeError):
        return None


def _normalize_qty(entry: dict[str, Any]) -> str:
    """Qty key varies — try a few. Stringify so minor float drift still matches."""
    for k in ("qty", "size", "quantity", "position_size"):
        if k in entry:
            return f"{float(entry[k]):.8f}"
    # If qty is absent, fall back to entry/exit-price tuple as a weaker key.
    return f"no-qty|{entry.get('entry_price')}|{entry.get('exit_price')}"


def find_duplicates(
    entries: Iterable[dict[str, Any]],
    window_s: float,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    """
    Find pairs of journal entries with matching (symbol, side, qty) whose
    timestamps are within window_s seconds of each other.

    Returns list of (entry_a, entry_b, delta_seconds).
    """
    bucketed: dict[tuple[str, str, str], list[tuple[float, dict[str, Any]]]] = defaultdict(list)

    for e in entries:
        ts = _parse_ts(e)
        if ts is None:
            continue
        key = (
            str(e.get("symbol", "")),
            str(e.get("side", "")).upper(),
            _normalize_qty(e),
        )
        bucketed[key].append((ts, e))

    dupes: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    for key, items in bucketed.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x[0])
        for (t_a, a), (t_b, b) in zip(items, items[1:]):
            delta = t_b - t_a
            if delta <= window_s:
                dupes.append((a, b, delta))
    return dupes


# ----------------------------- Alerting -----------------------------

def emit_alert(record: dict[str, Any]) -> None:
    """Emit a structured JSON line on stdout. Also ping Telegram if configured."""
    print(json.dumps(record, default=str))

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return
    try:
        msg = (
            "[WATCHDOG] Duplicate journal entries detected\n"
            f"symbol: {record['symbol']}  side: {record['side']}  qty: {record['qty']}\n"
            f"delta: {record['delta_s']:.2f}s  ids: {record['trade_ids']}"
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=DEFAULT_TIMEOUT_S,
        )
    except requests.RequestException as ex:
        # Never let alert delivery failure mask the real signal — print and move on.
        print(f"[WARN] telegram send failed: {ex}", file=sys.stderr)


# ----------------------------- Entry point -----------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default=os.environ.get("ENGINE_BASE_URL", DEFAULT_BASE_URL))
    p.add_argument("--window-s", type=float, default=DEFAULT_WINDOW_S)
    p.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args()

    try:
        entries = fetch_journal(args.base_url, args.timeout_s)
    except (requests.RequestException, RuntimeError, ValueError) as ex:
        print(f"[ERROR] engine unreachable or bad response: {ex}", file=sys.stderr)
        return 2

    dupes = find_duplicates(entries, args.window_s)
    if not dupes:
        print(f"[OK] no duplicate journal entries in window={args.window_s}s across {len(entries)} entries")
        return 0

    now = datetime.now(timezone.utc).isoformat()
    for a, b, delta in dupes:
        emit_alert({
            "detected_at": now,
            "symbol": a.get("symbol"),
            "side": a.get("side"),
            "qty": _normalize_qty(a),
            "delta_s": delta,
            "trade_ids": [a.get("trade_id"), b.get("trade_id")],
            "timestamps": [a.get("timestamp"), b.get("timestamp")],
            "watchdog": "watchdog_journal_duplicates",
            "incident_ref": "INC-2026-04-18-01",
        })
    return 1


if __name__ == "__main__":
    sys.exit(main())
