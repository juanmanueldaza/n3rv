from __future__ import annotations

from pathlib import Path

PROJECT_MARKERS = (
    ".git",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    ".n3rv",
)


class ProjectRootNotFoundError(RuntimeError):
    pass


def normalize_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def resolve_project_root(start: str | Path | None = None, max_depth: int = 10) -> Path:
    current = normalize_path(start or Path.cwd())
    if current.is_file():
        current = current.parent

    for _ in range(max_depth + 1):
        if any((current / marker).exists() for marker in PROJECT_MARKERS):
            return current
        if current.parent == current:
            break
        current = current.parent

    raise ProjectRootNotFoundError("Could not detect project root. Run from inside a project directory.")


def project_relative_path(project_root: Path, *parts: str) -> Path:
    return project_root.joinpath(*parts).resolve()
