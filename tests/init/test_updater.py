"""Tests for update orchestrator and utilities.

Covers run_update() integration, deep_merge_json(), validate_markers(),
and update strategies.
"""

from pathlib import Path

from n3rv.init.update import (
    FILE_UPDATE_MANIFEST,
    UpdateEntry,
    UpdateResult,
    UpdateStrategy,
    UpdateSummary,
    _handle_create_if_missing,
    deep_merge_json,
)
from n3rv.init.writer import MARKER_END, MARKER_START, validate_markers


def test_validate_markers_clean_content_returns_empty():
    """Test clean balanced markers return no warnings."""
    content = f"before\n{MARKER_START}\nstuff\n{MARKER_END}\nafter"
    assert validate_markers(content) == []


def test_validate_markers_no_markers_returns_empty():
    """Test content with no markers returns no warnings."""
    assert validate_markers("no markers here") == []


def test_validate_markers_mismatched_returns_warning():
    """Test mismatched markers return warning."""
    content = f"{MARKER_START}\nno end marker"
    warnings = validate_markers(content)
    assert len(warnings) == 1
    assert "Mismatched" in warnings[0]


def test_validate_markers_multiple_pairs_returns_warning():
    """Test multiple marker pairs return warning."""
    content = f"{MARKER_START}\na\n{MARKER_END}\n{MARKER_START}\nb\n{MARKER_END}"
    warnings = validate_markers(content)
    assert len(warnings) == 1
    assert "Multiple" in warnings[0]


def test_deep_merge_preserves_user_only_keys():
    """Test merge preserves user keys not in overlay."""
    base = {"user_key": "user_value", "shared": "old"}
    overlay = {"shared": "new", "n3rv_key": "inv_value"}
    result = deep_merge_json(base, overlay)
    assert result["user_key"] == "user_value"
    assert result["shared"] == "new"
    assert result["n3rv_key"] == "inv_value"


def test_deep_merge_recursive_nested_dicts():
    """Test merge handles nested dicts recursively."""
    base = {"permissions": {"allow": ["user_tool"], "deny": []}}
    overlay = {"permissions": {"allow": ["inv_tool"], "extra": True}}
    result = deep_merge_json(base, overlay)
    assert result["permissions"]["allow"] == ["inv_tool"]
    assert result["permissions"]["deny"] == []
    assert result["permissions"]["extra"] is True


def test_deep_merge_empty_base():
    """Test merge with empty base returns overlay."""
    result = deep_merge_json({}, {"key": "value"})
    assert result == {"key": "value"}


def test_deep_merge_empty_overlay():
    """Test merge with empty overlay preserves base."""
    result = deep_merge_json({"key": "value"}, {})
    assert result == {"key": "value"}


def test_manifest_has_expected_entries():
    """Test manifest has expected number of entries."""
    assert len(FILE_UPDATE_MANIFEST) == 38


def test_manifest_marker_files():
    """Test marker merge files are correctly identified."""
    marker_files = [e for e in FILE_UPDATE_MANIFEST if e.strategy == UpdateStrategy.MARKER_MERGE]
    assert len(marker_files) == 1  # AGENTS.md is marker_merge


def test_manifest_json_merge_files():
    """Test JSON merge files are correctly identified."""
    json_files = [e for e in FILE_UPDATE_MANIFEST if e.strategy == UpdateStrategy.JSON_MERGE]
    paths = {e.output_path for e in json_files}
    assert "opencode.json" in paths
    assert ".opencode/package.json" in paths
    assert len(json_files) == 2


def test_manifest_overwrite_files():
    """Test overwrite files include infrastructure files."""
    ow_files = [e for e in FILE_UPDATE_MANIFEST if e.strategy == UpdateStrategy.OVERWRITE]
    paths = {e.output_path for e in ow_files}
    assert ".n3rv/a2a-config.yaml" in paths
    assert ".opencode/plugins/n3rv-lifecycle.js" in paths
    assert ".opencode/plugins/n3rv-shell-env.js" in paths
    assert ".opencode/tools/n3rv-stats.ts" in paths
    assert len(ow_files) == 6


