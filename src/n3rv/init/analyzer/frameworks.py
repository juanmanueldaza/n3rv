"""Framework detector — reads project config files, maps deps to known frameworks."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from n3rv.init.analyzer.mappings import (
    KNOWN_FRAMEWORKS,
    KNOWN_NPM_FRAMEWORKS,
    FrameworkMapping,
)
from n3rv.init.analyzer.profile import FrameworkInfo
from n3rv.init.context import Stack

_PEP508_NAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?")


class FrameworkDetector:
    """Detect frameworks from project dependency manifests."""

    @staticmethod
    def _extract_package_name(dep_spec: str) -> str | None:
        """Extract bare package name from a PEP 508 dependency spec.

        Examples:
            'fastapi>=0.100' → 'fastapi'
            'sqlalchemy[asyncio]>=2.0' → 'sqlalchemy'
            'python>=3.10' → 'python'
        """
        match = _PEP508_NAME_RE.match(dep_spec.strip())
        if match:
            return match.group(0).lower().strip()
        return None

    def detect(self, root: Path, stack: Stack) -> list[FrameworkInfo]:
        if stack == Stack.PYTHON:
            return self._detect_python(root)
        elif stack == Stack.NODE:
            return self._detect_node(root)
        elif stack == Stack.GO:
            return self._detect_go(root)
        return []

    def _detect_python(self, root: Path) -> list[FrameworkInfo]:
        pyproject = root / "pyproject.toml"
        if not pyproject.exists():
            return []

        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            return []

        dep_names: set[str] = set()

        deps = data.get("project", {}).get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, str):
                    name = self._extract_package_name(dep)
                    if name:
                        dep_names.add(name)

        opt_deps = data.get("project", {}).get("optional-dependencies", {})
        if isinstance(opt_deps, dict):
            for opt_dep_list in opt_deps.values():
                if isinstance(opt_dep_list, list):
                    for dep in opt_dep_list:
                        if isinstance(dep, str):
                            name = self._extract_package_name(dep)
                            if name:
                                dep_names.add(name)

        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for dep_name in poetry_deps:
                if dep_name.lower() != "python":
                    dep_names.add(dep_name.lower().strip())

        return self._match_frameworks(dep_names, KNOWN_FRAMEWORKS)

    def _detect_node(self, root: Path) -> list[FrameworkInfo]:
        pkg_json = root / "package.json"
        if not pkg_json.exists():
            return []

        try:
            with pkg_json.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        dep_names: set[str] = set()

        for section in ("dependencies", "devDependencies"):
            section_data = data.get(section, {})
            if isinstance(section_data, dict):
                for dep_name in section_data:
                    dep_names.add(dep_name.lower().strip())

        return self._match_frameworks(dep_names, KNOWN_NPM_FRAMEWORKS)

    def _detect_go(self, root: Path) -> list[FrameworkInfo]:
        go_mod = root / "go.mod"
        if not go_mod.exists():
            return []

        try:
            content = go_mod.read_text(encoding="utf-8")
        except Exception:
            return []

        dep_names: set[str] = set()
        for match in re.finditer(r"^\s*(\S+)\s+v\d", content, re.MULTILINE):
            pkg = match.group(1).lower().strip()
            dep_names.add(pkg)
            last_segment = pkg.rsplit("/", 1)[-1]
            if last_segment:
                dep_names.add(last_segment)

        return self._match_frameworks(dep_names, KNOWN_FRAMEWORKS)

    def _match_frameworks(self, dep_names: set[str], mappings: dict[str, FrameworkMapping]) -> list[FrameworkInfo]:
        seen: set[str] = set()
        results: list[FrameworkInfo] = []

        for dep in sorted(dep_names):
            mapping = mappings.get(dep)
            if mapping and mapping["name"] not in seen:
                seen.add(mapping["name"])
                results.append(
                    FrameworkInfo(
                        name=mapping["name"],
                        category=mapping["category"],
                        guidance=mapping["guidance"],
                    )
                )

        return results
