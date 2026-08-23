from __future__ import annotations

from pathlib import Path

from n3rverberage.init import run_init
from n3rverberage.init.update import run_update


def _write_fastapi_pyproject(root: Path) -> None:
    content = """[project]
name = "fastapp"
version = "0.1.0"
dependencies = [
    "fastapi>=0.100.0",
    "sqlalchemy>=2.0",
    "pytest>=7.0",
]

[project.scripts]
test = "pytest"
lint = "ruff check ."
"""
    (root / "pyproject.toml").write_text(content, encoding="utf-8")
    (root / "src").mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)


def _write_generic_pyproject(root: Path) -> None:
    content = """[project]
name = "genericapp"
version = "0.1.0"
dependencies = [
    "some-lib>=1.0",
    "another-lib>=2.0",
]
"""
    (root / "pyproject.toml").write_text(content, encoding="utf-8")


class TestInit:
    def test_init_fastapi_project(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        result = run_init(tmp_path, project_name=None, stack_override=None, force=True)
        assert result == 0

        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text(encoding="utf-8")
        assert "FastAPI" in content
        assert "SQLAlchemy" in content
        assert "pytest" in content
        assert "pytest" in content  # tool command

    def test_init_generic_project(self, tmp_path: Path) -> None:
        _write_generic_pyproject(tmp_path)
        result = run_init(tmp_path, project_name=None, stack_override=None, force=True)
        assert result == 0

        agents_md = tmp_path / "AGENTS.md"
        content = agents_md.read_text(encoding="utf-8")
        assert "some-lib" not in content.lower()  # unknown libs not listed
        assert "Project Structure" not in content  # no structure detected

    def test_n3rv_agent_created(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        n3rv_agent = tmp_path / ".opencode" / "agents" / "n3rverberage.md"
        assert n3rv_agent.exists()
        agent_content = n3rv_agent.read_text(encoding="utf-8")
        assert "mode: primary" in agent_content
        assert "hidden: false" in agent_content
        assert "sdd-explorer" in agent_content
        assert "sdd-proposer" in agent_content
        assert "sdd-designer" in agent_content
        assert "git-ops" in agent_content
        assert "github-ops" in agent_content

    def test_commands_created_for_detected_tools(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        test_cmd = tmp_path / ".opencode" / "commands" / "test.md"
        lint_cmd = tmp_path / ".opencode" / "commands" / "lint.md"

        assert test_cmd.exists()
        test_content = test_cmd.read_text(encoding="utf-8")
        assert "pytest" in test_content

        assert lint_cmd.exists()
        lint_content = lint_cmd.read_text(encoding="utf-8")
        assert "ruff" in lint_content

    def test_no_typecheck_command_without_typechecker(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        typecheck_cmd = tmp_path / ".opencode" / "commands" / "typecheck.md"
        assert not typecheck_cmd.exists()

    def test_init_idempotent(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)
        # Second run without force should skip
        result = run_init(tmp_path, project_name=None, stack_override=None, force=False)
        assert result == 0  # no error, things were skipped

    def test_init_with_stack_override(self, tmp_path: Path) -> None:
        run_init(tmp_path, project_name="testproj", stack_override="python", force=True)
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text(encoding="utf-8")
        assert "testproj" in content

    def test_code_skill_has_framework_guidance(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        code_skill = tmp_path / ".opencode" / "skills" / "code" / "SKILL.md"
        content = code_skill.read_text(encoding="utf-8")
        assert "FastAPI" in content
        assert "Depends()" in content

    def test_code_skill_no_frameworks_generic(self, tmp_path: Path) -> None:
        _write_generic_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        code_skill = tmp_path / ".opencode" / "skills" / "code" / "SKILL.md"
        content = code_skill.read_text(encoding="utf-8")
        assert "FastAPI" not in content

    def test_plugins_scaffolded_on_init(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        lifecycle = tmp_path / ".opencode" / "plugins" / "n3rverberage-lifecycle.js"
        shell_env = tmp_path / ".opencode" / "plugins" / "n3rverberage-shell-env.js"
        assert lifecycle.is_file(), f"Missing {lifecycle}"
        assert shell_env.is_file(), f"Missing {shell_env}"

        lc_content = lifecycle.read_text(encoding="utf-8")
        assert "NervLifecycle" in lc_content
        assert "buildSDDSummary" in lc_content
        assert "experimental.session.compacting" in lc_content

        se_content = shell_env.read_text(encoding="utf-8")
        assert "NervShellEnv" in se_content
        assert "opencode:n3rverberage" in se_content

    def test_tools_scaffolded_on_init(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        stats_ts = tmp_path / ".opencode" / "tools" / "n3rverberage-stats.ts"
        package_json = tmp_path / ".opencode" / "package.json"
        assert stats_ts.is_file(), f"Missing {stats_ts}"
        assert package_json.is_file(), f"Missing {package_json}"

        ts_content = stats_ts.read_text(encoding="utf-8")
        assert "n3rverberage_memory_stats" in ts_content
        assert "n3rverberage_hub_health" in ts_content
        assert "n3rverberage_check_pending_tasks" in ts_content

        pkg_content = package_json.read_text(encoding="utf-8")
        assert "@opencode-ai/plugin" in pkg_content

    def test_docs_not_scaffolded_on_init(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        contributing = tmp_path / "CONTRIBUTING.md"
        security = tmp_path / "SECURITY.md"
        assert not contributing.is_file(), f"CONTRIBUTING.md should not be generated: {contributing}"
        assert not security.is_file(), f"SECURITY.md should not be generated: {security}"

    def test_opencode_json_has_new_keys(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        import json

        oc_json = tmp_path / "opencode.json"
        assert oc_json.is_file()
        data = json.loads(oc_json.read_text(encoding="utf-8"))

        assert "plugin" in data
        assert len(data["plugin"]) >= 2
        assert any("n3rverberage-lifecycle" in p for p in data["plugin"])
        assert any("n3rverberage-shell-env" in p for p in data["plugin"])

        instructions = data.get("instructions", [])
        assert "AGENTS.md" in instructions
        assert "CONTRIBUTING.md" in instructions
        assert "SECURITY.md" in instructions
        assert any("docs" in i for i in instructions)

        assert "tools" in data
        assert data["tools"].get("websearch") is True


class TestUpdate:
    def test_markers_preserved_on_update(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        agents_md = tmp_path / "AGENTS.md"
        # Add custom user content after markers
        agents_md.write_text(
            agents_md.read_text(encoding="utf-8") + "\n\n// My custom project notes\n// Team conventions here\n",
            encoding="utf-8",
        )

        run_update(tmp_path)

        updated_content = agents_md.read_text(encoding="utf-8")
        assert "My custom project notes" in updated_content
        assert "Team conventions here" in updated_content
        assert "FastAPI" in updated_content  # regenerated marker section

    def test_update_dry_run(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        agents_md_before = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
        run_update(tmp_path, dry_run=True)
        agents_md_after = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

        # AGENTS.md should not have been modified during dry run
        assert agents_md_before == agents_md_after

    def test_update_creates_missing_n3rv_agent(self, tmp_path: Path) -> None:
        _write_fastapi_pyproject(tmp_path)
        run_init(tmp_path, project_name=None, stack_override=None, force=True)

        n3rv_agent = tmp_path / ".opencode" / "agents" / "n3rverberage.md"
        n3rv_agent.unlink()
        assert not n3rv_agent.exists()

        run_update(tmp_path, force_commands=True)

        assert n3rv_agent.exists()
