"""Business logic for code graph: AST parsing, indexing, and querying."""

from __future__ import annotations

import ast
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from n3rverberage.mcp.code_graph_store import CodeGraphStore

logger = logging.getLogger("n3rverberage.mcp.code_graph")

_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".venv", "venv", ".mypy_cache",
    ".ruff_cache", "node_modules", ".tox", ".eggs", "*.egg-info",
})


@dataclass
class SymbolInfo:
    name: str
    kind: str
    file: str
    line: int
    end_line: int | None = None
    parent: str | None = None
    docstring: str | None = None
    args: list[str] | None = None


@dataclass
class ImportInfo:
    file: str
    module: str
    names: list[str] | None
    is_from_import: bool


@dataclass
class ReferenceInfo:
    file: str
    line: int
    context: str


@dataclass
class AffectedInfo:
    file: str
    reason: str
    depth: int


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _get_docstring(node: ast.AST) -> str | None:
    return ast.get_docstring(node)


def _extract_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract argument names from a function definition."""
    args: list[str] = []
    for arg in node.args.args:
        args.append(arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    for arg in node.args.kwonlyargs:
        args.append(arg.arg)
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return args


def _extract_symbols(tree: ast.Module, file_path: str) -> list[dict]:
    """Extract all symbol definitions from an AST."""
    symbols: list[dict] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = [d for d in node.decorator_list]
            kind = "decorated" if decorators else "function"
            symbols.append({
                "file_path": file_path,
                "name": node.name,
                "kind": kind,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", None),
                "parent": None,
                "docstring": _get_docstring(node),
                "args": _extract_args(node),
            })

            # Methods inside classes — handled by walking ClassDef children
        elif isinstance(node, ast.ClassDef):
            decorators = [d for d in node.decorator_list]
            kind = "decorated" if decorators else "class"
            symbols.append({
                "file_path": file_path,
                "name": node.name,
                "kind": kind,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", None),
                "parent": None,
                "docstring": _get_docstring(node),
                "args": None,
            })

            # Extract methods
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item_decorators = [d for d in item.decorator_list]
                    method_kind = "decorated" if item_decorators else "method"
                    symbols.append({
                        "file_path": file_path,
                        "name": item.name,
                        "kind": method_kind,
                        "line": item.lineno,
                        "end_line": getattr(item, "end_lineno", None),
                        "parent": node.name,
                        "docstring": _get_docstring(item),
                        "args": _extract_args(item),
                    })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols.append({
                        "file_path": file_path,
                        "name": target.id,
                        "kind": "variable",
                        "line": node.lineno,
                        "end_line": getattr(node, "end_lineno", None),
                        "parent": None,
                        "docstring": None,
                        "args": None,
                    })

    return symbols


def _extract_imports(tree: ast.Module, file_path: str) -> list[dict]:
    """Extract all import statements from an AST."""
    imports: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "file_path": file_path,
                    "module": alias.name,
                    "names": None,
                    "is_from_import": False,
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names] if node.names else None
            imports.append({
                "file_path": file_path,
                "module": module,
                "names": names,
                "is_from_import": True,
            })

    return imports


def _extract_calls(tree: ast.Module, file_path: str) -> list[dict]:
    """Extract all function/method call sites from an AST."""
    calls: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _resolve_call_name(node.func)
            if name:
                # Get the source line for context
                context = ""
                try:
                    context = ast.get_source_segment("", node) or ""
                except Exception:
                    pass
                calls.append({
                    "file_path": file_path,
                    "name": name,
                    "line": node.lineno,
                    "context": context.strip(),
                })

    return calls


def _resolve_call_name(func: ast.expr) -> str | None:
    """Resolve the name of a called function/method."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts = []
        current = func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        parts.reverse()
        return ".".join(parts)
    return None


