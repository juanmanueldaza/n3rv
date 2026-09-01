"""Tests for ExecWatcher — debounce + XXH3 incremental (T2)."""

from __future__ import annotations

from pathlib import Path


def test_resolve_debounce_clamp(monkeypatch) -> None:
    from n3rv.mcp.exec.watcher import _resolve_debounce

    monkeypatch.setenv("N3RV_EXEC_DEBOUNCE_MS", "50")
    assert _resolve_debounce() == 100  # clamp low
    monkeypatch.setenv("N3RV_EXEC_DEBOUNCE_MS", "999999")
    assert _resolve_debounce() == 60000  # clamp high
    monkeypatch.setenv("N3RV_EXEC_DEBOUNCE_MS", "bad")
    assert _resolve_debounce() == 500  # fallback
    monkeypatch.setenv("N3RV_EXEC_DEBOUNCE_MS", "300")
    assert _resolve_debounce() == 300


def test_watcher_pending_marks_staleness(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore
    from n3rv.mcp.exec.watcher import ExecWatcher

    db = tmp_path / "exec.db"
    store = ExecStore(db)
    watcher = ExecWatcher(tmp_path, debounce_ms=100, store=store)

    # Manually mark dirty
    watcher.mark_dirty("src/foo.py")
    assert "src/foo.py" in watcher.pending
    # get_dirty_files should return pending
    assert "src/foo.py" in watcher.get_dirty_files()

    watcher.clear_pending("src/foo.py")
    assert "src/foo.py" not in watcher.pending


def test_watcher_xxh3_stored(tmp_path: Path) -> None:
    from n3rv.mcp.exec.store import ExecStore
    from n3rv.mcp.exec.watcher import ExecWatcher, _content_hash

    db = tmp_path / "exec.db"
    store = ExecStore(db)
    watcher = ExecWatcher(tmp_path, debounce_ms=100, store=store)

    # Create file
    (tmp_path / "src").mkdir()
    p = tmp_path / "src" / "foo.py"
    p.write_text("x=1\n")
    h = _content_hash(b"x=1\n")
    # Simulate watcher handling
    watcher._handle_changed({str(p)})
    state = store.get_file_state("src/foo.py")
    assert state is not None
    assert state["xxh3"] == h
    assert state["mtime"] is not None

    # Edit file -> hash changes, dirty detection
    p.write_text("x=2\n")
    new_h = _content_hash(b"x=2\n")
    # Still stored old hash, so get_dirty_files should detect drift when pending empty
    watcher.clear_pending("src/foo.py")
    # force drift detection via mtime/hash mismatch
    dirty = watcher.get_dirty_files()
    assert "src/foo.py" in dirty

    # Re-handle to update store
    watcher._handle_changed({str(p)})
    state2 = store.get_file_state("src/foo.py")
    assert state2["xxh3"] == new_h


def test_watcher_should_watch() -> None:
    from pathlib import Path as PathAlias

    from n3rv.mcp.exec.watcher import _should_watch

    assert _should_watch(PathAlias("src/foo.py")) is True
    assert _should_watch(PathAlias("src/bar.ts")) is True
    assert _should_watch(PathAlias("pkg/main.go")) is True
    assert _should_watch(PathAlias("pyproject.toml")) is True
    assert _should_watch(PathAlias("ruff.toml")) is True
    assert _should_watch(PathAlias("package.json")) is True
    assert _should_watch(PathAlias("src/image.png")) is False
    assert _should_watch(PathAlias("README.md")) is False


def test_watcher_start_stop_idempotent(tmp_path: Path, monkeypatch) -> None:
    from n3rv.mcp.exec.watcher import ExecWatcher

    monkeypatch.setenv("N3RV_EXEC_NO_WATCH", "1")
    watcher = ExecWatcher(tmp_path, debounce_ms=100)
    watcher.start()
    assert watcher._running is True
    watcher.start()  # idempotent
    watcher.stop()
    assert watcher._running is False
    watcher.stop()  # idempotent
    monkeypatch.delenv("N3RV_EXEC_NO_WATCH", raising=False)


def test_staleness_banner_concept(tmp_path: Path) -> None:
    """Pending set surfaces as staleness banner — like code_graph_server _inject_staleness."""
    from n3rv.mcp.exec.watcher import ExecWatcher

    watcher = ExecWatcher(tmp_path, debounce_ms=100)
    watcher.mark_dirty("src/foo.py")
    watcher.mark_dirty("src/bar.py")
    # Simulate banner logic: pending intersection with referenced files
    referenced = {"src/foo.py", "src/other.py"}
    pending = set(watcher.pending)
    stale_refs = sorted(referenced.intersection(pending))
    assert stale_refs == ["src/foo.py"]
    other = sorted(pending - referenced)
    assert other == ["src/bar.py"]
    # banner text
    banner = "⚠️ " + ", ".join(f"Stale: {f} pending sync — Read it directly" for f in stale_refs)
    assert "Stale: src/foo.py pending sync" in banner
