"""Tests for the skill registry module."""

from __future__ import annotations

from pathlib import Path

from n3rverberage.init.registry import (
    SkillEntry,
    SkillRegistry,
    _parse_frontmatter,
    write_registry,
)

# --------------------------------------------------------------------------- #
# _parse_frontmatter
# --------------------------------------------------------------------------- #


def test_parse_frontmatter_with_valid_yaml():
    content = "---\nname: my-skill\ndescription: Does things\n---\n\n## Body"
    fm, body = _parse_frontmatter(content)
    assert fm["name"] == "my-skill"
    assert fm["description"] == "Does things"
    assert body.startswith("## Body")


def test_parse_frontmatter_no_frontmatter():
    content = "## Just a body"
    fm, body = _parse_frontmatter(content)
    assert fm == {}
    assert body == content


def test_parse_frontmatter_malformed_yaml():
    content = "---\n: bad: yaml: :\n---\n\nbody"
    fm, body = _parse_frontmatter(content)
    assert fm == {}


def test_parse_frontmatter_hub_skill_ids_list():
    content = "---\nname: sdd-apply\ndescription: Apply task\nhub-skill-ids: [implementation, plan-execution]\n---\n"
    fm, _ = _parse_frontmatter(content)
    assert fm["hub-skill-ids"] == ["implementation", "plan-execution"]


# --------------------------------------------------------------------------- #
# SkillRegistry.scan
# --------------------------------------------------------------------------- #

SKILL_CONTENT = """\
---
name: test-skill
description: A test skill
when_to_use: When you want to test things
model: low
hub-skill-ids: [review, reasoning]
---

## Goal

Do the thing.
"""

SKILL_NO_FRONTMATTER = "## Just a plain markdown skill\n\nNo YAML here."

SKILL_MISSING_DESCRIPTION = "---\nname: no-desc\n---\n\n## Body"


