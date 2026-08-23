from __future__ import annotations

from unittest.mock import Mock, patch

from typer.testing import CliRunner

from n3rv.cli import app

runner = CliRunner()


def test_memory_list_displays_filtered_memories() -> None:
    mock_service = Mock()
    mock_service.memory_context.return_value = {
        "count": 3,
        "memories": [
            {
                "id": "1234567890abcdef",
                "type": "decision",
                "scope": "project",
                "agent_source": "claude-code",
                "timestamp": "2025-01-01T00:00:00Z",
                "title": "Auth strategy",
                "content": "JWT with refresh tokens",
            },
            {
                "id": "abcdef1234567890",
                "type": "note",
                "scope": "session",
                "agent_source": "copilot-cli",
                "timestamp": "2025-01-01T00:00:00Z",
                "title": "Ignore me",
                "content": "Temporary",
            },
            {
                "id": "fedcba0987654321",
                "type": "decision",
                "scope": "project",
                "agent_source": "copilot-cli",
                "timestamp": "2025-01-01T00:00:00Z",
                "title": "Token rotation",
                "content": "Rotate refresh tokens",
            },
        ],
    }

    with (
        patch("n3rv.cli_memory.load_runtime_settings", return_value=Mock()),
        patch("n3rv.cli_memory.MemoryService", return_value=mock_service),
    ):
        result = runner.invoke(
            app,
            [
                "memory",
                "list",
                "--type",
                "decision",
                "--scope",
                "project",
                "--limit",
                "5",
            ],
        )

    assert result.exit_code == 0
    assert "Auth strategy" in result.stdout
    assert "Token rotation" in result.stdout
    assert "Ignore me" not in result.stdout
    mock_service.memory_context.assert_called_once_with(n=5)


def test_memory_list_shows_empty_message() -> None:
    mock_service = Mock()
    mock_service.memory_context.return_value = {"count": 0, "memories": []}

    with (
        patch("n3rv.cli_memory.load_runtime_settings", return_value=Mock()),
        patch("n3rv.cli_memory.MemoryService", return_value=mock_service),
    ):
        result = runner.invoke(app, ["memory", "list"])

    assert result.exit_code == 0
    assert "No memories found." in result.stdout


def test_memory_search_displays_results() -> None:
    mock_service = Mock()
    mock_service.memory_search.return_value = {
        "results": [
            {
                "score": 0.876,
                "type": "decision",
                "agent_source": "claude-code",
                "title": "Auth strategy",
                "content": "Authentication uses refresh tokens stored in secure cookies.",
            }
        ],
        "nudge": None,
    }

    with (
        patch("n3rv.cli_memory.load_runtime_settings", return_value=Mock()),
        patch("n3rv.cli_memory.MemoryService", return_value=mock_service),
    ):
        result = runner.invoke(
            app,
            [
                "memory",
                "search",
                "authentication",
                "--type",
                "decision",
                "--keyword",
                "refresh",
                "--limit",
                "3",
            ],
        )

    assert result.exit_code == 0
    assert "Auth strategy" in result.stdout
    assert "0.88" in result.stdout
    mock_service.memory_search.assert_called_once_with(
        query="authentication",
        type_filter="decision",
        keyword="refresh",
        limit=3,
    )


def test_memory_stats_displays_sections() -> None:
    mock_service = Mock()
    mock_service.memory_stats.return_value = {
        "total": 4,
        "by_type": {"decision": 2, "note": 2},
        "by_scope": {"project": 3, "session": 1, "personal": 0},
        "by_agent": {"claude-code": 3, "copilot-cli": 1},
    }

    with (
        patch("n3rv.cli_memory.load_runtime_settings", return_value=Mock()),
        patch("n3rv.cli_memory.MemoryService", return_value=mock_service),
    ):
        result = runner.invoke(app, ["memory", "stats"])

    assert result.exit_code == 0
    assert "Total memories: 4" in result.stdout
    assert "By Type" in result.stdout
    assert "By Scope" in result.stdout
    assert "By Agent" in result.stdout


def test_memory_command_handles_store_errors() -> None:
    mock_service = Mock()
    mock_service.memory_context.side_effect = RuntimeError("memory unavailable")

    with (
        patch("n3rv.cli_memory.load_runtime_settings", return_value=Mock()),
        patch("n3rv.cli_memory.MemoryService", return_value=mock_service),
    ):
        result = runner.invoke(app, ["memory", "list"])

    assert result.exit_code == 1
    assert "memory unavailable" in result.stdout
