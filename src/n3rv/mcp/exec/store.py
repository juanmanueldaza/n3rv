"""SQLite-backed store for n3rv-exec runs — twin to CodeGraphStore.

Persistent WAL twin: exec_runs + exec_file_states (XXH3) + exec_task_graph (phase 2).
Mirrors src/n3rv/mcp/code_graph_store.py:14-59 pattern: _SCHEMA + WAL + FTS5 fallback.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("n3rv.mcp.exec")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exec_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    command TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    git_sha TEXT,
    pass INTEGER NOT NULL,
    errors TEXT,
    output TEXT,
    duration_ms INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    file_paths TEXT
);

CREATE TABLE IF NOT EXISTS exec_file_states (
    file_path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    xxh3 TEXT NOT NULL,
    last_run_id INTEGER,
    FOREIGN KEY(last_run_id) REFERENCES exec_runs(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS exec_task_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    depends_on TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exec_runs_input_hash ON exec_runs(input_hash);
CREATE INDEX IF NOT EXISTS idx_exec_runs_tool ON exec_runs(tool);
CREATE INDEX IF NOT EXISTS idx_exec_runs_timestamp ON exec_runs(timestamp);
CREATE INDEX IF NOT EXISTS idx_exec_file_states_path ON exec_file_states(file_path);
"""


