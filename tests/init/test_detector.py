"""Tests for stack detection."""

from __future__ import annotations

from pathlib import Path

from n3rv.init.context import Stack
from n3rv.init.detector import detect_stack


def test_detect_python_from_pyproject_project_name(tmp_path: Path):
    """Test Python detection from pyproject.toml with [project].name."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "my-python-app"
version = "1.0.0"
""")

    info = detect_stack(tmp_path)
    assert info.stack == Stack.PYTHON
    assert info.project_name == "my-python-app"


def test_detect_python_from_pyproject_poetry_name(tmp_path: Path):
    """Test Python detection from pyproject.toml with [tool.poetry].name."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[tool.poetry]
name = "my-poetry-app"
version = "1.0.0"
""")

    info = detect_stack(tmp_path)
    assert info.stack == Stack.PYTHON
    assert info.project_name == "my-poetry-app"


def test_detect_node_from_package_json(tmp_path: Path):
    """Test Node detection from package.json."""
    package_json = tmp_path / "package.json"
    package_json.write_text("""
{
  "name": "my-node-app",
  "version": "1.0.0"
}
""")

    info = detect_stack(tmp_path)
    assert info.stack == Stack.NODE
    assert info.project_name == "my-node-app"


def test_detect_node_strips_org_prefix(tmp_path: Path):
    """Test Node detection strips @org/ prefix from scoped package names."""
    package_json = tmp_path / "package.json"
    package_json.write_text("""
{
  "name": "@myorg/my-scoped-app",
  "version": "1.0.0"
}
""")

    info = detect_stack(tmp_path)
    assert info.stack == Stack.NODE
    assert info.project_name == "my-scoped-app"


def test_detect_go_from_go_mod(tmp_path: Path):
    """Test Go detection from go.mod."""
    go_mod = tmp_path / "go.mod"
    go_mod.write_text("""
module github.com/user/my-go-app

go 1.21
""")

    info = detect_stack(tmp_path)
    assert info.stack == Stack.GO
    assert info.project_name == "my-go-app"


def test_detect_generic_fallback(tmp_path: Path):
    """Test generic stack fallback when no manifest found."""
    # Create a directory with a specific name but no manifest
    project_dir = tmp_path / "my-generic-project"
    project_dir.mkdir()

    info = detect_stack(project_dir)
    assert info.stack == Stack.GENERIC
    assert info.project_name == "my-generic-project"


def test_stack_override_python(tmp_path: Path):
    """Test explicit stack override to python."""
    # Create a Node project
    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "nodeapp"}')

    # Override to Python
    info = detect_stack(tmp_path, stack_override="python")
    assert info.stack == Stack.PYTHON
    # But project name should still come from package.json
    assert info.project_name == "nodeapp"


def test_stack_override_with_no_manifest(tmp_path: Path):
    """Test stack override with no manifest uses directory name."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()

    info = detect_stack(project_dir, stack_override="go")
    assert info.stack == Stack.GO
    assert info.project_name == "myproject"


def test_python_priority_over_node(tmp_path: Path):
    """Test that pyproject.toml takes priority over package.json if both exist."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "pythonapp"')
    (tmp_path / "package.json").write_text('{"name": "nodeapp"}')

    info = detect_stack(tmp_path)
    assert info.stack == Stack.PYTHON
    assert info.project_name == "pythonapp"
