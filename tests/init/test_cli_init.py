"""Integration tests for CLI."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from n3rv.cli import app

runner = CliRunner()


def test_init_command_creates_files(tmp_path: Path):
    """Test n3rv init creates files in temporary directory."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clitest"')

    result = runner.invoke(app, ["init", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert (tmp_path / ".n3rv/a2a-config.yaml").exists()
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "opencode.json").exists()
    assert (tmp_path / ".githooks/pre-push").exists()


def test_init_does_not_redeclare_n3rv_mcp(tmp_path: Path):
    """Test init leaves n3rv MCP servers to the user's global config.

    Redeclaring them here with bare commands overrode the working global
    entries with unresolvable mise shims, breaking n3rv-memory and n3rv-hub.
    """
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clitest"')

    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0

    ocode = json.loads((tmp_path / "opencode.json").read_text())
    assert "n3rv-memory" not in ocode.get("mcp", {})
    assert "n3rv-hub" not in ocode.get("mcp", {})


def test_init_creates_systemd_unit(tmp_path: Path):
    """Test init creates systemd unit file."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clitest"')

    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0

    unit_path = tmp_path / ".n3rv" / "systemd" / "n3rv-hub.service"
    assert unit_path.exists()
    content = unit_path.read_text()
    assert "N3RV A2A Hub for" in content
    n3rv_binary = shutil.which("n3rv")
    assert n3rv_binary is not None, "n3rv binary not found in PATH"
    assert f"ExecStart={n3rv_binary} hub start" in content
    assert "Restart=on-failure" in content


def test_init_mentions_daemon_setup(tmp_path: Path):
    """Test init output references daemon setup."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "clitest"')

    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert "n3rv daemon install" in result.stdout


def test_daemon_help_works():
    """Test daemon commands are registered."""
    result = runner.invoke(app, ["daemon", "--help"])
    assert result.exit_code == 0
    assert "Manage n3rv hub daemon" in result.stdout
    assert "install" in result.stdout
    assert "start" in result.stdout
    assert "stop" in result.stdout
    assert "status" in result.stdout
    assert "enable" in result.stdout
    assert "logs" in result.stdout
