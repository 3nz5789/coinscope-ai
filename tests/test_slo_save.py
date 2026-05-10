"""
tests/test_slo_save.py — SLO: No Silent Data Loss
===================================================

Tests for COI-5, COI-6, COI-7 fixes.

COI-5: atomic_write_json primitive — disk I/O error handling
COI-6: TradeMonitor.self_cancel() — archive + delete atomicity
COI-7: DailySessionState._to_dict() — trade_log persistence

Run: pytest tests/test_slo_save.py -v
"""

from __future__ import annotations

import collections
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# COI-5 — atomic_write_json primitive
# ---------------------------------------------------------------------------

from utils.io import atomic_write_json


class TestAtomicWriteJson:

    def test_writes_valid_json(self, tmp_path):
        dest = tmp_path / "out.json"
        result = atomic_write_json(dest, {"key": "value", "n": 42})
        assert result is True
        assert dest.exists()
        loaded = json.loads(dest.read_text())
        assert loaded == {"key": "value", "n": 42}

    def test_returns_false_on_replace_oserror(self, tmp_path):
        dest = tmp_path / "out.json"
        with patch("pathlib.Path.replace", side_effect=OSError("disk full")):
            result = atomic_write_json(dest, {"key": "value"})
        assert result is False
        # destination must NOT have been written (no partial file)
        assert not dest.exists()

    def test_cleans_up_tmp_on_failure(self, tmp_path):
        dest = tmp_path / "out.json"
        with patch("pathlib.Path.replace", side_effect=OSError("disk full")):
            atomic_write_json(dest, {"key": "value"})
        orphans = list(tmp_path.glob("*.tmp"))
        assert orphans == [], f"Orphaned .tmp files found: {orphans}"

    def test_creates_parent_dirs(self, tmp_path):
        dest = tmp_path / "deep" / "nested" / "out.json"
        result = atomic_write_json(dest, {"x": 1})
        assert result is True
        assert dest.exists()

    def test_overwrites_existing_file(self, tmp_path):
        dest = tmp_path / "out.json"
        dest.write_text(json.dumps({"old": True}))
        result = atomic_write_json(dest, {"new": True})
        assert result is True
        assert json.loads(dest.read_text()) == {"new": True}

    def test_does_not_raise_on_oserror(self, tmp_path):
        dest = tmp_path / "out.json"
        with patch("pathlib.Path.replace", side_effect=OSError("permission denied")):
            # must not raise — just return False
            try:
                result = atomic_write_json(dest, {"x": 1})
                assert result is False
            except OSError:
                pytest.fail("atomic_write_json raised OSError instead of returning False")


# ---------------------------------------------------------------------------
# COI-6 — TradeMonitor.self_cancel() atomicity
# Note: imports adjusted to match actual v2 module path.
# If TradeMonitor lives at a different path, update the import below.
# ---------------------------------------------------------------------------

try:
    from coinscope_trading_engine.live.trade_monitor import (  # type: ignore[import]
        TradeMonitor,
        STATE_ARCHIVED,
    )
    TRADE_MONITOR_AVAILABLE = True
except ImportError:
    TRADE_MONITOR_AVAILABLE = False


