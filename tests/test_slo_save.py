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
