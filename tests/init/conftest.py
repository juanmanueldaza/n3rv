"""Fixtures for init tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from n3rv.init import run_init


@pytest.fixture
def initialized_project(tmp_path: Path) -> Path:
    """Create a pre-initialized project for update tests."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"\n')
    run_init(tmp_path, project_name=None, stack_override=None, force=False)
    return tmp_path
