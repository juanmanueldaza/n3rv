"""MCP server that exposes persistent memory operations for opencode agents.

Agents call these tools to save, search, recall, and manage memories
stored in the ChromaDB vector store with SQLite relation backing.
"""

from __future__ import annotations

import os
from pathlib import Path

from n3rv.mcp.memory_service import MemoryService
from n3rv.mcp.shared import (
    build_mcp_server,
    detect_agent_source,
    resolve_runtime_settings,
    result_payload,
)

logger = __import__("logging").getLogger("n3rv.mcp.memory")

_SEARCH_NUDGE_THRESHOLD = 3


def build_memory_server(project_root: Path | None = None):
    """Build and return the n3rv-memory MCP server."""
    settings = resolve_runtime_settings(project_root)
    service = MemoryService(settings)
    server = build_mcp_server(
        "n3rv-memory",
        "Shared persistent memory for agent interactions.",
    )
    profile = os.environ.get("N3RV_MEMORY_PROFILE", "full")

    @server.tool(description="Persist a memory observation to project-local ChromaDB.")
    async def memory_save(
        content: str,
        title: str,
        type: str,
        topic_key: str | None = None,
        scope: str = "project",
    ) -> dict:
        return result_payload(
            service.memory_save(
                content=content,
                title=title,
                type=type,
                topic_key=topic_key,
                scope=scope,
                agent_source=detect_agent_source(),
            )
        )

    @server.tool(description="Fetch full content of a single active memory by ID.")
    async def memory_get(id: str) -> dict:
        return result_payload(service.memory_get(id))

    @server.tool(description="Semantic search across stored engineering memories.")
    async def memory_search(
        query: str,
        limit: int = 5,
        type_filter: str | None = None,
        keyword: str | None = None,
        snippet_only: bool = False,
        include_personal: bool = False,
    ) -> dict:
        return result_payload(
            service.memory_search(
                query=query,
                limit=limit,
                type_filter=type_filter,
                keyword=keyword,
                snippet_only=snippet_only,
                include_personal=include_personal,
            )
        )

    @server.tool(description="Recall a single memory by topic key.")
    async def memory_recall(topic_key: str) -> dict:
        return result_payload(service.memory_recall(topic_key=topic_key))

    @server.tool(description="Return recent memories in reverse chronological order.")
    async def memory_context(n: int = 10) -> dict:
        return result_payload(service.memory_context(n=n))

    @server.tool(description="Persist a session summary as a memory of type summary.")
    async def memory_session_summary(summary: str) -> dict:
        return result_payload(service.memory_session_summary(summary=summary, agent_source=detect_agent_source()))

    @server.tool(description="Persist a session-start context entry and return the new session id.")
    async def memory_session_start() -> dict:
        return result_payload(service.memory_session_start(agent_source=detect_agent_source()))

    @server.tool(description="Return aggregate counts for active memories.")
    async def memory_stats() -> dict:
        return result_payload(service.memory_stats())

    @server.tool(description="Return active memories surrounding a focus memory id.")
    async def memory_timeline(id: str, before: int = 5, after: int = 5) -> dict:
        return result_payload(service.memory_timeline(id=id, before=before, after=after))

    @server.tool(description="Record an agent verdict on the relationship between two memories.")
    async def memory_judge(source_id: str, target_id: str, verdict: str, reason: str | None = None) -> dict:
        return result_payload(
            service.memory_judge(
                source_id=source_id,
                target_id=target_id,
                verdict=verdict,
                reason=reason,
            )
        )

    @server.tool(description="Soft-delete memories of a given scope older than N days.")
    async def memory_prune(scope: str, older_than_days: int) -> dict:
        return result_payload(
            service.memory_prune(
                scope=scope,
                older_than_days=older_than_days,
            )
        )

    if profile != "safe":

        @server.tool(description="Delete a stored memory by id, optionally removing it permanently.")
        async def memory_delete(id: str, hard_delete: bool = False) -> dict:
            return result_payload(
                service.memory_delete(
                    id=id,
                    hard_delete=hard_delete,
                    enforce_profile=True,
                )
            )

    return server


def run_memory_server() -> None:
    """Entry point for n3rv-memory subprocess."""
    build_memory_server().run()


def main() -> None:
    """Entry point for n3rv-memory command."""
    run_memory_server()
