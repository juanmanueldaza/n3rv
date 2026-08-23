"""MCP server that exposes A2A hub task delegation for opencode agents.

Agents call these tools to delegate tasks across the hub and poll for work
assigned to them through the configured local hub URL (default 127.0.0.1:19820).
"""

from __future__ import annotations

import logging
from pathlib import Path

from n3rv.mcp.shared import (
    build_mcp_server,
    detect_agent_source,
    hub_rpc,
    resolve_runtime_settings,
    result_payload,
)
from n3rv.util import get_hub_url

logger = logging.getLogger("n3rv.mcp.hub")

_TERMINAL_TASK_STATES = {"completed", "failed", "canceled"}
_AGENT_ID_ALIASES = {
    "opencode": ("opencode",),
}

_rpc = hub_rpc


def _resolve_agent_ids(agent_id: str | None = None) -> list[str]:
    resolved = (agent_id or detect_agent_source()).strip().lower()
    if not resolved:
        raise ValueError("agent_id is required when N3RV_AGENT_SOURCE is not set")
    return list(dict.fromkeys(_AGENT_ID_ALIASES.get(resolved, (resolved,))))


def _list_pending_tasks(hub_url: str, agent_id: str | None = None) -> list[dict]:
    """Fetch pending tasks for agent(s) by calling HubStateStore via hub RPC.

    Uses tasks/list RPC which internally queries HubStateStore.
    Filters out terminal states client-side as a safety net.
    """
    tasks_by_id: dict[str, dict] = {}
    for candidate_id in _resolve_agent_ids(agent_id):
        result = _rpc(hub_url, "tasks/list", {"assigned_agent": candidate_id})
        for task in result.get("tasks", []):
            state = str(task.get("status", {}).get("state", "")).lower()
            if state in _TERMINAL_TASK_STATES:
                continue
            tasks_by_id[task["id"]] = task
    return sorted(
        tasks_by_id.values(),
        key=lambda task: task.get("status", {}).get("timestamp", ""),
    )


def build_hub_server(project_root: Path | None = None):
    settings = resolve_runtime_settings(project_root)
    hub_url = get_hub_url(settings)

    server = build_mcp_server(
        "n3rv-hub",
        "Delegate tasks to other agents and poll for assigned work via the A2A hub.",
    )

    @server.tool(
        description=(
            "Delegate a task to another agent via the A2A hub. "
            "skill_id must match one of the registered agent skills. "
            "The task stays assigned until the delegated agent calls complete_task."
        )
    )
    async def delegate_task(
        skill_id: str,
        description: str,
        requesting_agent: str = "unknown",
    ) -> dict:
        result = _rpc(
            hub_url,
            "tasks/send",
            {
                "skill_id": skill_id,
                "description": description,
                "requesting_agent": requesting_agent,
                "metadata": {"auto_complete": False},
            },
        )
        logger.info(
            "delegate_task skill=%s from=%s -> task=%s",
            skill_id,
            requesting_agent,
            result.get("id"),
        )
        return result_payload(result)

    @server.tool(
        description=(
            "List tasks assigned to an agent that are not yet completed. "
            "If agent_id is omitted, uses the current agent from N3RV_AGENT_SOURCE."
        )
    )
    async def list_pending_tasks(agent_id: str | None = None) -> list:
        tasks = _list_pending_tasks(hub_url, agent_id)
        logger.info(
            "list_pending_tasks agent=%s -> %d tasks",
            agent_id or detect_agent_source(),
            len(tasks),
        )
        return result_payload(tasks)

    @server.tool(
        description=(
            "Check pending tasks assigned to the current agent. "
            "Pass agent_id explicitly when N3RV_AGENT_SOURCE is not set."
        )
    )
    async def check_pending_tasks(agent_id: str | None = None) -> list:
        tasks = _list_pending_tasks(hub_url, agent_id)
        logger.info(
            "check_pending_tasks agent=%s -> %d tasks",
            agent_id or detect_agent_source(),
            len(tasks),
        )
        return result_payload(tasks)

    @server.tool(
        description=(
            "Mark a task as completed after executing it. "
            "Provide the task_id from check_pending_tasks or list_pending_tasks and a result summary."
        )
    )
    async def complete_task(task_id: str, result: str, completing_agent: str = "unknown") -> dict:
        out = _rpc(
            hub_url,
            "tasks/complete",
            {
                "task_id": task_id,
                "result": result,
                "completing_agent": completing_agent,
            },
        )
        logger.info("complete_task id=%s by=%s", task_id, completing_agent)
        return result_payload(out)

    @server.tool(description="Get the current state of a task by its ID.")
    async def get_task(task_id: str) -> dict:
        result = _rpc(hub_url, "tasks/get", {"task_id": task_id})
        return result_payload(result)

    return server


def run_hub_server() -> None:
    build_hub_server().run()


def main() -> None:
    run_hub_server()
