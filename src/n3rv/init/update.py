"""Update orchestrator for n3rv update command."""

from __future__ import annotations

import difflib
import json
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from n3rv.init import N3RV_DIR, NERV_DIR, SDD_PHASE_MAP
from n3rv.init.analyzer import analyze_project
from n3rv.init.context import ProjectContext
from n3rv.init.detector import detect_stack
from n3rv.init.lockfile import (
    diff_lockfile,
    record_entry,
    save_lockfile,
    update_lockfile_entry,
)
from n3rv.init.registry import write_registry
from n3rv.init.renderer import TemplateEngine
from n3rv.init.writer import (
    MARKER_END,
    MARKER_START,
    configure_git_hooks,
    configure_gitignore,
    validate_markers,
    write_file,
)


class UpdateStrategy(StrEnum):
    """Strategy for updating files."""

    MARKER_MERGE = "marker_merge"
    JSON_MERGE = "json_merge"
    OVERWRITE = "overwrite"
    SKIP_DEFAULT = "skip_default"
    CREATE_IF_MISSING = "create_if_missing"


_ONLY_CATEGORY_ALIASES: dict[str, UpdateStrategy] = {
    "marker-merge": UpdateStrategy.MARKER_MERGE,
    "marker_merge": UpdateStrategy.MARKER_MERGE,
    "json-merge": UpdateStrategy.JSON_MERGE,
    "json_merge": UpdateStrategy.JSON_MERGE,
    "overwrite": UpdateStrategy.OVERWRITE,
    "skip-default": UpdateStrategy.SKIP_DEFAULT,
    "skip_default": UpdateStrategy.SKIP_DEFAULT,
    "create-if-missing": UpdateStrategy.CREATE_IF_MISSING,
    "create_if_missing": UpdateStrategy.CREATE_IF_MISSING,
}


@dataclass(frozen=True)
class UpdateEntry:
    """Entry in the file update manifest."""

    template_name: str
    output_path: str
    strategy: UpdateStrategy
    make_executable: bool = False


@dataclass
class UpdateResult:
    """Result of updating a single file."""

    path: str
    strategy: UpdateStrategy
    result: str
    warning: str | None = None


@dataclass
class UpdateSummary:
    """Summary of update operation."""

    results: list[UpdateResult] = field(default_factory=list)

    @property
    def updated_count(self) -> int:
        return sum(1 for r in self.results if r.result in ("CREATED", "UPDATED", "OVERWRITTEN"))

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.result == "SKIPPED")

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.result == "ERROR")