@pytest.mark.skipif(not TRADE_MONITOR_AVAILABLE, reason="TradeMonitor not importable from this path")
class TestSelfCancel:

    def _make_monitor(self, tmp_path: Path) -> "TradeMonitor":
        """Build a minimal TradeMonitor for testing."""
        monitor_file = tmp_path / "monitor.json"
        monitor_file.write_text(json.dumps({"symbol": "BTCUSDT", "state": "ACTIVE"}))
        return TradeMonitor(path=monitor_file)

    def test_state_not_set_on_archive_failure(self, tmp_path):
        """If archive write fails, state must NOT become ARCHIVED."""
        monitor = self._make_monitor(tmp_path)
        with patch("utils.io.atomic_write_json", return_value=False):
            result = monitor.self_cancel()
        assert result is False
        assert monitor.state != STATE_ARCHIVED

    def test_monitor_file_intact_on_archive_failure(self, tmp_path):
        """If archive write fails, original monitor file must stay intact."""
        monitor = self._make_monitor(tmp_path)
        with patch("utils.io.atomic_write_json", return_value=False):
            monitor.self_cancel()
        assert monitor._path.exists(), "Monitor file deleted despite archive failure"

    def test_state_archived_even_if_unlink_fails(self, tmp_path):
        """After successful archive, unlink failure must not block ARCHIVED state."""
        monitor = self._make_monitor(tmp_path)
        with patch("pathlib.Path.unlink", side_effect=PermissionError("locked")):
            result = monitor.self_cancel()
        assert result is True
        assert monitor.state == STATE_ARCHIVED

    def test_clean_cancel_returns_true(self, tmp_path):
        """Happy path: archive written, monitor unlinked, state ARCHIVED, True returned."""
        monitor = self._make_monitor(tmp_path)
        result = monitor.self_cancel()
        assert result is True
        assert monitor.state == STATE_ARCHIVED
        assert not monitor._path.exists()


# ---------------------------------------------------------------------------
# COI-7 — DailySessionState trade_log persistence
# Note: imports adjusted to match actual v2 module path.
# ---------------------------------------------------------------------------

try:
    from coinscope_trading_engine.live.daily_session_state import (  # type: ignore[import]
        DailySessionState,
        MAX_LOG_SIZE,
    )
    SESSION_STATE_AVAILABLE = True
except ImportError:
    SESSION_STATE_AVAILABLE = False


@pytest.mark.skipif(not SESSION_STATE_AVAILABLE, reason="DailySessionState not importable from this path")
class TestTradeLogPersistence:

    def test_trade_log_survives_save_load_cycle(self, tmp_path):
        state = DailySessionState(path=tmp_path / "state.json")
        state.record_trade({"symbol": "BTCUSDT", "pnl": 0.012, "side": "LONG"})
        state.record_trade({"symbol": "ETHUSDT", "pnl": -0.005, "side": "SHORT"})
        assert state.save() is True

        loaded = DailySessionState.load(tmp_path / "state.json")
        assert len(loaded._trade_log) == 2
        assert loaded._trade_log[0]["symbol"] == "BTCUSDT"
        assert loaded._trade_log[1]["symbol"] == "ETHUSDT"

    def test_load_old_file_without_trade_log_key(self, tmp_path):
        """Old session files without trade_log key must load cleanly."""
        old_file = tmp_path / "state.json"
        old_file.write_text(json.dumps({
            "session_date": "2026-05-10",
            "daily_pnl": 0.0,
            "open_positions": 0,
            # no trade_log key — simulates pre-COI-7 file
        }))
        state = DailySessionState.load(old_file)
        assert isinstance(state._trade_log, collections.deque)
        assert len(state._trade_log) == 0

    def test_trade_log_capped_at_max_size_on_restore(self, tmp_path):
        state = DailySessionState(path=tmp_path / "state.json")
        for i in range(MAX_LOG_SIZE + 10):
            state.record_trade({"symbol": "BTCUSDT", "pnl": 0.001 * i})
        assert state.save() is True

        loaded = DailySessionState.load(tmp_path / "state.json")
        assert len(loaded._trade_log) == MAX_LOG_SIZE

    def test_trade_log_order_preserved(self, tmp_path):
        state = DailySessionState(path=tmp_path / "state.json")
        trades = [{"symbol": f"SYM{i}", "pnl": float(i)} for i in range(5)]
        for t in trades:
            state.record_trade(t)
        state.save()

        loaded = DailySessionState.load(tmp_path / "state.json")
        symbols = [t["symbol"] for t in loaded._trade_log]
        assert symbols == [f"SYM{i}" for i in range(5)]

    def test_save_returns_bool(self, tmp_path):
        state = DailySessionState(path=tmp_path / "state.json")
        result = state.save()
        assert isinstance(result, bool)
        assert result is True


# ---------------------------------------------------------------------------
# COI-79 — PairMonitor._save atomicity (port of COI-75 from docs tree to real engine)
# ---------------------------------------------------------------------------

