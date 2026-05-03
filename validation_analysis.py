#!/usr/bin/env python3
"""
validation_analysis.py — Validation Phase Data Analysis (T-8)

Runs §2 (data pull + schema check) and §3 D-category P0 checks plus S1 / X1
baseline computation from `Validation_Data_Analysis_Plan_v1.md`.

USAGE:
    python3 validation_analysis.py

ENV OVERRIDES:
    COINSCOPE_ENGINE   default: http://localhost:8001
    VALIDATION_SINCE   default: 2026-04-10
    SYMBOLS            default: BTCUSDT,ETHUSDT,SOLUSDT (comma-separated)

OUTPUT:
    validation_pulls/<UTC-timestamp>/
        _schema_sample.json
        journal.json
        performance.json
        scan_log.json
        risk_gate_log.json
        position_size_log.json
        regime_<SYM>.json (per symbol)
        data_pack_partial.md
        run_summary.txt

EXIT CODES:
    0 = ran cleanly
    1 = could not reach engine API
    2 = ran but D-category P0 check FAILED (RESTART trigger)

Stdlib only — no pip installs needed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ENGINE = os.environ.get("COINSCOPE_ENGINE", "http://localhost:8001").rstrip("/")
SINCE = os.environ.get("VALIDATION_SINCE", "2026-04-10")
SYMBOLS = [s.strip() for s in os.environ.get(
    "SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT"
).split(",") if s.strip()]

OUT_BASE = Path(__file__).resolve().parent / "validation_pulls"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%MZ")
OUT = OUT_BASE / NOW
OUT.mkdir(parents=True, exist_ok=True)

LOG_LINES: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    LOG_LINES.append(msg)


def fetch(path: str) -> Any:
    url = f"{ENGINE}{path}"
    log(f"  GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw)
    except urllib.error.URLError as e:
        log(f"    ERROR (URL): {e}")
        return None
    except urllib.error.HTTPError as e:
        log(f"    ERROR (HTTP {e.code}): {e}")
        return None
    except json.JSONDecodeError as e:
        log(f"    ERROR (JSON): {e}")
        return None


def save(name: str, data: Any) -> None:
    if data is None:
        return
    path = OUT / name
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def items(data: Any) -> list:
    """Normalize list-or-{items: [...]} to a list."""
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "data", "trades", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def get_field(record: dict, *names, default=None):
    """Try multiple field-name aliases; return first hit."""
    if not isinstance(record, dict):
        return default
    for n in names:
        if n in record and record[n] is not None:
            return record[n]
    return default


# ---------------------------------------------------------------------------
# [1/3] Schema sanity check
# ---------------------------------------------------------------------------
log("=" * 70)
log(f"CoinScopeAI Validation Phase Data Analysis — {NOW}")
log(f"Engine:    {ENGINE}")
log(f"Window:    since {SINCE}")
log(f"Symbols:   {SYMBOLS}")
log(f"Output:    {OUT}")
log("=" * 70)

log("\n[1/3] Schema sanity check…")
schema_sample = fetch("/journal?limit=1")
save("_schema_sample.json", schema_sample)
if schema_sample is None:
    log("\n!! CANNOT REACH ENGINE.")
    log(f"!! Confirm the engine is running and reachable at {ENGINE}.")
    log(f"!! Try:  curl -s {ENGINE}/journal?limit=1")
    (OUT / "run_summary.txt").write_text("\n".join(LOG_LINES))
    sys.exit(1)

sample_records = items(schema_sample)
detected_fields: list[str] = []
if sample_records:
    detected_fields = sorted(sample_records[0].keys()) if isinstance(
        sample_records[0], dict
    ) else []
    log(f"  Detected /journal fields: {detected_fields}")
else:
    log("  WARNING: empty /journal sample. Validation may have produced no trades, "
        "or the schema differs. Continuing.")


# ---------------------------------------------------------------------------
# [2/3] Pull validation window
# ---------------------------------------------------------------------------
log("\n[2/3] Pulling validation window…")
journal = fetch(f"/journal?since={SINCE}")
performance = fetch(f"/performance?since={SINCE}")
scan_log = fetch(f"/scan?since={SINCE}")
risk_gate_log = fetch(f"/risk-gate?since={SINCE}")
position_size_log = fetch(f"/position-size?since={SINCE}")
save("journal.json", journal)
save("performance.json", performance)
save("scan_log.json", scan_log)
save("risk_gate_log.json", risk_gate_log)
save("position_size_log.json", position_size_log)

for sym in SYMBOLS:
    regime = fetch(f"/regime/{sym}?since={SINCE}")
    save(f"regime_{sym}.json", regime)

journal_records = items(journal)
position_records = items(position_size_log)
risk_gate_records = items(risk_gate_log)
scan_records = items(scan_log)

log(f"\n  Row counts:")
log(f"    journal:        {len(journal_records)}")
log(f"    performance:    {'present' if performance else 'EMPTY'}")
log(f"    scan_log:       {len(scan_records)}")
log(f"    risk_gate_log:  {len(risk_gate_records)}")
log(f"    position_size:  {len(position_records)}")


# ---------------------------------------------------------------------------
# [3/3] D-category P0 + S1/X1 baseline
# ---------------------------------------------------------------------------
log("\n[3/3] D-category P0 checks (CRITICAL — D-breach = RESTART trigger)…")

# ---- D1: Max drawdown ----
equity_curve_raw = (
    performance.get("equity_curve")
    or performance.get("equity")
    or []
) if isinstance(performance, dict) else []

equity_points: list[float] = []
if isinstance(equity_curve_raw, list):
    for p in equity_curve_raw:
        if isinstance(p, (int, float)):
            equity_points.append(float(p))
        elif isinstance(p, dict):
            v = p.get("equity") or p.get("value") or p.get("balance")
            if v is not None:
                equity_points.append(float(v))
elif isinstance(equity_curve_raw, dict):
    for v in equity_curve_raw.values():
        if isinstance(v, (int, float)):
            equity_points.append(float(v))

peak = 0.0
max_dd = 0.0
for v in equity_points:
    if v > peak:
        peak = v
    if peak > 0:
        max_dd = max(max_dd, (peak - v) / peak)

# Fallback: if no equity curve, attempt to derive from journal pnl cumulative
if not equity_points and journal_records:
    cum = 0.0
    peak = 0.0
    for r in journal_records:
        cum += get_field(r, "pnl", default=0) or 0
        peak = max(peak, cum)
        if peak > 0:
            max_dd = max(max_dd, (peak - cum) / peak)

# ---- D2: Daily loss days >5% (approximate without per-day equity) ----
daily_pnl: dict[str, float] = defaultdict(float)
for r in journal_records:
    ts = get_field(r, "closed_at", "exit_time", "timestamp", default="")
    pnl = get_field(r, "pnl", default=0) or 0
    if isinstance(ts, str) and len(ts) >= 10:
        daily_pnl[ts[:10]] += pnl

# Without per-day equity, count any day with negative pnl as informational
negative_days = sum(1 for v in daily_pnl.values() if v < 0)
days_total = len(daily_pnl)

# ---- D3: Leverage cap (10x) ----
lev_violations = []
for r in position_records:
    lev = get_field(r, "effective_leverage", "leverage", default=0) or 0
    if lev > 10:
        lev_violations.append(r)

# ---- D4: Concurrent positions >3 ----
events: list[tuple[str, int]] = []
for r in journal_records:
    open_ts = get_field(r, "opened_at", "entry_time", "timestamp")
    close_ts = get_field(r, "closed_at", "exit_time")
    if open_ts:
        events.append((str(open_ts), +1))
    if close_ts:
        events.append((str(close_ts), -1))
events.sort()
open_count = 0
max_concurrent = 0
windows_over_3 = 0
for _, delta in events:
    open_count += delta
    if open_count > 3:
        windows_over_3 += 1
    max_concurrent = max(max_concurrent, open_count)

# ---- D5: Position heat >80% at entry ----
heat_violations = []
for r in position_records:
    h = get_field(r, "heat_at_entry", "heat", default=0) or 0
    if h > 0.80:
        heat_violations.append(r)

# ---- D7: Kill-switch trips ----
kill_switch_trips = [
    r for r in risk_gate_records
    if get_field(r, "kill_switch", "kill", "tripped", default=False)
]

# Print summary
log("\n  -------- D-CATEGORY SUMMARY --------")

def status(condition: bool) -> str:
    return "PASS" if condition else "FAIL"

d1_pass = max_dd <= 0.10
d3_pass = len(lev_violations) == 0
d4_pass = max_concurrent <= 3 and windows_over_3 == 0
d5_pass = len(heat_violations) == 0

log(f"  D1 max drawdown observed:  {max_dd:.2%}  (≤10%)  [{status(d1_pass)}]")
log(f"  D2 daily loss approx:      {negative_days} negative days of {days_total} total")
log(f"      (refine to >5% threshold once per-day equity is available)")
log(f"  D3 leverage >10x:          {len(lev_violations)}  (=0)  [{status(d3_pass)}]")
log(f"  D4 max concurrent posns:   {max_concurrent}  (≤3)  [{status(d4_pass)}]")
log(f"  D4 windows >3:             {windows_over_3}  (=0)")
log(f"  D5 heat >80%:              {len(heat_violations)}  (=0)  [{status(d5_pass)}]")
log(f"  D7 kill-switch trips:      {len(kill_switch_trips)}  (each must be audited)")

d_breach = not (d1_pass and d3_pass and d4_pass and d5_pass)
if d_breach:
    log("\n  !! D-CATEGORY P0 BREACH DETECTED !!")
    log("  !! Per the validation exit decision tree, this triggers RESTART minimum.")
    log("  !! Investigate immediately. Do NOT relax thresholds.")

# ---- S1 baseline: signal precision rolling 30d ----
log("\n=== S1 BASELINE (signal precision) ===")
closed_trades = [
    r for r in journal_records
    if get_field(r, "status", default="") in ("closed", "filled", "completed")
    and get_field(r, "pnl") is not None
]
s1_results: dict[int, dict] = {}
for conf_min in (7, 8, 9):
    band = [
        r for r in closed_trades
        if (get_field(r, "confluence", "confluence_score", default=0) or 0) >= conf_min
    ]
    if band:
        wins = sum(1 for r in band if (get_field(r, "pnl", default=0) or 0) > 0)
        precision = wins / len(band)
        log(f"  Confluence ≥{conf_min}: n={len(band)}, precision={precision:.1%}")
        s1_results[conf_min] = {"n": len(band), "precision": precision}
    else:
        log(f"  Confluence ≥{conf_min}: no closed trades")
        s1_results[conf_min] = {"n": 0, "precision": None}

# ---- X1 slippage ----
log("\n=== X1 SLIPPAGE BASELINE ===")
slips: list[float] = []
for r in journal_records:
    fill = get_field(r, "fill_price", "executed_price")
    intended = get_field(r, "intended_price", "signal_price", "entry_price")
    if fill and intended and intended != 0:
        slips.append(abs(float(fill) - float(intended)) / float(intended))
slips.sort()
x1_p50 = x1_p95 = x1_p99 = None
if slips:
    x1_p50 = slips[len(slips) // 2]
    x1_p95 = slips[min(int(len(slips) * 0.95), len(slips) - 1)]
    x1_p99 = slips[min(int(len(slips) * 0.99), len(slips) - 1)]
    note = "" if len(slips) >= 50 else "   (LOW SAMPLE SIZE — interpret with caution)"
    log(f"  Slippage n={len(slips)}: p50={x1_p50:.4%}, p95={x1_p95:.4%}, p99={x1_p99:.4%}{note}")
else:
    log("  No fillable trades found.")
    log("  Field aliases tried: fill_price/executed_price + intended_price/signal_price/entry_price")
    log("  If schema differs, edit the fetch in this script.")

# ---- X3: SL attachment ----
sl_attached = 0
sl_total = 0
for r in journal_records:
    if get_field(r, "status", default="") not in ("cancelled",):
        sl_total += 1
        if get_field(r, "sl", "stop_loss", "sl_price"):
            sl_attached += 1
sl_rate = (sl_attached / sl_total) if sl_total else None
if sl_rate is not None:
    log(f"\n=== X3 SL ATTACHMENT RATE ===")
    log(f"  {sl_attached} of {sl_total} = {sl_rate:.1%}  (must be 100%)  "
        f"[{status(sl_rate == 1.0)}]")

# ---------------------------------------------------------------------------
# Save partial data pack
# ---------------------------------------------------------------------------
pack = OUT / "data_pack_partial.md"
with open(pack, "w") as f:
    f.write(f"""# Validation Data Pack — Partial — {NOW}