class CodeGraphService:
    """Business logic for code graph: parse, index, query."""

    def __init__(self, store: CodeGraphStore, project_root: Path) -> None:
        self.store = store
        self.project_root = project_root.resolve()

    def _find_python_files(self, patterns: list[str] | None = None) -> list[Path]:
        """Find all .py files in the project root, skipping known directories."""
        files: list[Path] = []

        for path in self.project_root.rglob("*.py"):
            # Skip excluded directories
            parts = path.relative_to(self.project_root).parts
            if any(part in _SKIP_DIRS for part in parts):
                continue
            files.append(path)

        return sorted(files)

    def index(self, file_patterns: list[str] | None = None) -> dict:
        """Index Python files into the code graph. Incremental (skips unchanged)."""
        files = self._find_python_files(file_patterns)
        stats = {
            "files_indexed": 0,
            "symbols_found": 0,
            "imports_found": 0,
            "calls_found": 0,
            "files_skipped": 0,
            "errors": 0,
        }

        for i, path in enumerate(files):
            try:
                content = path.read_bytes()
                mtime = path.stat().st_mtime
                content_hash = _content_hash(content)
                rel_path = str(path.relative_to(self.project_root))

                # Check if unchanged
                meta = self.store.get_file_meta(rel_path)
                if meta and meta[0] == mtime and meta[1] == content_hash:
                    stats["files_skipped"] += 1
                    continue

                # Parse
                try:
                    source = content.decode("utf-8", errors="replace")
                    tree = ast.parse(source, filename=str(path))
                except SyntaxError as exc:
                    logger.warning("Syntax error in %s: %s", rel_path, exc)
                    stats["errors"] += 1
                    continue

                # Extract
                symbols = _extract_symbols(tree, rel_path)
                imports = _extract_imports(tree, rel_path)
                calls = _extract_calls(tree, rel_path)

                # Store
                self.store.clear_file(rel_path)
                if symbols:
                    self.store.insert_symbols(symbols)
                if imports:
                    self.store.insert_imports(imports)
                if calls:
                    self.store.insert_calls(calls)
                self.store.upsert_file(rel_path, mtime, content_hash)

                stats["files_indexed"] += 1
                stats["symbols_found"] += len(symbols)
                stats["imports_found"] += len(imports)
                stats["calls_found"] += len(calls)

                if (i + 1) % 50 == 0:
                    logger.info("Indexed %d/%d files", i + 1, len(files))

            except PermissionError:
                logger.warning("Permission denied: %s", path)
                stats["errors"] += 1
            except OSError as exc:
                logger.warning("Error reading %s: %s", path, exc)
                stats["errors"] += 1

        logger.info(
            "Index complete: %d indexed, %d skipped, %d symbols, %d imports, %d calls, %d errors",
            stats["files_indexed"],
            stats["files_skipped"],
            stats["symbols_found"],
            stats["imports_found"],
            stats["calls_found"],
            stats["errors"],
        )
        return stats

    def symbols(
        self,
        file_path: str | None = None,
        name: str | None = None,
        kind: str | None = None,
    ) -> list[dict]:
        """Query symbol definitions."""
        return self.store.query_symbols(file_path=file_path, name=name, kind=kind)

    def references(self, name: str) -> list[dict]:
        """Find all call sites for a function/method by name."""
        return self.store.query_references(name)

    def imports(self, file_path: str) -> dict:
        """Return import graph for a file."""
        return self.store.query_imports(file_path)

    def affected(self, file_path: str, max_depth: int = 5) -> list[dict]:
        """Transitive impact analysis: which files would be affected."""
        visited: set[str] = set()
        results: list[dict] = []

        def _walk(current_file: str, depth: int) -> None:
            if depth > max_depth or current_file in visited:
                return
            visited.add(current_file)

            # Find files that import from current_file
            imports_data = self.store.query_imports(current_file)
            for importer in imports_data.get("imported_by", []):
                if importer not in visited:
                    results.append({
                        "file": importer,
                        "reason": "direct_import" if depth == 0 else "transitive_import",
                        "depth": depth,
                    })
                    _walk(importer, depth + 1)

        _walk(file_path, 0)
        return results
