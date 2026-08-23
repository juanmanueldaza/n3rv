"""Init module for project scaffolding."""

from __future__ import annotations

import shutil
from pathlib import Path

from n3rverberage.init.analyzer import analyze_project
from n3rverberage.init.context import ProjectContext
from n3rverberage.init.detector import detect_stack
from n3rverberage.init.registry import write_registry
from n3rverberage.init.renderer import TemplateEngine
from n3rverberage.init.writer import (
    WriteResult,
    configure_git_hooks,
    configure_gitignore,
    write_file,
)

NERV_DIR = Path(".nerv")


def _check_nerv_migration(root: Path) -> bool:
    """Detect old .nerv/ directory and prompt user for migration."""
    nerv_path = root / NERV_DIR
    if not nerv_path.exists():
        return True

    print()
    print("!" * 58)
    print("!!  WARNING: Old nerv project detected               !!")
    print("!" * 58)
    print(f"!!  Found {NERV_DIR}/ - created by the old nerv CLI    !!")
    print("!!  (now renamed to n3rverberage).                           !!")
    print("!" * 58)
    print()
    print("n3rverberage can delete the old .nerv/ files and")
    print("initialize fresh n3rverberage-generated files.")
    print()
    print("  [1] Migrate - delete .nerv/ and init fresh")
    print("  [2] Keep - abort, keep using nerv")
    print()

    while True:
        try:
            choice = input("Choose [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if choice == "1":
            print()
            shutil.rmtree(nerv_path, ignore_errors=True)
            if nerv_path.exists():
                print(f"! Could not fully remove {NERV_DIR}/ - some files may remain.")
            else:
                print(f"Removed {NERV_DIR}/.")
            print()
            return True
        elif choice == "2":
            print()
            print("Aborting. Keeping existing nerv setup.")
            return False
        print("Please enter 1 or 2.")


# ──────────────────────────────────────────────
# SDD phase sub-agent metadata
# Shared template: opencode/agents/sdd-phase.md.j2
# Each entry maps an output path stem → template context
# ──────────────────────────────────────────────

SDD_PHASE_MAP: dict[str, dict] = {
    "sdd-explorer": {
        "phase_description": "Explore codebase to build context for a planned SDD change. Read-only investigation.",
        "phase_model": "opencode-go/deepseek-v4-pro",
        "phase_skill": "sdd-explore",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Read the change description from context",
            "2. Search memory for prior context on this topic",
            "3. Identify relevant files, modules, directories",
            "4. Read interfaces (not implementation details)",
            "5. Note patterns, conventions, dependencies, test coverage, risks",
        ],
        "phase_save_title": "SDD Explore: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-context",
        "phase_save_type": "context",
    },
    "sdd-proposer": {
        "phase_description": (
            "Propose 2-3 solution approaches, evaluate trade-offs, and recommend one for an SDD change."
        ),
        "phase_model": "opencode-go/deepseek-v4-pro",
        "phase_skill": "sdd-propose",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Load context from memory: topic_key=`sdd-<change_id>-context`",
            "2. Generate 2-3 distinct approaches with trade-offs",
            "3. Recommend one with rationale",
        ],
        "phase_save_title": "SDD Proposal: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-proposal",
        "phase_save_type": "decision",
    },
    "sdd-speccer": {
        "phase_description": "Write a formal spec with goals, acceptance criteria, and constraints for an SDD change.",
        "phase_model": "opencode-go/deepseek-v4-pro",
        "phase_skill": "sdd-spec",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Load proposal from memory: topic_key=`sdd-<change_id>-proposal`",
            "2. Write structured spec: goals, non-goals, acceptance criteria, constraints, out of scope",
            "3. Every acceptance criterion must be testable (binary pass/fail)",
        ],
        "phase_save_title": "SDD Spec: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-spec",
        "phase_save_type": "context",
    },
    "sdd-designer": {
        "phase_description": "Write technical design for an SDD change: components, interfaces, data flow, edge cases.",
        "phase_model": "opencode-go/deepseek-v4-pro",
        "phase_skill": "sdd-design",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Load spec from memory: topic_key=`sdd-<change_id>-spec`",
            "2. Load proposal from memory: topic_key=`sdd-<change_id>-proposal`",
            "3. Read relevant source files to ground design in codebase",
            "4. Produce technical design: components, interfaces, data flow, error handling, edge cases",
            "5. Design must be traceable to spec acceptance criteria",
        ],
        "phase_save_title": "SDD Design: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-design",
        "phase_save_type": "architecture",
    },
    "sdd-task-planner": {
        "phase_description": "Break SDD design into ordered list of atomic, reviewable implementation tasks.",
        "phase_model": "opencode-go/qwen3.5-plus",
        "phase_skill": "sdd-tasks",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Load design from memory: topic_key=`sdd-<change_id>-design`",
            "2. Load spec from memory: topic_key=`sdd-<change_id>-spec`",
            "3. Break into atomic tasks (each independently reviewable)",
            "4. Order tasks so earlier ones unblock later ones",
            "5. Every spec acceptance criterion covered by at least one task",
        ],
        "phase_save_title": "SDD Tasks: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-tasks",
        "phase_save_type": "context",
    },
    "sdd-verifier": {
        "phase_description": "Verify implementation against spec acceptance criteria. Produces pass/fail verdict.",
        "phase_model": "opencode-go/kimi-k2.6",
        "phase_skill": "sdd-verify",
        "phase_edit_denied": False,
        "phase_steps": [
            "1. Load spec from memory: topic_key=`sdd-<change_id>-spec`",
            "2. Load implementation notes from memory: topic_key=`sdd-<change_id>-impl`",
            "3. For each acceptance criterion: read code, run tests, mark PASS/FAIL/PARTIAL with evidence",
            "4. Run full test suite for regression check",
        ],
        "phase_save_title": "SDD Verify: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-verify",
        "phase_save_type": "context",
    },
    "sdd-archiver": {
        "phase_description": "Archive all SDD artifacts into a single completed record in memory.",
        "phase_model": "opencode-go/qwen3.5-plus",
        "phase_skill": "sdd-archive",
        "phase_edit_denied": True,
        "phase_steps": [
            "1. Load all phase artifacts from memory (context, proposal, spec, design, tasks, impl, verify)",
            "2. Write consolidated archive entry",
        ],
        "phase_save_title": "SDD Complete: <change_id>",
        "phase_save_topic_key": "sdd-<change_id>-done",
        "phase_save_type": "summary",
    },
}

