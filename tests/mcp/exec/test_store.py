"""Tests for ExecStore — SQLite WAL twin to CodeGraphStore (T1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def test_upsert_and_get_cached(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)

    run_id = store.upsert_run(
        tool="ruff",
        command="ruff check .",
        input_hash="abc123",
        config_hash="cfg1",
        git_sha="deadbeef",
        passed=True,
        errors=[],
        output="ok",
        duration_ms=42,
        file_paths=["src/foo.py"],
    )
    assert run_id == 1

    cached = store.get_cached("abc123")
    assert cached is not None
    assert cached["cached"] is True
    assert cached["input_hash"] == "abc123"
    assert cached["pass"] is True
    assert cached["config_hash"] == "cfg1"
    assert cached["tool"] == "ruff"

    # miss
    assert store.get_cached("missing") is None


def test_wal_enabled(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)
    store.upsert_run(tool="pytest", command="pytest -q", input_hash="h1", config_hash="c1", passed=True, duration_ms=10)

    with sqlite3.connect(db) as conn:
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    assert mode.lower() == "wal"


def test_file_states_xxh3(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)

    store.upsert_file_state("src/foo.py", mtime=123456.0, xxh3="abcxxh3", last_run_id=None)
    state = store.get_file_state("src/foo.py")
    assert state is not None
    assert state["xxh3"] == "abcxxh3"
    assert state["mtime"] == 123456.0

    # update xxh3
    store.upsert_file_state("src/foo.py", mtime=123457.0, xxh3="newhash")
    state2 = store.get_file_state("src/foo.py")
    assert state2["xxh3"] == "newhash"
    assert state2["mtime"] == 123457.0


def test_history_and_timeline(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)

    store.upsert_run(
        tool="ruff",
        command="ruff check .",
        input_hash="h1",
        config_hash="c1",
        passed=True,
        duration_ms=10,
        file_paths=["src/a.py"],
    )  # noqa: E501
    store.upsert_run(
        tool="pytest",
        command="pytest",
        input_hash="h2",
        config_hash="c1",
        passed=False,
        duration_ms=20,
        file_paths=["src/b.py"],
    )  # noqa: E501
    store.upsert_run(
        tool="ruff",
        command="ruff check .",
        input_hash="h3",
        config_hash="c2",
        passed=True,
        duration_ms=15,
        file_paths=["src/a.py"],
    )  # noqa: E501

    hist = store.get_history(limit=10)
    assert len(hist) == 3
    hist_ruff = store.get_history(limit=10, tool="ruff")
    assert len(hist_ruff) == 2
    assert all(r["tool"] == "ruff" for r in hist_ruff)

    tl = store.get_timeline("src/a.py")
    assert len(tl) == 2
    tl_b = store.get_timeline("src/b.py")
    assert len(tl_b) == 1


def test_cache_stats(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)

    # 3 runs, 2 unique hashes => hit_rate 1/3
    store.upsert_run(tool="ruff", command="ruff", input_hash="h1", config_hash="c1", passed=True, duration_ms=5)
    store.upsert_run(tool="ruff", command="ruff", input_hash="h1", config_hash="c1", passed=True, duration_ms=5)
    store.upsert_run(tool="ruff", command="ruff", input_hash="h2", config_hash="c1", passed=True, duration_ms=5)

    stats = store.get_cache_stats()
    assert stats["total_runs"] == 3
    assert stats["unique_hashes"] == 2
    assert abs(stats["hit_rate"] - 1 / 3) < 1e-6


def test_clear_file(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)
    store.upsert_file_state("src/foo.py", mtime=1.0, xxh3="h")
    assert store.get_file_state("src/foo.py") is not None
    store.clear_file("src/foo.py")
    assert store.get_file_state("src/foo.py") is None


def test_output_cap(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore

    db = tmp_path / "exec.db"
    store = ExecStore(db)
    big = "x" * 20000
    store.upsert_run(
        tool="ruff", command="ruff", input_hash="hbig", config_hash="c1", passed=True, duration_ms=5, output=big
    )
    cached = store.get_cached("hbig")
    assert cached is not None
    assert len(cached["output"]) <= 11000  # 10k + truncated suffix
    assert "truncated" in cached["output"]
