"""SQLite-backed conflict log for LWW merge resolution.

Stores conflict entries when a memory_save() with a topic_key
collides with an existing memory (same topic_key, different origin_uuid).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from n3rverberage.models.memory import ConflictLogEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_conflict_log (
    id TEXT PRIMARY KEY,
    topic_key TEXT NOT NULL,
    winning_memory_id TEXT NOT NULL,
    losing_memory_id TEXT NOT NULL,
    losing_origin_uuid TEXT NOT NULL,
    losing_updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conflict_log_topic_key
    ON memory_conflict_log(topic_key);

CREATE INDEX IF NOT EXISTS idx_conflict_log_created_at
    ON memory_conflict_log(created_at);
"""


class ConflictStore:
    """SQLite store for memory conflict log entries."""

    def __init__(self, db_path: Path) -> None:
        """Create/open SQLite database at db_path."""
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create tables and indexes if not exist."""
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def log_conflict(
        self,
        *,
        topic_key: str,
        winning_memory_id: str,
        losing_memory_id: str,
        losing_origin_uuid: str,
        losing_updated_at: str,
    ) -> str:
        """Insert a conflict entry. Returns the conflict_id."""
        conflict_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        self._conn.execute(
            """
            INSERT INTO memory_conflict_log
                (id, topic_key, winning_memory_id, losing_memory_id,
                 losing_origin_uuid, losing_updated_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conflict_id,
                topic_key,
                winning_memory_id,
                losing_memory_id,
                losing_origin_uuid,
                losing_updated_at,
                now,
            ),
        )
        self._conn.commit()
        return conflict_id

    def get_conflicts(
        self,
        topic_key: str | None = None,
        days: int = 7,
    ) -> list[ConflictLogEntry]:
        """Query conflicts with optional filters.

        Parameters
        ----------
        topic_key : str | None
            If provided, filter to conflicts for this topic_key.
        days : int
            Only return conflicts created within the last N days.

        Returns
        -------
        list[ConflictLogEntry]
            Matching conflict entries, newest first.
        """
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        params: list[str | int] = [cutoff]
        where = "WHERE created_at >= ?"

        if topic_key:
            where += " AND topic_key = ?"
            params.append(topic_key)

        rows = self._conn.execute(
            f"""
            SELECT id, topic_key, winning_memory_id, losing_memory_id,
                   losing_origin_uuid, losing_updated_at, created_at
            FROM memory_conflict_log
            {where}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()

        return [
            ConflictLogEntry(
                id=row["id"],
                topic_key=row["topic_key"],
                winning_memory_id=row["winning_memory_id"],
                losing_memory_id=row["losing_memory_id"],
                losing_origin_uuid=row["losing_origin_uuid"],
                losing_updated_at=row["losing_updated_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
