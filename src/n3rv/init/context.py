"""Project context data for template rendering."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator


class Stack(StrEnum):
    """Supported project stacks."""

    PYTHON = "python"
    NODE = "node"
    GO = "go"
    GENERIC = "generic"


class ProjectContext(BaseModel):
    """Context data for template rendering."""

    model_config = ConfigDict(frozen=True)

    project_name: str
    stack: Stack
    project_root: Path
    n3rv_version: str
    timestamp: str

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("project_name cannot be empty")
        return v

    @classmethod
    def build(cls, project_name: str, stack: Stack, project_root: Path) -> ProjectContext:
        from importlib.metadata import PackageNotFoundError, version

        try:
            nerv_version = version("n3rv")
        except PackageNotFoundError:
            nerv_version = "dev"

        timestamp = datetime.now(UTC).isoformat()

        return cls(
            project_name=project_name,
            stack=stack,
            project_root=project_root,
            n3rv_version=nerv_version,
            timestamp=timestamp,
        )

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "stack": self.stack.value,
            "project_root": str(self.project_root),
            "n3rv_version": self.n3rv_version,
            "timestamp": self.timestamp,
        }
