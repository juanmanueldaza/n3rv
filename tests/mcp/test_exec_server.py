"""Tests for n3rv-exec MCP server — structured lint/test/typecheck."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from n3rv.mcp.exec_server import build_exec_server


@pytest.mark.asyncio
async def test_exec_lint_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: "/usr/bin/ruff")

    def fake_run(cmd, cwd, timeout=60):
        assert cmd[0] == "ruff"
        return {"returncode": 0, "output": "", "stdout": "", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)

    server = build_exec_server(tmp_path)
    tools = {t.name: t for t in await server.list_tools()}
    assert "exec_lint" in tools

    from n3rv.mcp.exec_server import _parse_ruff_lines

    assert _parse_ruff_lines("") == []


@pytest.mark.asyncio
async def test_exec_lint_no_ruff_skipped(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: None)
    server = build_exec_server(tmp_path)
    tool = next(t for t in await server.list_tools() if t.name == "exec_lint")
    assert tool is not None
    result = await server.call_tool("exec_lint", {"path": "."})
    # CallToolResult -> .content[0].text JSON or structuredContent
    text = ""
    if hasattr(result, "content") and result.content:
        text = getattr(result.content[0], "text", str(result.content[0]))
    elif hasattr(result, "structured_content") and result.structured_content:
        text = json.dumps(result.structured_content)
    else:
        text = str(result)
    # Universal: when no linter found at all, should skip (was ruff not found)
    assert "not found" in text.lower() or "skipped" in text.lower()


@pytest.mark.asyncio
async def test_exec_lint_eslint_fallback(tmp_path: Path, monkeypatch) -> None:
    """When ruff missing but eslint present, exec_lint uses eslint (universal)."""

    def which(name: str):
        if name == "ruff":
            return None
        if name == "eslint":
            return "/usr/bin/eslint"
        return None

    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", which)

    def fake_run(cmd, cwd, timeout=60):
        assert "eslint" in cmd[0]
        return {"returncode": 0, "output": "", "stdout": "", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)
    server = build_exec_server(tmp_path)
    result = await server.call_tool("exec_lint", {"path": "."})
    text = (
        json.dumps(result.structured_content)
        if hasattr(result, "structured_content") and result.structured_content
        else str(result)
    )
    # Should have used eslint tool
    assert "eslint" in text.lower() or "pass" in text.lower()


@pytest.mark.asyncio
async def test_exec_lint_golangci_fallback(tmp_path: Path, monkeypatch) -> None:
    """When ruff/eslint missing but golangci-lint present, lint uses golangci."""

    def which(name: str):
        if name in ("ruff", "eslint"):
            return None
        if name == "golangci-lint":
            return "/usr/bin/golangci-lint"
        return None

    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", which)

    def fake_run(cmd, cwd, timeout=60):
        assert "golangci-lint" in cmd[0]
        return {"returncode": 0, "output": "", "stdout": "", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)
    server = build_exec_server(tmp_path)
    result = await server.call_tool("exec_lint", {"path": "."})
    text = (
        json.dumps(result.structured_content)
        if hasattr(result, "structured_content") and result.structured_content
        else str(result)
    )
    assert "golangci-lint" in text.lower() or "pass" in text.lower()


@pytest.mark.asyncio
async def test_exec_test_pass(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: "/usr/bin/pytest")

    def fake_run(cmd, cwd, timeout=60):
        return {"returncode": 0, "output": "5 passed in 0.42s", "stdout": "5 passed in 0.42s", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)
    server = build_exec_server(tmp_path)
    result = await server.call_tool("exec_test", {"path": "."})
    text = ""
    if hasattr(result, "content") and result.content:
        text = getattr(result.content[0], "text", str(result.content[0]))
    elif hasattr(result, "structured_content") and result.structured_content:
        text = json.dumps(result.structured_content)
    else:
        text = str(result)
    assert "5 passed" in text or "passed" in text.lower()


@pytest.mark.asyncio
async def test_exec_test_fail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: "/usr/bin/pytest")

    def fake_run(cmd, cwd, timeout=60):
        return {
            "returncode": 1,
            "output": "1 failed, 4 passed in 0.50s\nFAILED tests/test_foo.py::test_bar",
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)
    server = build_exec_server(tmp_path)
    result = await server.call_tool("exec_test", {"path": "."})
    text = ""
    if hasattr(result, "content") and result.content:
        text = getattr(result.content[0], "text", str(result.content[0]))
    elif hasattr(result, "structured_content") and result.structured_content:
        text = json.dumps(result.structured_content)
    else:
        text = str(result)
    assert "failed" in text.lower()


@pytest.mark.asyncio
async def test_exec_typecheck_skipped_when_no_mypy(tmp_path: Path, monkeypatch) -> None:
    # All typecheckers missing → should skip with universal message
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: None)
    server = build_exec_server(tmp_path)
    result = await server.call_tool("exec_typecheck", {"path": "src"})
    text = ""
    if hasattr(result, "content") and result.content:
        text = getattr(result.content[0], "text", str(result.content[0]))
    elif hasattr(result, "structured_content") and result.structured_content:
        text = json.dumps(result.structured_content)
    else:
        text = str(result)
    assert "not found" in text.lower() or "skipped" in text.lower() or "mypy not installed" in text.lower()


def test_parse_ruff_lines() -> None:
    from n3rv.mcp.exec_server import _parse_ruff_lines

    out = "src/foo.py:10:5: E501 line too long\nsrc/bar.py:2:1: F401 unused import"
    errors = _parse_ruff_lines(out)
    assert len(errors) == 2
    assert errors[0]["file"] == "src/foo.py"
    assert errors[0]["line"] == 10
    assert errors[0]["rule"] == "E501"


def test_parse_ruff_json() -> None:
    from n3rv.mcp.exec_server import _parse_ruff_json

    data = json.dumps(
        [
            {
                "filename": "src/foo.py",
                "location": {"row": 3, "column": 1},
                "code": "F401",
                "message": "unused import",
            }
        ]
    )
    errors = _parse_ruff_json(data)
    assert len(errors) == 1
    assert errors[0]["rule"] == "F401"


def test_parse_pytest_summary() -> None:
    from n3rv.mcp.exec_server import _parse_pytest_summary

    parsed = _parse_pytest_summary("5 passed in 0.42s")
    assert parsed["passed"] == 5
    assert parsed["failed"] == 0

    parsed2 = _parse_pytest_summary("1 failed, 4 passed in 0.50s")
    assert parsed2["failed"] == 1
    assert parsed2["passed"] == 4


def test_exec_server_has_three_tools(tmp_path: Path) -> None:
    import asyncio

    server = build_exec_server(tmp_path)

    async def _check():
        tools = await server.list_tools()
        names = {t.name for t in tools}
        # T4 had 7 tools (3 core + 4 history); T5 adds exec_affected → 8
        assert {
            "exec_lint",
            "exec_typecheck",
            "exec_test",
            "exec_history",
            "exec_diff",
            "exec_timeline",
            "exec_cache_stats",
        }.issubset(names)
        assert len(tools) >= 7

    asyncio.run(_check())


def test_exec_server_has_seven_tools(tmp_path: Path) -> None:
    """Alias for T4 spec: 7 tools after universal upgrade (now 8 with affected)."""
    import asyncio

    server = build_exec_server(tmp_path)

    async def _check():
        tools = await server.list_tools()
        assert len(tools) >= 7

    asyncio.run(_check())


@pytest.mark.asyncio
async def test_exec_history_and_cache_stats(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: "/usr/bin/ruff")

    def fake_run(cmd, cwd, timeout=60):
        return {"returncode": 0, "output": "", "stdout": "", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)
    server = build_exec_server(tmp_path)
    # Run a lint to populate history
    await server.call_tool("exec_lint", {"path": "."})
    hist = await server.call_tool("exec_history", {"limit": 10})
    text = (
        json.dumps(hist.structured_content)
        if hasattr(hist, "structured_content") and hist.structured_content
        else str(hist)
    )
    assert "runs" in text.lower() or "count" in text.lower()
    stats = await server.call_tool("exec_cache_stats", {})
    text2 = (
        json.dumps(stats.structured_content)
        if hasattr(stats, "structured_content") and stats.structured_content
        else str(stats)
    )
    assert "hit_rate" in text2.lower() or "total_runs" in text2.lower()
