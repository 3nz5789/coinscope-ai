#!/usr/bin/env python3
"""
CoinScopeAI Memory CLI
========================
Query, inspect, and maintain the MemPalace from the command line.

Usage::

    python -m memory search "Why did we go long on BTCUSDT?"
    python -m memory search "risk gate readings before drawdown" --wing wing_risk
    python -m memory signals --symbol BTCUSDT
    python -m memory regimes --symbol ETHUSDT
    python -m memory risks
    python -m memory decisions --agent research
    python -m memory knowledge
    python -m memory lessons
    python -m memory kg-query BTCUSDT
    python -m memory kg-timeline BTCUSDT
    python -m memory taxonomy
    python -m memory wake-up --wing wing_trading
    python -m memory status
    python -m memory export
    python -m memory prune --dry-run
    python -m memory prune --execute
"""

import argparse
import json
import sys
from typing import Any, Dict, List

from .manager import MemoryManager


# ------------------------------------------------------------------
# Formatters
# ------------------------------------------------------------------

def _fmt_hit(hit: Dict[str, Any], idx: int) -> str:
    wing = hit.get("wing", hit.get("metadata", {}).get("wing", "?"))
    room = hit.get("room", hit.get("metadata", {}).get("room", "?"))
    sim = hit.get("similarity", 0)
    text = hit.get("text", "")
    lines = [f"  [{idx}] {wing}/{room}  (similarity={sim:.3f})"]
    for line in text.strip().split("\n")[:6]:
        lines.append(f"      {line}")
    if text.count("\n") > 5:
        lines.append("      ...")
    return "\n".join(lines)


def _fmt_drawer(drawer: Dict[str, Any], idx: int) -> str:
    meta = drawer.get("metadata", {})
    wing = meta.get("wing", "?")
    room = meta.get("room", "?")
    date = meta.get("date", meta.get("filed_at", "?"))
    text = drawer.get("text", "")
    lines = [f"  [{idx}] {wing}/{room}  ({date})"]
    for line in text.strip().split("\n")[:6]:
        lines.append(f"      {line}")
    if text.count("\n") > 5:
        lines.append("      ...")
    return "\n".join(lines)


def _fmt_kg_fact(fact: Dict[str, Any]) -> str:
    s = fact.get("subject", "?")
    p = fact.get("predicate", "?")
    o = fact.get("object", "?")
    vf = fact.get("valid_from", "")
    ve = fact.get("valid_to", fact.get("ended", ""))
    line = f"  {s} -> {p} -> {o}"
    if vf:
        line += f"  (from: {vf}"
        if ve:
            line += f", to: {ve}"
        line += ")"
    return line


def _print_results(label: str, items: List, formatter):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")
    if not items:
        print("  No results found.\n")
        return
    for i, item in enumerate(items, 1):
        print(formatter(item, i))
        print(f"  {'─' * 56}")
    print(f"\n  Total: {len(items)}\n")


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

def cmd_search(args, mm: MemoryManager):
    query = " ".join(args.query)
    hits = mm.search(query, wing=args.wing, room=args.room, n_results=args.limit)
    _print_results(f'Search: "{query}"', hits, _fmt_hit)


def cmd_signals(args, mm: MemoryManager):
    drawers = mm.trading.signals_only(symbol=args.symbol or "", n=args.limit)
    label = f"Signals for {args.symbol}" if args.symbol else "Recent signals"
    _print_results(label, drawers, _fmt_drawer)


def cmd_regimes(args, mm: MemoryManager):
    drawers = mm.system.regime_changes(symbol=args.symbol or "", n=args.limit)
    label = f"Regime changes for {args.symbol}" if args.symbol else "Recent regime changes"
    _print_results(label, drawers, _fmt_drawer)


def cmd_risks(args, mm: MemoryManager):
    failed = mm.risk.failed_checks(n=args.limit)
    drawdowns = mm.risk.drawdowns(n=5)
    kills = mm.risk.kill_switch_events(n=5)

    total = len(failed) + len(drawdowns) + len(kills)
    if total == 0:
        print("\nNo risk events found")
        return

    print(f"\nRisk Events Summary")
    print(f"{'=' * 60}")
    if drawdowns:
        print(f"\n  Drawdown events ({len(drawdowns)}):")
        for i, r in enumerate(drawdowns, 1):
            print(_fmt_drawer(r, i))
    if kills:
        print(f"\n  Kill switch events ({len(kills)}):")
        for i, r in enumerate(kills, 1):
            print(_fmt_drawer(r, i))
    if failed:
        print(f"\n  Failed risk checks ({len(failed)}):")
        for i, r in enumerate(failed, 1):
            print(_fmt_drawer(r, i))
    print()


