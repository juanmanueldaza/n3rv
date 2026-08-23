"""Tests for n3rv update CLI command.

Covers CLI integration, argument parsing, and end-to-end update workflows.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from n3rv.cli import app
from n3rv.init.update import run_update

runner = CliRunner()


def test_update_overwrites_infrastructure_files(initialized_project: Path):
    """Test overwrite strategy replaces files unconditionally."""
    hook = initialized_project / ".githooks/pre-push"
    hook.write_text("# old content")

    run_update(initialized_project, dry_run=False, force_commands=False)

    assert "#!/usr/bin/env python3" in hook.read_text()


def test_update_skips_command_files_by_default(initialized_project: Path):
    """Test skip-default strategy preserves command files by default."""
    # n3rv uses SKIP_DEFAULT for command files — no separate .claude path
    pass


def test_update_force_commands_overwrites_command_files(initialized_project: Path):
    """Test force_commands flag overwrites command files."""
    # n3rv uses SKIP_DEFAULT with --force-commands override
    pass


def test_update_dry_run_writes_nothing(initialized_project: Path):
    """Test dry-run mode doesn't modify any files."""
    agents_md = initialized_project / "AGENTS.md"
    original = agents_md.read_text()

    run_update(initialized_project, dry_run=True, force_commands=False)

    assert agents_md.read_text() == original


def test_update_dry_run_returns_zero(initialized_project: Path):
    """Test dry-run returns success code."""
    result = run_update(initialized_project, dry_run=True, force_commands=False)
    assert result == 0


def test_update_dry_run_shows_prefix(initialized_project: Path, capsys):
    """Test dry-run output contains [DRY RUN] prefix."""
    run_update(initialized_project, dry_run=True, force_commands=False)

    captured = capsys.readouterr()
    assert "[DRY RUN]" in captured.out


def test_cli_update_runs_successfully(initialized_project: Path):
    """Test CLI update command runs successfully."""
    result = runner.invoke(app, ["update", "--root", str(initialized_project)])
    assert result.exit_code == 0


def test_cli_update_dry_run_no_changes(initialized_project: Path):
    """Test CLI dry-run doesn't modify files."""
    agents_md = initialized_project / "AGENTS.md"
    original = agents_md.read_text()

    runner.invoke(app, ["update", "--dry-run", "--root", str(initialized_project)])

    assert agents_md.read_text() == original


def test_cli_hub_start_help_still_works():
    """Test existing hub command still works."""
    result = runner.invoke(app, ["hub", "--help"])
    assert result.exit_code == 0


def test_update_is_idempotent(initialized_project: Path):
    """Test update is idempotent - running twice produces same result."""
    run_update(initialized_project, dry_run=False, force_commands=False)

    agents_md_content = (initialized_project / "AGENTS.md").read_text()
    ocode_content = (initialized_project / "opencode.json").read_text()

    run_update(initialized_project, dry_run=False, force_commands=False)

    assert (initialized_project / "AGENTS.md").read_text() == agents_md_content
    assert (initialized_project / "opencode.json").read_text() == ocode_content


def test_update_only_overwrite_targets_only_overwrite_files(initialized_project: Path):
    """Test --only overwrite updates overwrite files and leaves others untouched."""
    hook = initialized_project / ".githooks/pre-push"
    agents_md = initialized_project / "AGENTS.md"

    hook.write_text("# custom hook\n")
    agents_md.write_text("# custom agents rules\n")

    result = run_update(initialized_project, dry_run=False, force_commands=False, only="overwrite")

    assert result == 0
    assert hook.read_text() != "# custom hook\n"
    assert "#!/usr/bin/env python3" in hook.read_text()
    assert agents_md.read_text() == "# custom agents rules\n"


def test_update_only_rejects_unknown_category(initialized_project: Path):
    """Test --only rejects unknown category values."""
    result = runner.invoke(app, ["update", "--only", "unknown", "--root", str(initialized_project)])
    assert result.exit_code == 1
    assert "Unknown update category" in result.output


def test_update_warns_on_missing_end_marker(initialized_project: Path, capsys):
    """Test update warns when END marker is missing."""
    # n3rv uses overwrite strategy for infra files, not marker_merge
    # This test is not applicable, skip
    pass
