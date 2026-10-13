"""MCP server that exposes persistent memory operations for opencode agents.

Agents call these tools to save, search, recall, and manage memories
stored in the ChromaDB vector store with SQLite relation backing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError

from n3rv.mcp.memory_service import MemoryService
from n3rv.mcp.shared import (
    build_mcp_server,
    detect_agent_source,
    resolve_runtime_settings,
    result_payload,
)
from n3rv.platform import ProjectRootNotFoundError

logger = __import__("logging").getLogger("n3rv.mcp.memory")

_SEARCH_NUDGE_THRESHOLD = 3


class _UnavailableMemoryService:
    """Stands in for MemoryService when no project root can be resolved.

    The tools stay registered and every call fails with an actionable message.
    Exiting instead turns a configuration problem into a crash-loop: the client
    restarts the server, it dies again, and users of other, healthy sessions see
    disconnected tooling.

    Raises ``ToolError`` rather than a domain exception on purpose: MCP reports
    a deliberate ``ToolError`` back to the caller with its message intact, while
    any other exception is reported as a bare "Error executing tool ..." with
    the text withheld, which is exactly how this became hard to diagnose.
    """

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def __getattr__(self, name: str) -> Any:
        def _unavailable(*args: Any, **kwargs: Any) -> Any:
            raise ToolError(self._reason)

        return _unavailable


def build_memory_server(project_root: Path | None = None):
    """Build and return the n3rv-memory MCP server."""
    try:
        settings = resolve_runtime_settings(project_root)
    except ProjectRootNotFoundError as exc:
        reason = (
            f"{exc} n3rv-memory serves the project it is started in: start it from "
            "inside a project directory, or point N3RV_PROJECT_ROOT at one."
        )
        logger.error("memory storage unavailable: %s", reason)
        service: Any = _UnavailableMemoryService(reason)
    else:
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

    @server.tool(description="Soft-delete memories of a given scope older than N days. Optionally filter by type.")
    async def memory_prune(
        scope: str,
        older_than_days: int | None = None,
        type_filter: str | None = None,
        hard_delete: bool = False,
    ) -> dict:
        return result_payload(
            service.memory_prune(
                scope=scope,
                older_than_days=older_than_days,
                type_filter=type_filter,
                hard_delete=hard_delete,
            )
        )

    if profile != "safe":

        @server.tool(description="Delete a stored memory by id, optionally removing it permanently.")
        async def memory_delete(id: str, hard_delete: bool = False) -> dict:
            return result_payload(
                service.memory_delete(
                    id=id,
                    hard_delete=hard_delete,
                )
            )

    @server.tool(description="Query conflict log for LWW merge decisions.")
    async def memory_conflicts(
        topic_key: str | None = None,
        days: int = 7,
    ) -> dict:
        """Query conflict log with optional filters.

        Parameters
        ----------
        topic_key : str | None
            If provided, filter to conflicts for this topic_key.
        days : int
            Only return conflicts created within the last N days.

        Returns
        -------
        dict
            Dict with `conflicts` list of ConflictLogEntry dicts.
        """
        return result_payload(
            {"conflicts": [c.model_dump() for c in service.get_conflicts(topic_key=topic_key, days=days)]}
        )

    return server


def run_memory_server() -> None:
    """Entry point for n3rv-memory subprocess."""
    build_memory_server().run()


def main() -> None:
    """Entry point for n3rv-memory command."""
    run_memory_server()
