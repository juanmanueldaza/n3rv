"""Tests for file writing with conflict resolution."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from n3rverberage.init.writer import (
    GITIGNORE_SECTION_HEADER,
    MARKER_END,
    MARKER_START,
    WriteResult,
    configure_git_hooks,
    configure_gitignore,
    write_file,
)

GITIGNORE_PATTERNS = [
    ".n3rverberage/",
    ".opencode/",
    ".githooks/",
    "AGENTS.md",
    "opencode.json",
]


def test_write_new_file_creates_file(tmp_path: Path):
    """Test writing a new file returns CREATED."""
    target = tmp_path / "test.txt"
    result = write_file(target, "content", force=False)

    assert result == WriteResult.CREATED
    assert target.exists()
    assert target.read_text() == "content"


def test_skip_existing_file_without_force(tmp_path: Path):
    """Test existing file is skipped without force flag."""
    target = tmp_path / "test.txt"
    target.write_text("original")

    result = write_file(target, "new content", force=False)

    assert result == WriteResult.SKIPPED
    assert target.read_text() == "original"


def test_overwrite_existing_file_with_force(tmp_path: Path):
    """Test existing file is overwritten with force flag."""
    target = tmp_path / "test.txt"
    target.write_text("original")

    result = write_file(target, "new content", force=True)

    assert result == WriteResult.OVERWRITTEN
    assert target.read_text() == "new content"


def test_marker_injection_replaces_between_markers(tmp_path: Path):
    """Test marker-based injection replaces content between markers."""
    target = tmp_path / "doc.md"
    target.write_text(f"""# User Content

{MARKER_START}
Old n3rverberage section
{MARKER_END}

More user content""")

    result = write_file(target, "New n3rverberage section", force=False, use_markers=True)

    assert result == WriteResult.UPDATED
    content = target.read_text()
    assert "User Content" in content
    assert "New n3rverberage section" in content
    assert "Old n3rverberage section" not in content
    assert "More user content" in content


def test_marker_injection_without_markers_and_force(tmp_path: Path):
    """Test marker injection on file without markers with force overwrites."""
    target = tmp_path / "doc.md"
    target.write_text("Original user content")

    result = write_file(target, "New section", force=True, use_markers=True)

    assert result == WriteResult.OVERWRITTEN
    content = target.read_text()
    assert MARKER_START in content
    assert "New section" in content
    assert MARKER_END in content


def test_marker_injection_without_markers_no_force_skips(tmp_path: Path):
    """Test marker injection on file without markers without force skips."""
    target = tmp_path / "doc.md"
    target.write_text("Original user content")

    result = write_file(target, "New section", force=False, use_markers=True)

    assert result == WriteResult.SKIPPED
    assert target.read_text() == "Original user content"


def test_marker_injection_creates_new_file_with_markers(tmp_path: Path):
    """Test marker injection on new file wraps content with markers."""
    target = tmp_path / "doc.md"

    result = write_file(target, "Section content", force=False, use_markers=True)

    assert result == WriteResult.CREATED
    content = target.read_text()
    assert MARKER_START in content
    assert "Section content" in content
    assert MARKER_END in content


def test_marker_idempotence(tmp_path: Path):
    """Test marker-based writes are idempotent."""
    target = tmp_path / "doc.md"
    content = "Section content"

    # First write
    write_file(target, content, force=False, use_markers=True)
    first_result = target.read_text()

    # Second write with same content
    write_file(target, content, force=False, use_markers=True)
    second_result = target.read_text()

    assert first_result == second_result


def test_make_executable_sets_permissions(tmp_path: Path):
    """Test make_executable flag sets file as executable."""
    target = tmp_path / "script.sh"

    write_file(target, "#!/bin/bash\necho hi", force=False, make_executable=True)

    assert target.exists()
    # Check if executable bit is set
    assert os.access(target, os.X_OK)


def test_write_creates_parent_directories(tmp_path: Path):
    """Test writing file creates missing parent directories."""
    target = tmp_path / "nested" / "dir" / "file.txt"

    result = write_file(target, "content", force=False)

    assert result == WriteResult.CREATED
    assert target.exists()
    assert target.read_text() == "content"


def test_configure_git_hooks_with_git_repo(tmp_path: Path):
    """Test git hooks configuration in a git repository."""
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = configure_git_hooks(tmp_path)

    assert result is True
    # Verify git config was set
    config_result = subprocess.run(
        ["git", "config", "core.hooksPath"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert config_result.stdout.strip() == ".githooks"


def test_configure_git_hooks_without_git_repo(tmp_path: Path):
    """Test git hooks configuration without .git directory returns False."""
    result = configure_git_hooks(tmp_path)
    assert result is False


def test_configure_gitignore_adds_all_patterns_to_new_gitignore(tmp_path: Path):
    """Test all n3rverberage patterns are in .gitignore after configure."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    result = configure_gitignore(tmp_path)

    assert result is True
    gitignore = tmp_path / ".gitignore"
    content = gitignore.read_text()
    assert GITIGNORE_SECTION_HEADER in content
    for pattern in GITIGNORE_PATTERNS:
        assert pattern in content, f"Missing pattern: {pattern}"


def test_configure_gitignore_skips_if_section_header_present(tmp_path: Path):
    """Test idempotence when section header is already in .gitignore."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(f"__pycache__/\n{GITIGNORE_SECTION_HEADER}\n.n3rverberage/\n")

    result = configure_gitignore(tmp_path)

    assert result is False
    content = gitignore.read_text()
    assert GITIGNORE_SECTION_HEADER in content
    assert "__pycache__/" in content


def test_configure_gitignore_appends_section_to_existing(tmp_path: Path):
    """Test section is appended to existing .gitignore that lacks it."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n*.pyc\n")

    result = configure_gitignore(tmp_path)

    assert result is True
    content = gitignore.read_text()
    assert GITIGNORE_SECTION_HEADER in content
    assert "__pycache__/" in content  # original preserved
    for pattern in GITIGNORE_PATTERNS:
        assert pattern in content, f"Missing pattern: {pattern}"


def test_configure_gitignore_without_git_repo(tmp_path: Path):
    """Test returns False when no .git directory exists."""
    result = configure_gitignore(tmp_path)
    assert result is False


def test_configure_gitignore_migration_from_old_format(tmp_path: Path):
    """Test that old .n3rverberage/ entry is replaced by full section."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n.n3rverberage/\n")

    result = configure_gitignore(tmp_path)

    # Should add the full section (old .n3rverberage/ line stays, section appended)
    assert result is True
    content = gitignore.read_text()
    assert GITIGNORE_SECTION_HEADER in content
    for pattern in GITIGNORE_PATTERNS:
        assert pattern in content, f"Missing pattern: {pattern}"
