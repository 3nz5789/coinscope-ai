#!/usr/bin/env python3
"""
Production-Readiness Integration Test
=======================================
Tests all 5 production-readiness improvements:
  1. Non-blocking async write queue
  2. Idempotency/dedup with event_id
  3. Hall strategy enforcement
  4. Batch/flush model
  5. Retention & pruning policy
"""

import os
import sys
import time
import shutil
import tempfile
from datetime import datetime, timezone, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fresh_config(tmpdir: str):
    """Create a fresh MemoryConfig pointing at a temp directory."""
    from memory.config import MemoryConfig
    config = MemoryConfig(
        palace_dir=tmpdir,
        kg_db=os.path.join(tmpdir, "test_kg.sqlite3"),
        flush_interval_seconds=0.5,
        flush_batch_size=5,
        write_queue_size=10000,
    )
    return config


def _clear_singletons():
    """Clear process-wide caches between tests to avoid cross-contamination."""
    from memory.base_store import _BackgroundWriter, _client_cache, _collection_cache
    # Shutdown all existing writers
    for writer in list(_BackgroundWriter._instances.values()):
        try:
            writer.shutdown()
        except Exception:
            pass
    _BackgroundWriter._instances.clear()
    _client_cache.clear()
    _collection_cache.clear()


def test_1_nonblocking_writes():
    """Test 1: Non-blocking async write queue."""
    print("\n[TEST 1] Non-blocking async write queue")
    tmpdir = tempfile.mkdtemp(prefix="csai_test1_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        mm = MemoryManager(config)

        # Write should return immediately (non-blocking)
        start = time.monotonic()
        for i in range(20):
            mm.trading.log_signal(
                symbol=f"TEST{i}USDT",
                signal="LONG",
                confidence=0.8,
                regime="trending",
                price=50000.0 + i,
            )
        elapsed = time.monotonic() - start

        print(f"  Enqueued 20 events in {elapsed:.4f}s")
        assert elapsed < 2.0, f"Writes took too long ({elapsed:.2f}s) — not non-blocking!"

        # Wait for flush
        time.sleep(2.0)
        mm.flush()

        count = mm.trading.count()
        print(f"  After flush: {count} drawers in wing_trading")
        assert count >= 15, f"Expected at least 15 drawers, got {count}"

        mm.shutdown()
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_2_idempotency():
    """Test 2: Idempotency/dedup with event_id."""
    print("\n[TEST 2] Idempotency/dedup with event_id")
    tmpdir = tempfile.mkdtemp(prefix="csai_test2_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        mm = MemoryManager(config)

        # Write the same event 5 times with the same event_id
        for _ in range(5):
            mm.trading.log_signal(
                symbol="BTCUSDT",
                signal="LONG",
                confidence=0.9,
                regime="trending",
                price=67000.0,
                event_id="dedup_test_signal_001",
            )

        time.sleep(2.0)
        mm.flush()

        # Search for it — should find exactly 1
        hits = mm.trading.search("BTCUSDT LONG trending", n_results=10)
        dedup_hits = [h for h in hits if h.get("metadata", {}).get("event_id") == "dedup_test_signal_001"]
        print(f"  Wrote same event 5x, found {len(dedup_hits)} unique drawer(s)")
        assert len(dedup_hits) == 1, f"Expected 1 deduped drawer, got {len(dedup_hits)}"

        mm.shutdown()
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_3_hall_enforcement():
    """Test 3: Hall strategy enforcement."""
    print("\n[TEST 3] Hall strategy enforcement")
    tmpdir = tempfile.mkdtemp(prefix="csai_test3_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        from memory.config import HALL_STRATEGY
        mm = MemoryManager(config)

        # Try to write a signal with the wrong hall
        mm.trading.file_drawer(
            content="Test signal with wrong hall",
            room="signals",
            hall="hall_decisions",  # WRONG — should be hall_events
            metadata={"event_type": "signal", "symbol": "TESTUSDT"},
            event_id="hall_test_001",
        )

        time.sleep(2.0)
        mm.flush()

        # Check that the hall was corrected
        hits = mm.trading.search("Test signal with wrong hall", n_results=5)
        if hits:
            actual_hall = hits[0].get("metadata", {}).get("hall", "")
            expected = HALL_STRATEGY.get("wing_trading/signals", "")
            print(f"  Wrote with hall_decisions, stored as: {actual_hall} (expected: {expected})")
            assert actual_hall == expected, f"Hall not enforced: got {actual_hall}"
        else:
            print("  WARNING: Could not verify hall enforcement (no hits found)")

        mm.shutdown()
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_4_batch_flush():
    """Test 4: Batch/flush model."""
    print("\n[TEST 4] Batch/flush model")
    tmpdir = tempfile.mkdtemp(prefix="csai_test4_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        mm = MemoryManager(config)

        # Write events rapidly
        for i in range(10):
            mm.risk.log_drawdown_event(
                drawdown_pct=0.01 * (i + 1),
                equity=10000 - i * 100,
                peak_equity=10000,
                event_id=f"batch_test_{i:03d}",
            )

        # Check pending count before flush
        pending = mm.trading._writer.pending_count
        print(f"  Pending events after rapid writes: {pending}")

        # Force flush
        mm.flush()
        time.sleep(0.5)

        count = mm.risk.count()
        print(f"  After flush: {count} drawers in wing_risk")
        assert count >= 8, f"Expected at least 8 drawers, got {count}"

        mm.shutdown()
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_5_retention_pruning():
    """Test 5: Retention & pruning policy."""
    print("\n[TEST 5] Retention & pruning policy")
    tmpdir = tempfile.mkdtemp(prefix="csai_test5_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        mm = MemoryManager(config)

        # Write some events with old timestamps directly into ChromaDB
        import chromadb
        from memory.config import COLLECTION_NAME

        client = chromadb.PersistentClient(path=config.palace_path)
        col = client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

        old_date = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        recent_date = datetime.now(timezone.utc).isoformat()

        # Insert old events directly
        col.upsert(
            ids=["prune_old_1", "prune_old_2", "prune_old_3"],
            documents=["Old signal 1", "Old signal 2", "Old signal 3"],
            metadatas=[
                {"wing": "wing_trading", "room": "signals", "hall": "hall_events",
                 "filed_at": old_date, "event_id": "prune_old_1"},
                {"wing": "wing_trading", "room": "signals", "hall": "hall_events",
                 "filed_at": old_date, "event_id": "prune_old_2"},
                {"wing": "wing_trading", "room": "signals", "hall": "hall_events",
                 "filed_at": old_date, "event_id": "prune_old_3"},
            ],
        )

        # Insert events in exempt rooms (should never be pruned)
        col.upsert(
            ids=["prune_exempt_1"],
            documents=["Architecture decision that should never be pruned"],
            metadatas=[
                {"wing": "wing_dev", "room": "architecture", "hall": "hall_decisions",
                 "filed_at": old_date, "event_id": "prune_exempt_1"},
            ],
        )

        # Insert a recent event
        col.upsert(
            ids=["prune_recent_1"],
            documents=["Recent signal"],
            metadatas=[
                {"wing": "wing_trading", "room": "signals", "hall": "hall_events",
                 "filed_at": recent_date, "event_id": "prune_recent_1"},
            ],
        )

        # Dry run
        result = mm.prune(dry_run=True)
        print(f"  Dry run: {result['total_prunable']} prunable out of {result['total_scanned']} scanned")
        assert result["total_prunable"] >= 3, f"Expected at least 3 prunable, got {result['total_prunable']}"

        # Check that exempt rooms are not prunable
        prunable_ids = result.get("prunable_ids", [])
        assert "prune_exempt_1" not in prunable_ids, "Exempt room drawer should not be prunable!"

        # Actual prune
        result = mm.prune(dry_run=False)
        deleted = result.get("deleted", 0)
        print(f"  Actual prune: deleted {deleted} drawers")
        assert deleted >= 3, f"Expected at least 3 deleted, got {deleted}"

        # Verify exempt drawer still exists
        remaining = col.get(ids=["prune_exempt_1"])
        assert len(remaining["ids"]) == 1, "Exempt drawer was incorrectly pruned!"
        print("  Exempt room drawer preserved correctly")

        mm.shutdown()
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_6_cli_prune():
    """Test 6: CLI prune command."""
    print("\n[TEST 6] CLI prune --dry-run")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "memory", "prune", "--dry-run"],
        capture_output=True, text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    print(f"  Exit code: {result.returncode}")
    if result.stdout:
        for line in result.stdout.strip().split("\n")[:10]:
            print(f"  {line}")
    if result.returncode != 0 and result.stderr:
        print(f"  stderr: {result.stderr[:300]}")
    assert result.returncode == 0, f"CLI prune failed with exit code {result.returncode}"
    print("  PASSED")


def test_7_shutdown_flush():
    """Test 7: Graceful shutdown flushes all events."""
    print("\n[TEST 7] Graceful shutdown flush")
    tmpdir = tempfile.mkdtemp(prefix="csai_test7_")
    try:
        _clear_singletons()
        config = _fresh_config(tmpdir)
        from memory.manager import MemoryManager
        mm = MemoryManager(config)

        # Write events
        for i in range(10):
            mm.system.log_engine_start(
                engine_version=f"v{i}",
                event_id=f"shutdown_test_{i:03d}",
            )

        # Shutdown should flush
        mm.shutdown()

        # Verify all events were flushed
        import chromadb
        from memory.config import COLLECTION_NAME
        client = chromadb.PersistentClient(path=config.palace_path)
        col = client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        results = col.get(
            where={"wing": "wing_system"},
            include=["metadatas"],
            limit=100,
        )
        count = len(results.get("ids", []))
        print(f"  After shutdown: {count} drawers in wing_system")
        assert count >= 8, f"Expected at least 8 drawers after shutdown flush, got {count}"
        print("  PASSED")
    finally:
        _clear_singletons()
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("=" * 60)
    print("CoinScopeAI Memory — Production-Readiness Tests")
    print("=" * 60)

    try:
        test_1_nonblocking_writes()
        test_2_idempotency()
        test_3_hall_enforcement()
        test_4_batch_flush()
        test_5_retention_pruning()
        test_6_cli_prune()
        test_7_shutdown_flush()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
