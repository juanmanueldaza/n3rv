"""Session lifecycle, summaries, and context injection for agent memories."""

from __future__ import annotations

import logging
from uuid import uuid4

from n3rv.mcp.vector_store import VectorStore, _parse_timestamp
from n3rv.models.memory import (
    ContextEntry,
    ContextResult,
    MemoryScope,
    MemoryType,
    RecallResult,
    SaveResult,
    SessionStartResult,
)

logger = logging.getLogger("n3rv.mcp.session")

_SESSION_CONTEXT_TYPES = [
    MemoryType.DECISION,
    MemoryType.ARCHITECTURE,
    MemoryType.PATTERN,
    MemoryType.CONFIG,
]
_SESSION_CONTEXT_LIMIT = 5


class SessionManager:
    """Manages session lifecycle and context injection.

    Depends on VectorStore for persistence. Handles session start,
    summary persistence, and recent context retrieval.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        self.vector_store = vector_store

    def start_session(self, *, agent_source: str | None = None) -> SessionStartResult:
        """Start a new session: saves context entry and returns recent project memories.

        Returns session_id and up to _SESSION_CONTEXT_LIMIT high-value memories.
        """
        started_at = self.vector_store.now()
        session_id = uuid4().hex

        self.vector_store.save(
            document_id=self.vector_store.make_document_id(f"session-start-{session_id[:8]}"),
            content=f"Session started at {started_at.isoformat()}",
            metadata={
                "title": f"Session start - {session_id[:8]}",
                "type": MemoryType.CONTEXT.value,
                "topic_key": f"session-start-{session_id[:8]}",
                "scope": MemoryScope.SESSION.value,
                "timestamp": started_at.isoformat(),
                "agent_source": agent_source or "unknown",
                "deleted_at": "",
                "content_hash": self.vector_store.hash_content("session start"),
                "duplicate_count": 1,
                "last_seen_at": started_at.isoformat(),
                "revision_count": 1,
                "updated_at": started_at.isoformat(),
                "last_accessed_at": started_at.isoformat(),
            },
        )

        context = self._load_session_context(types=_SESSION_CONTEXT_TYPES, limit=_SESSION_CONTEXT_LIMIT)
        return SessionStartResult(session_id=session_id, started_at=started_at, context=context)

    def save_summary(self, *, summary: str, agent_source: str | None = None) -> SaveResult:
        """Persist a session summary as type=summary, scope=session."""
        timestamp = self.vector_store.now()
        title = f"Session summary - {timestamp.isoformat()}"

        doc_id = self.vector_store.make_document_id(None)

        self.vector_store.save(
            document_id=doc_id,
            content=summary,
            metadata={
                "title": title,
                "type": MemoryType.SUMMARY.value,
                "topic_key": None,
                "scope": MemoryScope.SESSION.value,
                "timestamp": timestamp.isoformat(),
                "agent_source": agent_source or "unknown",
                "deleted_at": "",
                "content_hash": self.vector_store.hash_content(summary),
                "duplicate_count": 1,
                "last_seen_at": timestamp.isoformat(),
                "revision_count": 1,
                "updated_at": timestamp.isoformat(),
                "last_accessed_at": timestamp.isoformat(),
            },
        )

        return SaveResult(
            id=doc_id,
            topic_key=None,
            status="created",
            timestamp=timestamp,
            revision_count=1,
        )

    def get_recent_context(self, *, n: int = 10) -> ContextResult:
        """Return up to n most recent active memories (reverse chronological)."""
        if not 1 <= n <= 50:
            raise ValueError("n must be between 1 and 50")

        result = self.vector_store.get_all(
            where=self.vector_store._active_where(),
            include=["documents", "metadatas"],
        )

        entries: list[ContextEntry] = []
        for item_id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"], strict=False):
            entries.append(self._build_context_entry(item_id, document, metadata))

        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return ContextResult(count=min(n, len(entries)), memories=entries[:n])

    def recall_memory(self, *, topic_key: str) -> RecallResult:
        """Recall the most recent active memory for a topic_key.

        Updates last_accessed_at. Returns found=False if no active memory exists.
        """
        validated_topic_key = self.vector_store.validate_topic_key(topic_key)
        result = self.vector_store.get(
            where=self.vector_store._active_where({"topic_key": validated_topic_key}),
            limit=1,
            include=["documents", "metadatas"],
        )

        if not result["ids"]:
            return RecallResult(found=False, topic_key=validated_topic_key)

        item_id = result["ids"][0]
        metadata = dict(result["metadatas"][0])

        now_iso = self.vector_store.now().isoformat()
        metadata["last_accessed_at"] = now_iso
        self.vector_store.update(ids=[item_id], metadatas=[metadata])

        entry = self._build_context_entry(item_id, result["documents"][0], metadata)
        return RecallResult(
            found=True,
            topic_key=validated_topic_key,
            id=entry.id,
            title=entry.title,
            content=entry.content,
            type=entry.type,
            timestamp=entry.timestamp,
            agent_source=entry.agent_source,
        )

    def _load_session_context(self, *, types: list[MemoryType], limit: int) -> list[ContextEntry]:
        """Return recent project-scoped memories of high-value types for session injection."""
        type_values = [t.value for t in types]
        result = self.vector_store.get_all(
            where=self.vector_store._active_where(
                {"scope": "project"},
                {"type": {"$in": type_values}},
            ),
            include=["documents", "metadatas"],
        )

        entries = [
            self._build_context_entry(item_id, doc, meta)
            for item_id, doc, meta in zip(result["ids"], result["documents"], result["metadatas"], strict=False)
        ]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    @staticmethod
    def _build_context_entry(item_id: str, document: str, metadata: dict) -> ContextEntry:
        """Build a ContextEntry from raw ChromaDB data."""
        updated_at_str = str(metadata.get("updated_at", ""))
        last_accessed_str = str(metadata.get("last_accessed_at", ""))

        return ContextEntry(
            id=item_id,
            title=str(metadata["title"]),
            content=document,
            type=MemoryType(str(metadata["type"])),
            scope=MemoryScope(str(metadata["scope"])),
            topic_key=metadata.get("topic_key"),
            timestamp=_parse_timestamp(str(metadata["timestamp"])),
            agent_source=str(metadata["agent_source"]),
            revision_count=int(metadata.get("revision_count", 1)),
            updated_at=_parse_timestamp(updated_at_str) if updated_at_str else None,
            last_accessed_at=_parse_timestamp(last_accessed_str) if last_accessed_str else None,
        )