SDD_PHASE_SLUGS = list(SDD_PHASE_MAP.keys())
SDD_PHASE_TEMPLATE = "opencode/agents/sdd-phase.md.j2"

# Build manifest entries dynamically from phase data
_SDD_MANIFEST_ENTRIES = [(SDD_PHASE_TEMPLATE, f".opencode/agents/{slug}.md", False, False) for slug in SDD_PHASE_SLUGS]

FILE_MANIFEST = [
    ("n3rverberage/a2a-config.yaml.j2", ".n3rverberage/a2a-config.yaml", False, False),
    (
        "n3rverberage/systemd/n3rverberage-hub.service.j2",
        ".n3rverberage/systemd/n3rverberage-hub.service",
        False,
        False,
    ),
    ("opencode.json.j2", "opencode.json", False, False),
    ("opencode.template.json.j2", "opencode.template.json", False, False),
    ("githooks/pre-push.py.j2", ".githooks/pre-push", False, True),
    # Plugins
    (
        "opencode/plugins/n3rverberage-lifecycle.js.j2",
        ".opencode/plugins/n3rverberage-lifecycle.js",
        False,
        False,
    ),
    (
        "opencode/plugins/n3rverberage-shell-env.js.j2",
        ".opencode/plugins/n3rverberage-shell-env.js",
        False,
        False,
    ),
    # Shared module (must be written before tools/plugins that import it)
    (
        "opencode/shared/rpc.js.j2",
        ".opencode/shared/rpc.js",
        False,
        False,
    ),
    # Custom tools
    (
        "opencode/tools/n3rverberage-stats.ts.j2",
        ".opencode/tools/n3rverberage-stats.ts",
        False,
        False,
    ),
    ("opencode/package.json.j2", ".opencode/package.json", False, False),
    # Skills (opencode-native path)
    (
        "opencode/skills/code/SKILL.md.j2",
        ".opencode/skills/code/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/testing/SKILL.md.j2",
        ".opencode/skills/testing/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/commits/SKILL.md.j2",
        ".opencode/skills/commits/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-explore/SKILL.md.j2",
        ".opencode/skills/sdd-explore/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-propose/SKILL.md.j2",
        ".opencode/skills/sdd-propose/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-spec/SKILL.md.j2",
        ".opencode/skills/sdd-spec/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-design/SKILL.md.j2",
        ".opencode/skills/sdd-design/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-tasks/SKILL.md.j2",
        ".opencode/skills/sdd-tasks/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-apply/SKILL.md.j2",
        ".opencode/skills/sdd-apply/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-verify/SKILL.md.j2",
        ".opencode/skills/sdd-verify/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/sdd-archive/SKILL.md.j2",
        ".opencode/skills/sdd-archive/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/judgment-day/SKILL.md.j2",
        ".opencode/skills/judgment-day/SKILL.md",
        False,
        False,
    ),
    # Slash commands
    ("opencode/commands/sdd-new.md.j2", ".opencode/commands/sdd-new.md", False, False),
    (
        "opencode/commands/judgment-day.md.j2",
        ".opencode/commands/judgment-day.md",
        False,
        False,
    ),
    ("opencode/commands/review.md.j2", ".opencode/commands/review.md", False, False),
    ("opencode/commands/handoff.md.j2", ".opencode/commands/handoff.md", False, False),
    (
        "opencode/commands/new-satellite.md.j2",
        ".opencode/commands/new-satellite.md",
        False,
        False,
    ),
    # SDD phase sub-agents (generated from SDD_PHASE_MAP)
    *_SDD_MANIFEST_ENTRIES,
    # Git & GitHub sub-agents
    ("opencode/agents/git-ops.md.j2", ".opencode/agents/git-ops.md", False, False),
    (
        "opencode/agents/github-ops.md.j2",
        ".opencode/agents/github-ops.md",
        False,
        False,
    ),
    # Git & GitHub skills
    (
        "opencode/skills/git-ops/SKILL.md.j2",
        ".opencode/skills/git-ops/SKILL.md",
        False,
        False,
    ),
    (
        "opencode/skills/github-ops/SKILL.md.j2",
        ".opencode/skills/github-ops/SKILL.md",
        False,
        False,
    ),
    # N3RVERBERAGE primary agent (user-facing entry point)
    ("opencode/agents/n3rverberage.md.j2", ".opencode/agents/n3rverberage.md", False, False),
    # Project board management
    (
        "opencode/agents/project-ops.md.j2",
        ".opencode/agents/project-ops.md",
        False,
        False,
    ),
    (
        "opencode/skills/project-board/SKILL.md.j2",
        ".opencode/skills/project-board/SKILL.md",
        False,
        False,
    ),
]


