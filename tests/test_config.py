from __future__ import annotations

from pathlib import Path

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