class ExecStore:
    """SQLite store for exec runs with WAL — twin to CodeGraphStore."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
            except sqlite3.OperationalError:
                pass
            conn.commit()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    # ── File states (XXH3 + mtime) ───────────────────────────────

    def upsert_file_state(self, file_path: str, mtime: float, xxh3: str, last_run_id: int | None = None) -> None:
        """Store XXH3 + mtime for a file."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO exec_file_states (file_path, mtime, xxh3, last_run_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    mtime=excluded.mtime,
                    xxh3=excluded.xxh3,
                    last_run_id=COALESCE(excluded.last_run_id, last_run_id)
                """,
                (file_path, mtime, xxh3, last_run_id),
            )
            conn.commit()

    def get_file_state(self, file_path: str) -> dict | None:
        """Return file state or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT file_path, mtime, xxh3, last_run_id FROM exec_file_states WHERE file_path = ?",
                (file_path,),
            ).fetchone()
        if row is None:
            return None
        return {"file_path": row[0], "mtime": row[1], "xxh3": row[2], "last_run_id": row[3]}

    def clear_file(self, file_path: str) -> None:
        """Remove file state entry."""
        with self._conn() as conn:
            conn.execute("DELETE FROM exec_file_states WHERE file_path = ?", (file_path,))
            conn.commit()

    # ── Runs ─────────────────────────────────────────────────────

    def upsert_run(
        self,
        *,
        tool: str,
        command: str,
        input_hash: str,
        config_hash: str,
        git_sha: str | None = None,
        passed: bool | None = None,
        errors: list[dict] | None = None,
        output: str | None = None,
        duration_ms: int = 0,
        file_paths: list[str] | None = None,
        timestamp: str | None = None,
    ) -> int:
        """Insert a run; returns row id."""
        ts = timestamp or datetime.now(UTC).isoformat()
        errors_json = json.dumps(errors) if errors is not None else None
        file_paths_json = json.dumps(file_paths) if file_paths is not None else None
        # 10KB output cap like exec_server
        if output is not None and len(output) > 10_000:
            output = output[:10_000] + "\n... truncated"
        pass_int = 1 if passed else 0
        if passed is None:
            pass_int = -1  # skipped
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO exec_runs
                    (tool, command, input_hash, config_hash, git_sha, pass, errors,
                     output, duration_ms, timestamp, file_paths)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool,
                    command,
                    input_hash,
                    config_hash,
                    git_sha,
                    pass_int,
                    errors_json,
                    output,
                    duration_ms,
                    ts,
                    file_paths_json,
                ),
            )
            conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def get_cached(self, input_hash: str) -> dict | None:
        """Return most recent run for input_hash with cached:true, or None."""
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, tool, command, input_hash, config_hash, git_sha, pass,
                       errors, output, duration_ms, timestamp, file_paths
                FROM exec_runs WHERE input_hash = ? ORDER BY timestamp DESC LIMIT 1
                """,
                (input_hash,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "tool": row[1],
            "command": row[2],
            "input_hash": row[3],
            "config_hash": row[4],
            "git_sha": row[5],
            "pass": bool(row[6]) if row[6] != -1 else None,
            "errors": json.loads(row[7]) if row[7] else [],
            "output": row[8],
            "duration_ms": row[9],
            "timestamp": row[10],
            "file_paths": json.loads(row[11]) if row[11] else [],
            "cached": True,
        }

    def get_history(self, limit: int = 20, tool: str | None = None) -> list[dict]:
        """Return last runs ordered newest first."""
        limit = max(1, min(limit, 100))
        with self._conn() as conn:
            if tool:
                rows = conn.execute(
                    """
                    SELECT id, tool, command, input_hash, config_hash, git_sha, pass,
                           errors, output, duration_ms, timestamp, file_paths
                    FROM exec_runs WHERE tool = ? ORDER BY timestamp DESC LIMIT ?
                    """,
                    (tool, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, tool, command, input_hash, config_hash, git_sha, pass,
                           errors, output, duration_ms, timestamp, file_paths
                    FROM exec_runs ORDER BY timestamp DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [
            {
                "id": r[0],
                "tool": r[1],
                "command": r[2],
                "input_hash": r[3],
                "config_hash": r[4],
                "git_sha": r[5],
                "pass": bool(r[6]) if r[6] != -1 else None,
                "errors": json.loads(r[7]) if r[7] else [],
                "output": r[8],
                "duration_ms": r[9],
                "timestamp": r[10],
                "file_paths": json.loads(r[11]) if r[11] else [],
            }
            for r in rows
        ]

    def get_timeline(self, file_path: str) -> list[dict]:
        """Return runs that touched file_path (via file_paths JSON)."""
        # Simple scan — file_paths is JSON array, use LIKE for filtering then python filter
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, tool, command, input_hash, config_hash, git_sha, pass,
                       errors, output, duration_ms, timestamp, file_paths
                FROM exec_runs ORDER BY timestamp DESC
                """
            ).fetchall()
        result: list[dict] = []
        for r in rows:
            fps = json.loads(r[11]) if r[11] else []
            if file_path in fps:
                result.append(
                    {
                        "id": r[0],
                        "tool": r[1],
                        "command": r[2],
                        "input_hash": r[3],
                        "config_hash": r[4],
                        "git_sha": r[5],
                        "pass": bool(r[6]) if r[6] != -1 else None,
                        "errors": json.loads(r[7]) if r[7] else [],
                        "output": r[8],
                        "duration_ms": r[9],
                        "timestamp": r[10],
                        "file_paths": fps,
                    }
                )
        return result

    def get_cache_stats(self) -> dict:
        """Return hit stats: total runs, unique hashes, est hit_rate."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM exec_runs").fetchone()[0]
            uniq = conn.execute("SELECT COUNT(DISTINCT input_hash) FROM exec_runs").fetchone()[0]
        hit_rate = 0.0
        if total > 0 and uniq > 0:
            # hits = total - uniq (repeats), rate = hits / total
            hits = total - uniq
            hit_rate = hits / total if total else 0.0
        return {"total_runs": total, "unique_hashes": uniq, "hit_rate": hit_rate}

    def get_counts(self) -> dict:
        """Aggregate counts for status reporting."""
        with self._conn() as conn:
            runs = conn.execute("SELECT COUNT(*) FROM exec_runs").fetchone()[0]
            files = conn.execute("SELECT COUNT(*) FROM exec_file_states").fetchone()[0]
        return {"runs": runs, "file_states": files}
