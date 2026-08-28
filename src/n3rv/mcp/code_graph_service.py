"""Business logic for code graph: AST parsing, indexing, and querying."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from n3rv.mcp.code_graph_store import CodeGraphStore

logger = logging.getLogger("n3rv.mcp.code_graph")

_SKIP_DIRS_LITERAL = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".tox",
        ".eggs",
    }
)
_SKIP_DIRS_GLOBS = ("*.egg-info",)


def _should_skip(rel_parts: tuple[str, ...]) -> bool:
    for part in rel_parts:
        if part in _SKIP_DIRS_LITERAL:
            return True
        for pat in _SKIP_DIRS_GLOBS:
            if fnmatch.fnmatch(part, pat):
                return True
    return False


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
    """Extract all symbol definitions from an AST, including nested decls."""
    symbols: list[dict] = []

    def _walk(node: ast.AST, parent: str | None, parent_kind: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = getattr(child, "decorator_list", [])
                # Determine kind: decorated vs function/method depending on parent kind
                if decorators:
                    kind = "decorated"
                elif parent_kind == "class":
                    kind = "method"
                else:
                    kind = "function"
                symbols.append(
                    {
                        "file_path": file_path,
                        "name": child.name,
                        "kind": kind,
                        "line": child.lineno,
                        "end_line": getattr(child, "end_lineno", None),
                        "parent": parent,
                        "docstring": _get_docstring(child),
                        "args": _extract_args(child),
                    }
                )
                # Recurse: nested functions/classes inside this function
                _walk(child, child.name, kind)
            elif isinstance(child, ast.ClassDef):
                decorators = getattr(child, "decorator_list", [])
                kind = "decorated" if decorators else "class"
                symbols.append(
                    {
                        "file_path": file_path,
                        "name": child.name,
                        "kind": kind,
                        "line": child.lineno,
                        "end_line": getattr(child, "end_lineno", None),
                        "parent": parent,
                        "docstring": _get_docstring(child),
                        "args": None,
                    }
                )
                _walk(child, child.name, kind)
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        symbols.append(
                            {
                                "file_path": file_path,
                                "name": target.id,
                                "kind": "variable",
                                "line": child.lineno,
                                "end_line": getattr(child, "end_lineno", None),
                                "parent": parent,
                                "docstring": None,
                                "args": None,
                            }
                        )
                _walk(child, parent, parent_kind)
            elif isinstance(child, ast.AnnAssign):
                target = child.target
                if isinstance(target, ast.Name):
                    symbols.append(
                        {
                            "file_path": file_path,
                            "name": target.id,
                            "kind": "variable",
                            "line": child.lineno,
                            "end_line": getattr(child, "end_lineno", None),
                            "parent": parent,
                            "docstring": None,
                            "args": None,
                        }
                    )
                _walk(child, parent, parent_kind)
            else:
                _walk(child, parent, parent_kind)

    _walk(tree, None, None)
    return symbols


def _extract_imports(tree: ast.Module, file_path: str) -> list[dict]:
    """Extract all import statements from an AST."""
    imports: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "file_path": file_path,
                        "module": alias.name,
                        "names": None,
                        "is_from_import": False,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names] if node.names else None
            imports.append(
                {
                    "file_path": file_path,
                    "module": module,
                    "names": names,
                    "is_from_import": True,
                }
            )

    return imports


def _extract_calls(tree: ast.Module, file_path: str, source: str = "") -> list[dict]:
    """Extract all function/method call sites from an AST."""
    calls: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _resolve_call_name(node.func)
            if name:
                context = ""
                try:
                    context = ast.get_source_segment(source, node) or ""
                except Exception:
                    pass
                calls.append(
                    {
                        "file_path": file_path,
                        "name": name,
                        "line": node.lineno,
                        "context": context.strip(),
                    }
                )

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
            try:
                parts = path.relative_to(self.project_root).parts
            except ValueError:
                continue
            if _should_skip(parts):
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
                calls = _extract_calls(tree, rel_path, source)

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
                    results.append(
                        {
                            "file": importer,
                            "reason": "direct_import" if depth == 0 else "transitive_import",
                            "depth": depth,
                        }
                    )
                    _walk(importer, depth + 1)

        _walk(file_path, 0)
        return results

    def _read_verbatim(self, rel_path: str, line: int, end_line: int | None) -> str:
        """Read verbatim source slice with line numbers."""
        abs_path = self.project_root / rel_path
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        lines = text.splitlines()
        # Clamp
        start = max(1, line)
        end = end_line if end_line is not None else start
        end = min(len(lines), end)
        # Include a little context: expand to end_line or start+10 if no end
        if end_line is None:
            end = min(len(lines), start + 10)
        sliced = lines[start - 1 : end]
        numbered = [f"{i}: {content}" for i, content in zip(range(start, end + 1), sliced, strict=False)]
        return "\n".join(numbered)

    def status(self) -> dict:
        """Aggregate status for CLI / MCP."""
        counts = self.store.get_counts()
        # pending comes from watcher if present; base service has empty pending
        pending = getattr(self, "_pending", None)
        if pending is None:
            pending_list: list[str] = []
        elif isinstance(pending, set):
            pending_list = sorted(pending)
        else:
            pending_list = list(pending)
        return {
            "files_indexed": counts["files"],
            "symbols_found": counts["symbols"],
            "imports_found": counts["imports"],
            "calls_found": counts["calls"],
            "pending": pending_list,
        }

    def reconcile(self) -> dict:
        """Connect-time catch-up: scan disk, re-index drifted files, prune stale."""
        files = self._find_python_files()
        existing = {str(p.relative_to(self.project_root)) for p in files}
        # Remove stale DB entries for deleted files
        stale_removed = self.store.remove_stale_files(existing)
        # Incremental index will handle drift via mtime+hash check
        stats = self.index()
        stats["stale_removed"] = stale_removed
        return stats

    def explore(
        self,
        query: str,
        max_nodes: int = 20,
        include_code: bool = True,
    ) -> dict:
        """Surgical explore: one call returns nodes + verbatim + call paths + blast radius."""
        if not query or not query.strip():
            return {"error": "query required"}
        max_nodes = max(1, min(int(max_nodes), 100))
        query = query.strip()

        # Ensure index is fresh (handles edits while watcher pending / hub down)
        # Lightweight: incremental index will skip unchanged quickly
        try:
            self.index()
        except Exception as exc:
            logger.warning("Explore reconcile failed: %s", exc)

        # Ranked search
        nodes = self.store.search_fts(query, limit=max_nodes)
        if not nodes:
            # Fallback to LIKE if FTS yielded nothing but symbols exist
            nodes = self.store.search_fts(query, limit=max_nodes)

        if include_code:
            code_by_file: dict[str, str] = {}
            for n in nodes:
                rel = n["file"]
                if rel not in code_by_file:
                    snippet = self._read_verbatim(rel, n["line"], n.get("end_line"))
                    if snippet:
                        code_by_file[rel] = snippet
                    else:
                        # Fallback: try to read whole file grouped if multiple nodes same file
                        continue
            # If multiple nodes same file, we want full grouped snippets per file not per-node slice
            # Merge: for each file, collect all line ranges and read once with union
            if nodes and code_by_file:
                # Rebuild grouped per-file with all symbol ranges merged
                from collections import defaultdict

                file_to_nodes: dict[str, list[dict]] = defaultdict(list)
                for n in nodes:
                    file_to_nodes[n["file"]].append(n)
                grouped: dict[str, str] = {}
                for rel, ns in file_to_nodes.items():
                    try:
                        text = (self.project_root / rel).read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue
                    lines = text.splitlines()
                    blocks: list[str] = []
                    for n in sorted(ns, key=lambda x: x["line"]):
                        s = max(1, n["line"])
                        e = n.get("end_line") or s
                        e = min(len(lines), e)
                        # Expand slightly if single line
                        if e - s < 1:
                            e = min(len(lines), s + 5)
                        snippet_lines = lines[s - 1 : e]
                        numbered = [f"{i}: {content}" for i, content in enumerate(snippet_lines, start=s)]
                        blocks.append("\n".join(numbered))
                    grouped[rel] = "\n---\n".join(blocks)
                code_by_file = grouped
        else:
            code_by_file = {}

        # Call paths: for each node, find call sites that reference its name
        call_paths: list[dict] = []
        seen_paths: set[tuple[str, str, str]] = set()
        for n in nodes:
            name = n["name"]
            # Callers: where this symbol is called
            refs = self.store.query_references(name)
            for r in refs:
                key = (r["file"], name, r.get("context", ""))
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                call_paths.append(
                    {
                        "from": r["file"],
                        "to": n["file"],
                        "via": name,
                        "line": r["line"],
                        "context": r.get("context", ""),
                    }
                )
            # Callees: what this symbol's file calls (outgoing)
            try:
                callees = self.store.query_callees(n["file"])
                for c in callees[:3]:  # limit per node to keep payload bounded
                    key2 = (n["file"], c["name"], c.get("context", ""))
                    if key2 in seen_paths:
                        continue
                    seen_paths.add(key2)
                    call_paths.append(
                        {
                            "from": n["file"],
                            "to": c["name"],
                            "via": c["name"],
                            "line": c["line"],
                            "context": c.get("context", ""),
                        }
                    )
            except Exception:
                pass

        # Blast radius: affected files for each result file + aggregate callers/callees
        blast_callers: list[dict] = []
        blast_callees: list[dict] = []
        affected_files_set: set[str] = set()
        affected_detailed: list[dict] = []
        for n in nodes:
            # affected via imports
            try:
                aff = self.affected(n["file"])
                for a in aff:
                    if a["file"] not in affected_files_set:
                        affected_files_set.add(a["file"])
                        affected_detailed.append(a)
            except Exception:
                pass
            # callers/callees per node
            try:
                refs = self.store.query_references(n["name"])
                for r in refs:
                    if r not in blast_callers:
                        blast_callers.append(r)
            except Exception:
                pass
            try:
                cs = self.store.query_callees(n["file"])
                for c in cs:
                    entry = {"file": n["file"], "name": c["name"], "line": c["line"]}
                    if entry not in blast_callees:
                        blast_callees.append(entry)
            except Exception:
                pass

        result: dict = {
            "nodes": nodes,
            "code_by_file": code_by_file,
            "call_paths": call_paths[:50],
            "blast_radius": {
                "callers": blast_callers[:20],
                "callees": blast_callees[:20],
                "affected_files": sorted(affected_files_set),
                "affected": affected_detailed[:20],
            },
        }
        return result
