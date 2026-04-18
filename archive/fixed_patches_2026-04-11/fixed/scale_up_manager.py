"""
Scale-Up Manager - Automated capital scaling

Manages 5 scaling profiles (S0-S4) with automatic promotion based on:
- Minimum number of profitable trades
- Minimum Sharpe ratio threshold
- Account size progression

BUG-15 FIX: current_index now persisted to disk so promotions survive restarts.
"""

import os
import json
from dataclasses import dataclass


@dataclass
class Profile:
    """Scaling profile"""
    name: str
    account_usd: float
    position_pct: float
    min_trades: int
    min_sharpe: float


PROFILES = [
    Profile("S0_SEED", 1_000, 0.0100, 0, 0.0),
    Profile("S1_STARTER", 2_000, 0.0200, 100, 0.8),
    Profile("S2_GROWTH", 5_000, 0.0200, 200, 1.0),
    Profile("S3_SCALE", 10_000, 0.0200, 300, 1.2),
    Profile("S4_PRO", 25_000, 0.0200, 500, 1.5),
]


class ScaleUpManager:
    """Automated scaling manager"""

    STATE_FILE = "scale_up_state.json"

    def __init__(self):
        self.current_index = self._load_state()  # BUG-15 FIX: load from disk

    def _load_state(self) -> int:
        """Load persisted scale index from disk."""
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE) as f:
                    data = json.load(f)
                idx = int(data.get("current_index", 0))
                # Guard against out-of-range values from a corrupt file
                return max(0, min(idx, len(PROFILES) - 1))
            except Exception:
                pass
        return 0

    def _save_state(self):
        """Persist current scale index to disk."""
        with open(self.STATE_FILE, "w") as f:
            json.dump({"current_index": self.current_index}, f)

    @property
    def current_profile(self):
        """Get current profile"""
        return PROFILES[self.current_index]

    def check_promotion(self, trades: int, sharpe: float):
        """Check if promotion criteria met"""
        if self.current_index >= len(PROFILES) - 1:
            return None

        next_p = PROFILES[self.current_index + 1]
        if trades >= next_p.min_trades and sharpe >= next_p.min_sharpe:
            self.current_index += 1
            self._save_state()  # BUG-15 FIX: persist after promotion
            print(
                f"🚀 PROMOTED to {next_p.name}: "
                f"${next_p.account_usd:,} | {next_p.position_pct:.1%} sizing"
            )
            return next_p

        return None

    def status(self):
        """Get scaling status"""
        p = self.current_profile
        next_p = (
            PROFILES[self.current_index + 1]
            if self.current_index < len(PROFILES) - 1
            else None
        )
        return {
            "current": p.name,
            "account_usd": p.account_usd,
            "position_pct": p.position_pct,
            "next_profile": next_p.name if next_p else "MAX",
            "next_requires": {
                "trades": next_p.min_trades if next_p else "-",
                "sharpe": next_p.min_sharpe if next_p else "-",
            },
        }
