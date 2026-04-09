#!/usr/bin/env python3
import argparse
import sys
import os
import json

# Add the current directory to sys.path so we can import the memory package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager
from memory.config import MemoryConfig, WINGS, ROOMS
from memory.base_store import PalaceStore

class CustomStore(PalaceStore):
    def __init__(self, config, wing):
        self._wing = wing
        super().__init__(config)

def main():
    parser = argparse.ArgumentParser(description="Scoopy Memory CLI - Project Coordinator Memory System")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search memory")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--wing", help="Filter by wing")
    search_parser.add_argument("--room", help="Filter by room")
    search_parser.add_argument("--limit", type=int, default=5, help="Result limit")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a memory")
    add_parser.add_argument("content", help="Memory content")
    add_parser.add_argument("--wing", required=True, help="Wing name (e.g., wing_project)")
    add_parser.add_argument("--room", required=True, help="Room name (e.g., facts)")
    add_parser.add_argument("--hall", help="Hall name (optional)")
    add_parser.add_argument("--category", help="Category metadata")

    # Wake-up command
    wakeup_parser = subparsers.add_parser("wake-up", help="Generate wake-up context")
    wakeup_parser.add_argument("--wing", help="Filter by wing")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show memory status")

    args = parser.parse_args()

    config = MemoryConfig()
    mm = MemoryManager(config)

    if args.command == "search":
        results = mm.deep_search(args.query, wing=args.wing, room=args.room, n_results=args.limit)
        print(results)

    elif args.command == "add":
        store = CustomStore(config, args.wing)
        metadata = {"category": args.category} if args.category else {}
        drawer_id = store.file_drawer(
            content=args.content,
            room=args.room,
            hall=args.hall or "",
            metadata=metadata
        )
        mm.flush()
        print(f"Memory added! Drawer ID: {drawer_id}")

    elif args.command == "wake-up":
        context = mm.wake_up(wing=args.wing)
        print(context)

    elif args.command == "status":
        stack = mm._get_stack()
        if stack:
            status = stack.status()
            print(json.dumps(status, indent=2))
        else:
            print("Memory stack not initialized.")

    else:
        parser.print_help()

    mm.shutdown()

if __name__ == "__main__":
    main()
