"""Tests for task listing in state store."""

from __future__ import annotations

from pathlib import Path

import pytest

from n3rv.a2a.state import HubStateStore
from n3rv.config import RuntimePaths, RuntimeSettings
from n3rv.models.a2a import TaskState


@pytest.fixture
def state_store(tmp_path: Path) -> HubStateStore:
    """Create a state store with temporary directory."""
    paths = RuntimePaths.from_project_root(tmp_path)
    settings = RuntimeSettings(paths=paths)
    return HubStateStore(settings)


def test_list_tasks_empty_directory(state_store: HubStateStore):
    """Test list_tasks returns empty list when no tasks exist."""
    tasks = state_store.list_tasks()
    assert tasks == []


def test_list_tasks_returns_all_tasks(state_store: HubStateStore):
    """Test list_tasks returns all valid task files."""
    # Create some tasks
    task1 = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Task 1",
    )

    task2 = state_store.create_task(
        requesting_agent="agent3",
        assigned_agent="agent4",
        target_skill="skill2",
        description="Task 2",
    )

    # List tasks
    tasks = state_store.list_tasks()

    assert len(tasks) == 2
    task_ids = {t.id for t in tasks}
    assert task1.id in task_ids
    assert task2.id in task_ids


def test_list_tasks_skips_malformed_json(state_store: HubStateStore):
    """Test list_tasks skips malformed JSON files without raising exception."""
    # Create a valid task
    task = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Valid task",
    )

    # Create a malformed task file
    malformed_path = state_store.tasks_dir / "task-malformed.json"
    malformed_path.write_text("{ invalid json }")

    # List tasks should skip malformed file
    tasks = state_store.list_tasks()

    assert len(tasks) == 1
    assert tasks[0].id == task.id


def test_list_tasks_with_different_states(state_store: HubStateStore):
    """Test list_tasks returns tasks in various states."""
    # Create tasks in different states
    state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Submitted task",
    )

    task2 = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Working task",
    )
    state_store.update_task(task2.id, state=TaskState.WORKING)

    task3 = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Completed task",
    )
    state_store.update_task(task3.id, state=TaskState.COMPLETED)

    # List all tasks
    tasks = state_store.list_tasks()

    assert len(tasks) == 3
    states = {t.state for t in tasks}
    assert TaskState.SUBMITTED in states
    assert TaskState.WORKING in states
    assert TaskState.COMPLETED in states
