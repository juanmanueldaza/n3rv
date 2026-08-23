"""Lightweight SQLite-backed store for memory verdict relations."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

logger = logging.getLogger("n3rv.mcp.relation")


class RelationStore:
    """SQLite store for memory verdict relations (judge results).

    Stores source→target verdicts with optional reason and agent_source.
    Uses UPSERT on (source_id, target_id) to allow updates.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_relations (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT,
                    agent_source TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(source_id, target_id)
                )
            """)
            conn.commit()

    def upsert(
        self,
        *,
        source_id: str,
        target_id: str,
        verdict: str,
        reason: str,
        agent_source: str,
    ) -> tuple[str, bool]:
        """Insert or update a relation. Returns (relation_id, is_new)."""
        relation_id = str(uuid5(NAMESPACE_URL, f"{source_id}:{target_id}"))
        now = _now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM memory_relations WHERE source_id=? AND target_id=?",
                (source_id, target_id),
            ).fetchone()

            is_new = existing is None

            conn.execute(
                """
                INSERT INTO memory_relations (id, source_id, target_id, verdict, reason, agent_source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id) DO UPDATE SET
                    id=excluded.id,
                    verdict=excluded.verdict,
                    reason=excluded.reason,
                    agent_source=excluded.agent_source,
                    created_at=excluded.created_at
            """,
                (relation_id, source_id, target_id, verdict, reason, agent_source, now),
            )
            conn.commit()

        return relation_id, is_new


def _now():
    from datetime import UTC, datetime

    return datetime.now(UTC)
