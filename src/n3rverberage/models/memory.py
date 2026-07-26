from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(StrEnum):
    ARCHITECTURE = "architecture"
    BUGFIX = "bugfix"
    CONFIG = "config"
    DECISION = "decision"
    DISCOVERY = "discovery"
    LEARNING = "learning"
    PATTERN = "pattern"
    CONTEXT = "context"
    SUMMARY = "summary"
    NOTE = "note"


class MemoryScope(StrEnum):
    PROJECT = "project"
    SESSION = "session"
    PERSONAL = "personal"


class RelationVerdict(StrEnum):
    SUPERSEDES = "supersedes"
    CONFLICTS_WITH = "conflicts_with"
    RELATED = "related"
    DUPLICATE = "duplicate"
    NO_CONFLICT = "no_conflict"


class ConflictCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    score: float


class SaveResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    topic_key: str | None = None
    status: str
    timestamp: datetime
    revision_count: int = 1
    conflicts: list[ConflictCandidate] = []


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    content: str
    type: MemoryType
    topic_key: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime
    agent_source: str


class SearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: list[SearchResult]
    nudge: str | None = None


class RecallResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    found: bool
    topic_key: str
    id: str | None = None
    title: str | None = None
    content: str | None = None
    type: MemoryType | None = None
    timestamp: datetime | None = None
    agent_source: str | None = None


class ContextEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    content: str
    type: MemoryType
    scope: MemoryScope
    topic_key: str | None = None
    timestamp: datetime
    agent_source: str
    revision_count: int = 1
    updated_at: datetime | None = None
    last_accessed_at: datetime | None = None


class ContextResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    memories: list[ContextEntry]


class TimelineEntry(ContextEntry):
    model_config = ConfigDict(frozen=True)

    is_focus: bool


class TimelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    focus: TimelineEntry
    before: list[TimelineEntry]
    after: list[TimelineEntry]


class SessionStartResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    started_at: datetime
    context: list[ContextEntry] = []


class JudgeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    target_id: str
    verdict: RelationVerdict
    status: str
    is_new: bool = True


class PruneResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    pruned: int
    scope: MemoryScope
    older_than_days: int


class ConflictLogEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    topic_key: str
    winning_memory_id: str
    losing_memory_id: str
    losing_origin_uuid: str
    losing_updated_at: str
    created_at: str
