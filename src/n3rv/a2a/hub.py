from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from aiohttp import web

from n3rv.a2a.agent_cards import load_agent_cards
from n3rv.a2a.router import RoutingDecision, SkillNotFoundError, TaskRouter
from n3rv.a2a.state import DelegationArtifact, HubStateStore
from n3rv.config import RuntimeSettings
from n3rv.init.registry import SkillRegistry
from n3rv.mcp.memory_service import MemoryService
from n3rv.mcp.shared import ensure_runtime_directories, resolve_runtime_settings
from n3rv.models.a2a import TaskState

logger = logging.getLogger("n3rv.hub")

HUB_KEY = web.AppKey("hub", "A2AHub")


def _format_sse_event(data: dict, event_type: str = "task-status") -> bytes:
    payload = json.dumps(data, separators=(",", ":"))
    return f"event: {event_type}\ndata: {payload}\n\n".encode()


class A2AHub:
    """A2A hub server: routes tasks to agents via JSON-RPC over HTTP."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        ensure_runtime_directories(settings.paths)
        self.cards = load_agent_cards(settings)
        self.memory = MemoryService(settings)
        self.registry = SkillRegistry.scan(settings.paths.project_root)
        self.router = TaskRouter(cards=self.cards, memory_service=self.memory, registry=self.registry)
        self.state = HubStateStore(settings)

    def create_app(self) -> web.Application:
        """Build aiohttp app with health, agent cards, and RPC routes."""
        app = web.Application()
        app[HUB_KEY] = self
        app.router.add_get("/health", self.get_health)
        app.router.add_get("/.well-known/agent.json", self.get_hub_card)
        app.router.add_get("/agents/{agent_id}/agent.json", self.get_agent_card)
        app.router.add_post("/rpc", self.handle_rpc)
        app.router.add_get("/rpc/stream", self.handle_sse_stream)
        return app

    async def _recover_tasks(self) -> None:
        """On startup, recover non-terminal tasks.

        SUBMITTED → rerouted. WORKING → marked RESTART_RECOVERY.
        """

        tasks = self.state.list_tasks()

        if not tasks:
            return

        terminal_states = {TaskState.COMPLETED, TaskState.CANCELED, TaskState.FAILED}
        non_terminal_tasks = [t for t in tasks if t.state not in terminal_states]

        if not non_terminal_tasks:
            return

        rerouted_count = 0
        working_count = 0
        for task in non_terminal_tasks:
            if task.state == TaskState.SUBMITTED:
                try:
                    await self._route_task(
                        task_id=task.id,
                        skill_id=task.target_skill,
                        description=task.description,
                        requesting_agent=task.requesting_agent,
                    )
                    rerouted_count += 1
                except Exception as exc:
                    self._handle_task_exception(task.id, exc)
            elif task.state == TaskState.WORKING:
                self.state.update_task(
                    task.id,
                    state=TaskState.FAILED,
                    error_code="RESTART_RECOVERY",
                    error_message=(
                        "Hub restarted while task was in progress. Task state is unknown and must be retried manually."
                    ),
                    metadata={
                        **task.metadata,
                        "recovery_timestamp": datetime.now(UTC).isoformat(),
                    },
                )
                working_count += 1

        if rerouted_count:
            logger.info("Task recovery: %d submitted tasks rerouted", rerouted_count)
        if working_count:
            logger.info("Task recovery: %d marked RESTART_RECOVERY", working_count)

    async def get_health(self, request: web.Request) -> web.Response:
        logger.debug("GET /health")
        return web.json_response({"status": "ok", "project": self.settings.project_name})

    async def get_hub_card(self, request: web.Request) -> web.Response:
        logger.debug("GET /.well-known/agent.json")
        return web.json_response(self.cards["hub"].model_dump(mode="json"))

    async def get_agent_card(self, request: web.Request) -> web.Response:
        agent_id = request.match_info["agent_id"]
        logger.debug("GET /agents/%s/agent.json", agent_id)
        card = self.cards.get(agent_id)
        if card is None:
            raise web.HTTPNotFound(text=f"Unknown agent: {agent_id}")
        return web.json_response(card.model_dump(mode="json"))

    async def handle_sse_stream(self, request: web.Request) -> web.StreamResponse:
        """SSE stream of task status updates.

        Query params: agent_id (optional) for agent-level stream,
        task_id (optional) for single-task stream.
        """
        agent_id = request.query.get("agent_id")
        task_id = request.query.get("task_id")

        if not agent_id and not task_id:
            raise web.HTTPBadRequest(text="Either agent_id or task_id query parameter is required")

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        try:
            if task_id:
                async for event_data in self.state.subscribe(task_id):
                    response.write(_format_sse_event(event_data))
                response.write(_format_sse_event({"type": "done", "task_id": task_id}, event_type="stream-end"))
            elif agent_id:
                async for event_data in self.state.subscribe_agent(agent_id):
                    response.write(_format_sse_event(event_data))
        except asyncio.CancelledError:
            logger.debug("SSE stream cancelled for %s", agent_id or task_id)
        except ConnectionResetError:
            logger.debug("SSE stream client disconnected for %s", agent_id or task_id)

        return response

    async def handle_rpc(self, request: web.Request) -> web.Response:
        """JSON-RPC 2.0 handler: routes to tasks/send, get, cancel, list, complete."""
        payload = await request.json()
        method = payload.get("method")
        request_id = payload.get("id")
        params = payload.get("params") or {}

        logger.info("RPC %s id=%s", method, request_id)

        try:
            if method == "tasks/send":
                result = await self.tasks_send(params)
            elif method == "tasks/get":
                result = await self.tasks_get(params)
            elif method == "tasks/cancel":
                result = await self.tasks_cancel(params)
            elif method == "tasks/list":
                result = await self.tasks_list(params)
            elif method == "tasks/complete":
                result = await self.tasks_complete(params)
            else:
                logger.warning("Unknown RPC method: %s", method)
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    },
                    status=404,
                )
        except KeyError as exc:
            logger.warning("RPC %s bad request: %s", method, exc)
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                },
                status=400,
            )

        logger.debug("RPC %s id=%s -> ok", method, request_id)
        return web.json_response({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def tasks_send(self, params: dict[str, Any]) -> dict[str, Any]:
        """Submit task, route to agent, auto-complete if metadata.auto_complete=True."""
        description = str(params["description"])
        if len(description) > 5000:
            raise web.HTTPBadRequest(text="Description too long (max 5000 chars)")
        requesting_agent = str(params.get("requesting_agent", "unknown"))
        skill_id = str(params["skill_id"]) if params.get("skill_id") else None
        metadata = dict(params.get("metadata") or {})

        logger.info(
            "tasks/send from=%s skill=%s desc=%r",
            requesting_agent,
            skill_id,
            description[:80],
        )

        task = self._create_task(
            requesting_agent=requesting_agent,
            skill_id=skill_id,
            description=description,
            metadata=metadata,
        )
        logger.debug("task created id=%s", task.id)

        try:
            task, decision = await self._route_task(
                task_id=task.id,
                skill_id=skill_id,
                description=description,
                requesting_agent=requesting_agent,
            )
            if metadata.get("auto_complete", False):
                task = await self._auto_complete_task(
                    task=task,
                    decision=decision,
                    requesting_agent=requesting_agent,
                    description=description,
                )
                logger.info("task=%s completed -> %s", task.id, decision.card.name)
        except Exception as exc:
            task = self._handle_task_exception(task.id, exc)

        return task.to_jsonrpc_result()

    def _create_task(
        self,
        *,
        requesting_agent: str,
        skill_id: str | None,
        description: str,
        metadata: dict,
    ) -> Any:
        """Create a new task in SUBMITTED state."""
        return self.state.create_task(
            requesting_agent=requesting_agent,
            assigned_agent="pending",
            target_skill=skill_id or "implementation",
            description=description,
            metadata=metadata,
        )

    async def _auto_complete_task(
        self,
        *,
        task: Any,
        decision: Any,
        requesting_agent: str,
        description: str,
    ) -> Any:
        """Auto-complete a task by saving delegation artifacts."""
        artifact = await self._save_delegation_artifacts(
            task_id=task.id,
            decision=decision,
            requesting_agent=requesting_agent,
            description=description,
        )
        return self.state.update_task(
            task.id,
            state=TaskState.COMPLETED,
            artifacts=[artifact],
            metadata={**task.metadata, "completed_at": task.updated_at.isoformat()},
        )

    async def _route_task(
        self,
        *,
        task_id: str,
        skill_id: str | None,
        description: str,
        requesting_agent: str,
    ) -> tuple[Any, RoutingDecision]:
        """Route task to agent. Returns updated task and routing decision."""
        decision = await self.router.route(
            skill_id=skill_id,
            description=description,
            requesting_agent=requesting_agent,
        )
        logger.info(
            "routed task=%s -> agent=%s skill=%s context_items=%d",
            task_id,
            decision.agent_id,
            decision.skill.id,
            len(decision.context),
        )
        task = self._load_task_or_fail(task_id)
        updated_task = self.state.update_task(
            task_id,
            state=TaskState.WORKING,
            assigned_agent=decision.agent_id,
            target_skill=decision.skill.id,
            context=decision.context,
            metadata={**task.metadata, "started_at": task.updated_at.isoformat()},
        )
        return updated_task, decision

    async def _save_delegation_artifacts(
        self,
        *,
        task_id: str,
        decision: RoutingDecision,
        requesting_agent: str,
        description: str = "",
    ) -> DelegationArtifact:
        """Save delegation event to memory (session scope) via MemoryService."""
        artifact = DelegationArtifact(
            artifact_id=f"artifact-{task_id}",
            text=f"Delegated to {decision.card.name} for skill {decision.skill.id}",
        )
        memory_content = (
            f"Task {task_id} delegated from {requesting_agent} to {decision.card.name}.\n"
            f"Skill: {decision.skill.id}\n"
            f"Description: {description[:500]}"
        )
        logger.debug("memory_save for task=%s", task_id)
        self.memory.memory_save(
            content=memory_content,
            title=f"Delegation: {decision.skill.id} → {decision.card.name}",
            type="context",
            topic_key=f"task-{task_id[:8]}",
            scope="session",
        )
        return artifact

    def _handle_task_exception(self, task_id: str, exc: Exception):
        """Map exception to error code and mark task as FAILED."""
        inner = exc.exceptions[0] if isinstance(exc, BaseExceptionGroup) else exc
        if isinstance(inner, SkillNotFoundError):
            logger.warning("task=%s SKILL_NOT_FOUND: %s", task_id, inner)
            return self._fail_task(task_id, error_code="SKILL_NOT_FOUND", error_message=str(inner))
        logger.exception("task=%s DELEGATION_FAILED: %s", task_id, exc)
        return self._fail_task(task_id, error_code="DELEGATION_FAILED", error_message=str(exc))

    def _load_task_or_fail(self, task_id: str):
        """Load task or raise KeyError."""
        task = self.state.load_task(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        return task

    def _fail_task(self, task_id: str, *, error_code: str, error_message: str):
        """Mark task as FAILED with error details."""
        task = self._load_task_or_fail(task_id)
        return self.state.update_task(
            task_id,
            state=TaskState.FAILED,
            error_code=error_code,
            error_message=error_message,
            metadata={**task.metadata, "failed_at": task.updated_at.isoformat()},
        )

    async def tasks_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch task by ID and return JSON-RPC result."""
        task_id = str(params["task_id"])
        task = self._load_task_or_fail(task_id)
        return task.to_jsonrpc_result()

    async def tasks_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        """Cancel task if not already in terminal state."""
        task_id = str(params["task_id"])
        task = self._load_task_or_fail(task_id)
        # OWASP: validate agent can only cancel own tasks or hub tasks
        requesting_agent = str(params.get("requesting_agent", "unknown"))
        if requesting_agent != task.assigned_agent and requesting_agent != "hub":
            logger.warning(
                "Unauthorized cancel: agent=%s task.assigned=%s",
                requesting_agent,
                task.assigned_agent,
            )
            raise web.HTTPForbidden(text="Agent can only cancel own tasks")
        if task.state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}:
            return task.to_jsonrpc_result()
        updated = self.state.update_task(
            task_id,
            state=TaskState.CANCELED,
            metadata={
                **task.metadata,
                "cancel_reason": params.get("reason", "user requested"),
            },
        )
        return updated.to_jsonrpc_result()

    async def tasks_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """List tasks, optionally filtered by agent or state."""
        assigned_agent = params.get("assigned_agent")
        state_filter = params.get("state")
        tasks = self.state.list_tasks()
        if assigned_agent:
            tasks = [t for t in tasks if t.assigned_agent == assigned_agent]
        if state_filter:
            tasks = [t for t in tasks if t.state.value == state_filter]
        logger.debug(
            "tasks/list agent=%s state=%s -> %d tasks",
            assigned_agent,
            state_filter,
            len(tasks),
        )
        return {"tasks": [t.to_jsonrpc_result() for t in tasks]}

    async def tasks_complete(self, params: dict[str, Any]) -> dict[str, Any]:
        """Mark task as COMPLETED with result text and artifact."""
        task_id = str(params["task_id"])
        result_text = str(params.get("result", "Task completed"))
        completing_agent = str(params.get("completing_agent", "unknown"))
        task = self._load_task_or_fail(task_id)
        # OWASP: validate agent can only complete own tasks or hub tasks
        if completing_agent != task.assigned_agent and completing_agent != "hub":
            logger.warning(
                "Unauthorized complete: agent=%s task.assigned=%s",
                completing_agent,
                task.assigned_agent,
            )
            raise web.HTTPForbidden(text="Agent can only complete own tasks")
        if task.state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}:
            return task.to_jsonrpc_result()
        artifact = DelegationArtifact(
            artifact_id=f"artifact-{task_id}-complete",
            text=result_text,
        )
        updated = self.state.update_task(
            task_id,
            state=TaskState.COMPLETED,
            artifacts=[artifact],
            metadata={
                **task.metadata,
                "completed_by": completing_agent,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info("task=%s completed by agent=%s", task_id, completing_agent)
        return updated.to_jsonrpc_result()


async def run_hub() -> None:
    settings = resolve_runtime_settings()
    hub = A2AHub(settings)
    app = hub.create_app()
    await hub._recover_tasks()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.a2a_host, port=settings.a2a_port)
    await site.start()
    logger.info("n3rv hub listening on %s:%d", settings.a2a_host, settings.a2a_port)

    pid_path = settings.paths.pid_file
    pid_path.write_text(str(os.getpid()))

    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown_event.set)
        except NotImplementedError:
            logger.debug("signal handlers not supported on this platform")

    try:
        await shutdown_event.wait()
        logger.info("n3rv hub shutting down on signal")
    finally:
        _mark_working_tasks_failed(hub)
        await runner.cleanup()
        logger.info("n3rv hub stopped")
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            logger.debug("failed to unlink pid file %s", pid_path)


def _mark_working_tasks_failed(hub: A2AHub) -> None:
    for task in hub.state.list_tasks():
        if task.state == TaskState.WORKING:
            hub.state.update_task(
                task.id,
                state=TaskState.FAILED,
                error_code="RESTART_RECOVERY",
                error_message="Hub shut down while task was in progress.",
                metadata={
                    **task.metadata,
                    "recovery_timestamp": datetime.now(UTC).isoformat(),
                },
            )


def main() -> None:
    log_level = os.environ.get("N3RV_LOG_LEVEL", "INFO").upper()

    settings = resolve_runtime_settings()
    ensure_runtime_directories(settings.paths)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    file_handler = RotatingFileHandler(settings.paths.log_file, maxBytes=10 * 1024 * 1024, backupCount=3)
    file_handler.setLevel(log_level)
    for handler in (console_handler, file_handler):
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler],
        force=True,
    )

    asyncio.run(run_hub())
