from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from n3rverberage.platform import project_relative_path, resolve_project_root

# ---------------------------------------------------------------------------
# Provider defaults — env-var-driven, used by factory.py and all providers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderDefaults:
    """Default provider settings resolved from environment variables.

    These are the **global** defaults applied when no provider-specific env
    var or constructor argument is set.  Each provider's own ``_default_model``
    / ``_default_base_url`` method checks these first, so setting a global
    env var overrides per-provider defaults *for all providers*.
    """

    provider: str
    model: str
    base_url: str

    @classmethod
    def from_env(cls) -> ProviderDefaults:
        return cls(
            provider=os.environ.get("N3RVERBERAGE_PROVIDER", "qwen"),
            model=os.environ.get(
                "N3RVERBERAGE_DEFAULT_MODEL",
                "qwen3-coder-plus",
            ),
            base_url=os.environ.get(
                "N3RVERBERAGE_DEFAULT_BASE_URL",
                "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            ),
        )


# Module-level singleton — evaluated once at import time.
# Tests can patch os.environ before import to control values.
DEFAULTS = ProviderDefaults.from_env()


class RuntimePaths(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_root: Path
    memory_dir: Path
    n3rverberage_dir: Path
    hub_state_dir: Path
    logs_dir: Path

    @property
    def pid_file(self) -> Path:
        return self.n3rverberage_dir / "hub.pid"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "hub.log"

    @classmethod
    def from_project_root(cls, project_root: Path) -> RuntimePaths:
        return cls(
            project_root=project_root,
            memory_dir=project_relative_path(project_root, ".n3rverberage", "memory"),
            n3rverberage_dir=project_relative_path(project_root, ".n3rverberage"),
            hub_state_dir=project_relative_path(project_root, ".n3rverberage", "hub-state"),
            logs_dir=project_relative_path(project_root, ".n3rverberage", "logs"),
        )


_DEFAULT_MEMORY_TTL: dict[str, dict] = {
    "session": {"default": 7, "overrides": {"summary": 7, "context": 30}},
    "personal": {"default": 90},
    "project": {
        "default": 365,
        "overrides": {
            "architecture": 365,
            "decision": 365,
            "bugfix": 180,
            "config": 180,
            "learning": 180,
        },
    },
}


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_name: str = "n3rverberage"
    a2a_host: str = "127.0.0.1"
    a2a_port: int = Field(default=19820, ge=1, le=65535)
    paths: RuntimePaths
    memory_ttl: dict = Field(default_factory=lambda: _DEFAULT_MEMORY_TTL.copy())

    @property
    def a2a_base_url(self) -> str:
        return f"http://{self.a2a_host}:{self.a2a_port}"


def load_runtime_settings(project_root: Path | None = None) -> RuntimeSettings:
    root = project_root or resolve_project_root()
    paths = RuntimePaths.from_project_root(root)
    settings = RuntimeSettings(project_name=root.name or "n3rverberage", paths=paths)

    config_path = paths.n3rverberage_dir / "a2a-config.yaml"
    if not config_path.exists():
        return settings

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    hub_section = raw.get("hub") or {}

    settings_data = settings.model_dump()
    if isinstance(raw.get("project"), str) and raw["project"].strip():
        settings_data["project_name"] = raw["project"].strip()
    if "host" in hub_section:
        settings_data["a2a_host"] = hub_section["host"]
    if "port" in hub_section:
        settings_data["a2a_port"] = hub_section["port"]
    return RuntimeSettings.model_validate(settings_data)
