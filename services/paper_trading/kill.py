"""
CoinScopeAI Paper Trading — Kill Switch CLI
==============================================
Emergency: flatten all positions and stop trading.

Usage:
    python -m services.paper_trading.kill [--reason REASON]
    python -m services.paper_trading.kill --deactivate
"""

import argparse
import json
import sys
from pathlib import Path

from .safety import KillSwitch


def main():
    parser = argparse.ArgumentParser(
        description="CoinScopeAI Kill Switch (EMERGENCY)",
    )
    parser.add_argument(
        "--reason", type=str, default="manual_cli",
        help="Reason for activating kill switch",
    )
    parser.add_argument(
        "--deactivate", action="store_true",
        help="Deactivate the kill switch (requires manual confirmation)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Check kill switch status only",
    )

    args = parser.parse_args()
    ks = KillSwitch()

    if args.status:
        status = ks.status()
        if status["active"]:
            print(f"🚨 KILL SWITCH: ACTIVE")
            print(f"   Reason: {status['reason']}")
        else:
            print(f"✅ Kill Switch: OFF")
        return

    if args.deactivate:
        if not ks.is_active:
            print("Kill switch is already off.")
            return

        print("⚠️  You are about to DEACTIVATE the kill switch.")
        print("   This will allow the trading engine to resume trading.")
        confirm = input("   Type 'CONFIRM' to proceed: ")
        if confirm.strip() != "CONFIRM":
            print("Aborted.")
            return

        ks.deactivate()
        print("✅ Kill switch deactivated.")
        return

    # Activate
    print("🚨 ACTIVATING KILL SWITCH")
    print(f"   Reason: {args.reason}")
    print()
    print("   This will:")
    print("   1. Halt all new trading immediately")
    print("   2. Signal the engine to close all positions")
    print("   3. Persist until manually deactivated")
    print()

    confirm = input("   Type 'KILL' to confirm: ")
    if confirm.strip() != "KILL":
        print("Aborted.")
        return

    ks.activate(args.reason)
    print()
    print("🚨 KILL SWITCH ACTIVATED")
    print("   All trading halted.")
    print("   To deactivate: python -m services.paper_trading.kill --deactivate")


if __name__ == "__main__":
    main()
