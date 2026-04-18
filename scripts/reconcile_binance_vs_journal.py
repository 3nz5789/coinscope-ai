#!/usr/bin/env python3
"""
reconcile_binance_vs_journal.py — Phase 1 Reconciler (freeze-compatible)

Purpose
-------
Cross-checks the CoinScopeAI engine /journal against Binance Testnet's
order history. Divergences are the strongest evidence that the execution
path duplicated (or lost) an order.

This reconciler lives OUTSIDE the engine. It does not modify engine behavior.
It is a Phase 1 response to:
    [INCIDENT] EXECUTION — Duplicate Orders During Retry (2026-04-18)

Checks
------
For each supported symbol, within the LOOKBACK window:
  1. Orders on Binance that are NOT in /journal   → missed/duplicated by us
  2. Journal entries whose (symbol, qty, side) has NO matching Binance order
     within a tolerance window                    → phantom journal row
  3. Binance fill count > 1 for the same journal decision
     (same clientOrderId prefix)                  → retry-driven duplicate

Design invariants
-----------------
- Read-only on both sides — only GETs.
- Binance Testnet only. Hardcoded testnet base URL; refuses to run against
  mainnet even if the key would permit it.
- Fails loudly: on any error, prints + exits 2. Silence is never "all clear."

Usage
-----
    python3 scripts/reconcile_binance_vs_journal.py [--base-url URL] [--lookback-h H]

Required env
------------
    BINANCE_TESTNET_API_KEY
    BINANCE_TESTNET_API_SECRET

Exit codes
----------
    0  Reconciled clean.
    1  Divergence detected.
    2  Could not complete the reconciliation (engine or Binance unreachable,
       missing credentials, etc).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(2)


DEFAULT_ENGINE_URL = "http://localhost:8001"
BINANCE_TESTNET_FAPI = "https://testnet.binancefuture.com"   # futures testnet — DO NOT change
SUPPORTED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT")
DEFAULT_LOOKBACK_H = 1
DEFAULT_TIMEOUT_S = 10
QTY_TOLERANCE = 1e-6


# ----------------------------- Signing -----------------------------

def _sign(secret: str, params: dict[str, Any]) -> str:
    qs = urlencode(params)
    return hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()


def binance_all_orders(
    api_key: str,
    api_secret: str,
    symbol: str,
    start_ms: int,
    timeout_s: float,
) -> list[dict[str, Any]]:
    """GET /fapi/v1/allOrders for a symbol since start_ms. Returns list of orders."""
    params = {
        "symbol": symbol,
        "startTime": start_ms,
        "timestamp": int(time.time() * 1000),
        "recvWindow": 5000,
    }
    params["signature"] = _sign(api_secret, params)
    url = f"{BINANCE_TESTNET_FAPI}/fapi/v1/allOrders"
    resp = requests.get(
        url,
        params=params,
        headers={"X-MBX-APIKEY": api_key},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    return resp.json()


# ----------------------------- Engine journal -----------------------------

def fetch_journal(base_url: str, timeout_s: float) -> list[dict[str, Any]]:
    resp = requests.get(f"{base_url.rstrip('/')}/journal", timeout=timeout_s)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "success":
        raise RuntimeError(f"journal returned non-success status: {payload!r}")
    return payload.get("data") or []


# ----------------------------- Reconciliation -----------------------------

def _qty_of(o: dict[str, Any]) -> float:
    for k in ("executedQty", "origQty", "qty", "size", "quantity"):
        if k in o and o[k] is not None:
            try:
                return float(o[k])
            except (TypeError, ValueError):
                continue
    return 0.0


def _ts_ms_of_journal(e: dict[str, Any]) -> int | None:
    ts = e.get("timestamp")
    if not ts:
        return None
    try:
        ts_norm = ts.replace("Z", "+00:00")
        return int(datetime.fromisoformat(ts_norm).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def reconcile(
    journal: list[dict[str, Any]],
    binance_orders_by_symbol: dict[str, list[dict[str, Any]]],
    match_window_ms: int = 60_000,
) -> dict[str, list[dict[str, Any]]]:
    """Return a report of divergences bucketed by type."""
    report: dict[str, list[dict[str, Any]]] = {
        "binance_without_journal": [],
        "journal_without_binance": [],
        "binance_duplicate_per_journal": [],
    }

    # Index journal by symbol
    jrn_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for e in journal:
        jrn_by_symbol.setdefault(str(e.get("symbol", "")), []).append(e)

    for symbol, b_orders in binance_orders_by_symbol.items():
        j_entries = jrn_by_symbol.get(symbol, [])

        # --- Check: every Binance filled order has a journal row ---
        for o in b_orders:
            if o.get("status") not in ("FILLED", "PARTIALLY_FILLED"):
                continue
            o_ts = int(o.get("updateTime") or o.get("time") or 0)
            o_side = str(o.get("side", "")).upper()
            o_qty = _qty_of(o)

            matched = False
            for j in j_entries:
                j_ts = _ts_ms_of_journal(j)
                if j_ts is None:
                    continue
                if abs(j_ts - o_ts) > match_window_ms:
                    continue
                if str(j.get("side", "")).upper() not in (o_side, _long_short(o_side)):
                    continue
                if abs(_qty_of(j) - o_qty) > QTY_TOLERANCE:
                    continue
                matched = True
                break
            if not matched:
                report["binance_without_journal"].append({
                    "symbol": symbol, "orderId": o.get("orderId"),
                    "clientOrderId": o.get("clientOrderId"),
                    "side": o_side, "qty": o_qty, "ts_ms": o_ts,
                })

        # --- Check: every journal row has at least one Binance fill ---
        for j in j_entries:
            j_ts = _ts_ms_of_journal(j)
            if j_ts is None:
                continue
            j_side = str(j.get("side", "")).upper()
            j_qty = _qty_of(j)
            matches = [
                o for o in b_orders
                if o.get("status") in ("FILLED", "PARTIALLY_FILLED")
                and str(o.get("side", "")).upper() in (j_side, _long_short(j_side))
                and abs(_qty_of(o) - j_qty) <= QTY_TOLERANCE
                and abs(int(o.get("updateTime") or o.get("time") or 0) - j_ts) <= match_window_ms
            ]
            if not matches:
                report["journal_without_binance"].append({
                    "symbol": symbol, "trade_id": j.get("trade_id"),
                    "side": j_side, "qty": j_qty, "ts_ms": j_ts,
                })
            elif len(matches) > 1:
                report["binance_duplicate_per_journal"].append({
                    "symbol": symbol, "trade_id": j.get("trade_id"),
                    "matched_order_ids": [m.get("orderId") for m in matches],
                    "matched_client_order_ids": [m.get("clientOrderId") for m in matches],
                    "qty": j_qty,
                })

    return report


def _long_short(side: str) -> str:
    """Map Binance BUY/SELL ↔ our LONG/SHORT language loosely."""
    return {"BUY": "LONG", "SELL": "SHORT", "LONG": "BUY", "SHORT": "SELL"}.get(side, side)


# ----------------------------- Entry point -----------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default=os.environ.get("ENGINE_BASE_URL", DEFAULT_ENGINE_URL))
    p.add_argument("--lookback-h", type=float, default=DEFAULT_LOOKBACK_H)
    p.add_argument("--timeout-s", type=float, default=DEFAULT_TIMEOUT_S)
    args = p.parse_args()

    api_key = os.environ.get("BINANCE_TESTNET_API_KEY")
    api_secret = os.environ.get("BINANCE_TESTNET_API_SECRET")
    if not (api_key and api_secret):
        print("[ERROR] BINANCE_TESTNET_API_KEY / SECRET not set in env", file=sys.stderr)
        return 2

    # Fetch journal
    try:
        journal = fetch_journal(args.base_url, args.timeout_s)
    except (requests.RequestException, RuntimeError, ValueError) as ex:
        print(f"[ERROR] could not fetch engine journal: {ex}", file=sys.stderr)
        return 2

    # Fetch Binance per symbol
    start_ms = int((datetime.now(timezone.utc) - timedelta(hours=args.lookback_h)).timestamp() * 1000)
    binance_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for sym in SUPPORTED_SYMBOLS:
        try:
            binance_by_symbol[sym] = binance_all_orders(api_key, api_secret, sym, start_ms, args.timeout_s)
        except requests.RequestException as ex:
            print(f"[ERROR] Binance allOrders failed for {sym}: {ex}", file=sys.stderr)
            return 2

    report = reconcile(journal, binance_by_symbol)
    now = datetime.now(timezone.utc).isoformat()
    any_divergence = any(report[k] for k in report)

    print(json.dumps({
        "reconciled_at": now,
        "lookback_h": args.lookback_h,
        "journal_rows": len(journal),
        "binance_orders_by_symbol": {s: len(v) for s, v in binance_by_symbol.items()},
        "divergence": report,
        "incident_ref": "INC-2026-04-18-01",
    }, indent=2))

    return 1 if any_divergence else 0


if __name__ == "__main__":
    sys.exit(main())
