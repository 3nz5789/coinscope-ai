"""
Scale-Up Manager - Automated capital scaling

Manages 5 scaling profiles (S0-S4) with automatic promotion based on:
- Minimum number of profitable trades
- Minimum Sharpe ratio threshold
- Account size progression

BUG-15 FIX: current_index now persisted to disk so promotions survive restarts.
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path

from utils.io import atomic_write_json, quarantine_corrupt_file

logger = logging.getLogger(__name__)


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
        """Load persisted scale index from disk.

        On a corrupt / schema-drifted state file the file is renamed to
        ``*.corrupt.<UTC-ISO8601>.json`` for forensics and 0 is returned
        (re-seeds at S0). ``OSError`` from opening the file is NOT swallowed
        -- it propagates so the operator sees real permission/disk errors.
        """
        if not os.path.exists(self.STATE_FILE):
            return 0
        with open(self.STATE_FILE) as f:
            raw = f.read()
        try:
            data = json.loads(raw)
            idx = int(data.get("current_index", 0))
            # Guard against out-of-range values from a corrupt file
            return max(0, min(idx, len(PROFILES) - 1))
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            backup = quarantine_corrupt_file(Path(self.STATE_FILE))
            if backup is not None:
                logger.warning(
                    "ScaleUpManager: corrupt state file at %s (%s); moved to %s, re-seeding at S0",
                    self.STATE_FILE, type(exc).__name__, backup,
                )
            else:
                logger.error(
                    "ScaleUpManager: corrupt state file at %s (%s) AND quarantine rename failed; re-seeding at S0 in place",
                    self.STATE_FILE, type(exc).__name__,
                )
            return 0

    def _save_state(self) -> bool:
        """Persist current scale index to disk."""
        return atomic_write_json(Path(self.STATE_FILE), {"current_index": self.current_index})

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
            if not self._save_state():  # COI-78: rollback if persist fails
                self.current_index -= 1
                print(
                    f"⚠️  Promotion to {next_p.name} aborted: state save failed; "
                    f"staying on {self.current_profile.name}"
                )
                return None
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