try:
    from engine.core.pair_monitor import PairMonitor  # type: ignore[import]
    PAIR_MONITOR_AVAILABLE = True
except ImportError:
    PAIR_MONITOR_AVAILABLE = False


@pytest.mark.skipif(not PAIR_MONITOR_AVAILABLE, reason="PairMonitor not importable from this path")
class TestPairMonitorSave:

    def test_save_returns_true_and_writes_file(self, tmp_path):
        m = PairMonitor(path=str(tmp_path / "pair.json"))
        m.record_trade("BTC/USDT", 0.012, "bull", "LONG")
        # record_trade already called _save once; verify file exists and parses
        assert (tmp_path / "pair.json").exists()
        data = json.loads((tmp_path / "pair.json").read_text())
        assert "BTC/USDT" in data
        assert data["BTC/USDT"]["trades"] == 1

    def test_save_returns_false_on_oserror(self, tmp_path):
        m = PairMonitor(path=str(tmp_path / "pair.json"))
        with patch("engine.core.pair_monitor.atomic_write_json", return_value=False):
            assert m._save() is False

    def test_no_partial_file_on_replace_oserror(self, tmp_path):
        dest = tmp_path / "pair.json"
        m = PairMonitor(path=str(dest))
        m.stats.clear()  # start clean
        with patch("pathlib.Path.replace", side_effect=OSError("disk full")):
            m._save()
        # destination must not exist and no .tmp files left behind
        assert not dest.exists()
        assert list(tmp_path.glob("*.tmp")) == []

    def test_save_returns_bool(self, tmp_path):
        m = PairMonitor(path=str(tmp_path / "pair.json"))
        result = m._save()
        assert isinstance(result, bool)
        assert result is True


# ---------------------------------------------------------------------------
# COI-81 — quarantine_corrupt_file primitive + read-side corrupt-file handling
# ---------------------------------------------------------------------------

import logging  # noqa: E402

from utils.io import quarantine_corrupt_file  # noqa: E402


