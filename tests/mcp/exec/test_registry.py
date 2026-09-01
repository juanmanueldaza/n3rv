"""Tests for registry — 20+ languages covering all codebase-memory-mcp grammars."""

from __future__ import annotations


def test_registry_has_20_plus_languages() -> None:
    from n3rv.mcp.exec.registry import REGISTRY

    assert len(REGISTRY) >= 20, f"Expected 20+ languages, got {len(REGISTRY)}"
    # Must include core tree-sitter set from #51
    for lang in ["python", "javascript", "typescript", "go", "rust", "java", "kotlin", "swift", "ruby", "php"]:
        assert lang in REGISTRY, f"Missing {lang}"


def test_registry_all_exts_26_plus() -> None:
    from n3rv.mcp.exec.registry import ALL_EXTS

    assert len(ALL_EXTS) >= 26, f"Expected 26+ exts, got {len(ALL_EXTS)}"
    for ext in [".py", ".ts", ".js", ".go", ".rs", ".java", ".rb", ".php", ".swift", ".cs", ".cpp"]:
        assert ext in ALL_EXTS, f"Missing {ext}"


def test_registry_ext_to_lint_mapping() -> None:
    from n3rv.mcp.exec.registry import get_lint_for_ext

    assert get_lint_for_ext(".py")[0] == "ruff"
    assert get_lint_for_ext(".js")[0] == "eslint"
    assert get_lint_for_ext(".go")[0] == "golangci-lint"
    assert get_lint_for_ext(".rs")[0] == "cargo"
    assert get_lint_for_ext(".rb")[0] == "rubocop"
    assert get_lint_for_ext(".php")[0] == "phpcs"
    # Unknown ext
    assert get_lint_for_ext(".unknown") is None


def test_registry_lint_chain_covers_all() -> None:
    from n3rv.mcp.exec.registry import LINT_CHAIN, REGISTRY

    assert len(LINT_CHAIN) == len(REGISTRY)
    tools = [t for t, _ in LINT_CHAIN]
    assert "ruff" in tools
    assert "eslint" in tools
    assert "golangci-lint" in tools


def test_watcher_covers_all_registry_exts() -> None:
    from pathlib import Path

    from n3rv.mcp.exec.registry import ALL_EXTS
    from n3rv.mcp.exec.watcher import _should_watch

    for ext in ALL_EXTS:
        assert _should_watch(Path(f"src/file{ext}")) is True, f"Watcher should watch {ext}"
    assert _should_watch(Path("src/image.png")) is False


def test_service_files_hash_uses_registry(tmp_path) -> None:
    """Service _files_hash should pick up all registry exts."""

    from n3rv.mcp.exec.service import _files_hash

    # Create one file per language
    (tmp_path / "a.py").write_text("x")
    (tmp_path / "b.rs").write_text("x")
    (tmp_path / "c.go").write_text("x")
    h1 = _files_hash(tmp_path)
    # Add another language file changes hash
    (tmp_path / "d.java").write_text("x")
    h2 = _files_hash(tmp_path)
    assert h1 != h2


def test_exec_server_per_extension_dispatch(tmp_path, monkeypatch) -> None:
    """exec_lint should pick per-extension linter when available."""
    from n3rv.mcp.exec_server import _detect_lint_tool

    # Mock ruff present but target is .go — should still prefer go's linter if available?
    # Our logic: per-ext first, then chain. So .go target should try golangci-lint if ruff also present.
    # But if both present, ruff is first in chain, but per-ext check will return golangci-lint for .go.
    monkeypatch.setattr("n3rv.mcp.exec_server.shutil.which", lambda x: True)
    # .go should map to golangci-lint
    lint = _detect_lint_tool("src/main.go")
    assert lint[0] == "golangci-lint"
    # .py should map to ruff
    lint2 = _detect_lint_tool("src/app.py")
    assert lint2[0] == "ruff"
    # .rs should map to cargo
    lint3 = _detect_lint_tool("src/lib.rs")
    assert lint3[0] == "cargo"
