"""
CoinScopeAI — Market Scanner Skill
===================================
Manus Skill Implementation: Core Trading Intelligence #1

Purpose:
    Scans Binance Futures pairs using the CoinScopeAI engine,
    ranks them by the FixedScorer (0-12), and returns a formatted
    signal table for the Manus agent to present to the user.

Usage (standalone):
    python market_scanner.py
    python market_scanner.py --pairs BTC/USDT,ETH/USDT --top 3 --filter LONG

Usage (via Manus API call):
    The Manus agent calls run_scan() or the /scan endpoint directly.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Optional

import requests

# ── Config ────────────────────────────────────────────────────────────────────

ENGINE_BASE_URL = "http://localhost:8001"

DEFAULT_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "TAO/USDT",
]

SCORE_LABELS = {
    (0.0, 4.9):  ("Weak",        "⚫"),
    (5.0, 5.9):  ("Moderate",    "🟡"),
    (6.0, 7.4):  ("Good",        "🟠"),
    (7.5, 8.9):  ("Strong",      "🟢"),
    (9.0, 12.0): ("Very Strong", "💎"),
}

REGIME_ICONS = {
    "bull":  "🟢 Bull",
    "bear":  "🔴 Bear",
    "chop":  "🟡 Chop",
    "unknown": "⚫ Unknown",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def score_label(score: float) -> str:
    """Return human-readable label + icon for a given score."""
    for (lo, hi), (label, icon) in SCORE_LABELS.items():
        if lo <= score <= hi:
            return f"{icon} {label}"
    return "⚫ Unknown"


def check_engine_health() -> bool:
    """Ping the engine health endpoint. Returns True if online."""
    try:
        r = requests.get(f"{ENGINE_BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


# ── Core Scan Logic ───────────────────────────────────────────────────────────

def run_scan(
    pairs: Optional[list] = None,
    top_n: int = 5,
    min_score: float = 5.5,
    signal_filter: str = "ALL",
) -> dict:
    """
    Run a market scan via the CoinScopeAI engine API.

    Args:
        pairs:         List of trading pairs. Defaults to DEFAULT_PAIRS.
        top_n:         Max number of results to return.
        min_score:     Minimum score threshold (0–12).
        signal_filter: 'LONG', 'SHORT', or 'ALL'.

    Returns:
        dict with keys:
            - results:       Filtered, ranked signal list
            - active_count:  Number of active signals (pre-filter)
            - total_scanned: Total pairs scanned
            - timestamp:     UTC timestamp string
            - status:        'ok' | 'engine_offline' | 'no_signals'
    """
    pairs = pairs or DEFAULT_PAIRS
    pairs_str = ",".join(pairs)

    # ── Step 1: Engine health check ───────────────────────────────────────────
    if not check_engine_health():
        return {
            "status": "engine_offline",
            "message": (
                "CoinScopeAI engine is offline.\n"
                "Start it with: uvicorn api:app --reload --port 8001"
            ),
            "results": [],
        }

    # ── Step 2: Call /scan endpoint ───────────────────────────────────────────
    try:
        response = requests.get(
            f"{ENGINE_BASE_URL}/scan",
            params={"pairs": pairs_str},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Scan timed out (>30s). Engine may be overloaded.",
            "results": [],
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"API error: {str(e)}",
            "results": [],
        }

    signals = data.get("signals", [])
    active_count = data.get("active_count", 0)
    total_scanned = data.get("total_scanned", len(pairs))

    # ── Step 3: Filter & rank ─────────────────────────────────────────────────
    # Keep only actionable signals
    filtered = [s for s in signals if s.get("signal") in ("LONG", "SHORT")]

    # Apply signal direction filter
    if signal_filter.upper() in ("LONG", "SHORT"):
        filtered = [s for s in filtered if s.get("signal") == signal_filter.upper()]

    # Apply minimum score threshold
    filtered = [s for s in filtered if s.get("score", 0) >= min_score]

    # Sort by score descending
    filtered.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Take top N
    top_results = filtered[:top_n]

    if not top_results:
        return {
            "status": "no_signals",
            "message": (
                f"No setups found above score {min_score}. "
                "Market may be choppy. Try lowering the threshold or check back in 15 min."
            ),
            "results": [],
            "active_count": active_count,
            "total_scanned": total_scanned,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

    return {
        "status": "ok",
        "results": top_results,
        "active_count": active_count,
        "total_scanned": total_scanned,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


# ── Output Formatter ──────────────────────────────────────────────────────────

def format_output(scan_result: dict) -> str:
    """
    Format scan result into a clean, agent-ready string for Manus to present.
    """
    status = scan_result.get("status")

    # ── Offline / Error states ─────────────────────────────────────────────────
    if status == "engine_offline":
        return f"⚠️  Engine Offline\n{scan_result['message']}"

    if status == "error":
        return f"❌  Error\n{scan_result['message']}"

    if status == "no_signals":
        return (
            f"📡  MARKET SCAN — {scan_result.get('timestamp', 'N/A')}\n"
            f"Scanned: {scan_result.get('total_scanned', 0)} pairs\n\n"
            f"ℹ️  {scan_result['message']}"
        )

    # ── Active signals table ───────────────────────────────────────────────────
    results = scan_result["results"]
    ts = scan_result["timestamp"]
    total = scan_result["total_scanned"]
    active = scan_result["active_count"]

    lines = [
        f"📡  MARKET SCAN — {ts}",
        f"Scanned: {total} pairs  |  Active Signals: {active}",
        "━" * 62,
        f"{'RANK':<5} {'PAIR':<12} {'SIGNAL':<7} {'SCORE':<7} {'TF':<5} {'RSI':<7} {'REGIME':<14} {'STRENGTH'}",
        "━" * 62,
    ]

    for i, sig in enumerate(results, 1):
        symbol   = sig.get("symbol", "???")
        signal   = sig.get("signal", "N/A")
        score    = sig.get("score", 0.0)
        tf       = sig.get("timeframe", "4h")
        rsi      = sig.get("rsi", 0.0)
        regime   = REGIME_ICONS.get(sig.get("regime", "unknown"), "⚫ Unknown")
        strength = score_label(score)

        # Flag chop-regime signals as lower confidence
        chop_flag = "  ⚠️ chop" if sig.get("regime") == "chop" else ""

        lines.append(
            f"{i:<5} {symbol:<12} {signal:<7} {score:<7.1f} {tf:<5} {rsi:<7.1f} {regime:<14} {strength}{chop_flag}"
        )

    lines += [
        "━" * 62,
        "Score Key:  0–4.9 Weak  |  5–5.9 Moderate  |  6–7.4 Good  |  7.5–8.9 Strong  |  9–12 Very Strong",
        "",
        "💡 Next Steps:",
        "  • 'Size my position on [PAIR]' → Kelly Criterion position sizing",
        "  • 'Check regime for [PAIR]'    → HMM regime confidence",
        "  • 'Alert me on [PAIR]'         → Telegram signal alert",
    ]

    return "\n".join(lines)


# ── JSON Output (for Manus agent consumption) ─────────────────────────────────

def format_json(scan_result: dict) -> str:
    """Return JSON string for programmatic Manus agent use."""
    return json.dumps(scan_result, indent=2)


# ── CLI Entrypoint ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="CoinScopeAI Market Scanner Skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python market_scanner.py
  python market_scanner.py --pairs BTC/USDT,ETH/USDT,SOL/USDT --top 3
  python market_scanner.py --filter LONG --min-score 7.0
  python market_scanner.py --json
        """,
    )
    parser.add_argument(
        "--pairs",
        type=str,
        default=",".join(DEFAULT_PAIRS),
        help="Comma-separated list of pairs to scan",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Max number of results to display (default: 5)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=5.5,
        help="Minimum score threshold 0–12 (default: 5.5)",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default="ALL",
        choices=["LONG", "SHORT", "ALL"],
        help="Signal direction filter (default: ALL)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted table",
    )

    args = parser.parse_args()

    pairs_list = [p.strip() for p in args.pairs.split(",") if p.strip()]

    result = run_scan(
        pairs=pairs_list,
        top_n=args.top,
        min_score=args.min_score,
        signal_filter=args.filter,
    )

    if args.json:
        print(format_json(result))
    else:
        print(format_output(result))

    # Exit code: 0 = signals found, 1 = no signals / error
    sys.exit(0 if result["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
