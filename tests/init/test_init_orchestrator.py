"""Tests for init orchestrator."""

from __future__ import annotations

import subprocess
from pathlib import Path

from n3rv.init import run_init


def test_init_in_empty_project_creates_all_files(tmp_path: Path):
    """Test full init creates all expected files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=False)

    assert exit_code == 0

    expected_files = [
        ".n3rv/a2a-config.yaml",
        "AGENTS.md",
        "opencode.json",
        ".githooks/pre-push",
        ".opencode/skills/code/SKILL.md",
        ".opencode/skills/testing/SKILL.md",
        ".opencode/skills/commits/SKILL.md",
        ".opencode/commands/sdd-new.md",
        ".opencode/agents/sdd-explorer.md",
    ]

    for file_path in expected_files:
        assert (tmp_path / file_path).exists(), f"Missing file: {file_path}"


def test_init_rerun_without_force_skips_files(tmp_path: Path):
    """Test re-running init without force skips existing files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=False)

    config = tmp_path / ".n3rv/a2a-config.yaml"
    original_content = config.read_text()
    config.write_text("# Modified\n" + original_content)

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=False)

    assert exit_code == 0
    assert "# Modified" in config.read_text()


def test_init_with_force_overwrites_files(tmp_path: Path):
    """Test init with force overwrites existing files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=False)

    ocode = tmp_path / "opencode.json"
    ocode.write_text('{"modified": true}')

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=True)

    assert exit_code == 0
    assert '{"modified"' not in ocode.read_text()


def test_init_with_explicit_project_name_and_stack(tmp_path: Path):
    """Test init with explicit project name and stack override."""
    exit_code = run_init(
        tmp_path,
        project_name="myapp",
        stack_override="go",
        force=False,
    )

    assert exit_code == 0

    config = tmp_path / ".n3rv/a2a-config.yaml"
    content = config.read_text()
    assert "project: myapp" in content
    assert "port: 19820" in content

    agents_md = tmp_path / "AGENTS.md"
    assert "**Stack**: go" in agents_md.read_text()


def test_init_updates_marker_files_idempotently(tmp_path: Path):
    """Test that marker-based files are updated idempotently."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=False)

    agents_md = tmp_path / "AGENTS.md"
    original = agents_md.read_text()
    agents_md.write_text("# My Project\n\n" + original + "\n## My Section\n")

    run_init(tmp_path, project_name=None, stack_override=None, force=False)

    content = agents_md.read_text()
    assert "# My Project" in content
    assert "## My Section" in content


def test_init_without_git_repo_logs_warning(tmp_path: Path, capfd):
    """Test init without .git directory logs warning but continues."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=False)

    assert exit_code == 0
    assert (tmp_path / ".githooks/pre-push").exists()


def test_init_with_git_repo_configures_hooks(tmp_path: Path):
    """Test init with git repo configures core.hooksPath."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=False)

    assert exit_code == 0

    result = subprocess.run(
        ["git", "config", "core.hooksPath"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == ".githooks"


def test_hooks_are_executable(tmp_path: Path):
    """Test that git hooks are created with executable permissions."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=False)

    import os

    pre_push = tmp_path / ".githooks/pre-push"

    assert os.access(pre_push, os.X_OK)
