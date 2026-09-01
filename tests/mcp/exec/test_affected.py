"""Tests for T5 Affected — detect_changes → affected 50-75% prune."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch


def test_get_affected_with_mocked_changed_files(tmp_path: Path) -> None:
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("x=1\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_auth.py").write_text("test\n")

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)

    affected = svc.get_affected(changed_files=["src/auth.py"])
    assert "src/auth.py" in affected["changed_files"]
    assert "src/auth.py" in affected["affected"]
    assert len(affected["affected"]) >= 1


def test_service_get_affected_prunes_50_percent(tmp_path: Path) -> None:
    """50% prune: affected subset vs all files."""
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    for p in ["src/a.py", "src/b.py", "src/c.py", "src/d.py"]:
        (tmp_path / p).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp_path / p).write_text("x\n")

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)

    affected = svc.get_affected(changed_files=["src/a.py"])
    total = 4
    pruned = total - len(affected["affected"])
    assert len(affected["affected"]) <= 2
    assert pruned >= 2


def test_exec_affected_tool(tmp_path: Path) -> None:
    """exec_affected MCP tool returns affected (mocked blast radius)."""
    import asyncio

    from n3rv.mcp.exec_server import build_exec_server

    server = build_exec_server(tmp_path)

    async def _check():
        with patch(
            "n3rv.mcp.exec.service.ExecService.get_affected",
            return_value={
                "changed_files": ["src/auth.py"],
                "affected_tests": ["tests/auth/test_auth.py"],
                "affected_lints": ["src/auth.py"],
                "affected": ["src/auth.py", "tests/auth/test_auth.py"],
            },
        ):
            # Rebuild server under patch so its exec_service uses mocked method
            srv = build_exec_server(tmp_path)
            result = await srv.call_tool("exec_affected", {"base_ref": "main"})
            text = ""
            if hasattr(result, "structured_content") and result.structured_content:
                text = json.dumps(result.structured_content)
            elif hasattr(result, "content") and result.content:
                text = getattr(result.content[0], "text", str(result.content[0]))
            else:
                text = str(result)
            assert "changed_files" in text.lower() or "affected" in text.lower()

    asyncio.run(_check())
    # Also check unmocked path returns structure
    import asyncio as _asyncio

    async def _check2():
        result = await server.call_tool("exec_affected", {"base_ref": "main"})
        text = (
            json.dumps(result.structured_content)
            if hasattr(result, "structured_content") and result.structured_content
            else str(result)
        )
        assert "changed_files" in text.lower()

    _asyncio.run(_check2())


def test_exec_test_affected_prunes(tmp_path: Path, monkeypatch) -> None:
    """exec_test(affected=true) only runs affected files (called files ⊆ affected)."""
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: "/usr/bin/pytest")

    called_cmds: list[list[str]] = []

    def fake_run(cmd, cwd, timeout=60):
        called_cmds.append(cmd)
        return {"returncode": 0, "output": "5 passed in 0.42s", "stdout": "5 passed in 0.42s", "stderr": ""}

    monkeypatch.setattr("n3rv.mcp.exec_server._run", fake_run)

    affected_mock = {
        "changed_files": ["src/auth.py"],
        "affected_tests": ["tests/auth/test_auth.py"],
        "affected_lints": ["src/auth.py"],
        "affected": ["src/auth.py", "tests/auth/test_auth.py"],
    }

    import asyncio

    from n3rv.mcp.exec_server import build_exec_server as build_exec_server2

    async def _call():
        with patch("n3rv.mcp.exec.service.ExecService.get_affected", return_value=affected_mock):
            srv = build_exec_server2(tmp_path)
            await srv.call_tool("exec_test", {"path": ".", "affected": True, "base_ref": "main"})
            # called_cmds should have been invoked with pruned path (affected test)
            # At least one call happened
            assert len(called_cmds) >= 1
            # The command should contain the affected test file (prune)
            cmd_str = " ".join(called_cmds[-1])
            assert "tests/auth/test_auth.py" in cmd_str or "test_auth" in cmd_str

    asyncio.run(_call())
