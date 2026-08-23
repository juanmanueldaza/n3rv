"""Tests for hub recovery logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from n3rv.a2a.hub import A2AHub
from n3rv.config import RuntimePaths, RuntimeSettings
from n3rv.models.a2a import TaskState


@pytest.fixture
def hub(tmp_path: Path) -> A2AHub:
    """Create a hub instance with temporary directory."""
    paths = RuntimePaths.from_project_root(tmp_path)
    settings = RuntimeSettings(paths=paths)
    return A2AHub(settings)


async def test_recover_tasks_with_no_tasks(hub: A2AHub):
    """Test recovery with no tasks logs appropriate message."""
    # No tasks in store
    await hub._recover_tasks()
    # Should complete without error


async def test_recover_completed_task_is_skipped(hub: A2AHub):
    """Test that completed tasks are skipped during recovery."""
    # Create a completed task
    task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Completed task",
    )
    hub.state.update_task(task.id, state=TaskState.COMPLETED)

    # Run recovery
    await hub._recover_tasks()

    # Task should still be completed
    recovered_task = hub.state.load_task(task.id)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.COMPLETED


async def test_recover_submitted_task_reroutes_to_matching_agent(hub: A2AHub):
    """Test that submitted tasks are rerouted and resumed on recovery."""
    task = hub.state.create_task(
        requesting_agent="opencode",
        assigned_agent="pending",
        target_skill="implementation",
        description="Implement auth module from design",
        metadata={"auto_complete": False},
    )

    await hub._recover_tasks()

    recovered_task = hub.state.load_task(task.id)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.WORKING
    assert recovered_task.assigned_agent == "opencode"
    assert recovered_task.target_skill == "implementation"


async def test_recover_working_task_marks_as_failed(hub: A2AHub):
    """Test that working tasks are marked as RESTART_RECOVERY failed."""
    # Create a working task
    task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Working task",
    )
    hub.state.update_task(task.id, state=TaskState.WORKING)

    # Run recovery
    await hub._recover_tasks()

    # Task should be marked as failed
    recovered_task = hub.state.load_task(task.id)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.FAILED
    assert recovered_task.error_code == "RESTART_RECOVERY"
    assert "restarted" in recovered_task.error_message.lower()
    assert "recovery_timestamp" in recovered_task.metadata


async def test_recover_canceled_task_is_skipped(hub: A2AHub):
    """Test that canceled tasks are skipped during recovery."""
    # Create a canceled task
    task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Canceled task",
    )
    hub.state.update_task(task.id, state=TaskState.CANCELED)

    # Run recovery
    await hub._recover_tasks()

    # Task should still be canceled
    recovered_task = hub.state.load_task(task.id)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.CANCELED


async def test_recover_failed_task_is_skipped(hub: A2AHub):
    """Test that already-failed tasks are skipped during recovery."""
    # Create a failed task
    task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Failed task",
    )
    hub.state.update_task(task.id, state=TaskState.FAILED, error_code="OTHER_ERROR")

    # Run recovery
    await hub._recover_tasks()

    # Task should still be failed with original error code
    recovered_task = hub.state.load_task(task.id)
    assert recovered_task is not None
    assert recovered_task.state == TaskState.FAILED
    assert recovered_task.error_code == "OTHER_ERROR"


async def test_recover_mixed_tasks(hub: A2AHub):
    """Test recovery with mixed task states."""
    # Create tasks in various states
    submitted_task = hub.state.create_task(
        requesting_agent="opencode",
        assigned_agent="pending",
        target_skill="implementation",
        description="Implement auth module from design",
        metadata={"auto_complete": False},
    )
    working_task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Working task",
    )
    hub.state.update_task(working_task.id, state=TaskState.WORKING)

    completed_task = hub.state.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Completed task",
    )
    hub.state.update_task(completed_task.id, state=TaskState.COMPLETED)

    # Run recovery
    await hub._recover_tasks()

    # Submitted task should be rerouted
    recovered_submitted = hub.state.load_task(submitted_task.id)
    assert recovered_submitted.state == TaskState.WORKING
    assert recovered_submitted.assigned_agent == "opencode"

    # Working task should be failed
    recovered_working = hub.state.load_task(working_task.id)
    assert recovered_working.state == TaskState.FAILED
    assert recovered_working.error_code == "RESTART_RECOVERY"

    # Completed task should be unchanged
    recovered_completed = hub.state.load_task(completed_task.id)
    assert recovered_completed.state == TaskState.COMPLETED