> Auto-generated by validation_analysis.py. Re-run on T-1 (2026-05-08) for final values.
> See raw pulls in this directory; see Validation_Data_Analysis_Plan_v1.md for full criteria.

## A. Engine Criteria — Computed

### Drawdown discipline (D)
- D1 max drawdown: **{max_dd:.2%}** (≤10%) — {status(d1_pass)}
- D2 negative-pnl days (informational): {negative_days} of {days_total}
- D3 leverage >10x: **{len(lev_violations)}** (=0) — {status(d3_pass)}
- D4 max concurrent positions: **{max_concurrent}** (≤3) — {status(d4_pass)}
- D4 windows >3: {windows_over_3} (=0)
- D5 heat violations >80%: **{len(heat_violations)}** (=0) — {status(d5_pass)}
- D7 kill-switch trips during validation: {len(kill_switch_trips)} (each must be audited)

### Signal quality (S1)
""")
    for conf_min, r in s1_results.items():
        if r["precision"] is None:
            f.write(f"- Confluence ≥{conf_min}: no data\n")
        else:
            f.write(f"- Confluence ≥{conf_min}: precision **{r['precision']:.1%}** "
                    f"(n={r['n']})\n")

    f.write("\n### Execution integrity (X)\n")
    if slips:
        f.write(f"- X1 slippage p50/p95/p99: **{x1_p50:.4%} / {x1_p95:.4%} / "
                f"{x1_p99:.4%}** (n={len(slips)})\n")
    else:
        f.write("- X1 slippage: no fillable trades found — schema check needed\n")
    if sl_rate is not None:
        f.write(f"- X3 SL attachment rate: **{sl_rate:.1%}** ({sl_attached} of "
                f"{sl_total}) — {status(sl_rate == 1.0)}\n")

    f.write(f"""
## B. Open Items Resolved or Pending
- PCC-OPEN-1 (S1 baseline): see §A above; founder picks baseline per
  Validation_Data_Analysis_Plan_v1.md §3.1 decision rule.
- PCC-OPEN-7 (X1 slippage baseline): see §A above; founder picks per §3.3 rule.

## C. Schema Confirmation
- See `_schema_sample.json` for actual field names.
- Detected fields: {detected_fields if detected_fields else 'EMPTY SAMPLE'}

## D. Run Metadata
- Engine endpoint: {ENGINE}
- Validation window since: {SINCE}
- Symbols pulled: {SYMBOLS}
- Pull timestamp (UTC): {NOW}
""")

log(f"\nSaved partial data pack: {pack}")
(OUT / "run_summary.txt").write_text("\n".join(LOG_LINES))
log(f"Saved run summary:       {OUT / 'run_summary.txt'}")

if d_breach:
    sys.exit(2)
sys.exit(0)
