"""Tool detector — extracts test/lint/build commands from project config."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from n3rv.init.analyzer.mappings import TOOL_SCRIPT_KEYS
from n3rv.init.analyzer.profile import ToolCommand
from n3rv.init.context import Stack


class ToolDetector:
    """Detect tool commands from project config files."""

    def detect(self, root: Path, stack: Stack) -> list[ToolCommand]:
        if stack == Stack.PYTHON:
            return self._detect_python(root)
        elif stack == Stack.NODE:
            return self._detect_node(root)
        return []

    def _detect_python(self, root: Path) -> list[ToolCommand]:
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return []

        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            return []

        scripts = data.get("project", {}).get("scripts", {})
        if not isinstance(scripts, dict):
            return []

        return self._extract_from_scripts(scripts)

    def _detect_node(self, root: Path) -> list[ToolCommand]:
        pkg_json = root / "package.json"
        if not pkg_json.exists():
            return []

        try:
            with pkg_json.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        scripts = data.get("scripts", {})
        if not isinstance(scripts, dict):
            return []

        return self._extract_from_scripts(scripts)

    def _extract_from_scripts(self, scripts: dict) -> list[ToolCommand]:
        results: list[ToolCommand] = []
        seen: set[str] = set()

        for key, value in scripts.items():
            key_lower = key.lower().strip()
            if not isinstance(value, str):
                continue

            mapping = TOOL_SCRIPT_KEYS.get(key_lower)
            if mapping and mapping["name"] not in seen:
                seen.add(mapping["name"])
                results.append(
                    ToolCommand(
                        name=mapping["name"],
                        command=value.strip(),
                        category=mapping["category"],
                    )
                )

        return results
