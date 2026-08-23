"""Org-level CLI commands for n3rverberage."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from n3rverberage.init import run_init
from n3rverberage.init.registry import write_registry
from n3rverberage.init.update import run_update
from n3rverberage.org import (
    ORG_CONFIG_FILENAME,
    OrgConfig,
    OrgNotFoundError,
    OrgProject,
    protect_repo,
    resolve_org_root,
)

org_app = typer.Typer(
    name="org",
    help="Manage reverberage org workspace: satellites, shared skills, sync",
)


@org_app.command("init")
def org_init(
    root: Path | None = typer.Option(None, "--root", help="Org root directory (default: CWD)"),
    org_name: str = typer.Option("reverberage", "--org-name", help="GitHub org name"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """Bootstrap an org control plane with org-config.yaml and shared skills."""
    from n3rverberage.org import OrgConfig

    if root is None:
        root = Path.cwd()
    config_dir = root / ".n3rverberage"
    config_path = config_dir / ORG_CONFIG_FILENAME

    if config_path.exists() and not force:
        print(f"✗ Org already initialized at {config_path}")
        raise typer.Exit(code=1)

    config = OrgConfig(
        org_name=org_name,
        config={
            "shared_skills_dir": ".opencode/shared/skills",
            "satellites_dir": ".",
        },
    )
    config.to_yaml(config_path)
    print(f"✓ Created {config_path}")

    # Scaffold shared skills directory with example
    shared_skills_dir = root / ".opencode" / "shared" / "skills"
    shared_skills_dir.mkdir(parents=True, exist_ok=True)
    readme = shared_skills_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Shared Skills\n\nPlace shared SKILL.md files here. They are loaded alongside satellite-local skills.\n"
        )
        print(f"✓ Created {readme}")
    print(f"✓ Org initialized at {root}")
    raise typer.Exit(code=0)


@org_app.command("add-satellite")
def org_add_satellite(
    name: str = typer.Argument(..., help="Satellite project name"),
    root: Path | None = typer.Option(None, "--root", help="Org root directory (default: CWD)"),
    description: str = typer.Option("", "--description", help="Short description"),
    satellite_type: str = typer.Option("satellite", "--type", help="Project type: satellite, tool"),
) -> None:
    """Create a new satellite: gh repo, clone, n3rverberage init, register in org config."""
    if root is None:
        root = Path.cwd()
    try:
        org_root = resolve_org_root(root)
    except OrgNotFoundError as exc:
        print(f"✗ {exc}")
        raise typer.Exit(code=1) from exc

    config_path = org_root / ".n3rverberage" / ORG_CONFIG_FILENAME
    config = OrgConfig.from_yaml(config_path)

    # Check for duplicates
    if name in [p.name for p in config.projects]:
        print(f"✗ Satellite '{name}' already registered in org config")
        raise typer.Exit(code=1)

    # Validate gh CLI
    gh_path = shutil.which("gh")
    if not gh_path:
        print("✗ gh CLI not found. Install: https://cli.github.com/")
        raise typer.Exit(code=1)

    satellites_dir = org_root / config.config.get("satellites_dir", ".")
    target = (satellites_dir / name).resolve()

    # Create GitHub repo
    repo_name = f"{config.org_name}/{name}"
    print(f"→ Creating repo {repo_name}...")
    result = subprocess.run(
        [gh_path, "repo", "create", repo_name, "--private", "--clone"],
        capture_output=True,
        text=True,
        cwd=satellites_dir,
    )
    if result.returncode != 0:
        print(f"✗ Failed to create repo: {result.stderr.strip()}")
        raise typer.Exit(code=1)

    # Verify clone exists
    if not (target / "pyproject.toml").exists():
        print(f"  → Running n3rverberage init in {target}...")
        exit_code = run_init(
            root=target,
            project_name=name,
            stack_override=None,
            force=False,
        )
        if exit_code != 0:
            print(f"✗ n3rverberage init failed in {target}")
            raise typer.Exit(code=exit_code)

    # Register in org config
    satellites_dir_rel = Path(config.config.get("satellites_dir", "."))
    project_rel_path = satellites_dir_rel / name
    project = OrgProject(
        name=name,
        path=project_rel_path,
        description=description,
        type=satellite_type,  # type: ignore[arg-type]
        repo_url=f"https://github.com/{config.org_name}/{name}",
    )
    config.projects.append(project)
    config.to_yaml(config_path)
    print(f"✓ Registered {name} in {config_path}")
    print(f"✓ Satellite '{name}' added and initialized.")
    raise typer.Exit(code=0)


@org_app.command("sync")
def org_sync(
    root: Path | None = typer.Option(None, "--root", help="Org root directory (default: CWD)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Only update one category: marker-merge, json-merge, overwrite, skip-default",
    ),
) -> None:
    """Sync all satellites: run n3rverberage update and regenerate hub registry."""
    if root is None:
        root = Path.cwd()
    try:
        org_root = resolve_org_root(root)
    except OrgNotFoundError as exc:
        print(f"✗ {exc}")
        raise typer.Exit(code=1) from exc

    config_path = org_root / ".n3rverberage" / ORG_CONFIG_FILENAME
    config = OrgConfig.from_yaml(config_path)

    if not config.projects:
        print("No satellites configured.")
        raise typer.Exit(code=0)

    results: list[tuple[str, str]] = []

    for project in config.projects:
        path = (org_root / project.path).resolve()
        if not path.exists():
            results.append((project.name, "SKIPPED"))
            print(f"⊘ {project.name}: path not found ({path})")
            continue
        if project.type != "satellite":
            results.append((project.name, "SKIPPED"))
            print(f"⊘ {project.name}: skipped (type={project.type})")
            continue

        if not dry_run:
            exit_code = run_update(path, dry_run=False, force_commands=False, only=only)
            status = "OK" if exit_code == 0 else f"ERROR (code {exit_code})"
        else:
            status = "OK (dry-run)"
        results.append((project.name, status))
        print(f"  {'→' if dry_run else '✓'} {project.name}: {status}")

    # Regenerate hub registry (dual-path scan when supported)
    if not dry_run:
        try:
            registry_path = write_registry(org_root, org_root=org_root)
            print(f"✓ Regenerated skill registry: {registry_path}")
        except TypeError:
            # Fallback for backward compat (Task 4 adds org_root param)
            registry_path = write_registry(org_root)
            print(f"✓ Regenerated skill registry: {registry_path}")
        except Exception as exc:
            print(f"⚠ Skill registry not written: {exc}")

    # Summary
    success = sum(1 for r in results if r[1].startswith("OK"))
    skipped = sum(1 for r in results if r[1].startswith("SKIPPED"))
    errors = sum(1 for r in results if r[1].startswith("ERROR"))
    print(f"\nSummary: {success} synced, {skipped} skipped, {errors} errors")
    raise typer.Exit(code=1 if errors > 0 else 0)


@org_app.command("protect")
def org_protect(
    project_name: str | None = typer.Argument(
        None,
        help="Project name to protect (default: all registered projects)",
    ),
    root: Path | None = typer.Option(None, "--root", help="Org root directory (default: CWD)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
) -> None:
    """Apply GitHub branch protection to registered projects.

    Detects CI workflow checks and configures:
    - Required status checks from CI jobs
    - Required PR reviews (1 approval, dismiss stale)
    - Admin enforcement
    """
    if root is None:
        root = Path.cwd()
    try:
        org_root = resolve_org_root(root)
    except OrgNotFoundError as exc:
        print(f"✗ {exc}")
        raise typer.Exit(code=1) from exc

    config_path = org_root / ".n3rverberage" / ORG_CONFIG_FILENAME
    config = OrgConfig.from_yaml(config_path)

    projects = [p for p in config.projects if p.repo_url and (project_name is None or p.name == project_name)]

    if not projects:
        if project_name:
            print(f"✗ Project '{project_name}' not found or has no repo_url")
        else:
            print("✗ No registered projects with repo_url found")
        raise typer.Exit(code=1)

    success = 0
    errors = 0
    for project in projects:
        ok = protect_repo(project.repo_url, dry_run=dry_run)
        if ok:
            success += 1
        else:
            errors += 1

    prefix = "[DRY RUN] " if dry_run else ""
    print(f"\n{prefix}{success} protected, {errors} failed")
    raise typer.Exit(code=1 if errors > 0 else 0)
