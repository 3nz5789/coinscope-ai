"""
utils/io.py — Atomic JSON write primitive
==========================================

Single shared helper for all safe-save paths in the engine.
Used by: DailySessionState.save(), TradeMonitor.save(), TradeMonitor.self_cancel()

COI-5: disk I/O error handling (SLO: No Silent Data Loss)
Locked: 2026-05-10
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
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
