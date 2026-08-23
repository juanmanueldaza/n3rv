"""Business logic for memory operations.

Orchestrates VectorStore + RelationStore + SessionManager.
No MCP decorators here — that lives in memory_server.py.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta

from n3rv.config import RuntimeSettings
from n3rv.mcp.conflict_store import ConflictStore
from n3rv.mcp.relation_store import RelationStore
from n3rv.mcp.session_manager import SessionManager
from n3rv.mcp.vector_store import VectorStore, _parse_timestamp
from n3rv.models.memory import (
    ConflictCandidate,
    ConflictLogEntry,
    ContextEntry,
    JudgeResult,
    MemoryScope,
    MemoryType,
    PruneResult,
    RelationVerdict,
    SaveResult,
    SearchResponse,
    SearchResult,
    TimelineEntry,
    TimelineResult,
)

logger = logging.getLogger("n3rv.mcp.service")

_SEARCH_NUDGE_THRESHOLD = 3
_SEARCH_NUDGE_MESSAGE = (
    "You've searched memory several times without saving new context. "
    "Consider using memory_save or memory_session_summary."
)
_CONFLICT_CANDIDATES_LIMIT = 3


def _to_dict(value):
    """Convert Pydantic model or list to dict for backward compat with tests."""
    if isinstance(value, (list,)):
        return [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


class MemoryService:
    """Dual-store memory system: ChromaDB (vector) + SQLite (relations)."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self._searches_since_write = 0
        self.vector_store = VectorStore(settings)
        self.relations = RelationStore(settings.paths.memory_dir / "relations.db")
        self.conflicts = ConflictStore(settings.paths.memory_dir / "conflicts.db")
        self.session_manager = SessionManager(self.vector_store)

    def memory_save(
        self,
        *,
        content: str,
        title: str,
        type: str,
        topic_key: str | None = None,
        scope: str = "project",
        agent_source: str | None = None,
        updated_at: str | None = None,
    ) -> dict:
        """Persist a memory observation. Returns dict for test compat.

        Parameters
        ----------
        updated_at : str | None
            Optional ISO timestamp for LWW merge. If None, uses now().
        """
        memory_type = MemoryType(type)
        memory_scope = MemoryScope(scope)
        self.vector_store.validate_content(content)
        self.vector_store.validate_title(title)
        validated_topic_key = self.vector_store.validate_topic_key(topic_key)
        now = self.vector_store.now()
        content_hash = self.vector_store.hash_content(content)
        document_id = self.vector_store.make_document_id(validated_topic_key)
        status = "created"
        revision_count = 1
        original_timestamp = now.isoformat()
        original_last_accessed = now.isoformat()
        self._reset_search_nudge()

        # Generate origin_uuid for this save
        import uuid as uuid_mod

        origin_uuid = str(uuid_mod.uuid4())

        if agent_source is None:
            from n3rv.mcp.shared import detect_agent_source

            agent_source = detect_agent_source()

        if validated_topic_key:
            existing = self.vector_store.get(
                where=self.vector_store._active_where({"topic_key": validated_topic_key}),
                limit=1,
                include=["metadatas", "documents"],
            )
            if existing["ids"]:
                document_id = existing["ids"][0]
                existing_meta = dict(existing["metadatas"][0])
                if existing_meta.get("content_hash") == content_hash:
                    # Same content hash → duplicate, just bump counts
                    existing_meta["duplicate_count"] = int(existing_meta.get("duplicate_count", 1)) + 1
                    existing_meta["last_seen_at"] = now.isoformat()
                    self.vector_store.update(ids=[document_id], metadatas=[existing_meta])
                    logger.debug("memory_save topic-duplicate id=%s", document_id)
                    return _to_dict(
                        SaveResult(
                            id=document_id,
                            topic_key=validated_topic_key,
                            status="duplicate",
                            timestamp=now,
                            revision_count=int(existing_meta.get("revision_count", 1)),
                        )
                    )
                else:
                    # Different content hash → LWW merge
                    new_updated_at = updated_at or now.isoformat()
                    existing_updated_at = str(existing_meta.get("updated_at", ""))

                    if existing_updated_at and new_updated_at <= existing_updated_at:
                        # Existing wins (LWW) → skip update
                        logger.debug(
                            "memory_save lww-merge-skip id=%s new_ts=%s existing_ts=%s",
                            document_id,
                            new_updated_at,
                            existing_updated_at,
                        )
                        return _to_dict(
                            SaveResult(
                                id=document_id,
                                topic_key=validated_topic_key,
                                status="duplicate",
                                timestamp=now,
                                revision_count=int(existing_meta.get("revision_count", 1)),
                            )
                        )

                    # New wins (LWW) → update and log conflict
                    self.conflicts.log_conflict(
                        topic_key=validated_topic_key,
                        winning_memory_id=document_id,
                        losing_memory_id=document_id,
                        losing_origin_uuid=str(existing_meta.get("origin_uuid", "unknown")),
                        losing_updated_at=existing_updated_at or now.isoformat(),
                        losing_content=existing["documents"][0] if existing["documents"] else None,
                        losing_title=str(existing_meta.get("title", "")) or None,
                        losing_type=str(existing_meta.get("type", "")) or None,
                        losing_agent_source=str(existing_meta.get("agent_source", "")) or None,
                    )
                    status = "updated"
                    revision_count = int(existing_meta.get("revision_count", 1)) + 1
                    original_timestamp = str(existing_meta.get("timestamp", now.isoformat()))
                    original_last_accessed = str(existing_meta.get("last_accessed_at", now.isoformat()))

        if status == "created":
            duplicate = self.vector_store.get(
                where=self.vector_store._active_where({"content_hash": content_hash}),
                include=["metadatas"],
                limit=1,
            )
            if duplicate["ids"]:
                dup_id = duplicate["ids"][0]
                dup_meta = dict(duplicate["metadatas"][0])
                dup_meta["duplicate_count"] = int(dup_meta.get("duplicate_count", 1)) + 1
                dup_meta["last_seen_at"] = now.isoformat()
                self.vector_store.update(ids=[dup_id], metadatas=[dup_meta])
                logger.debug("memory_save global-duplicate id=%s hash=%s", dup_id, content_hash)
                return _to_dict(
                    SaveResult(
                        id=dup_id,
                        topic_key=dup_meta.get("topic_key"),
                        status="duplicate",
                        timestamp=now,
                    )
                )

        metadata: dict[str, object] = {
            "title": title,
            "type": memory_type.value,
            "topic_key": validated_topic_key,
            "scope": memory_scope.value,
            "timestamp": original_timestamp,
            "agent_source": agent_source or "unknown",
            "deleted_at": "",
            "content_hash": content_hash,
            "duplicate_count": 1,
            "last_seen_at": now.isoformat(),
            "revision_count": revision_count,
            "updated_at": updated_at or now.isoformat(),
            "last_accessed_at": original_last_accessed,
            "origin_uuid": origin_uuid,
        }
        self.vector_store.save(
            document_id=document_id,
            content=content,
            metadata=metadata,
        )

        conflicts = self._bm25_candidates(content, exclude_id=document_id)

        logger.debug(
            "memory_save id=%s topic=%s status=%s conflicts=%d",
            document_id,
            validated_topic_key,
            status,
            len(conflicts),
        )
        return _to_dict(
            SaveResult(
                id=document_id,
                topic_key=validated_topic_key,
                status=status,
                timestamp=now,
                revision_count=revision_count,
                conflicts=conflicts,
            )
        )

    def memory_get(self, id: str) -> dict:
        """Fetch full content of a single active (non-deleted) memory by ID."""
        result = self.vector_store.get(ids=[id], include=["documents", "metadatas"])
        if not result["ids"]:
            raise KeyError(id)
        metadata = result["metadatas"][0]
        if str(metadata.get("deleted_at", "")):
            raise KeyError(id)
        return _to_dict(self._build_memory_entry(item_id=id, document=result["documents"][0], metadata=metadata))

    def memory_search(
        self,
        *,
        query: str,
        limit: int = 5,
        type_filter: str | None = None,
        keyword: str | None = None,
        snippet_only: bool = False,
        include_personal: bool = False,
    ) -> dict:
        """Semantic search across stored memories."""
        if not query or len(query) > 1_000:
            raise ValueError("query must be non-empty and at most 1000 characters")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if keyword is not None and (not keyword or len(keyword) > 1_000):
            raise ValueError("keyword must be non-empty and at most 1000 characters")

        filters: list[dict[str, object]] = []
        if type_filter:
            filters.append({"type": type_filter})
        if not include_personal:
            filters.append({"scope": {"$ne": "personal"}})
        where = self.vector_store._active_where(*filters)

        result = self.vector_store.query(
            query_texts=[query],
            n_results=limit,
            where=where,
            where_document={"$contains": keyword} if keyword else None,
        )

        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        items: list[SearchResult] = []
        for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances, strict=False):
            entry = self._build_memory_entry(item_id=item_id, document=document, metadata=metadata)
            content_out = document[:200] if snippet_only and len(document) > 200 else document
            items.append(
                SearchResult(
                    id=entry.id,
                    title=entry.title,
                    content=content_out,
                    type=entry.type,
                    topic_key=entry.topic_key,
                    score=self.vector_store._distance_to_score(float(distance)),
                    timestamp=entry.timestamp,
                    agent_source=entry.agent_source,
                )
            )

        logger.debug("memory_search query=%r limit=%d results=%d", query[:60], limit, len(items))
        self._searches_since_write += 1
        nudge = _SEARCH_NUDGE_MESSAGE if self._searches_since_write > _SEARCH_NUDGE_THRESHOLD else None
        return _to_dict(SearchResponse(results=items, nudge=nudge))

    def memory_recall(self, topic_key: str) -> dict:
        return _to_dict(self.session_manager.recall_memory(topic_key=topic_key))

    def memory_context(self, *, n: int = 10) -> dict:
        return _to_dict(self.session_manager.get_recent_context(n=n))

    def memory_session_summary(self, *, summary: str, agent_source: str | None = None) -> dict:
        self._reset_search_nudge()
        return _to_dict(self.session_manager.save_summary(summary=summary, agent_source=agent_source))

    def memory_session_start(self, *, agent_source: str | None = None) -> dict:
        return _to_dict(self.session_manager.start_session(agent_source=agent_source))

    def memory_delete(self, *, id: str, hard_delete: bool = False) -> dict:
        """Delete a memory by ID."""
        profile = __import__("os").environ.get("N3RV_MEMORY_PROFILE", "full")
        if hard_delete and profile == "safe":
            raise PermissionError("hard_delete not allowed in safe profile")

        result = self.vector_store.get(ids=[id], include=["metadatas"])
        if not result["ids"]:
            raise KeyError(id)

        if hard_delete:
            self.vector_store.delete(ids=[id])
        else:
            metadata = dict(result["metadatas"][0])
            metadata["deleted_at"] = self.vector_store.now().isoformat()
            self.vector_store.update(ids=[id], metadatas=[metadata])

        logger.debug("memory_delete id=%s hard_delete=%s", id, hard_delete)
        return {"id": id, "status": "deleted", "hard_delete": hard_delete}

    def memory_stats(self) -> dict:
        """Return aggregate counts: total, by_type, by_scope, by_agent."""
        result = self.vector_store.get_all(
            where=self.vector_store._active_where(),
            include=["metadatas"],
        )

        by_type: Counter[str] = Counter({t.value: 0 for t in MemoryType})
        by_scope: Counter[str] = Counter({s.value: 0 for s in MemoryScope})
        by_agent: Counter[str] = Counter()

        for metadata in result["metadatas"]:
            by_type[str(metadata["type"])] += 1
            by_scope[str(metadata["scope"])] += 1
            by_agent[str(metadata["agent_source"])] += 1

        return {
            "total": len(result["ids"]),
            "by_type": dict(by_type),
            "by_scope": dict(by_scope),
            "by_agent": dict(by_agent),
        }

    def memory_timeline(self, *, id: str, before: int = 5, after: int = 5) -> dict:
        """Return memories surrounding a focus memory (before + after)."""
        if not 0 <= before <= 20:
            raise ValueError("before must be between 0 and 20")
        if not 0 <= after <= 20:
            raise ValueError("after must be between 0 and 20")

        result = self.vector_store.get_all(
            where=self.vector_store._active_where(),
            include=["documents", "metadatas"],
        )

        entries = [
            self._build_memory_entry(item_id=item_id, document=document, metadata=metadata)
            for item_id, document, metadata in zip(
                result["ids"], result["documents"], result["metadatas"], strict=False
            )
        ]
        entries.sort(key=lambda item: item.timestamp)

        for index, entry in enumerate(entries):
            if entry.id != id:
                continue
            return _to_dict(
                TimelineResult(
                    focus=self._build_timeline_entry(entry, is_focus=True),
                    before=[
                        self._build_timeline_entry(item, is_focus=False)
                        for item in entries[max(0, index - before) : index]
                    ],
                    after=[
                        self._build_timeline_entry(item, is_focus=False)
                        for item in reversed(entries[index + 1 : index + 1 + after])
                    ],
                )
            )

        raise KeyError(id)

    def memory_judge(
        self,
        *,
        source_id: str,
        target_id: str,
        verdict: str,
        reason: str | None = None,
    ) -> dict:
        """Record an agent verdict on the relationship between two memories."""
        self.memory_get(source_id)
        self.memory_get(target_id)

        from n3rv.mcp.shared import detect_agent_source

        relation_verdict = RelationVerdict(verdict)
        relation_id, is_new = self.relations.upsert(
            source_id=source_id,
            target_id=target_id,
            verdict=relation_verdict.value,
            reason=reason or "",
            agent_source=detect_agent_source(),
        )

        logger.debug(
            "memory_judge %s->%s verdict=%s new=%s",
            source_id,
            target_id,
            verdict,
            is_new,
        )
        return _to_dict(
            JudgeResult(
                source_id=source_id,
                target_id=target_id,
                verdict=relation_verdict,
                status="created" if is_new else "updated",
                is_new=is_new,
            )
        )

    def memory_prune(
        self,
        *,
        scope: str,
        older_than_days: int | None = None,
        type_filter: str | None = None,
        hard_delete: bool = False,
    ) -> dict:
        """Delete old memories of the given scope, optionally filtered by type.

        When ``older_than_days`` is ``None``, uses the TTL from :attr:`settings.memory_ttl`,
        which provides scope-level defaults with per-type overrides.

        Parameters
        ----------
        scope:
            Memory scope to prune (session, personal, project).
        older_than_days:
            Override TTL. When ``None``, uses configured TTL for the scope/type.
        type_filter:
            Comma-separated list of memory types to prune (e.g. ``"summary,context"``).
            When ``None``, prunes all types in the scope.
        hard_delete:
            When ``True``, permanently removes from ChromaDB instead of soft-deleting.
        """
        memory_scope = MemoryScope(scope)
        types_to_prune: set[str] | None = None
        if type_filter:
            types_to_prune = {t.strip() for t in type_filter.split(",") if t.strip()}
            if not types_to_prune:
                raise ValueError("type_filter is set but empty")

        # Resolve TTL from config with per-type overrides
        if older_than_days is None:
            ttl_cfg = self.settings.memory_ttl.get(scope, {"default": 365})
            older_than_days = ttl_cfg["default"]
            overrides = ttl_cfg.get("overrides", {})
        else:
            overrides = {}

        if not 1 <= older_than_days <= 3650:
            raise ValueError("older_than_days must be between 1 and 3650")

        cutoff = self.vector_store.now() - timedelta(days=older_than_days)
        result = self.vector_store.get(
            where=self.vector_store._active_where({"scope": memory_scope.value}),
            include=["metadatas"],
        )

        ids_to_prune: list[str] = []
        metas_to_update: list[dict] = []
        now_iso = self.vector_store.now().isoformat()

        for item_id, metadata in zip(result["ids"], result["metadatas"], strict=False):
            mem_type = str(metadata.get("type", ""))

            # Apply type filter
            if types_to_prune is not None and mem_type not in types_to_prune:
                continue

            # Per-type TTL override (shorter-lived types get their own cutoff)
            type_ttl = overrides.get(mem_type, older_than_days)
            type_cutoff = self.vector_store.now() - timedelta(days=type_ttl) if type_ttl != older_than_days else cutoff

            ts_str = str(metadata.get("updated_at") or metadata.get("timestamp", ""))
            if not ts_str:
                continue
            try:
                ts = self.vector_store.parse_timestamp(ts_str)
            except ValueError:
                continue
            if ts < type_cutoff:
                if hard_delete:
                    ids_to_prune.append(item_id)
                else:
                    updated_meta = dict(metadata)
                    updated_meta["deleted_at"] = now_iso
                    ids_to_prune.append(item_id)
                    metas_to_update.append(updated_meta)

        if ids_to_prune:
            if hard_delete:
                self.vector_store.delete(ids=ids_to_prune)
            else:
                self.vector_store.update(ids=ids_to_prune, metadatas=metas_to_update)

        logger.debug(
            "memory_prune scope=%s older_than=%d types=%s hard_delete=%s pruned=%d",
            scope,
            older_than_days,
            type_filter or "all",
            hard_delete,
            len(ids_to_prune),
        )
        return _to_dict(
            PruneResult(
                pruned=len(ids_to_prune),
                scope=memory_scope,
                older_than_days=older_than_days,
            )
        )

    def get_conflicts(
        self,
        topic_key: str | None = None,
        days: int = 7,
    ) -> list[ConflictLogEntry]:
        """Query conflict log with optional filters.

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
        return self.conflicts.get_conflicts(topic_key=topic_key, days=days)

    # --- Private helpers ---

    def _bm25_candidates(self, content: str, *, exclude_id: str) -> list[ConflictCandidate]:
        """Return up to _CONFLICT_CANDIDATES_LIMIT existing memories most similar to content (BM25)."""
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            logger.debug("rank_bm25 not available; skipping conflict detection")
            return []

        result = self.vector_store.get_all(
            where=self.vector_store._active_where(),
            include=["documents", "metadatas"],
        )

        candidates = [
            (item_id, doc, meta)
            for item_id, doc, meta in zip(result["ids"], result["documents"], result["metadatas"], strict=False)
            if item_id != exclude_id
        ]
        if not candidates:
            return []

        cand_ids, cand_docs, cand_metas = zip(*candidates, strict=False)
        corpus_texts = [f"{m['title']} {d}" for d, m in zip(cand_docs, cand_metas, strict=False)]
        tokenized = [text.lower().split() for text in corpus_texts]
        bm25 = BM25Okapi(tokenized)

        query_tokens = content.lower().split()
        scores = bm25.get_scores(query_tokens)

        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results: list[ConflictCandidate] = []
        for idx, score in indexed[:_CONFLICT_CANDIDATES_LIMIT]:
            if score <= 0.0:
                break
            results.append(
                ConflictCandidate(
                    id=cand_ids[idx],
                    title=str(cand_metas[idx]["title"]),
                    score=round(float(score), 4),
                )
            )
        return results

    def _reset_search_nudge(self) -> None:
        self._searches_since_write = 0

    @staticmethod
    def _build_memory_entry(*, item_id: str, document: str, metadata: dict) -> ContextEntry:
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

    @staticmethod
    def _build_timeline_entry(entry: ContextEntry, *, is_focus: bool) -> TimelineEntry:
        return TimelineEntry(**entry.model_dump(), is_focus=is_focus)
