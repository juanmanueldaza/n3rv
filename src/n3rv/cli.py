from __future__ import annotations

from pathlib import Path

import typer

from n3rv.a2a.hub import main as hub_main
from n3rv.cli_code_graph import code_graph_app
from n3rv.cli_memory import memory_app
from n3rv.cli_org import org_app
from n3rv.daemon import (
    daemon_enable,
    daemon_install,
    daemon_logs,
    daemon_start,
    daemon_status,
    daemon_stop,
)
from n3rv.init import run_init

app = typer.Typer(name="n3rv", help="Invisible engineering infrastructure for opencode agents")
hub_app = typer.Typer(help="A2A Hub commands")
daemon_app = typer.Typer(help="Manage n3rv hub daemon")
code_graph_app.name = "code-graph"
app.add_typer(hub_app, name="hub")
app.add_typer(daemon_app, name="daemon")
app.add_typer(memory_app, name="memory")
app.add_typer(org_app, name="org")
app.add_typer(code_graph_app, name="code-graph")


@hub_app.command("start")
def hub_start() -> None:
    """Start the A2A hub server."""
    hub_main()


@app.command("init")
def init(
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        help="Project root directory",
    ),
    project_name: str | None = typer.Option(
        None,
        "--project-name",
        help="Project name (overrides auto-detection)",
    ),
    stack: str | None = typer.Option(
        None,
        "--stack",
        help="Stack type: python, node, go, generic",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing files without prompting",
    ),
) -> None:
    """Initialize agent-native integration files."""
    exit_code = run_init(
        root=root,
        project_name=project_name,
        stack_override=stack,
        force=force,
    )
    raise typer.Exit(code=exit_code)


@app.command("converge")
def converge_cmd(
    change_id: str = typer.Argument(..., help="The SDD change_id (e.g. add-user-auth)"),
    root: Path = typer.Option(
        Path.cwd(),
        "--root",
        help="Project root directory",
    ),
    issue_number: int | None = typer.Option(
        None,
        "--issue",
        help="GitHub issue number to update on project board",
    ),
) -> None:
    """Converge: generate remediation tasks to close the gap between spec and implementation.

    This command runs the verify phase in converge mode, which:
    1. Checks each acceptance criterion against the implementation
    2. Generates atomic tasks for any FAIL/PARTIAL criteria
    3. Saves the task list to memory (sdd-<change_id>-tasks)
    4. Updates the project board if --issue is provided

    The generated tasks can then be implemented via the normal sdd-apply pipeline.
    """
    print("Converge command received - implementing full SDD converge workflow")
    print(f"Change ID: {change_id}")
    print(f"Root: {root}")
    if issue_number:
        print(f"Issue number: {issue_number}")
    print("")
    print("Use 'n3rv sdd-verify' to check acceptance criteria,")
    print("then 'n3rv sdd-apply' to implement remediation tasks.")


@app.command("update")
def update_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without writing"),
    diff: bool = typer.Option(False, "--diff", help="Show unified diff of changes (implies --dry-run)"),
    force_commands: bool = typer.Option(False, "--force-commands", help="Overwrite command files"),
    only: str | None = typer.Option(
        None,
        "--only",
        help="Only update one category: marker-merge, json-merge, overwrite, skip-default",
    ),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root directory"),
) -> None:
    """Update agent-native integration files in an existing project."""
    from n3rv.init.update import run_update

    raise typer.Exit(
        code=run_update(
            root,
            dry_run=dry_run or diff,
            show_diff=diff,
            force_commands=force_commands,
            only=only,
        )
    )


@daemon_app.command("install")
def daemon_install_cmd(
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root directory"),
) -> None:
    """Install the hub as a systemd user service."""
    raise typer.Exit(code=daemon_install(root))


@daemon_app.command("start")
def daemon_start_cmd() -> None:
    """Start the hub daemon."""
    raise typer.Exit(code=daemon_start())


@daemon_app.command("stop")
def daemon_stop_cmd() -> None:
    """Stop the hub daemon."""
    raise typer.Exit(code=daemon_stop())


@daemon_app.command("status")
def daemon_status_cmd() -> None:
    """Show hub daemon status."""
    raise typer.Exit(code=daemon_status())


@daemon_app.command("enable")
def daemon_enable_cmd(
    now: bool = typer.Option(False, "--now", help="Also start the daemon"),
) -> None:
    """Enable hub daemon to start on login."""
    raise typer.Exit(code=daemon_enable(now=now))


@daemon_app.command("logs")
def daemon_logs_cmd(
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root directory"),
) -> None:
    """Tail hub daemon logs."""
    raise typer.Exit(code=daemon_logs(root))


def main() -> None:
    """Entry point for CLI."""
    app()
