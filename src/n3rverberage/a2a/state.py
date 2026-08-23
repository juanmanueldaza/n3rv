from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from n3rverberage.config import RuntimeSettings
from n3rverberage.models.a2a import TaskState

logger = logging.getLogger("n3rverberage.a2a.state")

_TASK_ID_RE = re.compile(r"^task-[a-f0-9]{32}$")


class DelegationArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    text: str


class HubTaskRecord(BaseModel):
    """Immutable task record with JSON-RPC result serialization."""

    model_config = ConfigDict(frozen=True)

    id: str
    state: TaskState
    requesting_agent: str
    assigned_agent: str
    target_skill: str
    description: str
    context: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    artifacts: list[DelegationArtifact] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    metadata: dict = Field(default_factory=dict)

    def to_jsonrpc_result(self) -> dict:
        """Serialize to A2A JSON-RPC result format."""
        return {
            "id": self.id,
            "kind": "task",
            "contextId": self.id,
            "status": {
                "state": self.state.value,
                "timestamp": self.updated_at.isoformat(),
            },
            "artifacts": [
                {
                    "artifactId": artifact.artifact_id,
                    "parts": [{"kind": "text", "text": artifact.text}],
                }
                for artifact in self.artifacts
            ]
            or None,
            "metadata": {
                "requesting_agent": self.requesting_agent,
                "assigned_agent": self.assigned_agent,
                "target_skill": self.target_skill,
                "description": self.description,
                "context": self.context,
                "error_code": self.error_code,
                "error_message": self.error_message,
                **self.metadata,
            },
        }


class HubStateStore:
    """File-based task persistence (JSON files in tasks/ directory).

    Provides create, update, list, load, and SSE subscription for HubTaskRecord.
    """

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self.tasks_dir = settings.paths.hub_state_dir / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._task_events: dict[str, asyncio.Event] = {}

    def _get_event(self, task_id: str) -> asyncio.Event:
        if task_id not in self._task_events:
            self._task_events[task_id] = asyncio.Event()
        return self._task_events[task_id]

    def create_task(
        self,
        *,
        requesting_agent: str,
        assigned_agent: str,
        target_skill: str,
        description: str,
        context: list[dict] | None = None,
        metadata: dict | None = None,
    ) -> HubTaskRecord:
        """Create a new task in SUBMITTED state."""
        now = datetime.now(UTC)
        task = HubTaskRecord(
            id=f"task-{uuid4().hex}",
            state=TaskState.SUBMITTED,
            requesting_agent=requesting_agent,
            assigned_agent=assigned_agent,
            target_skill=target_skill,
            description=description,
            context=context or [],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self.save_task(task)
        return task

    def save_task(self, task: HubTaskRecord) -> None:
        """Write task to JSON file (atomic: write to .tmp then rename)."""
        target = self._task_path(task.id)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(task.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(target)

    def load_task(self, task_id: str) -> HubTaskRecord | None:
        """Load a single task by ID. Returns None if file doesn't exist."""
        path = self._task_path(task_id)
        if not path.exists():
            return None
        return HubTaskRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def update_task(self, task_id: str, **changes) -> HubTaskRecord:
        """Update task fields and set updated_at to now. Raises KeyError if not found."""
        task = self.load_task(task_id)
        if task is None:
            raise KeyError(task_id)
        updated = task.model_copy(update={"updated_at": datetime.now(UTC), **changes})
        self.save_task(updated)
        event = self._task_events.get(task_id)
        if event is not None:
            event.set()
        return updated

    def _task_path(self, task_id: str) -> Path:
        """Build path for a task_id. Validates format (task-[32 hex chars])."""
        if not _TASK_ID_RE.match(task_id):
            raise ValueError(f"Invalid task_id format: {task_id!r}")
        return self.tasks_dir / f"{task_id}.json"

    def list_tasks(self) -> list[HubTaskRecord]:
        """List all tasks from JSON files. Skips files that fail to parse."""
        tasks = []
        for task_file in self.tasks_dir.glob("task-*.json"):
            try:
                task = HubTaskRecord.model_validate_json(task_file.read_text(encoding="utf-8"))
                tasks.append(task)
            except Exception:
                logger.exception("Failed to load task: %s", task_file)
                continue
        return tasks

    async def subscribe(self, task_id: str) -> AsyncGenerator[dict]:
        """SSE subscription: yields task state on updates via asyncio.Event.

        Yields initial state immediately, then waits for update_task()
        to fire the event. Stops when task reaches terminal state.
        """
        path = self._task_path(task_id)
        if not path.exists():
            return

        terminal_states = {TaskState.COMPLETED, TaskState.CANCELED, TaskState.FAILED}
        event = self._get_event(task_id)

        try:
            task = self.load_task(task_id)
            if task is not None:
                yield _task_sse_event(task)
                if task.state in terminal_states:
                    return

            while True:
                await event.wait()
                event.clear()
                task = self.load_task(task_id)
                if task is not None:
                    yield _task_sse_event(task)
                    if task.state in terminal_states:
                        return
        finally:
            self._task_events.pop(task_id, None)

    async def subscribe_agent(self, agent_id: str) -> AsyncGenerator[dict]:
        """SSE subscription for all tasks assigned to an agent.

        Yields initial state for existing tasks, then yields updates
        as they occur. Stops on generator close (client disconnect).
        """
        seen_ids: set[str] = set()
        agent_id_lower = agent_id.lower()

        def _tasks_for_agent() -> list[HubTaskRecord]:
            return [t for t in self.list_tasks() if t.assigned_agent.lower() == agent_id_lower]

        for task in _tasks_for_agent():
            seen_ids.add(task.id)
            yield _task_sse_event(task)

        while True:
            await asyncio.sleep(0.5)
            current_tasks = _tasks_for_agent()
            for task in current_tasks:
                if task.id not in seen_ids:
                    seen_ids.add(task.id)
                    yield _task_sse_event(task)

            if len(seen_ids) != len(current_tasks):
                seen_ids = {t.id for t in current_tasks}


def _task_sse_event(task: HubTaskRecord) -> dict:
    return {
        "id": task.id,
        "state": task.state.value,
        "assigned_agent": task.assigned_agent,
        "target_skill": task.target_skill,
        "description": task.description,
        "updated_at": task.updated_at.isoformat(),
    }
