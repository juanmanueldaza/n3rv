from __future__ import annotations

from pathlib import Path

from n3rv.init.analyzer.structure import StructureDetector
from n3rv.init.context import Stack


class TestStructureDetector:
    def test_standard_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "scripts").mkdir()

        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.has_src_dir is True
        assert result.has_tests_dir is True
        assert result.has_docs_dir is True
        assert result.has_scripts_dir is True

    def test_empty_project(self, tmp_path: Path) -> None:
        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.has_src_dir is False
        assert result.has_tests_dir is False
        assert result.has_docs_dir is False
        assert result.has_scripts_dir is False
        assert result.entry_points == []
        assert result.key_dirs == []

    def test_excluded_dirs_filtered(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".n3rv").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "venv").mkdir()
        (tmp_path / "dist").mkdir()
        (tmp_path / "build").mkdir()

        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.key_dirs == []

    def test_entry_points(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.scripts]
n3rv = "n3rv.cli:main"
n3rv-memory = "n3rv.mcp.memory_server:main"

[project.gui-scripts]
n3rv-gui = "n3rv.gui:main"
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert "n3rv" in result.entry_points
        assert "n3rv-memory" in result.entry_points
        assert "n3rv-gui" in result.entry_points

    def test_key_dirs_identified(self, tmp_path: Path) -> None:
        (tmp_path / "app").mkdir()
        (tmp_path / "lib").mkdir()
        (tmp_path / "config").mkdir()
        (tmp_path / "migrations").mkdir()

        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert "app" in result.key_dirs
        assert "config" in result.key_dirs
        assert "lib" in result.key_dirs
        assert "migrations" in result.key_dirs

    def test_test_dir_alias(self, tmp_path: Path) -> None:
        (tmp_path / "test").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.has_tests_dir is True

    def test_dot_dirs_filtered(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden_dir").mkdir()
        (tmp_path / ".config").mkdir()

        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert ".hidden_dir" not in result.key_dirs
        assert ".config" not in result.key_dirs

    def test_node_stack_no_entry_points(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.NODE)
        assert result.entry_points == []
        assert result.has_src_dir is True

    def test_corrupt_pyproject_structure(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("{{{invalid toml")
        (tmp_path / "src").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.has_src_dir is True
        assert result.entry_points == []

    def test_web_files_detected_from_html(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("<html></html>")
        result = StructureDetector().detect(tmp_path, Stack.GENERIC)
        assert result.has_web_files is True

    def test_web_files_detected_from_css(self, tmp_path: Path) -> None:
        (tmp_path / "styles.css").write_text("body {}")
        result = StructureDetector().detect(tmp_path, Stack.GENERIC)
        assert result.has_web_files is True

    def test_web_files_detected_from_js(self, tmp_path: Path) -> None:
        (tmp_path / "app.js").write_text("console.log('hi')")
        result = StructureDetector().detect(tmp_path, Stack.GENERIC)
        assert result.has_web_files is True

    def test_web_dirs_detected(self, tmp_path: Path) -> None:
        (tmp_path / "css").mkdir()
        (tmp_path / "js").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.GENERIC)
        assert result.has_web_files is True

    def test_web_assets_dir_detected(self, tmp_path: Path) -> None:
        (tmp_path / "assets").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.GENERIC)
        assert result.has_web_files is True

    def test_no_web_files_in_bare_project(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        result = StructureDetector().detect(tmp_path, Stack.PYTHON)
        assert result.has_web_files is False