def cmd_decisions(args, mm: MemoryManager):
    drawers = mm.agents.decisions(agent_role=args.agent or "", n=args.limit)
    _print_results("Agent decisions", drawers, _fmt_drawer)


def cmd_knowledge(args, mm: MemoryManager):
    if args.category:
        drawers = mm.knowledge.by_category(args.category, n=args.limit)
    else:
        drawers = mm.knowledge.architecture_decisions(n=args.limit)
    label = f"Knowledge: {args.category}" if args.category else "Architecture decisions"
    _print_results(label, drawers, _fmt_drawer)


def cmd_lessons(args, mm: MemoryManager):
    drawers = mm.tasks.lessons(n=args.limit)
    _print_results("Lessons learned", drawers, _fmt_drawer)


def cmd_kg_query(args, mm: MemoryManager):
    facts = mm.kg_query(args.entity, as_of=args.as_of)
    print(f"\n{'=' * 60}")
    print(f"  Knowledge graph: {args.entity}")
    print(f"{'=' * 60}\n")
    if not facts:
        print("  No facts found.\n")
        return
    for f in facts:
        print(_fmt_kg_fact(f))
    print(f"\n  Total facts: {len(facts)}\n")


def cmd_kg_timeline(args, mm: MemoryManager):
    entity = args.entity if args.entity else None
    timeline = mm.kg_timeline(entity)
    label = f"Timeline for {entity}" if entity else "Full timeline"
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")
    if not timeline:
        print("  No timeline entries.\n")
        return
    for f in timeline:
        print(_fmt_kg_fact(f))
    print(f"\n  Total: {len(timeline)}\n")


def cmd_taxonomy(args, mm: MemoryManager):
    tree = mm.taxonomy()
    print(f"\n{'=' * 60}")
    print("  Palace Taxonomy: wing -> room -> count")
    print(f"{'=' * 60}\n")
    if not tree:
        print("  Palace is empty.\n")
        return
    total = 0
    for wing in sorted(tree.keys()):
        rooms = tree[wing]
        wing_total = sum(rooms.values())
        total += wing_total
        print(f"  {wing} ({wing_total} drawers)")
        for room in sorted(rooms.keys()):
            print(f"    +-- {room}: {rooms[room]}")
    print(f"\n  Total drawers: {total}\n")


def cmd_wake_up(args, mm: MemoryManager):
    text = mm.wake_up(wing=args.wing)
    tokens_est = len(text) // 4
    print(f"\n{'=' * 60}")
    print(f"  Wake-up context (~{tokens_est} tokens)")
    print(f"{'=' * 60}\n")
    print(text)
    print()


def cmd_status(args, mm: MemoryManager):
    st = mm.status()
    print(json.dumps(st, indent=2, default=str))


def cmd_export(args, mm: MemoryManager):
    import chromadb
    from .config import COLLECTION_NAME
    try:
        client = chromadb.PersistentClient(path=mm.config.palace_path)
        col = client.get_collection(COLLECTION_NAME)
        results = col.get(include=["documents", "metadatas"], limit=100000)
    except Exception as e:
        print(f"Export error: {e}")
        return

    records = []
    for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"]):
        records.append({"id": doc_id, "text": doc, "metadata": meta})

    output = args.output or "memory_export.json"
    with open(output, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"Exported {len(records)} drawers to {output}")


