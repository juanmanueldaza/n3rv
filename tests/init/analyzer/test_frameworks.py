from __future__ import annotations

import json
from pathlib import Path

from n3rv.init.analyzer.frameworks import FrameworkDetector
from n3rv.init.context import Stack


def _write_pyproject(root: Path, deps: list[str]) -> None:
    content = '[project]\nname = "testapp"\ndependencies = [\n'
    for d in deps:
        content += f'    "{d}",\n'
    content += "]\n"
    (root / "pyproject.toml").write_text(content, encoding="utf-8")


def _write_poetry_pyproject(root: Path, deps: dict[str, str]) -> None:
    content = "[tool.poetry.dependencies]\n"
    content += 'python = "^3.10"\n'
    for name, version in deps.items():
        content += f'{name} = "{version}"\n'
    (root / "pyproject.toml").write_text(content, encoding="utf-8")


def _write_package_json(root: Path, deps: dict, dev_deps: dict | None = None) -> None:
    data = {"name": "testapp", "dependencies": deps}
    if dev_deps:
        data["devDependencies"] = dev_deps
    (root / "package.json").write_text(json.dumps(data), encoding="utf-8")


class TestFrameworkDetectorPython:
    def test_detect_fastapi(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["fastapi>=0.100.0"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        names = {fw.name for fw in result}
        assert "FastAPI" in names

    def test_detect_multiple_frameworks(self, tmp_path: Path) -> None:
        _write_pyproject(
            tmp_path,
            [
                "fastapi>=0.100.0",
                "sqlalchemy[asyncio]>=2.0",
                "pytest>=7.0",
            ],
        )
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        names = {fw.name for fw in result}
        assert "FastAPI" in names
        assert "SQLAlchemy" in names
        assert "pytest" in names

    def test_detect_flask(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["flask>=2.0"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert any(fw.name == "Flask" for fw in result)

    def test_detect_django(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["django>=4.0"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert any(fw.name == "Django" for fw in result)

    def test_detect_tortoise(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["tortoise-orm>=0.19"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert any(fw.name == "Tortoise ORM" for fw in result)

    def test_no_frameworks_unknown_deps(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["unknown-lib-123>=1.0", "another-fake-pkg"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_no_pyproject(self, tmp_path: Path) -> None:
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_corrupt_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("this is not valid toml {{{")
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert len(result) == 0

    def test_detect_fastapi_case_insensitive(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["FastAPI>=0.100.0"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        assert any(fw.name == "FastAPI" for fw in result)

    def test_poetry_format(self, tmp_path: Path) -> None:
        _write_poetry_pyproject(
            tmp_path,
            {
                "fastapi": "^0.100",
                "pytest": "^7.0",
            },
        )
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        names = {fw.name for fw in result}
        assert "FastAPI" in names
        assert "pytest" in names

    def test_optional_dependencies(self, tmp_path: Path) -> None:
        content = """[project]
name = "testapp"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff>=0.3",
]
"""
        (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        names = {fw.name for fw in result}
        assert "pytest" in names
        assert "ruff" in names

    def test_guidance_populated(self, tmp_path: Path) -> None:
        _write_pyproject(tmp_path, ["fastapi>=0.100"])
        result = FrameworkDetector().detect(tmp_path, Stack.PYTHON)
        fastapi_fw = next(fw for fw in result if fw.name == "FastAPI")
        assert len(fastapi_fw.guidance) > 0
        assert "Depends()" in fastapi_fw.guidance


class TestFrameworkDetectorNode:
    def test_detect_react(self, tmp_path: Path) -> None:
        _write_package_json(tmp_path, {"react": "^18.0"})
        result = FrameworkDetector().detect(tmp_path, Stack.NODE)
        assert any(fw.name == "React" for fw in result)

    def test_detect_express(self, tmp_path: Path) -> None:
        _write_package_json(tmp_path, {"express": "^4.0"})
        result = FrameworkDetector().detect(tmp_path, Stack.NODE)
        assert any(fw.name == "Express" for fw in result)

    def test_detect_from_dev_dependencies(self, tmp_path: Path) -> None:
        _write_package_json(tmp_path, {}, {"jest": "^29.0"})
        result = FrameworkDetector().detect(tmp_path, Stack.NODE)
        assert any(fw.name == "Jest" for fw in result)

    def test_no_package_json(self, tmp_path: Path) -> None:
        result = FrameworkDetector().detect(tmp_path, Stack.NODE)
        assert len(result) == 0


class TestFrameworkDetectorGo:
    def test_no_go_mod(self, tmp_path: Path) -> None:
        result = FrameworkDetector().detect(tmp_path, Stack.GO)
        assert len(result) == 0

    def test_go_mod_with_unknown_deps(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text(
            "module example.com/test\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n)\n"
        )
        result = FrameworkDetector().detect(tmp_path, Stack.GO)
        assert len(result) == 0
