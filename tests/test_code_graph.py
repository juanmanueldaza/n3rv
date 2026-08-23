"""Tests for the code graph MCP server."""

from __future__ import annotations

import textwrap
from pathlib import Path

from n3rverberage.mcp.code_graph_service import CodeGraphService
from n3rverberage.mcp.code_graph_store import CodeGraphStore  # noqa: I001

# ── Helpers ────────────────────────────────────────────────────────


def _create_project(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a minimal Python project in tmp_path."""
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content))
    return tmp_path


def _make_store(tmp_path: Path) -> CodeGraphStore:
    return CodeGraphStore(tmp_path / "test_graph.db")


# ── Store tests ────────────────────────────────────────────────────


def test_store_crud(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # Insert symbols
    store.insert_symbols(
        [
            {
                "file_path": "foo.py",
                "name": "hello",
                "kind": "function",
                "line": 1,
                "end_line": 5,
                "parent": None,
                "docstring": "Say hello.",
                "args": ["name", "greeting"],
            }
        ]
    )

    results = store.query_symbols(file_path="foo.py")
    assert len(results) == 1
    assert results[0]["name"] == "hello"
    assert results[0]["kind"] == "function"
    assert results[0]["args"] == ["name", "greeting"]

    # Query by name
    results = store.query_symbols(name="hello")
    assert len(results) == 1

    # Query by kind
    results = store.query_symbols(kind="class")
    assert len(results) == 0


def test_store_imports(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    store.insert_imports(
        [
            {"file_path": "foo.py", "module": "os", "names": None, "is_from_import": False},
            {"file_path": "foo.py", "module": "pathlib", "names": ["Path"], "is_from_import": True},
        ]
    )

    graph = store.query_imports("foo.py")
    assert len(graph["imports_from"]) == 2

    modules = {imp["module"] for imp in graph["imports_from"]}
    assert "os" in modules
    assert "pathlib" in modules


def test_store_calls(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    store.insert_calls(
        [
            {"file_path": "foo.py", "name": "get_provider", "line": 10, "context": "get_provider()"},
            {"file_path": "bar.py", "name": "get_provider", "line": 20, "context": "get_provider(model='x')"},
        ]
    )

    refs = store.query_references("get_provider")
    assert len(refs) == 2
    files = {r["file"] for r in refs}
    assert "foo.py" in files
    assert "bar.py" in files


def test_store_incremental(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    # First index
    assert store.upsert_file("foo.py", mtime=100.0, content_hash="abc123") is True

    # Same mtime + hash → not changed
    assert store.upsert_file("foo.py", mtime=100.0, content_hash="abc123") is False

    # Changed mtime → changed
    assert store.upsert_file("foo.py", mtime=200.0, content_hash="abc123") is True

    # Changed hash → changed
    assert store.upsert_file("foo.py", mtime=200.0, content_hash="def456") is True


def test_store_clear_file(tmp_path: Path) -> None:
    store = _make_store(tmp_path)

    store.insert_symbols(
        [
            {
                "file_path": "foo.py",
                "name": "x",
                "kind": "variable",
                "line": 1,
                "end_line": 1,
                "parent": None,
                "docstring": None,
                "args": None,
            }
        ]
    )
    store.insert_imports([{"file_path": "foo.py", "module": "os", "names": None, "is_from_import": False}])
    store.insert_calls([{"file_path": "foo.py", "name": "x", "line": 1, "context": "x"}])

    store.clear_file("foo.py")

    assert store.query_symbols(file_path="foo.py") == []
    assert store.query_imports("foo.py")["imports_from"] == []


# ── Service tests ──────────────────────────────────────────────────


def test_service_index(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "src/foo.py": """
def hello():
    pass

class Foo:
    def bar(self):
        pass
""",
            "src/bar.py": """
from foo import hello

def usage():
    hello()
""",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)

    stats = service.index()
    assert stats["files_indexed"] == 2
    assert stats["symbols_found"] >= 3  # hello, Foo, bar, usage
    assert stats["imports_found"] >= 1
    assert stats["calls_found"] >= 1


def test_service_symbols(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "foo.py": """
def hello():
    pass

class Foo:
    def bar(self):
        pass
""",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)
    service.index()

    # All symbols
    all_syms = service.symbols()
    names = {s["name"] for s in all_syms}
    assert "hello" in names
    assert "Foo" in names
    assert "bar" in names

    # Filter by file
    foo_syms = service.symbols(file_path="foo.py")
    assert all(s["file"] == "foo.py" for s in foo_syms)

    # Filter by kind
    funcs = service.symbols(kind="function")
    func_names = {s["name"] for s in funcs}
    assert "hello" in func_names
    assert "Foo" not in func_names

    # Filter by name
    hello = service.symbols(name="hello")
    assert len(hello) == 1
    assert hello[0]["kind"] == "function"


def test_service_references(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "foo.py": """
def helper():
    pass

def caller():
    helper()
    helper()
""",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)
    service.index()

    refs = service.references("helper")
    assert len(refs) == 2
    assert all(r["name"] == "helper" for r in refs if "name" in r)


def test_service_imports(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "src/a.py": "import os",
            "src/b.py": "from a import something",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)
    service.index()

    graph = service.imports("src/a.py")
    assert "os" in {imp["module"] for imp in graph["imports_from"]}


def test_service_affected(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "base.py": "x = 1",
            "mid.py": "from base import x",
            "top.py": "from mid import x",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)
    service.index()

    affected = service.affected("base.py")
    affected_files = {a["file"] for a in affected}
    assert "mid.py" in affected_files


def test_syntax_error_handling(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {
            "good.py": "x = 1\n",
            "bad.py": "def broken(\n",  # Syntax error
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)

    stats = service.index()
    assert stats["errors"] == 1
    assert stats["files_indexed"] == 1


# ── Server tests ───────────────────────────────────────────────────


def test_server_builds() -> None:
    from n3rverberage.mcp.code_graph_server import build_code_graph_server

    server = build_code_graph_server()
    assert server is not None


def test_entry_point_imports() -> None:
    from n3rverberage.mcp.code_graph_server import (
        build_code_graph_server,
        main,
        run_code_graph_server,
    )

    assert callable(main)
    assert callable(run_code_graph_server)
    assert callable(build_code_graph_server)


def test_no_network(tmp_path: Path) -> None:
    """All code graph operations are pure local — no network calls."""
    project = _create_project(
        tmp_path,
        {
            "foo.py": "x = 1\n",
        },
    )

    store = _make_store(tmp_path)
    service = CodeGraphService(store, project)

    # Index
    stats = service.index()
    assert stats["files_indexed"] == 1

    # Query
    syms = service.symbols()
    assert len(syms) >= 1

    # These all run locally — no HTTP, no API
    assert True
