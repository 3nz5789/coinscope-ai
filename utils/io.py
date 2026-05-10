import json, logging, os, tempfile
from pathlib import Path
from typing import Any
_log = logging.getLogger(__name__)


def atomic_write_json(path: Path, data: dict) -> bool:
    tmp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, suffix=".tmp",
            delete=False, encoding="utf-8"
        ) as fh:
            tmp_path = Path(fh.name)
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(path)
        return True
    except OSError as exc:
        _log.error("atomic_write_json: failed writing %s: %s", path, exc)
        if tmp_path:
            try: tmp_path.unlink(missing_ok=True)
            except OSError: pass
        return False
