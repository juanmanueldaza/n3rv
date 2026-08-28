"""MCP server that exposes code graph analysis for opencode agents.

Agents call these tools to query symbol definitions, import graphs,
call sites, and impact analysis across a Python project.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from n3rv.mcp.code_graph_service import CodeGraphService
from n3rv.mcp.code_graph_store import CodeGraphStore
from n3rv.mcp.code_graph_watcher import CodeGraphWatcher, _resolve_debounce
from n3rv.mcp.shared import (
    build_mcp_server,
    resolve_runtime_settings,
    result_payload,
)

logger = logging.getLogger("n3rv.mcp.code_graph")

# Per-project-root watcher singletons so we don't spin multiple Observers.
_watchers: dict[Path, CodeGraphWatcher] = {}
_watchers_lock = threading.Lock()


def _get_watcher(project_root: Path) -> CodeGraphWatcher | None:
    """Return a lazy watcher singleton for project_root, if enabled."""
    root = project_root.resolve()
    if os.environ.get("N3RV_CODE_GRAPH_NO_WATCH", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return None
    with _watchers_lock:
        if root not in _watchers:
            settings = resolve_runtime_settings(root)
            db_path = settings.paths.n3rv_dir / "code_graph.db"
            store = CodeGraphStore(db_path)
            svc = CodeGraphService(store, root)
            w = CodeGraphWatcher(root, svc, debounce_ms=_resolve_debounce())
            _watchers[root] = w
        w = _watchers[root]
    return w


def _inject_staleness(result: dict, watcher: CodeGraphWatcher | None) -> dict:
    """Prepend a banner / append a footer when watcher has pending files."""
    if watcher is None or not watcher.pending:
        return result
    pending_list = sorted(watcher.pending)
    referenced = set()
    # Gather files referenced by the result
    for node in result.get("nodes", []):
        if "file" in node:
            referenced.add(node["file"])
        if "file_path" in node:
            referenced.add(node["file_path"])
    for cp in result.get("call_paths", []):
        referenced.add(cp.get("from", ""))
        referenced.add(cp.get("to", ""))
    if referenced:
        # Banner: files referenced but still pending
        stale_refs = sorted(referenced.intersection(pending_list))
        if stale_refs:
            banner = "⚠️ " + ", ".join(f"Stale: {f} pending sync — Read it directly" for f in stale_refs)
            result["banner"] = banner
    # Footer: other pending files not referenced by this response
    other = sorted(set(pending_list) - referenced)
    if other:
        result["footer"] = "Pending sync for: " + ", ".join(other)
    return result


def build_code_graph_server(project_root: Path | None = None):
    """Build and return the n3rv-code-graph MCP server."""
    settings = resolve_runtime_settings(project_root)
    db_path = settings.paths.n3rv_dir / "code_graph.db"
    store = CodeGraphStore(db_path)
    project_root = project_root or Path.cwd()
    svc = CodeGraphService(store, project_root)
    # Ensure index is fresh on server startup (connect-time catch-up)
    try:
        svc.reconcile()
    except Exception as exc:
        logger.warning("CodeGraph reconcile on startup failed: %s", exc)
    _ = _get_watcher(project_root)
    server = build_mcp_server(
        "n3rv-code-graph",
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

    @server.tool(description="Surgical explore: one call returns relevant source + call paths + blast radius.")
    async def code_graph_explore(
        project_path: str,
        query: str,
        max_nodes: int | None = None,
        include_code: bool = True,
    ) -> dict:
        """Explore code semantically in a single call.

        Returns nodes, verbatim code grouped by file, call paths, and blast radius.
        During an active watcher debounce, files still pending sync carry a staleness banner.
        """
        root = Path(project_path).resolve()
        if not root.exists():
            return {"error": f"Path not found: {project_path}"}
        svc = CodeGraphService(store, root)
        # Ensure watcher pending set is visible for staleness injection
        watcher = _get_watcher(root)
        result = svc.explore(
            query,
            max_nodes=max_nodes if max_nodes is not None else 20,
            include_code=include_code,
        )
        result = _inject_staleness(result, watcher)
        return result_payload(result)

    return server


def run_code_graph_server() -> None:
    """Entry point for n3rv-code-graph subprocess."""
    build_code_graph_server().run()


def main() -> None:
    """Entry point for n3rv-code-graph command."""
    run_code_graph_server()
