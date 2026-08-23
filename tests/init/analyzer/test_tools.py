from __future__ import annotations

import json
from pathlib import Path

from n3rv.init.analyzer.tools import ToolDetector
from n3rv.init.context import Stack


class TestToolDetectorPython:
    def test_extract_test_from_scripts(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.scripts]
test = "pytest"
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        test_cmd = next((t for t in result if t.name == "test"), None)
        assert test_cmd is not None
        assert test_cmd.command == "pytest"
        assert test_cmd.category == "testing"

    def test_extract_lint_from_scripts(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.scripts]
lint = "ruff check ."
format = "black ."
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        names = {t.name for t in result}
        assert "lint" in names
        assert "format" in names
        lint_cmd = next(t for t in result if t.name == "lint")
        assert lint_cmd.command == "ruff check ."

    def test_no_scripts_section(self, tmp_path: Path) -> None:
        content = '[project]\nname = "testapp"\n'
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_no_pyproject(self, tmp_path: Path) -> None:
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_unknown_script_keys_ignored(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.scripts]
greet = "echo hello"
deploy = "ansible-playbook deploy.yml"
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_typecheck_script(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.scripts]
typecheck = "mypy src/"
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.PYTHON)
        typecheck = next((t for t in result if t.name == "typecheck"), None)
        assert typecheck is not None
        assert typecheck.command == "mypy src/"
        assert typecheck.category == "typechecking"


class TestToolDetectorNode:
    def test_extract_from_package_json(self, tmp_path: Path) -> None:
        data = {
            "name": "testapp",
            "scripts": {
                "test": "jest",
                "lint": "eslint .",
                "build": "webpack",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(data), encoding="utf-8")
        result = ToolDetector().detect(tmp_path, Stack.NODE)
        names = {t.name for t in result}
        assert "test" in names
        assert "lint" in names
        assert "build" in names

    def test_no_package_json(self, tmp_path: Path) -> None:
        result = ToolDetector().detect(tmp_path, Stack.NODE)
        assert len(result) == 0


class TestToolDetectorGo:
    def test_go_returns_empty(self, tmp_path: Path) -> None:
        result = ToolDetector().detect(tmp_path, Stack.GO)
        assert len(result) == 0