def _make_skill_dir(tmp_path: Path, subpath: str, content: str) -> Path:
    skill_dir = tmp_path / subpath
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def test_scan_finds_valid_skills(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.name == "test-skill"
    assert entry.description == "A test skill"
    assert entry.model == "low"
    assert entry.hub_skill_ids == ["review", "reasoning"]


def test_scan_skips_no_frontmatter(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/plain-skill", SKILL_NO_FRONTMATTER)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 0


def test_scan_skips_missing_description(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/no-desc", SKILL_MISSING_DESCRIPTION)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 0


def test_scan_empty_dir(tmp_path: Path):
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 0


def test_scan_multiple_skills(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/skill-a", SKILL_CONTENT)
    content_b = SKILL_CONTENT.replace("test-skill", "skill-b").replace("A test skill", "Skill B")
    _make_skill_dir(tmp_path, ".opencode/skills/skill-b", content_b)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 2


def test_scan_deduplicates_symlinks(tmp_path: Path):
    original = _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    link_dir = tmp_path / ".github" / "skills" / "test-skill"
    link_dir.mkdir(parents=True)
    link = link_dir / "SKILL.md"
    link.symlink_to(original)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 1


# --------------------------------------------------------------------------- #
# SkillRegistry.find_by_skill_id
# --------------------------------------------------------------------------- #


def test_find_by_skill_id_match(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    results = registry.find_by_skill_id("review")
    assert len(results) == 1
    assert results[0].name == "test-skill"


def test_find_by_skill_id_no_match(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    results = registry.find_by_skill_id("implementation")
    assert results == []


def test_find_by_skill_id_empty_registry(tmp_path: Path):
    registry = SkillRegistry.scan(tmp_path)
    assert registry.find_by_skill_id("anything") == []


# --------------------------------------------------------------------------- #
# SkillEntry.as_context_item
# --------------------------------------------------------------------------- #


def test_as_context_item_structure(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    item = registry.entries[0].as_context_item()
    assert item["content"] == SKILL_CONTENT
    assert item["metadata"]["source"] == "skill"
    assert item["metadata"]["skill_name"] == "test-skill"
    assert "skill_path" in item["metadata"]


# --------------------------------------------------------------------------- #
# SkillRegistry.to_markdown
# --------------------------------------------------------------------------- #


def test_to_markdown_empty():
    registry = SkillRegistry([])
    md = registry.to_markdown()
    assert "_No agentskills.io skills found._" in md


def test_to_markdown_with_entries(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    md = registry.to_markdown()
    assert "test-skill" in md
    assert "review, reasoning" in md
    assert "| Name |" in md


def test_to_markdown_truncates_long_descriptions():
    long_desc = "x" * 100
    entry = SkillEntry(
        name="long-skill",
        description=long_desc,
        path=Path("/fake/SKILL.md"),
        raw_content="",
    )
    registry = SkillRegistry([entry])
    md = registry.to_markdown()
    assert "…" in md


# --------------------------------------------------------------------------- #
# Dual-path scan (org-level)
# --------------------------------------------------------------------------- #


def test_scan_with_shared_skills(tmp_path: Path):
    """When org_root is provided, shared skills are loaded alongside local."""
    # Shared skill
    _make_skill_dir(
        tmp_path,
        ".opencode/shared/skills/shared-code",
        "---\nname: shared-code\ndescription: Shared coding skill\n---\n",
    )
    # Local skill
    _make_skill_dir(
        tmp_path,
        ".opencode/skills/local-code",
        "---\nname: local-code\ndescription: Local coding skill\n---\n",
    )
    registry = SkillRegistry.scan(tmp_path, org_root=tmp_path)
    assert len(registry.entries) == 2
    names = {e.name: e.origin for e in registry.entries}
    assert names["shared-code"] == "shared"
    assert names["local-code"] == "local"


def test_scan_local_overrides_shared_by_name(tmp_path: Path):
    """When a local skill has the same name as a shared one, local wins."""
    # Shared skill
    _make_skill_dir(
        tmp_path,
        ".opencode/shared/skills/dup-skill",
        "---\nname: dup-skill\ndescription: Shared version\n---\n",
    )
    # Local skill with same name
    _make_skill_dir(
        tmp_path,
        ".opencode/skills/dup-skill",
        "---\nname: dup-skill\ndescription: Local version\n---\n",
    )
    registry = SkillRegistry.scan(tmp_path, org_root=tmp_path)
    assert len(registry.entries) == 1
    assert registry.entries[0].description == "Local version"
    assert registry.entries[0].origin == "local"


def test_scan_without_org_root_is_backward_compat(tmp_path: Path):
    """Scan without org_root does NOT load shared skills."""
    _make_skill_dir(
        tmp_path,
        ".opencode/shared/skills/shared-code",
        "---\nname: shared-code\ndescription: Shared\n---\n",
    )
    registry = SkillRegistry.scan(tmp_path)
    # Shared dir is NOT under .opencode/skills/, so it's ignored
    assert len(registry.entries) == 0


def test_scan_shared_skills_dir_not_found(tmp_path: Path):
    """When shared dir doesn't exist, scan proceeds with local only."""
    _make_skill_dir(
        tmp_path,
        ".opencode/skills/local-code",
        "---\nname: local-code\ndescription: Local\n---\n",
    )
    registry = SkillRegistry.scan(tmp_path, org_root=tmp_path)
    assert len(registry.entries) == 1
    assert registry.entries[0].name == "local-code"


def test_write_registry_with_org_root(tmp_path: Path):
    """write_registry passes org_root through to scan."""
    _make_skill_dir(
        tmp_path,
        ".opencode/shared/skills/shared-code",
        "---\nname: shared-code\ndescription: Shared\n---\n",
    )
    out = write_registry(tmp_path, org_root=tmp_path)
    content = out.read_text()
    assert "shared" in content.lower()
    assert "Origin" in content


def test_scan_origin_field_present(tmp_path: Path):
    """Every scanned entry has an origin field."""
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    registry = SkillRegistry.scan(tmp_path)
    assert len(registry.entries) == 1
    assert registry.entries[0].origin == "local"


# --------------------------------------------------------------------------- #
# write_registry
# --------------------------------------------------------------------------- #


def test_write_registry_creates_file(tmp_path: Path):
    _make_skill_dir(tmp_path, ".opencode/skills/test-skill", SKILL_CONTENT)
    out = write_registry(tmp_path)
    assert out.exists()
    assert out.name == "skill-registry.md"
    assert out.parent.name == ".n3rverberage"
    content = out.read_text()
    assert "test-skill" in content


def test_write_registry_empty_project(tmp_path: Path):
    out = write_registry(tmp_path)
    assert out.exists()
    content = out.read_text()
    assert "_No agentskills.io skills found._" in content
