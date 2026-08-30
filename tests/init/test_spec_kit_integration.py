"""Tests for the spec-kit integration in n3rv init scaffolding."""

from __future__ import annotations

from pathlib import Path

from n3rv.init import FILE_MANIFEST, run_init


def _manifest_output_paths() -> list[str]:
    """Extract output target paths from the FILE_MANIFEST."""
    return [entry[1] for entry in FILE_MANIFEST]


def test_spec_kit_templates_registered_in_manifest():
    """The spec-kit templates and skills must be present in the manifest."""
    outputs = _manifest_output_paths()

    expected = [
        ".opencode/commands/spec-kit.md",
        ".opencode/skills/sdd-spec-kit-spec/SKILL.md",
        ".opencode/skills/sdd-spec-kit-plan/SKILL.md",
        ".opencode/skills/sdd-spec-kit-tasks/SKILL.md",
        ".specify/templates/spec-template.md",
        ".specify/templates/plan-template.md",
        ".specify/templates/tasks-template.md",
        ".specify/templates/constitution-template.md",
        ".specify/templates/checklist-template.md",
        ".specify/templates/NOTICE.md",
    ]

    for path in expected:
        assert path in outputs, f"Missing spec-kit manifest entry: {path}"


def test_spec_kit_template_files_exist():
    """The bundled spec-kit template files must exist in the templates dir."""
    templates_root = Path(__file__).parents[2] / "src" / "n3rv" / "init" / "templates"

    expected_templates = [
        "spec-template.md.j2",
        "plan-template.md.j2",
        "tasks-template.md.j2",
        "constitution-template.md.j2",
        "checklist-template.md.j2",
        "specify-templates-NOTICE.md.j2",
        "opencode/commands/spec-kit.md.j2",
        "opencode/skills/sdd-spec-kit-spec/SKILL.md.j2",
        "opencode/skills/sdd-spec-kit-plan/SKILL.md.j2",
        "opencode/skills/sdd-spec-kit-tasks/SKILL.md.j2",
    ]

    for rel in expected_templates:
        t = templates_root / rel
        assert t.exists(), f"Missing template file: {rel}"


def test_init_creates_spec_kit_files(tmp_path: Path):
    """Full init must create the spec-kit integration files."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    exit_code = run_init(tmp_path, project_name=None, stack_override=None, force=True)

    assert exit_code == 0

    expected_files = [
        ".opencode/commands/spec-kit.md",
        ".opencode/skills/sdd-spec-kit-spec/SKILL.md",
        ".opencode/skills/sdd-spec-kit-plan/SKILL.md",
        ".opencode/skills/sdd-spec-kit-tasks/SKILL.md",
        ".specify/templates/spec-template.md",
        ".specify/templates/plan-template.md",
        ".specify/templates/tasks-template.md",
        ".specify/templates/constitution-template.md",
        ".specify/templates/checklist-template.md",
        ".specify/templates/NOTICE.md",
    ]

    for file_path in expected_files:
        assert (tmp_path / file_path).exists(), f"Missing init output: {file_path}"


def test_adopted_templates_match_canonical_spec_kit_content():
    """The bundled spec-kit templates must match spec-kit's canonical content.

    This verifies the core promise of consuming spec-kit: n3rv scaffolds byte-
    compatible spec-kit templates rather than homebrew approximations. We assert
    on distinctive canonical marker strings from the upstream spec-kit core pack
    rather than the full file (which omits nothing but keeps the test focused).
    """
    templates_root = Path(__file__).parents[2] / "src" / "n3rv" / "init" / "templates"

    # (template file, distinctive canonical marker that must be present)
    expected_markers = [
        (
            "spec-template.md.j2",
            "## User Scenarios & Testing *(mandatory)*",
        ),
        (
            "spec-template.md.j2",
            "**FR-001**: System MUST [specific capability",
        ),
        (
            "plan-template.md.j2",
            "## Constitution Check",
        ),
        (
            "plan-template.md.j2",
            "## Complexity Tracking",
        ),
        (
            "tasks-template.md.j2",
            "## Phase 2: Foundational (Blocking Prerequisites)",
        ),
        (
            "tasks-template.md.j2",
            "## Format: `[ID] [P?] [Story] Description`",
        ),
        (
            "constitution-template.md.j2",
            "## Governance",
        ),
        (
            "checklist-template.md.j2",
            "**Marker Semantics**:",
        ),
    ]

    for rel, marker in expected_markers:
        content = (templates_root / rel).read_text()
        assert marker in content, f"'{marker}' missing from {rel}"

    # The canonical templates must contain no Jinja syntax so rendering is a no-op.
    for rel, _ in expected_markers:
        content = (templates_root / rel).read_text()
        assert "{{" not in content and "{%" not in content, f"{rel} has Jinja syntax"


def test_init_creates_canonical_content(tmp_path: Path):
    """Init output for spec-kit templates must preserve canonical content (no Jinja mangling)."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=True)

    spec = (tmp_path / ".specify/templates/spec-template.md").read_text()
    assert "## User Scenarios & Testing *(mandatory)*" in spec
    assert '**Input**: User description: "$ARGUMENTS"' in spec

    tasks = (tmp_path / ".specify/templates/tasks-template.md").read_text()
    assert "## Format: `[ID] [P?] [Story] Description`" in tasks

    notice = (tmp_path / ".specify/templates/NOTICE.md").read_text()
    assert "GitHub Spec Kit" in notice
    assert "MIT License" in notice


def test_spec_kit_skill_has_spec_sections(tmp_path: Path):
    """The generated spec-kit-spec skill references the canonical spec-kit spec structure."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=True)

    skill_path = tmp_path / ".opencode/skills/sdd-spec-kit-spec/SKILL.md"
    content = skill_path.read_text()

    for section in ["User Scenarios & Testing", "Edge Cases", "Requirements", "Success Criteria", "Assumptions"]:
        assert section in content, f"Missing '{section}' in spec-kit-spec skill"


def test_spec_kit_tasks_skill_has_phases(tmp_path: Path):
    """The generated spec-kit-tasks skill references all task phases."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testapp"')

    run_init(tmp_path, project_name=None, stack_override=None, force=True)

    skill_path = tmp_path / ".opencode/skills/sdd-spec-kit-tasks/SKILL.md"
    content = skill_path.read_text()

    for phase in ["Setup", "Foundational", "User Stories", "Polish"]:
        assert phase in content, f"Missing '{phase}' phase in spec-kit-tasks skill"