class TestQuarantineCorruptFile:

    def test_renames_with_timestamp_suffix(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json")
        backup = quarantine_corrupt_file(p)
        assert backup is not None
        assert not p.exists()
        assert backup.exists()
        assert backup.read_text() == "not json"
        assert backup.name.startswith("state.corrupt.")
        assert backup.name.endswith(".json")

    def test_preserves_original_suffix(self, tmp_path):
        p = tmp_path / "data.bin"
        p.write_text("garbage")
        backup = quarantine_corrupt_file(p)
        assert backup is not None
        assert backup.suffix == ".bin"

    def test_returns_none_on_rename_oserror(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json")
        with patch("pathlib.Path.rename", side_effect=OSError("disk full")):
            backup = quarantine_corrupt_file(p)
        assert backup is None


@pytest.mark.skipif(not PAIR_MONITOR_AVAILABLE, reason="PairMonitor not importable from this path")
class TestPairMonitorLoadCorruption:

    def test_corrupt_json_quarantined_and_starts_fresh(self, tmp_path, caplog):
        path = tmp_path / "pair.json"
        path.write_text("{ not valid json")
        caplog.set_level(logging.WARNING, logger="engine.core.pair_monitor")

        m = PairMonitor(path=str(path))
        assert m.stats == {}
        # original removed, backup with same content present
        assert not path.exists()
        backups = list(tmp_path.glob("pair.corrupt.*.json"))
        assert len(backups) == 1
        assert backups[0].read_text() == "{ not valid json"
        # warning logged with file path
        assert any(
            "PairMonitor" in r.message and "corrupt" in r.message and str(path) in r.message
            for r in caplog.records
        ), caplog.records

    def test_schema_drift_quarantined(self, tmp_path, caplog):
        # Valid JSON but doesn't match PairStats schema -> TypeError on unpacking
        path = tmp_path / "pair.json"
        path.write_text(json.dumps({"BTC/USDT": {"unknown_field": 1}}))
        caplog.set_level(logging.WARNING, logger="engine.core.pair_monitor")

        m = PairMonitor(path=str(path))
        assert m.stats == {}
        assert not path.exists()
        assert len(list(tmp_path.glob("pair.corrupt.*.json"))) == 1

    def test_missing_file_returns_empty_no_backup_no_log(self, tmp_path, caplog):
        path = tmp_path / "pair.json"
        caplog.set_level(logging.WARNING, logger="engine.core.pair_monitor")

        m = PairMonitor(path=str(path))
        assert m.stats == {}
        assert list(tmp_path.glob("pair.corrupt.*.json")) == []
        assert not any("corrupt" in r.message for r in caplog.records)

    def test_valid_file_loads_unchanged(self, tmp_path):
        path = tmp_path / "pair.json"
        # Use a real PairMonitor to write a valid file first
        m1 = PairMonitor(path=str(path))
        m1.record_trade("BTC/USDT", 0.012, "bull", "LONG")
        # Now reload from disk
        m2 = PairMonitor(path=str(path))
        assert "BTC/USDT" in m2.stats
        assert m2.stats["BTC/USDT"].trades == 1
        # No corruption backup created on the happy path
        assert list(tmp_path.glob("pair.corrupt.*.json")) == []


try:
    from engine.core.scale_up_manager import ScaleUpManager, PROFILES  # type: ignore[import]
    SCALE_UP_AVAILABLE = True
except ImportError:
    SCALE_UP_AVAILABLE = False


@pytest.mark.skipif(not SCALE_UP_AVAILABLE, reason="ScaleUpManager not importable from this path")
class TestScaleUpManagerLoadCorruption:

    def _state_file(self, monkeypatch, tmp_path) -> Path:
        """Point ScaleUpManager.STATE_FILE at tmp_path for the duration of one test."""
        target = tmp_path / "scale_up_state.json"
        monkeypatch.setattr(ScaleUpManager, "STATE_FILE", str(target))
        return target

    def test_corrupt_json_quarantined_and_reseeds_at_s0(self, monkeypatch, tmp_path, caplog):
        target = self._state_file(monkeypatch, tmp_path)
        target.write_text("definitely not json")
        caplog.set_level(logging.WARNING, logger="engine.core.scale_up_manager")

        m = ScaleUpManager()
        assert m.current_index == 0
        assert not target.exists()
        backups = list(tmp_path.glob("scale_up_state.corrupt.*.json"))
        assert len(backups) == 1
        assert backups[0].read_text() == "definitely not json"
        assert any(
            "ScaleUpManager" in r.message and "corrupt" in r.message
            for r in caplog.records
        ), caplog.records

    def test_schema_drift_quarantined(self, monkeypatch, tmp_path, caplog):
        target = self._state_file(monkeypatch, tmp_path)
        # current_index is a non-int -> ValueError on int() cast
        target.write_text(json.dumps({"current_index": "nope"}))
        caplog.set_level(logging.WARNING, logger="engine.core.scale_up_manager")

        m = ScaleUpManager()
        assert m.current_index == 0
        assert not target.exists()
        assert len(list(tmp_path.glob("scale_up_state.corrupt.*.json"))) == 1

    def test_missing_file_returns_zero_no_backup_no_log(self, monkeypatch, tmp_path, caplog):
        self._state_file(monkeypatch, tmp_path)
        caplog.set_level(logging.WARNING, logger="engine.core.scale_up_manager")

        m = ScaleUpManager()
        assert m.current_index == 0
        assert list(tmp_path.glob("scale_up_state.corrupt.*.json")) == []
        assert not any("corrupt" in r.message for r in caplog.records)

    def test_valid_file_loads_unchanged(self, monkeypatch, tmp_path):
        target = self._state_file(monkeypatch, tmp_path)
        target.write_text(json.dumps({"current_index": 2}))
        m = ScaleUpManager()
        assert m.current_index == 2
        assert list(tmp_path.glob("scale_up_state.corrupt.*.json")) == []

    def test_oserror_on_open_propagates(self, monkeypatch, tmp_path):
        target = self._state_file(monkeypatch, tmp_path)
        target.write_text(json.dumps({"current_index": 1}))
        with patch("builtins.open", side_effect=PermissionError("denied")):
            with pytest.raises(PermissionError):
                ScaleUpManager()
