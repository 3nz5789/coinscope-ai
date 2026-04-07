"""
CoinScopeAI Paper Trading — Status CLI
=========================================
Check current positions, P&L, system health.

Usage:
    python -m services.paper_trading.status
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    state_file = Path("/tmp/coinscopeai_paper_trading_state.json")
    kill_file = Path("/tmp/coinscopeai_kill_switch.flag")

    print("=" * 60)
    print(" CoinScopeAI Paper Trading — Status")
    print("=" * 60)

    # Kill switch status
    if kill_file.exists():
        try:
            kill_data = json.loads(kill_file.read_text())
            print(f"\n🚨 KILL SWITCH: ACTIVE")
            print(f"   Reason: {kill_data.get('reason', 'unknown')}")
            print(f"   Activated: {datetime.fromtimestamp(kill_data.get('activated_at', 0), tz=timezone.utc)}")
        except Exception:
            print("\n🚨 KILL SWITCH: ACTIVE (corrupt flag file)")
    else:
        print("\n✅ Kill Switch: OFF")

    # Engine state
    if not state_file.exists():
        print("\n⚠️  No state file found. Engine may not be running.")
        print(f"   Expected: {state_file}")
        return

    try:
        state = json.loads(state_file.read_text())
    except Exception as e:
        print(f"\n❌ Failed to read state: {e}")
        return

    saved_at = state.get("saved_at", 0)
    started_at = state.get("started_at", 0)
    age = datetime.now(timezone.utc).timestamp() - saved_at

    print(f"\n📊 State (saved {age:.0f}s ago)")

    # Safety
    safety = state.get("safety", {})
    print(f"\n💰 Account")
    print(f"   Equity:     {safety.get('equity', 0):>12.2f} USDT")
    print(f"   Peak:       {safety.get('peak_equity', 0):>12.2f} USDT")
    print(f"   Daily P&L:  {safety.get('daily_pnl', 0):>+12.2f} USDT")
    print(f"   Drawdown:   {safety.get('drawdown_pct', 0):>12.1%}")
    print(f"   Daily Loss: {safety.get('daily_loss_pct', 0):>12.1%}")

    # Portfolio
    portfolio = state.get("portfolio", {})
    print(f"\n📈 Portfolio")
    print(f"   Open Positions:    {portfolio.get('open_positions', 0)}")
    print(f"   Unrealized P&L:    {portfolio.get('total_unrealized_pnl', 0):+.2f} USDT")
    print(f"   Realized P&L:      {portfolio.get('total_realized_pnl', 0):+.2f} USDT")
    print(f"   Total Trades:      {portfolio.get('total_trades', 0)}")
    print(f"   Winning:           {portfolio.get('winning_trades', 0)}")
    print(f"   Losing:            {portfolio.get('losing_trades', 0)}")

    positions = portfolio.get("positions", {})
    if positions:
        print(f"\n   Open Positions:")
        for sym, pos in positions.items():
            print(f"     {sym}: {pos.get('side', '?')} @ {pos.get('entry_price', 0):.2f} "
                  f"P&L: {pos.get('unrealized_pnl', 0):+.2f}")

    # Signals
    signals = state.get("signal_stats", {})
    print(f"\n🤖 ML Signals")
    print(f"   Model Loaded:      {signals.get('model_loaded', False)}")
    print(f"   Candles Processed: {signals.get('candles_processed', 0)}")
    print(f"   Signals Generated: {signals.get('signals_generated', 0)}")

    # Safety details
    print(f"\n🛡️  Safety")
    print(f"   Orders Submitted:  {safety.get('total_orders_submitted', 0)}")
    print(f"   Orders Rejected:   {safety.get('total_orders_rejected', 0)}")
    print(f"   Consec. Losses:    {safety.get('consecutive_losses', 0)}")

    rejections = safety.get("recent_rejections", [])
    if rejections:
        print(f"   Recent Rejections:")
        for r in rejections[-3:]:
            print(f"     {r.get('symbol', '?')}: {r.get('reason', '?')}")

    print()


if __name__ == "__main__":
    main()
