#!/usr/bin/env python3
"""NERV Memory Bridge — semantic memory from Hermes via direct Python import.

Usage:
  uv run python nerv_memory_bridge.py save --title "..." --type decision --content "..."
  uv run python nerv_memory_bridge.py search "query" --limit 3 --type-filter architecture
  uv run python nerv_memory_bridge.py recall "topic-key"
  uv run python nerv_memory_bridge.py context --n 5

Run from inside a project directory (one with .git or pyproject.toml).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# NERV imports — must be run from within the nerv project venv
_NERV_DIR = Path(__file__).resolve().parent


def _get_service():
    """Bootstrap MemoryService from the current project root."""
    sys.path.insert(0, str(_NERV_DIR / "src"))
    from nerv.config import load_runtime_settings
    from nerv.mcp.memory_service import MemoryService

    settings = load_runtime_settings(project_root=Path.cwd())
    return MemoryService(settings)


def cmd_save(args: argparse.Namespace) -> None:
    svc = _get_service()
    result = svc.memory_save(
        content=args.content,
        title=args.title,
        type=args.type,
        topic_key=args.topic_key,
        scope=args.scope,
    )
    print(json.dumps(result, indent=2, default=str))


def cmd_search(args: argparse.Namespace) -> None:
    svc = _get_service()
    result = svc.memory_search(
        query=args.query,
        limit=args.limit,
        type_filter=args.type_filter,
        keyword=args.keyword,
        snippet_only=args.snippet_only,
        include_personal=args.include_personal,
    )
    # Print as readable text, not raw JSON
    items = result.get("results", [])
    if not items:
        print("No memories found.")
        return
    for i, item in enumerate(items, 1):
        print(f"[{i}] {item['title']}  (score={item.get('score', 0):.2f})")
        print(f"    type={item['type']}  topic={item.get('topic_key', '-')}")
        print(f"    {item['content'][:300]}")
        print()
    print(f"--- {len(items)} results ---")


def cmd_recall(args: argparse.Namespace) -> None:
    svc = _get_service()
    result = svc.memory_recall(topic_key=args.topic_key)
    found = result.get("found", False)
    if not found:
        print(f"No memory found for topic_key='{args.topic_key}'")
        return
    print(f"Title: {result.get('title', '-')}")
    print(f"Type: {result.get('type', '-')}")
    print(f"Timestamp: {result.get('timestamp', '-')}")
    print("Content:")
    print(result.get("content", ""))


def cmd_context(args: argparse.Namespace) -> None:
    svc = _get_service()
    result = svc.memory_context(n=args.n)
    memories = result.get("memories", [])
    if not memories:
        print("No recent memories.")
        return
    for i, mem in enumerate(memories, 1):
        print(f"[{i}] {mem.get('title', '-')}  ({mem.get('type', '-')})")
        content = mem.get("content", "")
        print(f"    {content[:200]}")
        print()
    print(f"--- {len(memories)} recent memories ---")


def main() -> None:
    parser = argparse.ArgumentParser(description="NERV Memory Bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    # save
    p_save = sub.add_parser("save")
    p_save.add_argument("--title", required=True)
    p_save.add_argument(
        "--type",
        required=True,
        choices=[
            "architecture",
            "bugfix",
            "config",
            "decision",
            "discovery",
            "learning",
            "pattern",
            "context",
            "summary",
            "note",
        ],
    )
    p_save.add_argument("--content", required=True)
    p_save.add_argument("--topic-key")
    p_save.add_argument("--scope", default="project", choices=["project", "session", "personal"])
    p_save.set_defaults(func=cmd_save)

    # search
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument(
        "--type-filter",
        choices=[
            "architecture",
            "bugfix",
            "config",
            "decision",
            "discovery",
            "learning",
            "pattern",
            "context",
            "summary",
            "note",
        ],
    )
    p_search.add_argument("--keyword")
    p_search.add_argument("--snippet-only", action="store_true", default=True)
    p_search.add_argument("--include-personal", action="store_true")
    p_search.set_defaults(func=cmd_search)

    # recall
    p_recall = sub.add_parser("recall")
    p_recall.add_argument("topic_key")
    p_recall.set_defaults(func=cmd_recall)

    # context
    p_ctx = sub.add_parser("context")
    p_ctx.add_argument("--n", type=int, default=5)
    p_ctx.set_defaults(func=cmd_context)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
