"""Integration tests for the full org workflow."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from n3rverberage.cli import app
from n3rverberage.org import ORG_CONFIG_FILENAME, OrgConfig

runner = CliRunner()


def _make_a2a_config(sat_path: Path, name: str, port: int = 19821) -> None:
    import yaml

    (sat_path / ".n3rverberage").mkdir(parents=True)
    a2a_config = {"project": name, "hub": {"host": "127.0.0.1", "port": port}}
    (sat_path / ".n3rverberage" / "a2a-config.yaml").write_text(yaml.safe_dump(a2a_config), encoding="utf-8")


class TestFullOrgWorkflow:
    """End-to-end: org init -> add satellites -> sync -> verify."""

    def test_full_workflow(self, tmp_path: Path) -> None:
        # Step 1: org init
        result = runner.invoke(app, ["org", "init", "--root", str(tmp_path)])
        assert result.exit_code == 0
        config_path = tmp_path / ".n3rverberage" / ORG_CONFIG_FILENAME
        assert config_path.exists()
        assert (tmp_path / ".opencode" / "shared" / "skills").is_dir()

        # Step 2: register satellites manually (avoids gh dependency)
        from n3rverberage.org import OrgProject

        # Create satellite dirs with a2a-config.yaml
        sat1_path = tmp_path / "satellites" / "transcriber"
        sat1_path.mkdir(parents=True)
        _make_a2a_config(sat1_path, "transcriber", port=19821)

        sat2_path = tmp_path / "satellites" / "summarizer"
        sat2_path.mkdir(parents=True)
        _make_a2a_config(sat2_path, "summarizer", port=19822)

        # Update config
        config = OrgConfig.from_yaml(config_path)
        config.projects.append(
            OrgProject(
                name="transcriber",
                path=Path("satellites/transcriber"),
                type="satellite",
                description="Audio transcription satellite",
            )
        )
        config.projects.append(
            OrgProject(
                name="summarizer",
                path=Path("satellites/summarizer"),
                type="satellite",
                description="Text summarization satellite",
            )
        )
        config.to_yaml(config_path)

        # Verify config roundtrip
        loaded = OrgConfig.from_yaml(config_path)
        assert len(loaded.projects) == 2

        # Step 3: sync (dry-run to avoid needing n3rverberage init on fake dirs)
        result = runner.invoke(app, ["org", "sync", "--root", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0
        assert "transcriber" in result.stdout
        assert "summarizer" in result.stdout

        # Step 4: verify agent card discovery
        from n3rverberage.config import load_runtime_settings

        settings = load_runtime_settings(tmp_path)
        from n3rverberage.a2a.agent_cards import load_agent_cards

        cards = load_agent_cards(settings, org_config_path=config_path)
        assert "n3rverberage-transcriber" in cards
        assert "n3rverberage-summarizer" in cards
        assert cards["n3rverberage-transcriber"].name == "n3rverberage-transcriber"
        assert cards["n3rverberage-summarizer"].name == "n3rverberage-summarizer"
        # Infrastructure cards still present
        assert "hub" in cards
        assert "opencode" in cards

        # Step 5: verify skill registry (shared + local)
        # Place a shared skill
        shared_skills_dir = tmp_path / ".opencode" / "shared" / "skills" / "org-policy"
        shared_skills_dir.mkdir(parents=True)
        (shared_skills_dir / "SKILL.md").write_text(
            "---\nname: org-policy\ndescription: Org-wide coding policy\n---\n",
            encoding="utf-8",
        )

        from n3rverberage.init.registry import SkillRegistry, write_registry

        registry = SkillRegistry.scan(tmp_path, org_root=tmp_path)
        names = {e.name for e in registry.entries}
        assert "org-policy" in names
        for entry in registry.entries:
            assert entry.origin in ("local", "shared")

        # Verify registry writing
        out = write_registry(tmp_path, org_root=tmp_path)
        content = out.read_text()
        assert "org-policy" in content
        assert "Origin" in content
