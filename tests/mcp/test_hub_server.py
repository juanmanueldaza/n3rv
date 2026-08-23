from __future__ import annotations

import pytest

from n3rv.mcp import hub_server


def test_resolve_agent_ids_uses_current_agent_aliases(monkeypatch) -> None:
    monkeypatch.setenv("N3RV_AGENT_SOURCE", "opencode")

    assert hub_server._resolve_agent_ids() == ["opencode"]


def test_resolve_agent_ids_defaults_to_opencode_without_env(monkeypatch) -> None:
    monkeypatch.delenv("N3RV_AGENT_SOURCE", raising=False)

    assert hub_server._resolve_agent_ids() == ["opencode"]


def test_resolve_agent_ids_raises_on_empty_source(monkeypatch) -> None:
    monkeypatch.setenv("N3RV_AGENT_SOURCE", "")

    with pytest.raises(ValueError, match="agent_id is required"):
        hub_server._resolve_agent_ids()


def test_list_pending_tasks_filters_terminal_states_and_deduplicates(
    monkeypatch,
) -> None:
    def fake_rpc(hub_url: str, method: str, params: dict) -> dict:
        assert hub_url == "http://hub"
        assert method == "tasks/list"

        if params["assigned_agent"] == "opencode":
            return {
                "tasks": [
                    {
                        "id": "task-1",
                        "status": {
                            "state": "working",
                            "timestamp": "2026-04-21T04:32:18Z",
                        },
                    },
                    {
                        "id": "task-2",
                        "status": {
                            "state": "completed",
                            "timestamp": "2026-04-21T04:32:19Z",
                        },
                    },
                ]
            }
        raise AssertionError(f"unexpected params: {params}")

    monkeypatch.setattr(hub_server, "_rpc", fake_rpc)

    tasks = hub_server._list_pending_tasks("http://hub", "opencode")

    assert [task["id"] for task in tasks] == ["task-1"]
