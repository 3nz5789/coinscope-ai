"""
utils/io.py — Atomic JSON write + corrupt-file quarantine primitives
======================================================================

Single shared module for safe-persistence helpers in the engine.

Used by:
* ``atomic_write_json`` — DailySessionState.save(), TradeMonitor.save(),
  TradeMonitor.self_cancel(), PaperTradingEngine{,V2}._save_state(),
  ScaleUpManager._save_state(), PairMonitor._save()
* ``quarantine_corrupt_file`` — PairMonitor._load(),
  ScaleUpManager._load_state()

COI-5: disk I/O error handling (SLO: No Silent Data Loss) — write side
COI-81: corrupt-file quarantine (SLO: No Silent Data Loss) — read side
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


def atomic_write_json(path: Path, data: dict[str, Any]) -> bool:
    """Write *data* as JSON to *path* atomically.

    Strategy: write to a sibling .tmp file -> fsync -> atomic rename.
    On any OSError the .tmp is cleaned up and False is returned.
    Never raises -- the caller decides how to handle a False result.

    Args:
        path: Destination file path. Parent directory must exist or be
              creatable.
        data: JSON-serialisable dict.

    Returns:
        True on success, False on any OSError (logged at ERROR level).
    """
    tmp_path: Path | None = None
    try:
        dir_ = path.parent
        dir_.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=dir_,
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        ) as fh:
            tmp_path = Path(fh.name)
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())

        tmp_path.replace(path)
        return True

    except OSError as exc:
        _log.error("atomic_write_json: failed writing %s: %s", path, exc)
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False


def quarantine_corrupt_file(path: Path) -> Path | None:
    """Rename a corrupt state file to ``<stem>.corrupt.<UTC-ISO8601>.<suffix>``.

    Used by state-loaders when the on-disk content fails to parse or
    deserialize. Returns the backup Path on success, ``None`` if the rename
    itself fails (in which case the caller should log at ERROR and continue
    with defaults; the next atomic_write_json will overwrite the bad file
    in place).

    Args:
        path: The corrupt file's current path.

    Returns:
        The new ``Path`` of the renamed backup, or ``None`` on rename failure.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    # Stem of "pair_monitor.json" is "pair_monitor"; we want
    # "pair_monitor.corrupt.<ts>.json" -- preserve the original suffix.
    backup = path.with_name(f"{path.stem}.corrupt.{ts}{path.suffix}")
    try:
        path.rename(backup)
        return backup
    except OSError as exc:
        _log.error(
            "quarantine_corrupt_file: rename of %s -> %s failed: %s",
            path, backup, exc,
        )
        return None
