from __future__ import annotations

from pathlib import Path

import pytest

from n3rv.config import RuntimePaths, load_runtime_settings


def test_runtime_paths_pid_file(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path)
    assert paths.pid_file == paths.n3rv_dir / "hub.pid"


def test_runtime_paths_log_file(tmp_path: Path) -> None:
    paths = RuntimePaths.from_project_root(tmp_path)
    assert paths.log_file == paths.logs_dir / "hub.log"


def test_load_runtime_settings_defaults_project_name_to_root_name(tmp_path) -> None:
    settings = load_runtime_settings(tmp_path)

    assert settings.project_name == tmp_path.name
    assert settings.a2a_host == "127.0.0.1"
    assert settings.a2a_port == 19820


def test_load_runtime_settings_reads_project_and_hub_config(tmp_path) -> None:
    n3rv_dir = tmp_path / ".n3rv"
    n3rv_dir.mkdir()
    (n3rv_dir / "a2a-config.yaml").write_text(
        "project: demo-app\nhub:\n  host: 0.0.0.0\n  port: 9009\n",
        encoding="utf-8",
    )

    settings = load_runtime_settings(tmp_path)

    assert settings.project_name == "demo-app"
    assert settings.a2a_host == "0.0.0.0"
    assert settings.a2a_port == 9009


# ---------------------------------------------------------------------------
# N3RV_PROJECT_ROOT override
# ---------------------------------------------------------------------------


def test_project_root_env_override_is_used(tmp_path, monkeypatch) -> None:
    """A server started outside a project can be pointed at one explicitly."""
    served = tmp_path / "served-project"
    served.mkdir()
    outside = tmp_path / "not-a-project"
    outside.mkdir()

    monkeypatch.setenv("N3RV_PROJECT_ROOT", str(served))
    monkeypatch.chdir(outside)

    settings = load_runtime_settings(None)

    assert settings.paths.project_root == served.resolve()
    assert settings.project_name == "served-project"


def test_explicit_argument_beats_env_override(tmp_path, monkeypatch) -> None:
    env_root = tmp_path / "from-env"
    env_root.mkdir()
    argument_root = tmp_path / "from-argument"
    argument_root.mkdir()

    monkeypatch.setenv("N3RV_PROJECT_ROOT", str(env_root))

    settings = load_runtime_settings(argument_root)

    assert settings.paths.project_root == argument_root.resolve()


def test_no_project_root_and_no_override_raises(tmp_path, monkeypatch) -> None:
    """Cwd detection is still consulted, and still fails loudly."""
    from n3rv.platform import ProjectRootNotFoundError

    outside = tmp_path / "not-a-project"
    outside.mkdir()
    monkeypatch.delenv("N3RV_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(outside)

    with pytest.raises(ProjectRootNotFoundError):
        load_runtime_settings(None)
