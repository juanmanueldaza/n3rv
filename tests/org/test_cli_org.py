"""Tests for n3rverberage org CLI scaffold."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from n3rverberage.cli import app
from n3rverberage.org import ORG_CONFIG_FILENAME, OrgConfig


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.compile(r"\x1b\[[0-9;]*[a-zA-Z]").sub("", text)


runner = CliRunner()


class TestOrgCliGroup:
    def test_org_group_exists(self) -> None:
        result = runner.invoke(app, ["org", "--help"])
        assert result.exit_code == 0
        assert "Manage reverberage org workspace" in result.stdout

    def test_org_init_in_help(self) -> None:
        result = runner.invoke(app, ["org", "--help"])
        assert "init" in result.stdout

    def test_org_add_satellite_in_help(self) -> None:
        result = runner.invoke(app, ["org", "--help"])
        assert "add-satellite" in result.stdout

    def test_org_sync_in_help(self) -> None:
        result = runner.invoke(app, ["org", "--help"])
        assert "sync" in result.stdout

    def test_org_init_help(self) -> None:
        result = runner.invoke(app, ["org", "init", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--org-name" in out
        assert "--root" in out
        assert "--force" in out

    def test_org_add_satellite_help(self) -> None:
        result = runner.invoke(app, ["org", "add-satellite", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "name" in out
        assert "--description" in out

    def test_org_sync_help(self) -> None:
        result = runner.invoke(app, ["org", "sync", "--help"])
        assert result.exit_code == 0
        out = _strip_ansi(result.stdout)
        assert "--dry-run" in out
        assert "--only" in out


class TestOrgInitCli:
    def test_init_creates_config(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        assert result.exit_code == 0
        config_path = tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME
        assert config_path.exists()
        assert "Org initialized" in result.stdout

    def test_init_creates_shared_skills_dir(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        shared_dir = tmp_path / ".opencode" / "shared" / "skills"
        assert shared_dir.is_dir()
        assert (shared_dir / "README.md").exists()

    def test_init_errors_if_already_exists(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        result = runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        assert result.exit_code == 1
        assert "already initialized" in result.stdout.lower()

    def test_init_force_overwrites(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        result = runner.invoke(app, ["org", "init", "--root", str(tmp_path), "--force"])
        assert result.exit_code == 0
        assert "Org initialized" in result.stdout

    def test_init_custom_org_name(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path), "--org-name", "myorg"])
        config = OrgConfig.from_yaml(tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME)
        assert config.org_name == "myorg"


class TestOrgAddSatelliteCli:
    def test_errors_without_org_config(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["org", "add-satellite", "test-sat", "--root", str(tmp_path)])
        assert result.exit_code == 1
        assert "org init" in result.stdout.lower()

    def test_errors_on_duplicate_name(self, tmp_path: Path) -> None:
        from n3rverberage.org import OrgProject

        # Init org and pre-register a satellite
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        config = OrgConfig.from_yaml(tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME)
        config.projects.append(OrgProject(name="test-sat", path=Path("test-sat"), type="satellite"))
        config.to_yaml(tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME)

        result = runner.invoke(
            app,
            ["org", "add-satellite", "test-sat", "--root", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "already registered" in result.stdout.lower()

    def test_errors_without_gh(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        with patch("shutil.which", return_value=None):
            result = runner.invoke(
                app,
                ["org", "add-satellite", "test-sat", "--root", str(tmp_path)],
            )
        assert result.exit_code == 1
        assert "gh CLI" in result.stdout


class TestOrgSyncCli:
    def test_errors_without_org_config(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["org", "sync", "--root", str(tmp_path)])
        assert result.exit_code == 1
        assert "org init" in result.stdout.lower()

    def test_empty_org(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        result = runner.invoke(app, ["org", "sync", "--root", str(tmp_path)])
        assert result.exit_code == 0
        assert "No satellites" in result.stdout

    def test_dry_run_with_satellite(self, tmp_path: Path) -> None:
        runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        # Manually add a satellite entry to config
        config = OrgConfig.from_yaml(tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME)
        from n3rverberage.org import OrgProject

        sat_path = tmp_path / "satellites" / "test-sat"
        sat_path.mkdir(parents=True)
        config.projects.append(OrgProject(name="test-sat", path=Path("satellites/test-sat"), type="satellite"))
        config.to_yaml(tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME)

        result = runner.invoke(app, ["org", "sync", "--root", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        assert "test-sat" in result.stdout
        assert "dry-run" in result.stdout.lower()