def cmd_prune(args, mm: MemoryManager):
    """Prune old drawers based on retention policy."""
    dry_run = not args.execute

    if dry_run:
        print(f"\n{'=' * 60}")
        print("  Retention Pruning — DRY RUN (no data will be deleted)")
        print(f"{'=' * 60}\n")
    else:
        print(f"\n{'=' * 60}")
        print("  Retention Pruning — EXECUTING (data will be deleted)")
        print(f"{'=' * 60}\n")

    result = mm.prune(dry_run=dry_run)

    if "error" in result:
        print(f"  Error: {result['error']}\n")
        return

    # Print retention config
    print("  Retention configuration:")
    for wing, days in sorted(result.get("retention_config", {}).items()):
        label = f"{days} days" if days >= 0 else "indefinite"
        print(f"    {wing}: {label}")
    print(f"  Exempt rooms: {', '.join(result.get('exempt_rooms', []))}")
    print()

    # Print summary
    print(f"  Total drawers scanned: {result.get('total_scanned', 0)}")
    print(f"  Total prunable:        {result.get('total_prunable', 0)}")
    print()

    pruned_by_wing = result.get("pruned_by_wing", {})
    if pruned_by_wing:
        print("  Breakdown by wing:")
        for wing, count in sorted(pruned_by_wing.items()):
            print(f"    {wing}: {count} drawers")
        print()

    if dry_run:
        preview_ids = result.get("prunable_ids", [])
        if preview_ids:
            print(f"  Preview of prunable drawer IDs (first {len(preview_ids)}):")
            for did in preview_ids[:20]:
                print(f"    - {did}")
            if len(preview_ids) > 20:
                print(f"    ... and {len(preview_ids) - 20} more")
        print()
        print("  To actually delete, run: python -m memory prune --execute")
    else:
        deleted = result.get("deleted", 0)
        print(f"  Deleted: {deleted} drawers")

    print()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="csai-memory",
        description="CoinScopeAI Memory — query, inspect, and maintain the MemPalace",
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # search
    p = sub.add_parser("search", help="Semantic search across all wings")
    p.add_argument("query", nargs="+", help="Search query")
    p.add_argument("--wing", default=None, help="Filter by wing")
    p.add_argument("--room", default=None, help="Filter by room")
    p.add_argument("--limit", type=int, default=10, help="Max results")

    # signals
    p = sub.add_parser("signals", help="Show trade signals")
    p.add_argument("--symbol", default="", help="Filter by symbol")
    p.add_argument("--limit", type=int, default=20)

    # regimes
    p = sub.add_parser("regimes", help="Show regime changes")
    p.add_argument("--symbol", default="", help="Filter by symbol")
    p.add_argument("--limit", type=int, default=20)

    # risks
    p = sub.add_parser("risks", help="Show risk events")
    p.add_argument("--limit", type=int, default=20)

    # decisions
    p = sub.add_parser("decisions", help="Show agent decisions")
    p.add_argument("--agent", default="", help="Agent role filter")
    p.add_argument("--limit", type=int, default=20)

    # knowledge
    p = sub.add_parser("knowledge", help="Show project knowledge")
    p.add_argument("--category", default="", help="Category filter")
    p.add_argument("--limit", type=int, default=20)

    # lessons
    p = sub.add_parser("lessons", help="Show lessons learned")
    p.add_argument("--limit", type=int, default=20)

    # kg-query
    p = sub.add_parser("kg-query", help="Query knowledge graph for an entity")
    p.add_argument("entity", help="Entity to query")
    p.add_argument("--as-of", default=None, help="Date filter (YYYY-MM-DD)")

    # kg-timeline
    p = sub.add_parser("kg-timeline", help="Show knowledge graph timeline")
    p.add_argument("entity", nargs="?", default=None, help="Entity (optional)")

    # taxonomy
    sub.add_parser("taxonomy", help="Show wing -> room -> count tree")

    # wake-up
    p = sub.add_parser("wake-up", help="Generate agent wake-up context")
    p.add_argument("--wing", default=None, help="Wing filter")

    # status
    sub.add_parser("status", help="Show full system status (JSON)")

    # export
    p = sub.add_parser("export", help="Export all drawers to JSON")
    p.add_argument("--output", default="memory_export.json", help="Output file")

    # prune
    p = sub.add_parser("prune", help="Prune old drawers based on retention policy")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview what would be deleted (default)",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Actually delete prunable drawers",
    )

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    mm = MemoryManager()

    commands = {
        "search": cmd_search,
        "signals": cmd_signals,
        "regimes": cmd_regimes,
        "risks": cmd_risks,
        "decisions": cmd_decisions,
        "knowledge": cmd_knowledge,
        "lessons": cmd_lessons,
        "kg-query": cmd_kg_query,
        "kg-timeline": cmd_kg_timeline,
        "taxonomy": cmd_taxonomy,
        "wake-up": cmd_wake_up,
        "status": cmd_status,
        "export": cmd_export,
        "prune": cmd_prune,
    }

    fn = commands.get(args.command)
    if fn:
        fn(args, mm)
    else:
        parser.print_help()

    # Ensure graceful shutdown
    mm.shutdown()


if __name__ == "__main__":
    main()
