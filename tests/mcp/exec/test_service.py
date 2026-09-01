"""Tests for ExecService — inputHash cache 70× (T3)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_cached_without_rerun(tmp_path: Path) -> None:
    """Second identical exec returns cached:true without subprocess."""
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=120\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x=1\n")

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)

    # Mock _tool_hash to be stable and _run to count
    with patch.object(
        svc, "_run", return_value={"returncode": 0, "output": "ok", "stdout": "ok", "stderr": ""}
    ) as mock_run:
        r1 = svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert r1["cached"] is False
        assert mock_run.call_count == 1

        r2 = svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert r2["cached"] is True
        # No second run
        assert mock_run.call_count == 1
        assert r2["input_hash"] == r1["input_hash"]


def test_config_change_invalidates(tmp_path: Path) -> None:
    """Editing ruff.toml/pyproject.toml invalidates configHash -> cache miss."""
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=120\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x=1\n")

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)

    with patch.object(
        svc, "_run", return_value={"returncode": 0, "output": "ok", "stdout": "ok", "stderr": ""}
    ) as mock_run:
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 1
        # cache hit
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 1

        # Change config
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=80\n")
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 2


def test_file_change_invalidates(tmp_path: Path) -> None:
    """File hash change invalidates."""
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x=1\n")

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)

    with patch.object(
        svc, "_run", return_value={"returncode": 0, "output": "ok", "stdout": "ok", "stderr": ""}
    ) as mock_run:
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 1
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 1

        (tmp_path / "src" / "foo.py").write_text("x=2\n")
        svc.execute(tool="ruff", command=["ruff", "check", "."], file_paths=["src/foo.py"])
        assert mock_run.call_count == 2


def test_compute_input_hash_stable(tmp_path: Path) -> None:
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "foo.py").write_text("x=1\n")
    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)
    h1 = svc.compute_input_hash("ruff", ["src/foo.py"])
    h2 = svc.compute_input_hash("ruff", ["src/foo.py"])
    assert h1 == h2
    # Different tool => different hash
    h3 = svc.compute_input_hash("pytest", ["src/foo.py"])
    assert h1 != h3


def test_cache_stats(tmp_path: Path) -> None:
    from n3rv.mcp.exec.service import ExecService
    from n3rv.mcp.exec.store import ExecStore

    store = ExecStore(tmp_path / "exec.db")
    svc = ExecService(tmp_path, store)
    stats = svc.get_cache_stats()
    assert "hit_rate" in stats
    assert "total_runs" in stats
