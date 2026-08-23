"""ChromaDB vector store for semantic memory persistence."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from chromadb import PersistentClient
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from n3rv.config import RuntimeSettings
from n3rv.models.memory import MemoryScope

logger = logging.getLogger("n3rv.mcp.vector")

_SIMPLE_HASH_DIM = 384
_TOPIC_KEY_PATTERN = re.compile(r"^[a-z0-9-]+$")


class _SimpleHashEmbeddingFunction(EmbeddingFunction):
    """Deterministic hash-based embeddings — no ML deps required."""

    def name(self) -> str:
        return "n3rv-hash"

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            vec = [0.0] * _SIMPLE_HASH_DIM
            for i, ch in enumerate(text[:2048]):
                digest = int(hashlib.md5(f"{i}:{ch}".encode()).hexdigest(), 16)
                vec[digest % _SIMPLE_HASH_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            embeddings.append([x / norm for x in vec])
        return embeddings


def _make_embedding_function() -> EmbeddingFunction | None:
    try:
        import onnxruntime  # noqa: F401

        return None
    except (ImportError, Exception):
        return _SimpleHashEmbeddingFunction()


def _collection_name(project_root: Path) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", project_root.name.lower()).strip("-") or "project"
    return f"{slug}_memories"


def _content_hash(content: str) -> str:
    normalized = content.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _now():
    return datetime.now(UTC)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class VectorStore:
    """ChromaDB-backed vector store for memory persistence."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self._ensure_directories()
        self.client = PersistentClient(path=str(settings.paths.memory_dir))
        ef = _make_embedding_function()
        if ef is not None:
            logger.warning("onnxruntime unavailable — using hash embedding fallback")
        self.collection_name = _collection_name(settings.paths.project_root)
        try:
            self.collection = self.client.get_or_create_collection(
                self.collection_name,
                embedding_function=ef,
            )
        except Exception:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                self.collection_name,
                embedding_function=ef,
            )
        self._ensure_metadata_defaults()

    def _ensure_directories(self) -> None:
        self.settings.paths.memory_dir.mkdir(parents=True, exist_ok=True)

    def save(self, *, document_id: str, content: str, metadata: dict) -> None:
        self.collection.upsert(ids=[document_id], documents=[content], metadatas=[metadata])

    def get(
        self,
        ids: list[str] | None = None,
        where: dict | None = None,
        include: list[str] | None = None,
        limit: int | None = None,
    ) -> dict:
        kwargs: dict = {}
        if ids is not None:
            kwargs["ids"] = ids
        if where is not None:
            kwargs["where"] = where
        if include is not None:
            kwargs["include"] = include
        if limit is not None:
            kwargs["limit"] = limit
        return self.collection.get(**kwargs)

    def update(self, ids: list[str], metadatas: list[dict]) -> None:
        self.collection.update(ids=ids, metadatas=metadatas)

    def query(
        self,
        *,
        query_texts: list[str],
        n_results: int,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> dict:
        kwargs = {"query_texts": query_texts, "n_results": n_results}
        if where is not None:
            kwargs["where"] = where
        if where_document is not None:
            kwargs["where_document"] = where_document
        return self.collection.query(**kwargs)

    def delete(self, ids: list[str]) -> None:
        self.collection.delete(ids=ids)

    def get_all(self, where: dict | None = None, include: list[str] | None = None) -> dict:
        return self.get(where=where, include=include)

    def _active_where(self, *filters: dict[str, object]) -> dict[str, object]:
        all_filters: list[dict[str, object]] = [*filters, {"deleted_at": ""}]
        if len(all_filters) == 1:
            return all_filters[0]
        return {"$and": list(all_filters)}

    def _distance_to_score(self, distance: float) -> float:
        return 1.0 / (1.0 + max(distance, 0.0))

    def make_document_id(self, topic_key: str | None) -> str:
        if topic_key:
            return str(uuid5(NAMESPACE_URL, topic_key))
        return str(uuid4())

    def validate_topic_key(self, topic_key: str | None) -> str | None:
        if topic_key is None:
            return None
        if len(topic_key) > 100 or not _TOPIC_KEY_PATTERN.fullmatch(topic_key):
            raise ValueError("topic_key must match [a-z0-9-]+")
        return topic_key

    def validate_content(self, content: str) -> None:
        if not content or len(content) > 10_000:
            raise ValueError("content must be non-empty and at most 10000 characters")

    def validate_title(self, title: str) -> None:
        if not title or len(title) > 200:
            raise ValueError("title must be non-empty and at most 200 characters")

    def hash_content(self, content: str) -> str:
        return _content_hash(content)

    def now(self):
        return _now()

    def parse_timestamp(self, value: str) -> datetime:
        return _parse_timestamp(value)

    def _ensure_metadata_defaults(self) -> None:
        result = self.get(include=["documents", "metadatas"])
        ids_to_update: list[str] = []
        metadatas_to_update: list[dict] = []

        for item_id, document, metadata in zip(result["ids"], result["documents"], result["metadatas"], strict=False):
            updated_metadata = dict(metadata)
            changed = False

            if "deleted_at" not in updated_metadata:
                updated_metadata["deleted_at"] = ""
                changed = True
            if updated_metadata.get("scope") == "global":
                updated_metadata["scope"] = MemoryScope.PERSONAL.value
                changed = True
            if "content_hash" not in updated_metadata:
                updated_metadata["content_hash"] = _content_hash(document)
                changed = True
            if "duplicate_count" not in updated_metadata:
                updated_metadata["duplicate_count"] = 1
                changed = True
            if "last_seen_at" not in updated_metadata:
                updated_metadata["last_seen_at"] = str(updated_metadata["timestamp"])
                changed = True
            if "revision_count" not in updated_metadata:
                updated_metadata["revision_count"] = 1
                changed = True
            if "updated_at" not in updated_metadata:
                updated_metadata["updated_at"] = str(updated_metadata["timestamp"])
                changed = True
            if "last_accessed_at" not in updated_metadata:
                updated_metadata["last_accessed_at"] = str(updated_metadata["timestamp"])
                changed = True

            if changed:
                ids_to_update.append(item_id)
                metadatas_to_update.append(updated_metadata)

        if ids_to_update:
            self.update(ids=ids_to_update, metadatas=metadatas_to_update)
