"""MCP server that exposes code graph analysis for opencode agents.

Agents call these tools to query symbol definitions, import graphs,
call sites, and impact analysis across a Python project.
"""

from __future__ import annotations

import logging
from pathlib import Path

from n3rverberage.mcp.code_graph_service import CodeGraphService
from n3rverberage.mcp.code_graph_store import CodeGraphStore
from n3rverberage.mcp.shared import (
    build_mcp_server,
    resolve_runtime_settings,
    result_payload,
)

logger = logging.getLogger("n3rverberage.mcp.code_graph")


def build_code_graph_server(project_root: Path | None = None):
    """Build and return the n3rverberage-code-graph MCP server."""
    settings = resolve_runtime_settings(project_root)
    db_path = settings.paths.n3rverberage_dir / "code_graph.db"
    store = CodeGraphStore(db_path)
    _ = CodeGraphService(store, project_root or Path.cwd())  # ensure indexing works
    server = build_mcp_server(
        "n3rverberage-code-graph",
        "Code analysis: symbol index, imports, references, and impact analysis.",
    )

    @server.tool(description="Index project Python files into the code graph. Incremental (skips unchanged files).")
    async def code_graph_index(project_path: str) -> dict:
        """Walk project_path for .py files, parse with ast, store in SQLite.
        Returns summary: files_indexed, symbols_found, imports_found, calls_found, files_skipped.
        """
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        return result_payload(svc.index())

    @server.tool(description="List symbol definitions (functions, classes, methods) in a file or across the project.")
    async def code_graph_symbols(
        project_path: str,
        file_path: str | None = None,
        name: str | None = None,
        kind: str | None = None,
    ) -> dict:
        """Query symbol definitions. Optional filters: file_path, name, kind."""
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        return result_payload(svc.symbols(file_path=file_path, name=name, kind=kind))

    @server.tool(description="Find all call sites for a function or method by name.")
    async def code_graph_references(project_path: str, name: str) -> dict:
        """Find all places where `name` is called as a function."""
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        return result_payload(svc.references(name))

    @server.tool(description="Show import graph for a file: what it imports, and what imports it.")
    async def code_graph_imports(project_path: str, file_path: str) -> dict:
        """Returns {imports_from: [...], imported_by: [...]} for the given file."""
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        return result_payload(svc.imports(file_path))

    @server.tool(description="Impact analysis: which files would be affected if this file changes.")
    async def code_graph_affected(project_path: str, file_path: str, max_depth: int = 5) -> dict:
        """Transitive impact analysis up to max_depth levels."""
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        return result_payload(svc.affected(file_path, max_depth=max_depth))

    return server


def run_code_graph_server() -> None:
    """Entry point for n3rverberage-code-graph subprocess."""
    build_code_graph_server().run()


def main() -> None:
    """Entry point for n3rverberage-code-graph command."""
    run_code_graph_server()
