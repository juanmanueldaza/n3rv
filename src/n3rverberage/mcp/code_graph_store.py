"""SQLite-backed store for code graph symbols, imports, and call sites."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("n3rverberage.mcp.code_graph")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS code_graph_files (
    file_path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    content_hash TEXT NOT NULL,
    indexed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS code_graph_symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    parent TEXT,
    docstring TEXT,
    args TEXT,
    UNIQUE(file_path, name, kind, parent)
);

CREATE TABLE IF NOT EXISTS code_graph_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    module TEXT NOT NULL,
    names TEXT,
    is_from_import INTEGER NOT NULL,
    UNIQUE(file_path, module, names)
);

CREATE TABLE IF NOT EXISTS code_graph_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    name TEXT NOT NULL,
    line INTEGER NOT NULL,
    context TEXT
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON code_graph_symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON code_graph_symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON code_graph_symbols(kind);
CREATE INDEX IF NOT EXISTS idx_calls_name ON code_graph_calls(name);
CREATE INDEX IF NOT EXISTS idx_calls_file ON code_graph_calls(file_path);
CREATE INDEX IF NOT EXISTS idx_imports_file ON code_graph_imports(file_path);
CREATE INDEX IF NOT EXISTS idx_imports_module ON code_graph_imports(module);
"""


class CodeGraphStore:
    """SQLite store for code graph data (symbols, imports, calls)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ── File tracking ──────────────────────────────────────────────

    def upsert_file(self, file_path: str, mtime: float, content_hash: str) -> bool:
        """Store file metadata. Returns True if file was actually changed."""
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT mtime, content_hash FROM code_graph_files WHERE file_path = ?",
                (file_path,),
            ).fetchone()

            is_changed = existing is None or existing[0] != mtime or existing[1] != content_hash

            if is_changed:
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    INSERT INTO code_graph_files (file_path, mtime, content_hash, indexed_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        mtime=excluded.mtime,
                        content_hash=excluded.content_hash,
                        indexed_at=excluded.indexed_at
                    """,
                    (file_path, mtime, content_hash, now),
                )
                conn.commit()

        return is_changed

    def get_file_meta(self, file_path: str) -> tuple[float, str] | None:
        """Return (mtime, content_hash) for a file, or None if not indexed."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT mtime, content_hash FROM code_graph_files WHERE file_path = ?",
                (file_path,),
            ).fetchone()
        return (row[0], row[1]) if row else None

    def clear_file(self, file_path: str) -> None:
        """Remove all symbols, imports, and calls for a file."""
        with self._conn() as conn:
            conn.execute("DELETE FROM code_graph_symbols WHERE file_path = ?", (file_path,))
            conn.execute("DELETE FROM code_graph_imports WHERE file_path = ?", (file_path,))
            conn.execute("DELETE FROM code_graph_calls WHERE file_path = ?", (file_path,))
            conn.commit()

    # ── Batch inserts ──────────────────────────────────────────────

    def insert_symbols(self, symbols: list[dict]) -> None:
        """Batch insert symbol definitions."""
        with self._conn() as conn:
            for s in symbols:
                args_json = json.dumps(s.get("args")) if s.get("args") is not None else None
                conn.execute(
                    """
                    INSERT OR REPLACE INTO code_graph_symbols
                        (file_path, name, kind, line, end_line, parent, docstring, args)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s["file_path"],
                        s["name"],
                        s["kind"],
                        s["line"],
                        s.get("end_line"),
                        s.get("parent"),
                        s.get("docstring"),
                        args_json,
                    ),
                )
            conn.commit()

    def insert_imports(self, imports: list[dict]) -> None:
        """Batch insert import statements."""
        with self._conn() as conn:
            for imp in imports:
                names_json = json.dumps(imp.get("names")) if imp.get("names") is not None else None
                conn.execute(
                    """
                    INSERT OR REPLACE INTO code_graph_imports
                        (file_path, module, names, is_from_import)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        imp["file_path"],
                        imp["module"],
                        names_json,
                        1 if imp.get("is_from_import") else 0,
                    ),
                )
            conn.commit()

    def insert_calls(self, calls: list[dict]) -> None:
        """Batch insert call sites."""
        with self._conn() as conn:
            for call in calls:
                conn.execute(
                    "INSERT INTO code_graph_calls (file_path, name, line, context) VALUES (?, ?, ?, ?)",
                    (call["file_path"], call["name"], call["line"], call.get("context", "")),
                )
            conn.commit()

    # ── Queries ────────────────────────────────────────────────────

    def query_symbols(
        self,
        file_path: str | None = None,
        name: str | None = None,
        kind: str | None = None,
    ) -> list[dict]:
        """Query symbols with optional filters."""
        conditions: list[str] = []
        params: list = []
        if file_path:
            conditions.append("file_path = ?")
            params.append(file_path)
        if name:
            conditions.append("name = ?")
            params.append(name)
        if kind:
            conditions.append("kind = ?")
            params.append(kind)

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        cols = "file_path, name, kind, line, end_line, parent, docstring, args"
        query = (
            f"SELECT {cols} FROM code_graph_symbols{where}"
            " ORDER BY file_path, line"
        )

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "file": r[0],
                "name": r[1],
                "kind": r[2],
                "line": r[3],
                "end_line": r[4],
                "parent": r[5],
                "docstring": r[6],
                "args": json.loads(r[7]) if r[7] else None,
            }
            for r in rows
        ]

    def query_references(self, name: str) -> list[dict]:
        """Find all call sites for a given name."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT file_path, line, context FROM code_graph_calls WHERE name = ? ORDER BY file_path, line",
                (name,),
            ).fetchall()
        return [{"file": r[0], "line": r[1], "context": r[2]} for r in rows]

    def query_imports(self, file_path: str) -> dict:
        """Return import graph for a file: what it imports and what imports it."""
        with self._conn() as conn:
            # What this file imports
            from_rows = conn.execute(
                "SELECT module, names, is_from_import FROM code_graph_imports WHERE file_path = ?",
                (file_path,),
            ).fetchall()

            # What imports this file (by matching module names against file_path patterns)
            # We look for any import where the module string appears in the file path
            by_rows = conn.execute(
                "SELECT DISTINCT file_path FROM code_graph_imports WHERE module LIKE ?",
                (f"%{Path(file_path).stem}%",),
            ).fetchall()

        imports_from = [
            {
                "module": r[0],
                "names": json.loads(r[1]) if r[1] else None,
                "is_from_import": bool(r[2]),
            }
            for r in from_rows
        ]
        imported_by = [r[0] for r in by_rows if r[0] != file_path]

        return {"imports_from": imports_from, "imported_by": imported_by}

    def query_all_files(self) -> list[str]:
        """Return all indexed file paths."""
        with self._conn() as conn:
            rows = conn.execute("SELECT file_path FROM code_graph_files ORDER BY file_path").fetchall()
        return [r[0] for r in rows]
