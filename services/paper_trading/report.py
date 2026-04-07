"""
CoinScopeAI Paper Trading — Report Generator CLI
===================================================
Generate a performance report from the trade journal.

Usage:
    python -m services.paper_trading.report [--output PATH]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="CoinScopeAI Paper Trading — Performance Report",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON instead of text",
    )

    args = parser.parse_args()

    state_file = Path("/tmp/coinscopeai_paper_trading_state.json")
    if not state_file.exists():
        print("No state file found. Run the engine first.")
        sys.exit(1)

    try:
        state = json.loads(state_file.read_text())
    except Exception as e:
        print(f"Failed to read state: {e}")
        sys.exit(1)

    portfolio = state.get("portfolio", {})
    safety = state.get("safety", {})
    signals = state.get("signal_stats", {})

    total_trades = portfolio.get("total_trades", 0)
    wins = portfolio.get("winning_trades", 0)
    losses = portfolio.get("losing_trades", 0)
    win_rate = wins / max(total_trades, 1)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_started_at": state.get("started_at", 0),
        "account": {
            "equity": safety.get("equity", 0),
            "peak_equity": safety.get("peak_equity", 0),
            "drawdown_pct": safety.get("drawdown_pct", 0),
            "daily_pnl": safety.get("daily_pnl", 0),
        },
        "trading": {
            "total_trades": total_trades,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate": win_rate,
            "total_realized_pnl": portfolio.get("total_realized_pnl", 0),
            "total_unrealized_pnl": portfolio.get("total_unrealized_pnl", 0),
            "open_positions": portfolio.get("open_positions", 0),
        },
        "signals": {
            "candles_processed": signals.get("candles_processed", 0),
            "signals_generated": signals.get("signals_generated", 0),
        },
        "safety": {
            "orders_submitted": safety.get("total_orders_submitted", 0),
            "orders_rejected": safety.get("total_orders_rejected", 0),
            "consecutive_losses": safety.get("consecutive_losses", 0),
            "kill_switch_active": safety.get("kill_switch", {}).get("active", False),
        },
    }

    if args.json:
        output = json.dumps(report, indent=2)
    else:
        output = _format_text_report(report)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Report saved to {args.output}")
    else:
        print(output)


def _format_text_report(report: dict) -> str:
    """Format report as human-readable text."""
    lines = [
        "=" * 60,
        " CoinScopeAI Paper Trading — Performance Report",
        "=" * 60,
        f" Generated: {report['generated_at']}",
        "",
        "─── Account ───────────────────────────────────────────",
        f"  Equity:          {report['account']['equity']:>12.2f} USDT",
        f"  Peak Equity:     {report['account']['peak_equity']:>12.2f} USDT",
        f"  Drawdown:        {report['account']['drawdown_pct']:>12.1%}",
        f"  Daily P&L:       {report['account']['daily_pnl']:>+12.2f} USDT",
        "",
        "─── Trading ───────────────────────────────────────────",
        f"  Total Trades:    {report['trading']['total_trades']:>12d}",
        f"  Wins:            {report['trading']['winning_trades']:>12d}",
        f"  Losses:          {report['trading']['losing_trades']:>12d}",
        f"  Win Rate:        {report['trading']['win_rate']:>12.1%}",
        f"  Realized P&L:    {report['trading']['total_realized_pnl']:>+12.2f} USDT",
        f"  Unrealized P&L:  {report['trading']['total_unrealized_pnl']:>+12.2f} USDT",
        f"  Open Positions:  {report['trading']['open_positions']:>12d}",
        "",
        "─── Signals ───────────────────────────────────────────",
        f"  Candles:         {report['signals']['candles_processed']:>12d}",
        f"  Signals:         {report['signals']['signals_generated']:>12d}",
        "",
        "─── Safety ────────────────────────────────────────────",
        f"  Orders Submitted:{report['safety']['orders_submitted']:>12d}",
        f"  Orders Rejected: {report['safety']['orders_rejected']:>12d}",
        f"  Consec. Losses:  {report['safety']['consecutive_losses']:>12d}",
        f"  Kill Switch:     {'🚨 ACTIVE' if report['safety']['kill_switch_active'] else '✅ OFF':>12s}",
        "",
        "=" * 60,
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
