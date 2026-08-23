"""Project profile data models for LCL injection."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

from n3rv.init.context import Stack


@dataclass(frozen=True)
class FrameworkInfo:
    """Information about a detected framework."""

    name: str
    category: str
    guidance: str = ""
    version_hint: str | None = None


@dataclass(frozen=True)
class ToolCommand:
    """A detected tool command (test, lint, typecheck, etc.)."""

    name: str
    command: str
    category: str


@dataclass(frozen=True)
class MCPServerInfo:
    """A recommended MCP server for the project's opencode.json config."""

    name: str
    type: str  # "local" or "remote"
    command: list[str] | None = None
    url: str | None = None
    environment: dict[str, str] | None = None
    description: str = ""
    disabled: bool = False


@dataclass(frozen=True)
class StructureInfo:
    """Detected project directory structure."""

    has_src_dir: bool = False
    has_tests_dir: bool = False
    has_docs_dir: bool = False
    has_scripts_dir: bool = False
    has_web_files: bool = False
    entry_points: list[str] = field(default_factory=list)
    key_dirs: list[str] = field(default_factory=list)


class ProjectProfile(BaseModel):
    """Full project profile – the LCL that fills the Entry Plug workspace."""

    model_config = ConfigDict(frozen=True)

    stack: Stack
    project_name: str
    frameworks: list[FrameworkInfo] = field(default_factory=list)
    tools: list[ToolCommand] = field(default_factory=list)
    structure: StructureInfo = field(default_factory=StructureInfo)
    mcp_servers: list[MCPServerInfo] = field(default_factory=list)

    def to_j2_context(self) -> dict:
        """Flatten profile into Jinja2-compatible template context."""
        return {
            "profile_frameworks": [
                {
                    "name": fw.name,
                    "category": fw.category,
                    "guidance": fw.guidance,
                    "version_hint": fw.version_hint,
                }
                for fw in self.frameworks
            ],
            "profile_tools": [
                {
                    "name": t.name,
                    "command": t.command,
                    "category": t.category,
                }
                for t in self.tools
            ],
            "profile_structure": {
                "has_src_dir": self.structure.has_src_dir,
                "has_tests_dir": self.structure.has_tests_dir,
                "has_docs_dir": self.structure.has_docs_dir,
                "has_scripts_dir": self.structure.has_scripts_dir,
                "has_web_files": self.structure.has_web_files,
                "entry_points": self.structure.entry_points,
                "key_dirs": self.structure.key_dirs,
            },
            "profile_has_frameworks": len(self.frameworks) > 0,
            "profile_has_tools": len(self.tools) > 0,
            "profile_mcp_servers": [
                {
                    "name": s.name,
                    "type": s.type,
                    "command": s.command,
                    "url": s.url,
                    "environment": s.environment,
                    "description": s.description,
                    "disabled": s.disabled,
                }
                for s in self.mcp_servers
            ],
            "profile_has_mcp_servers": len(self.mcp_servers) > 0,
        }

    def get_tool(self, name: str) -> ToolCommand | None:
        """Find a tool by name (case-insensitive)."""
        for t in self.tools:
            if t.name.lower() == name.lower():
                return t
        return None

    def get_frameworks_by_category(self, category: str) -> list[FrameworkInfo]:
        """Get all frameworks of a given category."""
        return [fw for fw in self.frameworks if fw.category == category]
