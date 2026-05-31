"""Writer utilities for project scaffolding."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger("n3rv.init.writer")

MARKER_START = "# >>> N3RV-MARKER-START"
MARKER_END = "# >>> N3RV-MARKER-END"


class WriteResult(StrEnum):
    """Result of a write operation."""

    CREATED = "created"
    UPDATED = "updated"
    OVERWRITTEN = "overwritten"
    SKIPPED = "skipped"


def write_file(
    target: Path,
    content: str,
    *,
    force: bool = False,
    use_markers: bool = False,
    make_executable: bool = False,
) -> WriteResult:
    """Write content to target file.

    Args:
        target: Path to write to
        content: File content
        force: Overwrite existing files without checking markers
        use_markers: Check for MARKER_START/END markers before overwriting
        make_executable: chmod +x the file

    Returns:
        WriteResult indicating what happened
    """
    from n3rv.init.update import MARKER_END, MARKER_START

    if target.exists() and not force:
        if use_markers:
            existing = target.read_text(encoding="utf-8")
            if MARKER_START in existing and MARKER_END in existing:
                start_idx = existing.find(MARKER_START)
                end_idx = existing.find(MARKER_END) + len(MARKER_END)
                before = existing[:start_idx]
                after = existing[end_idx:]
                new_content = f"{before}{MARKER_START}\n{content}\n{MARKER_END}{after}"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_content, encoding="utf-8")
                return WriteResult.UPDATED
            return WriteResult.SKIPPED
        return WriteResult.SKIPPED

    existed = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)

    if use_markers and (not existed or force):
        content = f"{MARKER_START}\n{content}\n{MARKER_END}\n"

    target.write_text(content, encoding="utf-8")
    if make_executable:
        target.chmod(0o755)
    return WriteResult.OVERWRITTEN if existed else WriteResult.CREATED


def configure_git_hooks(root: Path) -> bool:
    """Configure git hooks for the project.

    Args:
        root: Project root directory

    Returns:
        True if hooks were configured, False otherwise
    """
    import subprocess

    git_dir = root / ".git"
    if not git_dir.is_dir():
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Create pre-push hook that delegates to .n3rv/githooks/
    pre_push = hooks_dir / "pre-push"
    pre_push.write_text(
        "#!/bin/sh\n# N3RV pre-push hook\nexec .n3rv/githooks/pre-push\n",
        encoding="utf-8",
    )
    pre_push.chmod(0o755)

    # Create .githooks/pre-push wrapper
    githooks_dir = root / ".githooks"
    githooks_dir.mkdir(parents=True, exist_ok=True)
    wrapper = githooks_dir / "pre-push"
    if not wrapper.exists():
        wrapper.write_text(
            "#!/usr/bin/env python3\n# N3RV pre-push hook\n# Add your checks here\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

    # Set core.hooksPath to .githooks
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=root,
        capture_output=True,
    )
    return True


def validate_markers(content: str) -> list[str]:
    """Check if content has valid marker pairs.

    Args:
        content: File content to check

    Returns:
        List of warning strings (empty if no issues)
    """
    from n3rv.init.update import MARKER_END, MARKER_START

    start_count = content.count(MARKER_START)
    end_count = content.count(MARKER_END)

    warnings: list[str] = []
    if start_count != end_count:
        warnings.append(f"Mismatched markers: {start_count} start-tags vs {end_count} end-tags")
    if start_count > 1:
        warnings.append(f"Multiple marker sections ({start_count} pairs) — only first pair guaranteed")
    if start_count == 0 and end_count == 0:
        return []

    return warnings
