from __future__ import annotations

from pathlib import Path


def _tools_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".opencode" / "tools" / "n3rv-stats.ts"


def _shared_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".opencode" / "shared" / "rpc.js"


class TestN3rvStatsTools:
    def test_file_exists(self) -> None:
        assert _tools_path().is_file()

    def test_imports_tool(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "@opencode-ai/plugin" in content

    def test_exports_memory_stats(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "export const n3rv_memory_stats" in content

    def test_exports_task_status(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "export const n3rv_task_status" in content

    def test_exports_hub_health(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "export const n3rv_hub_health" in content

    def test_exports_check_pending_tasks(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "export const n3rv_check_pending_tasks" in content

    def test_hub_health_uses_shared_healthcheck(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        # n3rv_hub_health delegates to healthCheck() in shared module
        assert "healthCheck" in content

    def test_shared_healthcheck_returns_connected_false(self) -> None:
        shared = _shared_path().read_text(encoding="utf-8")
        # healthCheck() in shared module returns {connected: false} on failure
        assert "connected: false" in shared

    def test_task_status_accepts_task_id_param(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "task_id" in content

    def test_check_pending_tasks_falls_back_to_env(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "N3RV_AGENT_SOURCE" in content or "agent_id" in content

    def test_all_tools_use_tool_helper(self) -> None:
        content = _tools_path().read_text(encoding="utf-8")
        assert "tool({" in content

    def test_timeout_handling_present(self) -> None:
        shared = _shared_path().read_text(encoding="utf-8")
        # Timeout handling moved to shared/rpc.js
        assert "AbortController" in shared or "timeout" in shared.lower()
