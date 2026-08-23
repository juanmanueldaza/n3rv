from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from n3rv.a2a.hub import A2AHub


async def build_client(runtime_settings) -> TestClient:
    hub = A2AHub(runtime_settings)
    client = TestClient(TestServer(hub.create_app()))
    await client.start_server()
    return client


@pytest.mark.asyncio
async def test_serves_agent_cards(runtime_settings) -> None:
    client = await build_client(runtime_settings)
    try:
        response = await client.get("/.well-known/agent.json")
        payload = await response.json()

        assert response.status == 200
        assert payload["name"] == "n3rv-hub"
        assert payload["capabilities"] == {"streaming": True}
        assert "authentication" not in payload
        child = await client.get("/agents/opencode/agent.json")
        child_payload = await child.json()
        assert child_payload["name"] == "opencode"
        assert child_payload["capabilities"] == {"streaming": True}
        assert "authentication" not in child_payload
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tasks_send_persists_completed_task(runtime_settings) -> None:
    client = await build_client(runtime_settings)
    try:
        response = await client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tasks/send",
                "params": {
                    "requesting_agent": "claude",
                    "skill_id": "implementation",
                    "description": "Implement auth module from design",
                    "metadata": {"auto_complete": True},
                },
            },
        )
        payload = await response.json()

        assert response.status == 200
        task = payload["result"]
        assert task["status"]["state"] == "completed"
        task_path = runtime_settings.paths.hub_state_dir / "tasks" / f"{task['id']}.json"
        assert task_path.exists()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_tasks_get_returns_persisted_task(runtime_settings) -> None:
    client = await build_client(runtime_settings)
    try:
        sent = await client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "5",
                "method": "tasks/send",
                "params": {
                    "requesting_agent": "claude",
                    "skill_id": "implementation",
                    "description": "Implement auth module from design",
                    "metadata": {"auto_complete": True},
                },
            },
        )
        task_id = (await sent.json())["result"]["id"]

        fetched = await client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "6",
                "method": "tasks/get",
                "params": {"task_id": task_id},
            },
        )
        payload = await fetched.json()

        assert fetched.status == 200
        assert payload["result"]["id"] == task_id
        assert payload["result"]["status"]["state"] == "completed"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_cancel_working_task(runtime_settings) -> None:
    client = await build_client(runtime_settings)
    try:
        sent = await client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "3",
                "method": "tasks/send",
                "params": {
                    "requesting_agent": "claude",
                    "skill_id": "implementation",
                    "description": "Implement auth module from design",
                    "metadata": {"auto_complete": False},
                },
            },
        )
        task_id = (await sent.json())["result"]["id"]

        cancelled = await client.post(
            "/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "4",
                "method": "tasks/cancel",
                "params": {
                    "task_id": task_id,
                    "reason": "user requested",
                    "requesting_agent": "opencode",
                },
            },
        )
        payload = await cancelled.json()

        assert cancelled.status == 200
        assert payload["result"]["status"]["state"] == "canceled"
    finally:
        await client.close()