N3RV_DIR = Path(".n3rv")


def _check_n3rv_migration(root: Path) -> bool:
    """Detect old .n3rv/ directory and prompt user for migration."""
    old_path = root / N3RV_DIR
    new_path = root / ".n3rverberage"
    if not old_path.exists() or new_path.exists():
        return True

    print()
    print("!" * 58)
    print("!!  WARNING: Old n3rv project detected               !!")
    print("!" * 58)
    print(f"!!  Found {N3RV_DIR}/ using the old n3rv naming.         !!")
    print("!!  (now renamed to n3rverberage).                         !!")
    print("!" * 58)
    print()
    print("n3rverberage will delete the old .n3rv/ files and")
    print("initialize fresh n3rverberage-generated files.")
    print()
    print("  [1] Migrate - delete .n3rv/ and init fresh")
    print("  [2] Keep - abort, keep using n3rv")
    print()

    while True:
        try:
            choice = input("Choose [1/2]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if choice == "1":
            print()
            shutil.rmtree(old_path, ignore_errors=True)
            if old_path.exists():
                print(f"! Could not fully remove {N3RV_DIR}/ - some files may remain.")
            else:
                print(f"Removed {N3RV_DIR}/.")
            print()
            return True
        elif choice == "2":
            print()
            print("Aborting. Keeping existing n3rv setup.")
            return False
        print("Please enter 1 or 2.")


def run_init(
    root: Path,
    project_name: str | None,
    stack_override: str | None,
    force: bool,
) -> int:
    try:
        if not _check_nerv_migration(root) and not force:
            return 0
        if not _check_n3rv_migration(root) and not force:
            return 0

        stack_info = detect_stack(root, stack_override=stack_override)
        final_project_name = project_name or stack_info.project_name

        context = ProjectContext.build(
            project_name=final_project_name,
            stack=stack_info.stack,
            project_root=root,
        )

        print(f"Detected: {stack_info.stack.value} ({stack_info.project_name})")

        n3rverberage_binary = shutil.which("n3rverberage")
        if not n3rverberage_binary:
            print("✗ Error: n3rverberage binary not found in PATH")
            return 1

        templates_dir = Path(__file__).parent / "templates"
        user_overrides_dir = root / ".n3rverberage" / "template-overrides"
        engine = TemplateEngine(templates_dir, user_overrides_dir=user_overrides_dir)

        profile = analyze_project(root, context)
        render_ctx = {
            **context.to_dict(),
            **profile.to_j2_context(),
            "n3rverberage_binary": n3rverberage_binary,
        }

        created_count = 0
        skipped_count = 0
        error_count = 0

        # Scaffold AGENTS.md via Jinja2 template
        try:
            agents_md = root / "AGENTS.md"
            existed = agents_md.exists()
            if existed and not force:
                print("⊘ Skipped AGENTS.md (already exists)")
                skipped_count += 1
            else:
                content = engine.render("opencode/agents.md.j2", render_ctx)
                result = write_file(
                    agents_md,
                    content,
                    force=force,
                    use_markers=True,
                )
                if result in (WriteResult.CREATED, WriteResult.OVERWRITTEN):
                    print("✓ Created AGENTS.md")
                    created_count += 1
                elif result == WriteResult.UPDATED:
                    print("✓ Updated AGENTS.md")
                    created_count += 1
        except Exception as exc:
            print(f"✗ Error scaffolding AGENTS.md: {exc}")
            error_count += 1

        # Append dynamic command entries based on detected tools
        dynamic_entries = []
        for tool in profile.tools:
            template_name = f"opencode/commands/{tool.name}.md.j2"
            output_path = f".opencode/commands/{tool.name}.md"
            template_path = templates_dir / template_name
            if template_path.exists():
                dynamic_entries.append((template_name, output_path, False, False))

        all_manifest_entries = list(FILE_MANIFEST) + dynamic_entries

        for (
            template_name,
            output_path,
            use_markers,
            make_executable,
        ) in all_manifest_entries:
            try:
                # Merge phase-specific context for SDD agents
                entry_ctx = dict(render_ctx)
                if template_name == SDD_PHASE_TEMPLATE:
                    phase_key = Path(output_path).stem
                    phase_data = SDD_PHASE_MAP.get(phase_key, {})
                    entry_ctx.update(phase_data)

                content = engine.render(template_name, entry_ctx)
                target = root / output_path
                result = write_file(
                    target,
                    content,
                    force=force,
                    use_markers=use_markers,
                    make_executable=make_executable,
                )

                if result == WriteResult.CREATED:
                    print(f"✓ Created {output_path}")
                    created_count += 1
                elif result == WriteResult.UPDATED:
                    print(f"✓ Updated {output_path}")
                    created_count += 1
                elif result == WriteResult.OVERWRITTEN:
                    print(f"✓ Overwritten {output_path}")
                    created_count += 1
                elif result == WriteResult.SKIPPED:
                    print(f"⊘ Skipped {output_path} (already exists)")
                    skipped_count += 1

            except Exception as exc:
                print(f"✗ Error {output_path}: {exc}")
                error_count += 1

        if configure_git_hooks(root):
            print("✓ Configured git hooks")
        else:
            print("⚠ Warning: No .git directory found, skipping git hooks config")

        if configure_gitignore(root):
            print("✓ Added n3rverberage patterns to .gitignore")
        else:
            pass  # already present or no git repo

        try:
            registry_path = write_registry(root)
            print(f"✓ Updated {registry_path.relative_to(root)}")
        except Exception as exc:
            print(f"⚠ Skill registry not written: {exc}")

        print(f"\nDone. {created_count} files created/updated, {skipped_count} skipped.")
        if error_count > 0:
            print(f"⚠ {error_count} errors occurred")
            return 1

        print("N3RVERBERAGE is configured. Work inside opencode.")
        print("Next: Run 'n3rverberage daemon install' to set up the hub as a background service.")
        return 0

    except Exception as exc:
        print(f"✗ Fatal error: {exc}")
        return 1
