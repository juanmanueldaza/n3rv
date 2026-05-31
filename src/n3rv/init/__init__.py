"""Init module for project scaffolding."""

from __future__ import annotations

import shutil
from pathlib import Path

from n3rv.init.analyzer import analyze_project
from n3rv.init.context import ProjectContext
from n3rv.init.detector import detect_stack
from n3rv.init.registry import write_registry
from n3rv.init.renderer import TemplateEngine
from n3rv.init.writer import (
    WriteResult,
    configure_git_hooks,
    write_file,
)

FILE_MANIFEST = [
    ("n3rv/a2a-config.yaml.j2", ".n3rv/a2a-config.yaml", False, False),
    (
        "n3rv/systemd/n3rv-hub.service.j2",
        ".n3rv/systemd/n3rv-hub.service",
        False,
        False,
    ),
    ("opencode.json.j2", "opencode.json", False, False),
    ("githooks/pre-push.py.j2", ".githooks/pre-push", False, True),
    # Docs
    ("CONTRIBUTING.md.j2", "CONTRIBUTING.md", False, False),
    ("SECURITY.md.j2", "SECURITY.md", False, False),
    # Plugins
    (
        "opencode/plugins/n3rv-lifecycle.js.j2",
        ".opencode/plugins/n3rv-lifecycle.js",
        False,
        False,
    ),
    (
        "opencode/plugins/n3rv-shell-env.js.j2",
        ".opencode/plugins/n3rv-shell-env.js",
        False,
        False,
    ),
    # Custom tools
    (
        "opencode/tools/n3rv-stats.ts.j2",
        ".opencode/tools/n3rv-stats.ts",
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
    # SDD phase sub-agents
    (
        "opencode/agents/sdd-explorer.md.j2",
        ".opencode/agents/sdd-explorer.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-proposer.md.j2",
        ".opencode/agents/sdd-proposer.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-speccer.md.j2",
        ".opencode/agents/sdd-speccer.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-designer.md.j2",
        ".opencode/agents/sdd-designer.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-task-planner.md.j2",
        ".opencode/agents/sdd-task-planner.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-verifier.md.j2",
        ".opencode/agents/sdd-verifier.md",
        False,
        False,
    ),
    (
        "opencode/agents/sdd-archiver.md.j2",
        ".opencode/agents/sdd-archiver.md",
        False,
        False,
    ),
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
    # N3RV primary agent (user-facing entry point)
    ("opencode/agents/n3rv.md.j2", ".opencode/agents/n3rv.md", False, False),
]


def run_init(
    root: Path,
    project_name: str | None,
    stack_override: str | None,
    force: bool,
) -> int:
    try:
        stack_info = detect_stack(root, stack_override=stack_override)
        final_project_name = project_name or stack_info.project_name

        context = ProjectContext.build(
            project_name=final_project_name,
            stack=stack_info.stack,
            project_root=root,
        )

        print(f"Detected: {stack_info.stack.value} ({stack_info.project_name})")

        n3rv_binary = shutil.which("n3rv")
        if not n3rv_binary:
            print("✗ Error: nerv binary not found in PATH")
            return 1

        templates_dir = Path(__file__).parent / "templates"
        engine = TemplateEngine(templates_dir)

        profile = analyze_project(root, context)
        render_ctx = {
            **context.to_dict(),
            **profile.to_j2_context(),
            "n3rv_binary": n3rv_binary,
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
                content = engine.render(template_name, render_ctx)
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

        try:
            registry_path = write_registry(root)
            print(f"✓ Updated {registry_path.relative_to(root)}")
        except Exception as exc:
            print(f"⚠ Skill registry not written: {exc}")

        print(f"\nDone. {created_count} files created/updated, {skipped_count} skipped.")
        if error_count > 0:
            print(f"⚠ {error_count} errors occurred")
            return 1

        print("N3RV is configured. Work inside opencode.")
        print("Next: Run 'n3rv daemon install' to set up the hub as a background service.")
        return 0

    except Exception as exc:
        print(f"✗ Fatal error: {exc}")
        return 1