FILE_UPDATE_MANIFEST: list[UpdateEntry] = [
    UpdateEntry(
        "opencode/agents.md.j2",
        "AGENTS.md",
        UpdateStrategy.MARKER_MERGE,
    ),
    UpdateEntry("n3rv/a2a-config.yaml.j2", ".n3rv/a2a-config.yaml", UpdateStrategy.OVERWRITE),
    UpdateEntry(
        "n3rv/systemd/n3rv-hub.service.j2",
        ".n3rv/systemd/n3rv-hub.service",
        UpdateStrategy.OVERWRITE,
    ),
    UpdateEntry("opencode.json.j2", "opencode.json", UpdateStrategy.JSON_MERGE),
    UpdateEntry(
        "githooks/pre-push.py.j2",
        ".githooks/pre-push",
        UpdateStrategy.OVERWRITE,
        make_executable=True,
    ),
    # Shared module (must be written before tools/plugins that import it)
    UpdateEntry(
        "opencode/shared/rpc.js.j2",
        ".opencode/shared/rpc.js",
        UpdateStrategy.CREATE_IF_MISSING,
    ),
    # Plugins & tools (infrastructure — overwrite to keep in sync)
    UpdateEntry(
        "opencode/plugins/n3rv-lifecycle.js.j2",
        ".opencode/plugins/n3rv-lifecycle.js",
        UpdateStrategy.OVERWRITE,
    ),
    UpdateEntry(
        "opencode/plugins/n3rv-shell-env.js.j2",
        ".opencode/plugins/n3rv-shell-env.js",
        UpdateStrategy.OVERWRITE,
    ),
    UpdateEntry(
        "opencode/tools/n3rv-stats.ts.j2",
        ".opencode/tools/n3rv-stats.ts",
        UpdateStrategy.OVERWRITE,
    ),
    # Package config — merge to preserve user extensions
    UpdateEntry(
        "opencode/package.json.j2",
        ".opencode/package.json",
        UpdateStrategy.JSON_MERGE,
    ),
    # Skills in opencode-native path
    UpdateEntry(
        "opencode/skills/code/SKILL.md.j2",
        ".opencode/skills/code/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/testing/SKILL.md.j2",
        ".opencode/skills/testing/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/commits/SKILL.md.j2",
        ".opencode/skills/commits/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-explore/SKILL.md.j2",
        ".opencode/skills/sdd-explore/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-propose/SKILL.md.j2",
        ".opencode/skills/sdd-propose/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-spec/SKILL.md.j2",
        ".opencode/skills/sdd-spec/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-design/SKILL.md.j2",
        ".opencode/skills/sdd-design/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-tasks/SKILL.md.j2",
        ".opencode/skills/sdd-tasks/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-apply/SKILL.md.j2",
        ".opencode/skills/sdd-apply/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-verify/SKILL.md.j2",
        ".opencode/skills/sdd-verify/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/sdd-archive/SKILL.md.j2",
        ".opencode/skills/sdd-archive/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/judgment-day/SKILL.md.j2",
        ".opencode/skills/judgment-day/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    # Slash commands
    UpdateEntry(
        "opencode/commands/sdd-new.md.j2",
        ".opencode/commands/sdd-new.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/commands/judgment-day.md.j2",
        ".opencode/commands/judgment-day.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/commands/new-satellite.md.j2",
        ".opencode/commands/new-satellite.md",
        UpdateStrategy.CREATE_IF_MISSING,
    ),
    UpdateEntry(
        "opencode/commands/review.md.j2",
        ".opencode/commands/review.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/commands/handoff.md.j2",
        ".opencode/commands/handoff.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    # SDD phase sub-agents (generated from SDD_PHASE_MAP)
    *[
        UpdateEntry("opencode/agents/sdd-phase.md.j2", f".opencode/agents/{slug}.md", UpdateStrategy.SKIP_DEFAULT)
        for slug in [
            "sdd-explorer",
            "sdd-proposer",
            "sdd-speccer",
            "sdd-designer",
            "sdd-task-planner",
            "sdd-verifier",
            "sdd-archiver",
        ]
    ],
    # Git & GitHub sub-agents
    UpdateEntry(
        "opencode/agents/git-ops.md.j2",
        ".opencode/agents/git-ops.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/agents/github-ops.md.j2",
        ".opencode/agents/github-ops.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    # Git & GitHub skills
    UpdateEntry(
        "opencode/skills/git-ops/SKILL.md.j2",
        ".opencode/skills/git-ops/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/skills/github-ops/SKILL.md.j2",
        ".opencode/skills/github-ops/SKILL.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    # N3RV primary agent
    UpdateEntry(
        "opencode/agents/n3rv.md.j2",
        ".opencode/agents/n3rv.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    # Specialist sub-agents (external knowledge + environment awareness)
    UpdateEntry(
        "opencode/agents/n3rv-scout.md.j2",
        ".opencode/agents/n3rv-scout.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
    UpdateEntry(
        "opencode/agents/n3rv-sensor.md.j2",
        ".opencode/agents/n3rv-sensor.md",
        UpdateStrategy.SKIP_DEFAULT,
    ),
]


def deep_merge_json(base: dict, overlay: dict) -> dict:
    """Merge overlay into base. overlay wins on key conflicts. Recursive for nested dicts."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_json(result[key], value)
        else:
            result[key] = value
    return result


def _resolve_only_category(only: str) -> UpdateStrategy:
    normalized = only.strip().lower().replace(" ", "-")
    normalized = normalized.replace("_", "-")
    if normalized == "all":
        raise ValueError("Internal error: 'all' is not a selectable category")
    try:
        return _ONLY_CATEGORY_ALIASES[normalized]
    except KeyError as exc:
        allowed = ", ".join(
            [
                "all",
                "marker-merge",
                "json-merge",
                "overwrite",
                "skip-default",
                "create-if-missing",
            ]
        )
        raise ValueError(f"Unknown update category: {only}. Allowed values: {allowed}") from exc


def _select_manifest_entries(only: str | None) -> list[UpdateEntry]:
    if only is None or only.strip().lower() == "all":
        return list(FILE_UPDATE_MANIFEST)
    strategy = _resolve_only_category(only)
    return [entry for entry in FILE_UPDATE_MANIFEST if entry.strategy == strategy]


def _check_nerv_migration_update(root: Path) -> bool:
    """Detect old .nerv/ directory and prompt user for migration."""
    import shutil

    nerv_path = root / NERV_DIR
    if not nerv_path.exists():
        return True

    print()
    print("!" * 58)
    print("!!  WARNING: Old nerv project detected               !!")
    print("!" * 58)
    print(f"!!  Found {NERV_DIR}/ - created by the old nerv CLI    !!")
    print("!!  (now renamed to n3rv).                           !!")
    print("!" * 58)
    print()
    print("n3rv can delete the old .nerv/ files and")
    print("initialize fresh n3rv-generated files.")
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


def _check_n3rv_migration_update(root: Path) -> bool:
    """Detect old .n3rv/ directory and prompt user for migration."""
    import shutil

    old_path = root / N3RV_DIR
    new_path = root / ".n3rv"
    if not old_path.exists() or new_path.exists():
        return True

    print()
    print("!" * 58)
    print("!!  WARNING: Old n3rv project detected               !!")
    print("!" * 58)
    print(f"!!  Found {N3RV_DIR}/ using the old n3rv naming.         !!")
    print("!!  (now renamed to n3rv).                         !!")
    print("!" * 58)
    print()
    print("n3rv will delete the old .n3rv/ files and")
    print("initialize fresh n3rv-generated files.")
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


def run_update(
    root: Path,
    dry_run: bool = False,
    show_diff: bool = False,
    force_commands: bool = False,
    only: str | None = None,
) -> int:
    try:
        if not _check_nerv_migration_update(root):
            return 0
        if not _check_n3rv_migration_update(root):
            return 0

        stack_info = detect_stack(root, stack_override=None)
        context = ProjectContext.build(
            project_name=stack_info.project_name,
            stack=stack_info.stack,
            project_root=root,
        )

        templates_dir = Path(__file__).parent / "templates"
        user_overrides_dir = root / ".n3rv" / "template-overrides"
        engine = TemplateEngine(templates_dir, user_overrides_dir=user_overrides_dir)

        n3rv_binary = shutil.which("n3rv")
        if not n3rv_binary:
            print("✗ Error: n3rv binary not found in PATH")
            return 1

        render_ctx = {**context.to_dict(), "n3rv_binary": n3rv_binary}

        profile = analyze_project(root, context)
        render_ctx.update(profile.to_j2_context())

        summary = UpdateSummary()
        entries = _select_manifest_entries(only)

        # Append dynamic command entries based on detected tools
        template_dir = templates_dir
        for tool in profile.tools:
            tpl_name = f"opencode/commands/{tool.name}.md.j2"
            out_path = f".opencode/commands/{tool.name}.md"
            if (template_dir / tpl_name).exists():
                entries.append(UpdateEntry(tpl_name, out_path, UpdateStrategy.CREATE_IF_MISSING))

        # Drift detection — compare lockfile against current state
        rendered: dict[str, Path] = {}
        for entry in entries:
            if (root / entry.output_path).is_file():
                rendered[entry.output_path] = root / entry.output_path
        drift = diff_lockfile(root, rendered) if not dry_run else {}
        if drift:
            print()
            print("── Drift detected (files modified since last n3rv update) ──")
            for path, reason in sorted(drift.items()):
                print(f"  ⚠ {path}: {reason}")

        for entry in entries:
            # Compute diff content before processing
            old_content = ""
            target_path = root / entry.output_path
            if target_path.is_file():
                old_content = target_path.read_text(encoding="utf-8")
            new_content = engine.render(entry.template_name, _entry_render_context(entry, render_ctx))

            result = _process_entry(entry, root, engine, render_ctx, dry_run, force_commands)
            summary.results.append(result)
            _print_result(result, dry_run)

            if show_diff and old_content and result.result not in ("ERROR", "SKIPPED"):
                _show_diff(entry.output_path, old_content, new_content)

            # Record lockfile entry for successfully written files
            if not dry_run and result.result not in ("ERROR", "SKIPPED"):
                target = root / entry.output_path
                if target.is_file():
                    lock_entry = record_entry(target, entry.template_name)
                    update_lockfile_entry(root, entry.output_path, lock_entry)

        _print_summary(summary, dry_run)

        if not dry_run:
            try:
                registry_path = write_registry(root)
                print(f"✓ Updated {registry_path.relative_to(root)}")
            except Exception as exc:
                print(f"⚠ Skill registry not written: {exc}")

            if configure_git_hooks(root):
                print("✓ Configured git hooks")
            else:
                print("⚠ Warning: No .git directory found, skipping git hooks config")

            if configure_gitignore(root):
                print("✓ Added n3rv patterns to .gitignore")

            # Final lockfile save with all entries
            full_rendered: dict[str, Path] = {}
            for entry in entries:
                if (root / entry.output_path).is_file():
                    full_rendered[entry.output_path] = root / entry.output_path
            lock_entries: dict[str, Any] = {}
            for rel, abspath in full_rendered.items():
                lock_entries[rel] = record_entry(abspath, "")
            save_lockfile(root, lock_entries)

        return 1 if summary.error_count > 0 else 0

    except Exception as exc:
        print(f"✗ Fatal error: {exc}")
        return 1


def _entry_render_context(entry: UpdateEntry, render_ctx: dict) -> dict:
    """Return render context for an entry, merging SDD phase metadata when applicable."""
    if entry.template_name != "opencode/agents/sdd-phase.md.j2":
        return render_ctx
    phase_key = Path(entry.output_path).stem
    return {**render_ctx, **SDD_PHASE_MAP.get(phase_key, {})}


def _process_entry(
    entry: UpdateEntry,
    root: Path,
    engine: TemplateEngine,
    render_ctx: dict,
    dry_run: bool,
    force_commands: bool,
) -> UpdateResult:
    try:
        content = engine.render(entry.template_name, _entry_render_context(entry, render_ctx))
        target = root / entry.output_path

        if entry.strategy == UpdateStrategy.MARKER_MERGE:
            return _handle_marker_merge(entry, target, content, dry_run)
        elif entry.strategy == UpdateStrategy.JSON_MERGE:
            return _handle_json_merge(entry, target, content, dry_run)
        elif entry.strategy == UpdateStrategy.OVERWRITE:
            return _handle_overwrite(entry, target, content, dry_run)
        elif entry.strategy == UpdateStrategy.SKIP_DEFAULT:
            return _handle_skip_default(entry, target, content, dry_run, force_commands)
        elif entry.strategy == UpdateStrategy.CREATE_IF_MISSING:
            return _handle_create_if_missing(entry, target, content, dry_run)
        else:
            return UpdateResult(
                entry.output_path,
                entry.strategy,
                "ERROR",
                warning=f"Unknown strategy: {entry.strategy}",
            )

    except Exception as exc:
        return UpdateResult(entry.output_path, entry.strategy, "ERROR", warning=str(exc))


def _handle_marker_merge(entry: UpdateEntry, target: Path, content: str, dry_run: bool) -> UpdateResult:
    content_clean = content
    if MARKER_START in content and MARKER_END in content:
        start_idx = content.find(MARKER_START)
        end_idx = content.find(MARKER_END)
        if start_idx != -1 and end_idx != -1:
            start_line_end = content.find("\n", start_idx)
            if start_line_end != -1:
                content_clean = content[start_line_end + 1 : end_idx].rstrip()

    if not target.exists():
        if not dry_run:
            result = write_file(
                target,
                content_clean,
                force=False,
                use_markers=True,
                make_executable=entry.make_executable,
            )
            return UpdateResult(entry.output_path, entry.strategy, result.upper())
        else:
            return UpdateResult(entry.output_path, entry.strategy, "CREATED")

    existing_content = target.read_text(encoding="utf-8")
    warnings = validate_markers(existing_content)

    for warning in warnings:
        print(f"⚠ {entry.output_path}: {warning}", flush=True)

    if MARKER_START in existing_content and MARKER_END in existing_content:
        if not dry_run:
            result = write_file(
                target,
                content_clean,
                force=False,
                use_markers=True,
                make_executable=entry.make_executable,
            )
            return UpdateResult(
                entry.output_path,
                entry.strategy,
                result.upper(),
                warning=warnings[0] if warnings else None,
            )
        else:
            return UpdateResult(
                entry.output_path,
                entry.strategy,
                "UPDATED",
                warning=warnings[0] if warnings else None,
            )
    else:
        return UpdateResult(entry.output_path, entry.strategy, "SKIPPED", warning="No markers found")


def _handle_json_merge(entry: UpdateEntry, target: Path, content: str, dry_run: bool) -> UpdateResult:
    try:
        try:
            template_data = json.loads(content)
        except json.JSONDecodeError as e:
            return UpdateResult(
                entry.output_path,
                entry.strategy,
                "ERROR",
                warning=f"Invalid JSON in template: {e}",
            )

        if not target.exists():
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(template_data, indent=4) + "\n", encoding="utf-8")
            return UpdateResult(entry.output_path, entry.strategy, "CREATED")

        try:
            existing_data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return UpdateResult(
                entry.output_path,
                entry.strategy,
                "ERROR",
                warning=f"Invalid JSON in existing file: {e}",
            )

        merged = deep_merge_json(existing_data, template_data)

        if not dry_run:
            target.write_text(json.dumps(merged, indent=4) + "\n", encoding="utf-8")

        return UpdateResult(entry.output_path, entry.strategy, "UPDATED")

    except Exception as exc:
        return UpdateResult(entry.output_path, entry.strategy, "ERROR", warning=str(exc))


def _handle_overwrite(entry: UpdateEntry, target: Path, content: str, dry_run: bool) -> UpdateResult:
    if not dry_run:
        result = write_file(
            target,
            content,
            force=True,
            use_markers=False,
            make_executable=entry.make_executable,
        )
        return UpdateResult(entry.output_path, entry.strategy, result.upper())
    else:
        if target.exists():
            return UpdateResult(entry.output_path, entry.strategy, "OVERWRITTEN")
        else:
            return UpdateResult(entry.output_path, entry.strategy, "CREATED")


def _handle_skip_default(
    entry: UpdateEntry, target: Path, content: str, dry_run: bool, force_commands: bool
) -> UpdateResult:
    if not force_commands:
        return UpdateResult(
            entry.output_path,
            entry.strategy,
            "SKIPPED",
            warning="use --force-commands to update",
        )
    else:
        return _handle_overwrite(entry, target, content, dry_run)


def _handle_create_if_missing(entry: UpdateEntry, target: Path, content: str, dry_run: bool) -> UpdateResult:
    if target.exists():
        return UpdateResult(entry.output_path, entry.strategy, "SKIPPED")

    if not dry_run:
        result = write_file(
            target,
            content,
            force=False,
            use_markers=False,
            make_executable=entry.make_executable,
        )
        return UpdateResult(entry.output_path, entry.strategy, result.upper())

    return UpdateResult(entry.output_path, entry.strategy, "CREATED")


def _show_diff(path: str, old_content: str, new_content: str) -> None:
    """Print a unified diff between old and new content."""
    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    if diff_lines:
        print(f"  Diff for {path}:")
        for line in diff_lines:
            prefix = line[:1] if line[:1] in ("+", "-", "@") else " "
            print(f"    {prefix}{line.rstrip()}")


def _print_result(result: UpdateResult, dry_run: bool):
    prefix = "[DRY RUN] " if dry_run else ""
    if result.result == "CREATED":
        print(f"{prefix}✓ Created {result.path}")
    elif result.result == "UPDATED":
        print(f"{prefix}✓ Updated {result.path}")
    elif result.result == "OVERWRITTEN":
        print(f"{prefix}✓ Overwritten {result.path}")
    elif result.result == "SKIPPED":
        print(f"{prefix}⊘ Skipped {result.path}")
    elif result.result == "ERROR":
        print(f"{prefix}✗ Error {result.path}: {result.warning}")


def _print_summary(summary: UpdateSummary, dry_run: bool):
    prefix = "[DRY RUN] " if dry_run else ""
    print(
        f"\n{prefix}Done. ✓ {summary.updated_count} updated / ⊘ {summary.skipped_count} skipped",
        end="",
    )
    if summary.error_count > 0:
        print(f" / ✗ {summary.error_count} errors")
    else:
        print()
