from __future__ import annotations

import asyncio
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from n3rv.config import RuntimePaths, RuntimeSettings, load_runtime_settings


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".git").mkdir()
    return root.resolve()


@pytest.fixture
def runtime_settings(project_root: Path) -> RuntimeSettings:
    return load_runtime_settings(project_root)


@pytest.fixture
def temp_settings(tmp_path: Path) -> RuntimeSettings:
    paths = RuntimePaths(
        project_root=tmp_path,
        memory_dir=tmp_path / ".n3rv" / "memory",
        n3rv_dir=tmp_path / ".n3rv",
        hub_state_dir=tmp_path / ".n3rv" / "hub-state",
        logs_dir=tmp_path / ".n3rv" / "logs",
    )
    return RuntimeSettings(paths=paths)


@pytest.fixture
def windows_style_path(project_root: Path) -> PureWindowsPath:
    return PureWindowsPath("C:/workspace") / project_root.name / "src" / "n3rv"


@pytest.fixture
def linux_style_path(project_root: Path) -> PurePosixPath:
    return PurePosixPath("/") / "workspace" / project_root.name / "src" / "n3rv"


@pytest.fixture
def async_tick():
    async def _tick() -> None:
        await asyncio.sleep(0)

    return _tick
