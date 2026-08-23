"""Structure detector — scans project directory layout."""

from __future__ import annotations

import tomllib
from pathlib import Path

from n3rv.init.analyzer.mappings import EXCLUDED_DIRS
from n3rv.init.analyzer.profile import StructureInfo
from n3rv.init.context import Stack

_STRUCTURE_DIRS: dict[str, str] = {
    "src": "has_src_dir",
    "tests": "has_tests_dir",
    "test": "has_tests_dir",
    "docs": "has_docs_dir",
    "doc": "has_docs_dir",
    "scripts": "has_scripts_dir",
}


_WEB_EXTENSIONS: frozenset[str] = frozenset({".html", ".htm", ".css", ".js", ".mjs", ".cjs"})
_WEB_DIRS: frozenset[str] = frozenset({"css", "js", "assets", "public", "static"})


class StructureDetector:
    """Detect project directory structure."""

    def detect(self, root: Path, stack: Stack) -> StructureInfo:
        has_src_dir = False
        has_tests_dir = False
        has_docs_dir = False
        has_scripts_dir = False
        has_web_files = False
        key_dirs: list[str] = []

        try:
            entries = list(root.iterdir())
        except OSError:
            return StructureInfo()

        for entry in entries:
            if entry.is_file() and entry.suffix.lower() in _WEB_EXTENSIONS:
                has_web_files = True
                continue

            if not entry.is_dir():
                continue
            name = entry.name
            if name in EXCLUDED_DIRS:
                continue
            if name.startswith("."):
                continue

            if name.lower() in _WEB_DIRS:
                has_web_files = True

            attr = _STRUCTURE_DIRS.get(name.lower())
            if attr == "has_src_dir":
                has_src_dir = True
            elif attr == "has_tests_dir":
                has_tests_dir = True
            elif attr == "has_docs_dir":
                has_docs_dir = True
            elif attr == "has_scripts_dir":
                has_scripts_dir = True
            else:
                key_dirs.append(name)

        entry_points = self._detect_entry_points(root, stack)

        return StructureInfo(
            has_src_dir=has_src_dir,
            has_tests_dir=has_tests_dir,
            has_docs_dir=has_docs_dir,
            has_scripts_dir=has_scripts_dir,
            has_web_files=has_web_files,
            entry_points=entry_points,
            key_dirs=sorted(key_dirs),
        )

    def _detect_entry_points(self, root: Path, stack: Stack) -> list[str]:
        if stack != Stack.PYTHON:
            return []

        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return []

        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            return []

        scripts = data.get("project", {}).get("scripts", {})
        gui_scripts = data.get("project", {}).get("gui-scripts", {})

        points: list[str] = []
        if isinstance(scripts, dict):
            points.extend(scripts.keys())
        if isinstance(gui_scripts, dict):
            points.extend(gui_scripts.keys())

        return sorted(points)
