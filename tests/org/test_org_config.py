"""Tests for OrgConfig model and org discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from n3rverberage.org import (
    ORG_CONFIG_FILENAME,
    OrgConfig,
    OrgNotFoundError,
    OrgProject,
    resolve_org_root,
)


class TestOrgProject:
    def test_default_type_is_satellite(self) -> None:
        p = OrgProject(name="test", path=Path("satellites/test"))
        assert p.type == "satellite"

    def test_hub_type(self) -> None:
        p = OrgProject(name="hub", path=Path("."), type="hub")
        assert p.type == "hub"

    def test_repo_url_optional(self) -> None:
        p = OrgProject(name="test", path=Path("."))
        assert p.repo_url is None

    def test_with_repo_url(self) -> None:
        p = OrgProject(
            name="test",
            path=Path("satellites/test"),
            repo_url="https://github.com/reverberage/test",
        )
        assert p.repo_url == "https://github.com/reverberage/test"

    def test_frozen(self) -> None:
        p = OrgProject(name="test", path=Path("."))
        with pytest.raises((TypeError, ValueError)):
            p.name = "changed"  # type: ignore[misc]


class TestOrgConfig:
    def test_default_org_name(self) -> None:
        c = OrgConfig()
        assert c.org_name == "reverberage"

    def test_empty_projects(self) -> None:
        c = OrgConfig()
        assert c.projects == []

    def test_default_config_keys(self) -> None:
        c = OrgConfig()
        assert "shared_skills_dir" in c.config
        assert "satellites_dir" in c.config

    def test_add_project(self) -> None:
        c = OrgConfig()
        p = OrgProject(name="transcriber", path=Path("satellites/transcriber"))
        c.projects.append(p)
        assert len(c.projects) == 1

    def test_duplicate_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            OrgConfig(
                projects=[
                    OrgProject(name="dup", path=Path("a")),
                    OrgProject(name="dup", path=Path("b")),
                ]
            )


class TestOrgConfigYaml:
    def test_roundtrip(self, tmp_path: Path) -> None:
        config = OrgConfig(
            org_name="reverberage",
            projects=[
                OrgProject(
                    name="transcriber",
                    path=Path("satellites/transcriber"),
                    description="Audio transcription",
                    type="satellite",
                ),
                OrgProject(
                    name="hub",
                    path=Path("."),
                    description="Control plane",
                    type="hub",
                ),
            ],
        )
        path = tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME
        config.to_yaml(path)
        assert path.exists()

        loaded = OrgConfig.from_yaml(path)
        assert loaded.org_name == "reverberage"
        assert len(loaded.projects) == 2
        assert loaded.projects[0].name == "transcriber"
        assert loaded.projects[1].type == "hub"

    def test_from_yaml_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(OrgNotFoundError):
            OrgConfig.from_yaml(tmp_path / "nonexistent.yaml")

    def test_from_yaml_invalid_not_a_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- just a list", encoding="utf-8")
        with pytest.raises(ValueError, match="expected a mapping"):
            OrgConfig.from_yaml(path)

    def test_from_yaml_invalid_syntax(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("{{{{ invalid yaml }}}}", encoding="utf-8")
        with pytest.raises((ValueError, yaml.YAMLError)):
            OrgConfig.from_yaml(path)

    def test_broken_project_path(self, tmp_path: Path) -> None:
        """Broken paths are NOT rejected at model level — they are handled during sync."""
        config = OrgConfig(
            projects=[
                OrgProject(name="missing", path=Path("does/not/exist")),
            ]
        )
        # Validation: path existence is NOT enforced on OrgProject (frozen model)
        # It's handled at sync time. So this should pass without error.
        assert len(config.projects) == 1

    def test_to_yaml_creates_parent_dirs(self, tmp_path: Path) -> None:
        config = OrgConfig(org_name="reverberage")
        path = tmp_path / "deep" / "nested" / ORG_CONFIG_FILENAME
        config.to_yaml(path)
        assert path.exists()


class TestResolveOrgRoot:
    def test_finds_config_in_current_dir(self, tmp_path: Path) -> None:
        n3rverberage_dir = tmp_path / ".n3rverberage"
        n3rverberage_dir.mkdir(parents=True)
        config_path = n3rverberage_dir / ORG_CONFIG_FILENAME
        config = OrgConfig(org_name="reverberage")
        config.to_yaml(config_path)

        root = resolve_org_root(tmp_path)
        assert root == tmp_path.resolve()

    def test_finds_config_in_parent_dir(self, tmp_path: Path) -> None:
        n3rverberage_dir = tmp_path / ".n3rverberage"
        n3rverberage_dir.mkdir(parents=True)
        config = OrgConfig(org_name="reverberage")
        config.to_yaml(n3rverberage_dir / ORG_CONFIG_FILENAME)

        child = tmp_path / "deep" / "nested"
        child.mkdir(parents=True)

        root = resolve_org_root(child)
        assert root == tmp_path.resolve()

    def test_not_found_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(OrgNotFoundError, match="org init"):
            resolve_org_root(tmp_path)


class TestDiscoverSatelliteCards:
    def test_no_satellites_returns_empty(self) -> None:
        config = OrgConfig(org_name="reverberage")
        cards = config.discover_satellite_cards()
        assert cards == []

    def test_hub_type_skipped(self, tmp_path: Path) -> None:
        config = OrgConfig(
            projects=[
                OrgProject(name="hub", path=Path("."), type="hub"),
            ]
        )
        cards = config.discover_satellite_cards(tmp_path)
        assert cards == []

    def test_satellite_with_a2a_config(self, tmp_path: Path) -> None:
        sat_path = tmp_path / "satellites" / "transcriber"
        (sat_path / ".n3rverberage").mkdir(parents=True)
        a2a_config = {"project": "transcriber", "hub": {"host": "127.0.0.1", "port": 19821}}
        (sat_path / ".n3rverberage" / "a2a-config.yaml").write_text(yaml.safe_dump(a2a_config), encoding="utf-8")

        config = OrgConfig(
            projects=[
                OrgProject(
                    name="transcriber",
                    path=Path("satellites/transcriber"),
                    type="satellite",
                ),
            ]
        )
        cards = config.discover_satellite_cards(tmp_path)
        assert len(cards) == 1
        assert cards[0].name == "n3rverberage-transcriber"

    def test_satellite_missing_a2a_skipped(self, tmp_path: Path) -> None:
        sat_path = tmp_path / "satellites" / "missing"
        sat_path.mkdir(parents=True)

        config = OrgConfig(
            projects=[
                OrgProject(name="missing", path=Path("satellites/missing"), type="satellite"),
            ]
        )
        cards = config.discover_satellite_cards(tmp_path)
        assert cards == []
