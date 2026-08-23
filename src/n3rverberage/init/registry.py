"""Skill registry: scans agentskills.io SKILL.md files and generates a compact registry."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("n3rverberage.registry")

_SKILL_DIRS = [
    ".opencode/skills",
]

_SHARED_SKILL_DIRS = [
    ".opencode/shared/skills",
]


class SkillEntry(BaseModel):
    """A single agentskills.io skill parsed from a SKILL.md file."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    when_to_use: str = ""
    model: str = "medium"
    hub_skill_ids: list[str] = Field(default_factory=list)
    path: Path
    raw_content: str
    origin: str = "local"

    def as_context_item(self) -> dict:
        return {
            "content": self.raw_content,
            "metadata": {
                "source": "skill",
                "skill_name": self.name,
                "skill_path": str(self.path),
                "origin": self.origin,
            },
        }


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_yaml = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        logger.debug("YAML parse error in skill frontmatter: %s", exc)
        return {}, text
    return data if isinstance(data, dict) else {}, body


def _load_skill(path: Path) -> SkillEntry | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("cannot read skill file %s: %s", path, exc)
        return None

    frontmatter, _ = _parse_frontmatter(text)
    name = frontmatter.get("name") or path.parent.name
    description = frontmatter.get("description", "")
    if not name or not description:
        return None

    raw_hub_ids = frontmatter.get("hub-skill-ids", [])
    hub_skill_ids = raw_hub_ids if isinstance(raw_hub_ids, list) else []

    return SkillEntry(
        name=str(name),
        description=str(description),
        when_to_use=str(frontmatter.get("when_to_use", "")),
        model=str(frontmatter.get("model", "medium")),
        hub_skill_ids=[str(s) for s in hub_skill_ids],
        path=path,
        raw_content=text,
    )


class SkillRegistry:
    """Registry of available agentskills.io skills for a project."""

    def __init__(self, entries: list[SkillEntry]) -> None:
        self.entries = entries

    @classmethod
    def scan(cls, root: Path, org_root: Path | None = None) -> SkillRegistry:
        entries: list[SkillEntry] = []
        seen_paths: set[str] = set()
        seen_names: set[str] = set()

        # Phase 1: shared skills (lower priority) — only when org_root provided
        if org_root is not None:
            for skill_dir in [org_root / d for d in _SHARED_SKILL_DIRS]:
                if not skill_dir.is_dir():
                    continue
                for skill_file in sorted(skill_dir.rglob("SKILL.md")):
                    path_key = skill_file.resolve().as_posix()
                    if path_key in seen_paths:
                        continue
                    seen_paths.add(path_key)
                    entry = _load_skill(skill_file)
                    if entry is None:
                        continue
                    if entry.name in seen_names:
                        continue
                    seen_names.add(entry.name)
                    entry = entry.model_copy(update={"origin": "shared"})
                    entries.append(entry)

        # Phase 2: local skills (higher priority — overrides shared by name)
        for skill_dir in [root / d for d in _SKILL_DIRS]:
            if not skill_dir.is_dir():
                continue
            for skill_file in sorted(skill_dir.rglob("SKILL.md")):
                path_key = skill_file.resolve().as_posix()
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)
                entry = _load_skill(skill_file)
                if entry is None:
                    continue
                if entry.name in seen_names:
                    # Local overrides shared — remove old, insert new
                    entries = [e for e in entries if e.name != entry.name]
                seen_names.add(entry.name)
                entry = entry.model_copy(update={"origin": "local"})
                entries.append(entry)
                logger.debug("registered skill %s from %s", entry.name, skill_file)

        logger.info("skill registry: %d skills loaded", len(entries))
        return cls(entries)

    def find_by_skill_id(self, skill_id: str) -> list[SkillEntry]:
        return [e for e in self.entries if skill_id in e.hub_skill_ids]

    def to_markdown(self) -> str:
        lines = [
            "# Skill Registry",
            "",
            "<!-- generated by n3rverberage — do not edit manually -->",
            "",
        ]
        if not self.entries:
            lines.append("_No agentskills.io skills found._")
            return "\n".join(lines)

        lines += [
            "| Name | Description | When to Use | Model | Origin | Hub Skill IDs |",
            "|------|-------------|-------------|-------|--------|---------------|",
        ]
        for e in self.entries:
            hub_ids = ", ".join(e.hub_skill_ids) if e.hub_skill_ids else "—"
            when = e.when_to_use[:60] + "…" if len(e.when_to_use) > 60 else e.when_to_use
            desc = e.description[:60] + "…" if len(e.description) > 60 else e.description
            lines.append(f"| `{e.name}` | {desc} | {when} | {e.model} | {e.origin} | {hub_ids} |")

        return "\n".join(lines) + "\n"


def write_registry(root: Path, org_root: Path | None = None) -> Path:
    registry = SkillRegistry.scan(root, org_root=org_root)
    out = root / ".n3rverberage" / "skill-registry.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(registry.to_markdown(), encoding="utf-8")
    logger.info("skill registry written to %s (%d skills)", out, len(registry.entries))
    return out