def test_manifest_skip_default_files_are_commands():
    """Test skip default files are SDD skills, commands, and agents."""
    skip_files = [e for e in FILE_UPDATE_MANIFEST if e.strategy == UpdateStrategy.SKIP_DEFAULT]
    assert len(skip_files) == 28
    paths = {e.output_path for e in skip_files}
    assert ".opencode/skills/code/SKILL.md" in paths
    assert ".opencode/skills/testing/SKILL.md" in paths
    assert ".opencode/skills/commits/SKILL.md" in paths
    assert ".opencode/skills/sdd-explore/SKILL.md" in paths
    assert ".opencode/skills/judgment-day/SKILL.md" in paths
    assert ".opencode/commands/sdd-new.md" in paths
    assert ".opencode/agents/sdd-explorer.md" in paths


def test_manifest_git_hooks_are_executable():
    """Test git hooks have executable flag."""
    hook_files = [e for e in FILE_UPDATE_MANIFEST if "githooks" in e.template_name]
    assert all(e.make_executable for e in hook_files)


def test_manifest_create_if_missing_files():
    """Test create-if-missing files — shared/rpc.js is the only one."""
    cim_files = [e for e in FILE_UPDATE_MANIFEST if e.strategy == UpdateStrategy.CREATE_IF_MISSING]
    assert len(cim_files) == 1
    assert cim_files[0].output_path == ".opencode/shared/rpc.js"


def test_update_summary_counts_correctly():
    """Test UpdateSummary counts results correctly."""
    summary = UpdateSummary(
        results=[
            UpdateResult("AGENTS.md", UpdateStrategy.MARKER_MERGE, "UPDATED"),
            UpdateResult("opencode.json", UpdateStrategy.JSON_MERGE, "SKIPPED"),
            UpdateResult(".githooks/pre-push", UpdateStrategy.OVERWRITE, "OVERWRITTEN"),
            UpdateResult(".opencode/skills/code/SKILL.md", UpdateStrategy.SKIP_DEFAULT, "SKIPPED"),
        ]
    )
    assert summary.updated_count == 2  # UPDATED + OVERWRITTEN
    assert summary.skipped_count == 2
    assert summary.error_count == 0


def test_create_if_missing_creates_when_absent(tmp_path: Path):
    """Test create-if-missing creates file when it does not exist."""
    target = tmp_path / "AGENTS.md"
    entry = UpdateEntry("opencode/AGENTS.md.j2", "AGENTS.md", UpdateStrategy.CREATE_IF_MISSING)

    result = _handle_create_if_missing(entry, target, "# content", dry_run=False)

    assert result.result == "CREATED"
    assert target.exists()
    assert target.read_text() == "# content"


def test_create_if_missing_skips_when_present(tmp_path: Path):
    """Test create-if-missing skips file when it already exists."""
    target = tmp_path / "AGENTS.md"
    target.write_text("# user customized content")
    entry = UpdateEntry("opencode/AGENTS.md.j2", "AGENTS.md", UpdateStrategy.CREATE_IF_MISSING)

    result = _handle_create_if_missing(entry, target, "# new content", dry_run=False)

    assert result.result == "SKIPPED"
    assert target.read_text() == "# user customized content"


def test_create_if_missing_dry_run_reports_created(tmp_path: Path):
    """Test create-if-missing dry run reports CREATED without writing."""
    target = tmp_path / "AGENTS.md"
    entry = UpdateEntry("opencode/AGENTS.md.j2", "AGENTS.md", UpdateStrategy.CREATE_IF_MISSING)

    result = _handle_create_if_missing(entry, target, "# content", dry_run=True)

    assert result.result == "CREATED"
    assert not target.exists()
