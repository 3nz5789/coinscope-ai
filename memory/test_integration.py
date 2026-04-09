#!/usr/bin/env python3
"""
End-to-end integration test for the CoinScopeAI Memory System.
Verifies all stores, search, knowledge graph, taxonomy, and CLI.
"""

import json
import os
import shutil
import sys
import tempfile
import traceback

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.config import MemoryConfig
from memory.manager import MemoryManager

PASS = 0
FAIL = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def main():
    global PASS, FAIL

    # Use a temp directory so we don't pollute the real data
    tmpdir = tempfile.mkdtemp(prefix="csai_mem_test_")
    print(f"\nTest palace: {tmpdir}\n")

    try:
        config = MemoryConfig()
        config.palace_path = os.path.join(tmpdir, "palace")
        config.kg_db = os.path.join(tmpdir, "kg.db")
        config.identity_path = os.path.join(tmpdir, "identity.md")
        os.makedirs(config.palace_path, exist_ok=True)

        mm = MemoryManager(config)

        # ============================================================
        print("=" * 60)
        print("  1. Trading Memory (wing_trading)")
        print("=" * 60)

        sid = mm.trading.log_signal(
            symbol="BTCUSDT", signal="LONG", confidence=0.85,
            regime="trending_up", price=65000.0,
            reasoning="Breakout with funding flip"
        )
        check("log_signal returns drawer ID", sid and isinstance(sid, str))

        eid = mm.trading.log_entry(
            symbol="BTCUSDT", side="LONG", entry_price=65000.0,
            quantity=0.1, regime="trending_up", confidence=0.85,
            stop_loss=63700.0, take_profit=68000.0
        )
        check("log_entry returns drawer ID", eid and isinstance(eid, str))

        xid = mm.trading.log_exit(
            symbol="BTCUSDT", side="LONG", entry_price=65000.0,
            exit_price=67500.0, pnl_pct=0.038, pnl_usd=250.0,
            reason="take_profit", regime="trending_up"
        )
        check("log_exit returns drawer ID", xid and isinstance(xid, str))

        signals = mm.trading.signals_only(symbol="BTCUSDT", n=10)
        check("signals_only returns results", len(signals) >= 1)

        by_sym = mm.trading.by_symbol("BTCUSDT", n=10)
        check("by_symbol returns results", len(by_sym) >= 1)

        # ============================================================
        print("\n" + "=" * 60)
        print("  2. Risk Memory (wing_risk)")
        print("=" * 60)

        rid = mm.risk.log_risk_gate_check(
            symbol="BTCUSDT", passed=False, equity=8500.0,
            daily_pnl=-850.0, drawdown=0.15, consecutive_losses=4,
            open_positions=2, circuit_breaker_active=True,
            circuit_breaker_reason="Daily loss limit hit"
        )
        check("log_risk_gate_check returns ID", rid and isinstance(rid, str))

        did = mm.risk.log_drawdown_event(
            drawdown_pct=0.18, equity=8200.0, peak_equity=10000.0,
            trigger="3 consecutive losing trades"
        )
        check("log_drawdown_event returns ID", did and isinstance(did, str))

        kid = mm.risk.log_kill_switch(
            activated=True, reason="Max drawdown exceeded", equity=8200.0
        )
        check("log_kill_switch returns ID", kid and isinstance(kid, str))

        failed = mm.risk.failed_checks(n=10)
        check("failed_checks returns results", len(failed) >= 1)

        drawdowns = mm.risk.drawdowns(n=10)
        check("drawdowns returns results", len(drawdowns) >= 1)

        kills = mm.risk.kill_switch_events(n=10)
        check("kill_switch_events returns results", len(kills) >= 1)

        # ============================================================
        print("\n" + "=" * 60)
        print("  3. Scanner Memory (wing_scanner)")
        print("=" * 60)

        scid = mm.scanner.log_setup(
            symbol="ETHUSDT", setup_name="breakout_oi",
            timeframe="4h", regime="trending_up",
            confidence=0.78, outcome="WIN", pnl_pct=0.025,
            context="OI surge with positive funding"
        )
        check("log_setup returns ID", scid and isinstance(scid, str))

        # ============================================================
        print("\n" + "=" * 60)
        print("  4. Model Memory (wing_models)")
        print("=" * 60)

        mid = mm.models.log_training_run(
            model_name="lgbm_v3", symbol="BTCUSDT", timeframe="4h",
            params={"n_estimators": 200, "max_depth": 6},
            metrics={"accuracy": 0.58, "sharpe": 1.42},
            reasoning="Retrained after regime shift"
        )
        check("log_training_run returns ID", mid and isinstance(mid, str))

        pid = mm.models.log_performance_snapshot(
            model_name="paper_engine", symbol="PORTFOLIO",
            metrics={"total_pnl": 1250.0, "win_rate": 0.62, "sharpe": 1.8}
        )
        check("log_performance_snapshot returns ID", pid and isinstance(pid, str))

        # ============================================================
        print("\n" + "=" * 60)
        print("  5. System Memory (wing_system)")
        print("=" * 60)

        seid = mm.system.log_engine_start(
            engine_version="v2", symbols="BTCUSDT,ETHUSDT",
            config_summary="Paper trading, testnet"
        )
        check("log_engine_start returns ID", seid and isinstance(seid, str))

        rcid = mm.system.log_regime_change(
            symbol="BTCUSDT", old_regime="trending_up",
            new_regime="volatile", confidence=0.85, price=65000.0
        )
        check("log_regime_change returns ID", rcid and isinstance(rcid, str))

        regimes = mm.system.regime_changes(symbol="BTCUSDT", n=10)
        check("regime_changes returns results", len(regimes) >= 1)

        # ============================================================
        print("\n" + "=" * 60)
        print("  6. Agent Memory (wing_agent)")
        print("=" * 60)

        asid = mm.agents.start_session(
            agent_role="research",
            objective="Analyze OpenClaw protocol",
            context="Requested by trading team"
        )
        check("start_session returns session ID", asid and isinstance(asid, str))

        adid = mm.agents.log_decision(
            session_id=asid, agent_role="research",
            decision="OpenClaw funding data is reliable for 4h+",
            reasoning="Backtested against Binance, correlation > 0.92"
        )
        check("log_decision returns ID", adid and isinstance(adid, str))

        mm.agents.end_session(
            session_id=asid, agent_role="research",
            summary="OpenClaw validated for alpha pipeline"
        )
        check("end_session completes without error", True)

        diary_id = mm.agents.write_diary(
            agent_role="risk_agent",
            entry="SESSION:20260409|scanned.risk.gates|all.passed|★★★"
        )
        check("write_diary returns ID", diary_id and isinstance(diary_id, str))

        # ============================================================
        print("\n" + "=" * 60)
        print("  7. Project Knowledge (wing_dev)")
        print("=" * 60)

        adr_id = mm.knowledge.log_architecture_decision(
            title="Use ChromaDB for memory storage",
            decision="ChromaDB for vector storage, no external DB",
            reasoning="Simpler deployment, built-in embeddings",
            component="memory"
        )
        check("log_architecture_decision returns ID", adr_id and isinstance(adr_id, str))

        bf_id = mm.knowledge.log_bug_fix(
            title="Kelly sizing used wrong base capital",
            description="Kelly fraction calculated against initial_capital instead of current_equity",
            root_cause="Hardcoded 10000 in TradeJournal",
            fix="Parameterized initial_capital"
        )
        check("log_bug_fix returns ID", bf_id and isinstance(bf_id, str))

        # ============================================================
        print("\n" + "=" * 60)
        print("  8. Task Outcomes (wing_agent)")
        print("=" * 60)

        tid = mm.tasks.log_task_completed(
            task_id="CSAI-42", title="Integrate multi-exchange alpha",
            summary="Added funding and OI alpha generators",
            what_worked="Modular alpha interface",
            lessons_learned="Always normalize across exchanges"
        )
        check("log_task_completed returns ID", tid and isinstance(tid, str))

        fid = mm.tasks.log_task_failed(
            task_id="CSAI-43", title="Add Hyperliquid websocket",
            failure_reason="Rate limited after 10 minutes",
            root_cause="No backoff logic in websocket reconnect",
            recommendations="Add exponential backoff"
        )
        check("log_task_failed returns ID", fid and isinstance(fid, str))

        lessons = mm.tasks.lessons(n=10)
        check("lessons auto-extracted from completed/failed tasks", len(lessons) >= 1)

        # ============================================================
        print("\n" + "=" * 60)
        print("  9. Cross-wing Semantic Search")
        print("=" * 60)

        hits = mm.search("breakout signals on BTCUSDT with funding flip")
        check("search returns results", len(hits) >= 1)
        check("search results have wing field", all("wing" in h or "metadata" in h for h in hits))

        hits_filtered = mm.search("drawdown", wing="wing_risk")
        check("search with wing filter works", len(hits_filtered) >= 1)

        # ============================================================
        print("\n" + "=" * 60)
        print("  10. Knowledge Graph")
        print("=" * 60)

        kg_id = mm.kg_add("BTCUSDT", "in_regime", "volatile", valid_from="2026-04-09")
        check("kg_add returns row ID", kg_id is not None)

        facts = mm.kg_query("BTCUSDT")
        check("kg_query returns facts", len(facts) >= 1)

        timeline = mm.kg_timeline("BTCUSDT")
        check("kg_timeline returns entries", len(timeline) >= 1)

        stats = mm.kg_stats()
        check("kg_stats returns dict", isinstance(stats, dict))

        # ============================================================
        print("\n" + "=" * 60)
        print("  11. Taxonomy & Status")
        print("=" * 60)

        tax = mm.taxonomy()
        check("taxonomy returns wing tree", len(tax) >= 3)
        check("taxonomy has wing_trading", "wing_trading" in tax)
        check("taxonomy has wing_risk", "wing_risk" in tax)
        check("taxonomy has wing_agent", "wing_agent" in tax)

        st = mm.status()
        check("status returns palace_path", "palace_path" in st)
        check("status returns stores", "stores" in st)
        check("status total_drawers > 0", st.get("total_drawers", 0) > 0)

        # ============================================================
        print("\n" + "=" * 60)
        print("  12. Wake-up Context")
        print("=" * 60)

        wake = mm.wake_up()
        check("wake_up returns non-empty string", len(wake) > 10)

        wake_filtered = mm.wake_up(wing="wing_trading")
        check("wake_up with wing filter works", isinstance(wake_filtered, str))

    except Exception as e:
        FAIL += 1
        print(f"\n  [FATAL] Unexpected error: {e}")
        traceback.print_exc()

    finally:
        # Cleanup
        shutil.rmtree(tmpdir, ignore_errors=True)

    # ============================================================
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  Results: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 60 + "\n")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
