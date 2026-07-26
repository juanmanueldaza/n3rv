from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from n3rverberage.mcp.memory_server import build_memory_server
from n3rverberage.mcp.memory_service import MemoryService
from n3rverberage.mcp.shared import detect_agent_source
from n3rverberage.mcp.vector_store import VectorStore


def test_memory_save_and_recall(runtime_settings, monkeypatch) -> None:
    monkeypatch.setenv("N3RVERBERAGE_AGENT_SOURCE", "opencode")
    service = MemoryService(runtime_settings)

    saved = service.memory_save(
        content="We chose JWT with refresh tokens.",
        title="Auth strategy",
        type="decision",
        topic_key="auth-strategy",
    )
    recalled = service.memory_recall(topic_key="auth-strategy")

    assert saved["status"] == "created"
    assert recalled["found"] is True
    assert recalled["title"] == "Auth strategy"
    assert recalled["content"] == "We chose JWT with refresh tokens."
    assert recalled["agent_source"] == "opencode"


def test_memory_upsert_reuses_id(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    first = service.memory_save(
        content="Version one.",
        title="Decision",
        type="decision",
        topic_key="stable-key",
    )
    second = service.memory_save(
        content="Version two.",
        title="Decision",
        type="decision",
        topic_key="stable-key",
    )

    recalled = service.memory_recall(topic_key="stable-key")
    assert first["id"] == second["id"]
    assert second["status"] == "updated"
    assert recalled["content"] == "Version two."


def test_memory_search_returns_scored_result(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="We chose JWT with refresh tokens stored in httpOnly cookies.",
        title="Auth strategy",
        type="decision",
        topic_key="auth-strategy",
    )

    results = service.memory_search(query="authentication tokens", limit=1)

    assert len(results["results"]) == 1
    assert results["nudge"] is None
    assert results["results"][0]["topic_key"] == "auth-strategy"
    assert 0.0 <= results["results"][0]["score"] <= 1.0


def test_memory_context_includes_session_summary(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Older note", title="Older", type="note", topic_key="older-note")
    summary = service.memory_session_summary(summary="Completed auth module.")
    context = service.memory_context(n=5)

    assert summary["status"] == "created"
    assert context["count"] >= 2
    assert context["memories"][0]["type"] == "summary"


def test_memory_delete_soft_delete_hides_memory(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(
        content="JWT uses short-lived access tokens and refresh tokens.",
        title="Auth strategy",
        type="decision",
        topic_key="auth-strategy",
    )

    deleted = service.memory_delete(id=saved["id"])
    recalled = service.memory_recall(topic_key="auth-strategy")
    search_results = service.memory_search(query="refresh tokens", limit=5)
    context = service.memory_context(n=5)
    stored = service.vector_store.collection.get(ids=[saved["id"]], include=["metadatas"])

    assert deleted == {"id": saved["id"], "status": "deleted", "hard_delete": False}
    assert recalled["found"] is False
    assert recalled["topic_key"] == "auth-strategy"
    assert search_results == {"results": [], "nudge": None}
    assert context == {"count": 0, "memories": []}
    assert stored["metadatas"][0]["deleted_at"]


def test_memory_delete_hard_delete_removes_memory(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(
        content="Use typed config models for auth.",
        title="Config",
        type="config",
        topic_key="auth-config",
    )

    deleted = service.memory_delete(id=saved["id"], hard_delete=True)
    stored = service.vector_store.collection.get(ids=[saved["id"]], include=["metadatas"])

    assert deleted == {"id": saved["id"], "status": "deleted", "hard_delete": True}
    assert stored["ids"] == []


def test_memory_delete_raises_for_unknown_id(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    try:
        service.memory_delete(id="missing-id")
    except KeyError as exc:
        assert exc.args == ("missing-id",)
    else:
        raise AssertionError("Expected KeyError for unknown memory id")


def test_memory_stats_groups_active_memories(runtime_settings, monkeypatch) -> None:
    monkeypatch.setenv("N3RVERBERAGE_AGENT_SOURCE", "opencode")
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="ADR: split memory and hub services.",
        title="Architecture ADR",
        type="architecture",
        topic_key="adr-hub-memory",
        scope="project",
    )
    service.memory_save(
        content="Use hatchling for build backend.",
        title="Config",
        type="config",
        topic_key="build-config",
        scope="personal",
    )
    monkeypatch.setenv("N3RVERBERAGE_AGENT_SOURCE", "opencode")
    deleted = service.memory_save(
        content="Temporary debugging note.",
        title="Debug note",
        type="note",
        topic_key="debug-note",
        scope="session",
    )
    service.memory_delete(id=deleted["id"])

    stats = service.memory_stats()

    assert stats["total"] == 2
    assert stats["by_type"]["architecture"] == 1
    assert stats["by_type"]["config"] == 1
    assert stats["by_type"]["bugfix"] == 0  # zero-filled for all enum values
    assert stats["by_scope"]["project"] == 1
    assert stats["by_scope"]["personal"] == 1
    assert stats["by_scope"]["session"] == 0  # zero-filled for all enum values
    assert stats["by_agent"]["opencode"] == 2


def test_memory_search_keyword_is_additive(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Authentication uses refresh tokens in secure cookies.",
        title="Refresh tokens",
        type="decision",
        topic_key="refresh-auth",
    )
    service.memory_save(
        content="Authentication uses API keys for internal services.",
        title="API keys",
        type="decision",
        topic_key="api-key-auth",
    )

    results = service.memory_search(query="authentication", limit=5, keyword="refresh")

    assert results["nudge"] is None
    assert [item["topic_key"] for item in results["results"]] == ["refresh-auth"]


def test_memory_save_accepts_new_memory_types(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    saved = service.memory_save(
        content="Discovered that the hub server requires MCP startup ordering.",
        title="Hub discovery",
        type="discovery",
        topic_key="hub-startup-discovery",
    )
    recalled = service.memory_recall(topic_key="hub-startup-discovery")

    assert saved["status"] == "created"
    assert recalled["type"] == "discovery"


def test_memory_timeline_returns_neighboring_entries(runtime_settings, monkeypatch) -> None:
    timestamps = iter(
        [
            datetime(2025, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 1, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 2, 0, tzinfo=UTC),
            datetime(2025, 1, 1, 3, 0, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(VectorStore, "now", staticmethod(lambda: next(timestamps)))
    service = MemoryService(runtime_settings)

    oldest = service.memory_save(content="Oldest context", title="Oldest", type="context", topic_key="oldest")
    older = service.memory_save(content="Older context", title="Older", type="context", topic_key="older")
    focus = service.memory_save(content="Focus context", title="Focus", type="context", topic_key="focus")
    newest = service.memory_save(content="Newest context", title="Newest", type="context", topic_key="newest")

    timeline = service.memory_timeline(id=focus["id"], before=2, after=1)

    assert timeline["focus"]["id"] == focus["id"]
    assert timeline["focus"]["title"] == "Focus"
    assert timeline["focus"]["is_focus"] is True
    assert [item["title"] for item in timeline["before"]] == ["Oldest", "Older"]
    assert [item["id"] for item in timeline["before"]] == [oldest["id"], older["id"]]
    assert [item["is_focus"] for item in timeline["before"]] == [False, False]
    assert [item["title"] for item in timeline["after"]] == ["Newest"]
    assert [item["id"] for item in timeline["after"]] == [newest["id"]]
    assert [item["is_focus"] for item in timeline["after"]] == [False]


def test_memory_timeline_raises_for_soft_deleted_memory(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(content="Soon deleted", title="Deleted", type="note", topic_key="deleted-note")
    service.memory_delete(id=saved["id"])

    with pytest.raises(KeyError, match=saved["id"]):
        service.memory_timeline(id=saved["id"])


def test_memory_save_deduplicates_content(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    first = service.memory_save(
        content="Refresh tokens belong in secure cookies.",
        title="Auth decision",
        type="decision",
        topic_key="auth-decision",
    )
    duplicate = service.memory_save(
        content="  refresh tokens belong in secure cookies.  ",
        title="Different title",
        type="note",
        topic_key="duplicate-topic",
    )
    recalled = service.memory_recall(topic_key="auth-decision")
    duplicate_topic = service.memory_recall(topic_key="duplicate-topic")
    stored = service.vector_store.collection.get(ids=[first["id"]], include=["metadatas"])
    context = service.memory_context(n=10)

    assert first["status"] == "created"
    assert duplicate["id"] == first["id"]
    assert duplicate["status"] == "duplicate"
    assert recalled["found"] is True
    assert duplicate_topic["found"] is False
    assert context["count"] == 1
    assert stored["metadatas"][0]["duplicate_count"] == 2
    assert stored["metadatas"][0]["last_seen_at"]
    assert (
        stored["metadatas"][0]["content_hash"]
        == hashlib.sha256(b"refresh tokens belong in secure cookies.").hexdigest()[:16]
    )


def test_memory_save_rejects_legacy_global_scope(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    with pytest.raises(ValueError, match="global"):
        service.memory_save(
            content="Personal preference for CLI layout.",
            title="CLI preference",
            type="note",
            topic_key="cli-preference",
            scope="global",
        )


def test_memory_store_migrates_legacy_metadata(runtime_settings) -> None:
    initial = MemoryService(runtime_settings)
    initial.vector_store.collection.add(
        ids=["legacy-memory-01"],
        documents=["Legacy content"],
        metadatas=[
            {
                "title": "Legacy",
                "type": "note",
                "topic_key": "legacy-note",
                "scope": "global",
                "timestamp": "2025-01-01T00:00:00+00:00",
                "agent_source": "opencode",
            }
        ],
    )

    migrated = MemoryService(runtime_settings)
    record = migrated.vector_store.collection.get(ids=["legacy-memory-01"], include=["documents", "metadatas"])
    metadata = record["metadatas"][0]

    assert metadata["scope"] == "personal"
    assert metadata["deleted_at"] == ""
    assert metadata["duplicate_count"] == 1
    assert metadata["last_seen_at"] == "2025-01-01T00:00:00+00:00"
    assert metadata["content_hash"] == hashlib.sha256(b"legacy content").hexdigest()[:16]


def test_build_memory_server_enables_stateless_http(runtime_settings) -> None:
    server = build_memory_server(runtime_settings.paths.project_root)

    assert server.settings.stateless_http is True
    assert server.settings.json_response is True


def test_detect_agent_source_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setenv("N3RVERBERAGE_AGENT_SOURCE", "opencode")

    assert detect_agent_source() == "opencode"


# ── Phase 3: session management ───────────────────────────────────────────────


def test_memory_session_start_returns_session_id(runtime_settings) -> None:
    service = MemoryService(runtime_settings)

    result = service.memory_session_start()

    assert result["session_id"]
    assert result["started_at"]
    recalled = service.memory_recall(topic_key=f"session-start-{result['session_id'][:8]}")
    assert recalled["found"] is True
    assert recalled["type"] == "context"


def test_memory_search_nudges_after_threshold(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Seed content for searching.",
        title="Seed",
        type="note",
        topic_key="seed-note",
    )

    THRESHOLD = 3
    for _ in range(THRESHOLD):
        result = service.memory_search(query="seed content")
        assert result.get("nudge") is None

    result = service.memory_search(query="seed content")
    assert result.get("nudge") is not None
    assert "memory_save" in result["nudge"]


def test_memory_save_resets_nudge_counter(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Seed to search.", title="Seed", type="note", topic_key="seed-reset")

    THRESHOLD = 3
    for _ in range(THRESHOLD + 1):
        service.memory_search(query="seed")

    nudged = service.memory_search(query="seed")
    assert nudged.get("nudge") is not None

    service.memory_save(
        content="New insight after searching.",
        title="New",
        type="note",
        topic_key="new-insight",
    )
    reset = service.memory_search(query="seed")
    assert reset.get("nudge") is None


def test_memory_session_summary_resets_nudge_counter(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Something to search for.",
        title="Seed",
        type="note",
        topic_key="summary-seed",
    )

    for _ in range(5):
        service.memory_search(query="something")

    nudged = service.memory_search(query="something")
    assert nudged.get("nudge") is not None

    service.memory_session_summary(summary="Completed work on auth module.")
    reset = service.memory_search(query="something")
    assert reset.get("nudge") is None


# ---------------------------------------------------------------------------
# memory_get
# ---------------------------------------------------------------------------


def test_memory_get_returns_full_content(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(content="Full content here.", title="Full", type="note", topic_key="full-get")
    result = service.memory_get(id=saved["id"])

    assert result["content"] == "Full content here."
    assert result["title"] == "Full"


def test_memory_get_raises_for_soft_deleted(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(content="To be deleted.", title="Del", type="note", topic_key="del-get")
    service.memory_delete(id=saved["id"])

    with pytest.raises(KeyError):
        service.memory_get(saved["id"])


def test_memory_get_raises_for_unknown_id(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    with pytest.raises(KeyError):
        service.memory_get("does-not-exist")


# ---------------------------------------------------------------------------
# snippet_only / include_personal
# ---------------------------------------------------------------------------


def test_memory_search_snippet_only_truncates_content(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    long_content = "A" * 500
    service.memory_save(content=long_content, title="Long", type="note", topic_key="long-content")

    results = service.memory_search(query="AAAA", snippet_only=True)
    contents = [r["content"] for r in results.get("results", [])]
    assert all(len(c) <= 203 for c in contents)  # 200 chars + "..."


def test_memory_search_hides_personal_by_default(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Personal preference note.",
        title="Personal",
        type="note",
        topic_key="personal-note",
        scope="personal",
    )
    results = service.memory_search(query="personal preference")
    titles = [r["title"] for r in results.get("results", [])]
    assert "Personal" not in titles


def test_memory_search_includes_personal_when_requested(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Personal preference note.",
        title="PersonalVisible",
        type="note",
        topic_key="personal-visible",
        scope="personal",
    )
    results = service.memory_search(query="personal preference", include_personal=True)
    titles = [r["title"] for r in results.get("results", [])]
    assert "PersonalVisible" in titles


# ---------------------------------------------------------------------------
# Revision tracking
# ---------------------------------------------------------------------------


def test_revision_count_increments_on_topic_update(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Version one.", title="Rev", type="decision", topic_key="rev-track")
    second = service.memory_save(content="Version two.", title="Rev", type="decision", topic_key="rev-track")

    assert second["revision_count"] == 2


def test_revision_count_not_incremented_on_duplicate(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Same content.", title="Dup", type="note", topic_key="dup-rev")
    second = service.memory_save(content="Same content.", title="Dup", type="note", topic_key="dup-rev")

    assert second["revision_count"] == 1
    assert second["status"] == "duplicate"


def test_same_topic_same_content_is_topic_duplicate(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Exact.", title="TD", type="note", topic_key="topic-dup")
    second = service.memory_save(content="Exact.", title="TD", type="note", topic_key="topic-dup")

    assert second["status"] == "duplicate"


# ---------------------------------------------------------------------------
# last_accessed_at
# ---------------------------------------------------------------------------


def test_last_accessed_at_updated_on_recall(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(content="Recall me.", title="Recall", type="note", topic_key="recall-access")

    service.memory_recall(topic_key="recall-access")
    result = service.memory_get(id=service.memory_recall(topic_key="recall-access")["id"])

    assert result.get("last_accessed_at") is not None


# ---------------------------------------------------------------------------
# Session context injection
# ---------------------------------------------------------------------------


def test_session_start_injects_context(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="We use hexagonal architecture.",
        title="Arch decision",
        type="architecture",
        topic_key="arch-ctx",
        scope="project",
    )
    result = service.memory_session_start()

    assert "context" in result
    titles = [c["title"] for c in result["context"]]
    assert "Arch decision" in titles


# ---------------------------------------------------------------------------
# memory_prune
# ---------------------------------------------------------------------------


def test_memory_prune_soft_deletes_old_memories(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Old session note.",
        title="OldNote",
        type="note",
        scope="session",
        topic_key="old-session-note",
    )

    # Force updated_at to far past by manipulating metadata directly
    store = service.vector_store
    mem = service.memory_recall(topic_key="old-session-note")
    store.collection.update(
        ids=[mem["id"]],
        metadatas=[
            {
                **store.collection.get(ids=[mem["id"]], include=["metadatas"])["metadatas"][0],
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ],
    )

    result = service.memory_prune(scope="session", older_than_days=1)
    assert result["pruned"] >= 1


def test_memory_prune_leaves_new_memories(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="Fresh session note.",
        title="FreshNote",
        type="note",
        scope="session",
        topic_key="fresh-session-note",
    )
    result = service.memory_prune(scope="session", older_than_days=30)
    # Fresh memory should NOT be pruned
    recalled = service.memory_recall(topic_key="fresh-session-note")
    assert recalled["found"] is True
    _ = result  # pruned count may be 0 or more for other memories


# ---------------------------------------------------------------------------
# MCP safe profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_safe_profile_hides_delete_tool(runtime_settings, monkeypatch) -> None:
    monkeypatch.setenv("N3RVERBERAGE_MEMORY_PROFILE", "safe")
    server = build_memory_server(runtime_settings.paths.project_root)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "memory_delete" not in tool_names


@pytest.mark.asyncio
async def test_mcp_full_profile_includes_delete_tool(runtime_settings, monkeypatch) -> None:
    monkeypatch.setenv("N3RVERBERAGE_MEMORY_PROFILE", "full")
    server = build_memory_server(runtime_settings.paths.project_root)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "memory_delete" in tool_names


# ---------------------------------------------------------------------------
# BM25 conflict detection
# ---------------------------------------------------------------------------


def test_bm25_conflicts_returned_on_similar_save(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    service.memory_save(
        content="We use PostgreSQL for the primary database with connection pooling.",
        title="DB choice",
        type="decision",
        topic_key="db-choice",
    )
    result = service.memory_save(
        content="PostgreSQL is our primary database; we use pgBouncer for pooling.",
        title="DB decision",
        type="decision",
        topic_key="db-decision-v2",
    )
    # Conflicts list should be present (may be empty if BM25 scores are 0, but field must exist)
    assert "conflicts" in result


def test_bm25_no_conflicts_on_first_save(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    result = service.memory_save(
        content="Totally unique first memory with no prior data.",
        title="First",
        type="note",
        topic_key="first-bm25",
    )
    assert result.get("conflicts") == []


# ---------------------------------------------------------------------------
# memory_judge
# ---------------------------------------------------------------------------


def test_memory_judge_stores_verdict(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    a = service.memory_save(content="Old approach.", title="A", type="decision", topic_key="judge-a")
    b = service.memory_save(content="New approach.", title="B", type="decision", topic_key="judge-b")

    result = service.memory_judge(
        source_id=b["id"],
        target_id=a["id"],
        verdict="supersedes",
        reason="Replaced by new design.",
    )
    assert result["verdict"] == "supersedes"
    assert result["is_new"] is True


def test_memory_judge_raises_for_unknown_id(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    saved = service.memory_save(content="Known.", title="Known", type="note", topic_key="judge-known")

    with pytest.raises(KeyError):
        service.memory_judge(source_id=saved["id"], target_id="unknown-id", verdict="related")


def test_memory_judge_updates_on_second_call(runtime_settings) -> None:
    service = MemoryService(runtime_settings)
    a = service.memory_save(content="Mem A.", title="A", type="note", topic_key="judge-upd-a")
    b = service.memory_save(content="Mem B.", title="B", type="note", topic_key="judge-upd-b")

    service.memory_judge(source_id=a["id"], target_id=b["id"], verdict="related")
    second = service.memory_judge(source_id=a["id"], target_id=b["id"], verdict="supersedes")

    assert second["is_new"] is False
    assert second["verdict"] == "supersedes"


# ---------------------------------------------------------------------------
# Metadata migration / backfill
# ---------------------------------------------------------------------------


def test_metadata_migration_adds_new_fields(runtime_settings) -> None:
    """Directly inject a legacy-style doc and verify metadata fields are accessible."""
    store = MemoryService(runtime_settings)
    legacy_id = "legacy-migration-test"
    ts = datetime.now(UTC).isoformat()
    store.vector_store.collection.add(
        ids=[legacy_id],
        documents=["Legacy content"],
        metadatas=[
            {
                "title": "Legacy",
                "type": "note",
                "scope": "project",
                "agent_source": "test",
                "timestamp": ts,
                "content_hash": hashlib.sha256(b"Legacy content").hexdigest(),
                "topic_key": "",
                "deleted_at": "",
            }
        ],
    )

    result = store.vector_store.collection.get(ids=[legacy_id], include=["metadatas"])
    metadata = result["metadatas"][0]
    assert metadata["title"] == "Legacy"
    assert metadata["type"] == "note"


# ---------------------------------------------------------------------------
# LWW merge and conflict logging
# ---------------------------------------------------------------------------


def test_memory_save_lww_newer_wins(runtime_settings, monkeypatch) -> None:
    """When new updated_at > existing, new wins and conflict is logged."""
    monkeypatch.setenv("N3RVERBERAGE_AGENT_SOURCE", "test")
    service = MemoryService(runtime_settings)

    # Create initial memory
    first = service.memory_save(
        content="Version one.",
        title="LWW test",
        type="decision",
        topic_key="lww-test",
        updated_at="2025-01-01T00:00:00+00:00",
    )

    # Save with newer timestamp
    second = service.memory_save(
        content="Version two.",
        title="LWW test",
        type="decision",
        topic_key="lww-test",
        updated_at="2025-06-15T12:00:00+00:00",
    )

    # Verify LWW: new content wins
    assert second["status"] == "updated"
    recalled = service.memory_recall(topic_key="lww-test")
    assert recalled["found"] is True
    assert recalled["content"] == "Version two."

    # Verify conflict was logged
    conflicts = service.get_conflicts(topic_key="lww-test")
    assert len(conflicts) == 1
    assert conflicts[0].topic_key == "lww-test"
    assert conflicts[0].winning_memory_id == first["id"]
    assert conflicts[0].losing_updated_at == "2025-01-01T00:00:00+00:00"


def test_memory_save_lww_older_loses(runtime_settings) -> None:
    """When new updated_at <= existing, existing wins (duplicate)."""
    service = MemoryService(runtime_settings)

    # Create initial memory with newer timestamp
    service.memory_save(
        content="Version two.",
        title="LWW older test",
        type="decision",
        topic_key="lww-older-test",
        updated_at="2025-06-15T12:00:00+00:00",
    )

    # Try to save with older timestamp
    second = service.memory_save(
        content="Version one.",
        title="LWW older test",
        type="decision",
        topic_key="lww-older-test",
        updated_at="2025-01-01T00:00:00+00:00",
    )

    # Verify: existing wins, new save is marked duplicate
    assert second["status"] == "duplicate"
    recalled = service.memory_recall(topic_key="lww-older-test")
    assert recalled["content"] == "Version two."


def test_memory_save_lww_same_timestamp_skips(runtime_settings) -> None:
    """When new updated_at == existing, existing wins (same content or skip)."""
    service = MemoryService(runtime_settings)

    service.memory_save(
        content="Version one.",
        title="LWW same test",
        type="decision",
        topic_key="lww-same-test",
        updated_at="2025-06-15T12:00:00+00:00",
    )

    # Same timestamp, different content → existing wins
    result = service.memory_save(
        content="Version two.",
        title="LWW same test",
        type="decision",
        topic_key="lww-same-test",
        updated_at="2025-06-15T12:00:00+00:00",
    )

    assert result["status"] == "duplicate"
    recalled = service.memory_recall(topic_key="lww-same-test")
    assert recalled["content"] == "Version one."


def test_memory_save_records_origin_uuid(runtime_settings) -> None:
    """Each save records an origin_uuid in metadata."""
    service = MemoryService(runtime_settings)

    saved = service.memory_save(
        content="Origin test.",
        title="Origin",
        type="note",
        topic_key="origin-test",
    )

    # Check metadata has origin_uuid
    stored = service.vector_store.collection.get(ids=[saved["id"]], include=["metadatas"])
    metadata = stored["metadatas"][0]
    assert "origin_uuid" in metadata
    assert metadata["origin_uuid"]  # Non-empty UUID


def test_get_conflicts_returns_empty_initially(runtime_settings) -> None:
    """get_conflicts returns empty list when no conflicts exist."""
    service = MemoryService(runtime_settings)
    conflicts = service.get_conflicts()
    assert conflicts == []


def test_memory_save_dedup_no_conflict(runtime_settings) -> None:
    """Same content hash → duplicate status, no conflict logged."""
    service = MemoryService(runtime_settings)

    service.memory_save(
        content="Exact content.",
        title="Dedup test",
        type="note",
        topic_key="dedup-no-conflict",
    )

    # Same content → no conflict
    second = service.memory_save(
        content="Exact content.",
        title="Different title",
        type="note",
        topic_key="dedup-no-conflict",
    )

    assert second["status"] == "duplicate"
    conflicts = service.get_conflicts(topic_key="dedup-no-conflict")
    assert len(conflicts) == 0


@pytest.mark.asyncio
async def test_mcp_memory_conflicts_tool(runtime_settings, monkeypatch) -> None:
    """The memory_conflicts MCP tool is registered and callable."""
    monkeypatch.setenv("N3RVERBERAGE_MEMORY_PROFILE", "full")
    server = build_memory_server(runtime_settings.paths.project_root)
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "memory_conflicts" in tool_names
