"""Tests for state store subscription."""

from __future__ import annotations

import asyncio
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


async def test_subscribe_yields_initial_state(state_store: HubStateStore):
    """Test subscribe yields initial task state."""
    task = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Test task",
    )

    events = []
    async for state in state_store.subscribe(task.id):
        events.append(state)
        # Stop after first event for this test
        break

    assert len(events) == 1
    assert events[0]["id"] == task.id
    assert events[0]["state"] == TaskState.SUBMITTED.value


async def test_subscribe_terminates_on_completion(state_store: HubStateStore):
    """Test subscribe terminates when task reaches completed state."""
    task = state_store.create_task(
        requesting_agent="agent1",
        assigned_agent="agent2",
        target_skill="skill1",
        description="Test task",
    )

    # Set up subscription
    events = []

    async def collect_events():
        async for state in state_store.subscribe(task.id):
            events.append(state)

    # Start subscription in background
    subscription_task = asyncio.create_task(collect_events())

    # Give it a moment to start
    await asyncio.sleep(0.2)

    # Update task to completed
    state_store.update_task(task.id, state=TaskState.COMPLETED)

    # Wait for subscription to finish
    await asyncio.wait_for(subscription_task, timeout=2.0)

    # Should have at least 2 events: initial and final
    assert len(events) >= 2
    assert events[-1]["state"] == TaskState.COMPLETED.value


async def test_subscribe_handles_missing_task(state_store: HubStateStore):
    """Test subscribe handles missing task file gracefully."""
    events = []

    # Subscribe to non-existent task
    async for state in state_store.subscribe("task-00000000000000000000000000000000"):
        events.append(state)
        # Should not yield anything
        break

    # Should yield nothing or terminate quickly
    assert len(events) == 0
