"""Stack detection from project manifest files."""

from __future__ import annotations

import json
import logging
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from n3rverberage.init.context import Stack

logger = logging.getLogger("n3rverberage.init.detector")


@dataclass
class StackInfo:
    """Stack detection result."""

    stack: Stack
    project_name: str


def detect_stack(root: Path, stack_override: str | None = None) -> StackInfo:
    if stack_override:
        stack = Stack(stack_override)
    else:
        stack = _detect_stack_from_manifests(root)

    project_name = _extract_project_name(root, stack)

    return StackInfo(stack=stack, project_name=project_name)


def _detect_stack_from_manifests(root: Path) -> Stack:
    if (root / "pyproject.toml").exists():
        return Stack.PYTHON
    if (root / "package.json").exists():
        return Stack.NODE
    if (root / "go.mod").exists():
        return Stack.GO
    return Stack.GENERIC


def _extract_project_name(root: Path, stack: Stack) -> str:
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        name = _extract_from_pyproject(pyproject)
        if name:
            return name

    package_json = root / "package.json"
    if package_json.exists():
        name = _extract_from_package_json(package_json)
        if name:
            return name

    go_mod = root / "go.mod"
    if go_mod.exists():
        name = _extract_from_go_mod(go_mod)
        if name:
            return name

    return root.name


def _extract_from_pyproject(path: Path) -> str | None:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        if "project" in data and "name" in data["project"]:
            return data["project"]["name"]
        if "tool" in data and "poetry" in data["tool"] and "name" in data["tool"]["poetry"]:
            return data["tool"]["poetry"]["name"]
    except Exception:
        logger.debug("Failed to parse pyproject.toml: %s", path, exc_info=True)
    return None


def _extract_from_package_json(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("name")
        if name:
            if name.startswith("@") and "/" in name:
                name = name.split("/", 1)[1]
            return name
    except Exception:
        logger.debug("Failed to parse package.json: %s", path, exc_info=True)
    return None


def _extract_from_go_mod(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
        match = re.match(r"^\s*module\s+(.+)", content, re.MULTILINE)
        if match:
            module_path = match.group(1).strip()
            return module_path.split("/")[-1]
    except Exception:
        logger.debug("Failed to parse go.mod: %s", path, exc_info=True)
    return None
