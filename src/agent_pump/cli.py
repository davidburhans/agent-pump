"""CLI entry point for agent-pump."""

import asyncio
from pathlib import Path

import click
from rich.console import Console

from agent_pump.models.app_state import AppState
from agent_pump.tui.app import AgentPumpApp
from agent_pump.utils.verification import load_verification_config, save_verification_config

console = Console()


@click.group(invoke_without_command=True, name="agent-pump")
@click.argument(
    "projects",
    nargs=-1,
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run without the TUI (headless mode)",
)
@click.option(
    "--max-iterations",
    "-n",
    default=10,
    type=int,
    help="Maximum number of workflow iterations",
)
@click.option(
    "--branch",
    "-b",
    type=str,
    help="Branch to isolate work (overrides project config)",
)
@click.version_option()
@click.pass_context
def main(
    ctx: click.Context,
    projects: tuple[Path, ...],
    no_tui: bool,
    max_iterations: int,
    branch: str | None,
) -> None:
    """
    Agent Pump - Automated AI coding agent orchestrator.

    Run gemini-cli in a loop to implement features from ROADMAP.md.

    \b
    Examples:
        agent-pump ./my-project
        agent-pump ./project1 ./project2
        agent-pump --branch feature/dev ./my-project
    """
    if ctx.invoked_subcommand is not None:
        return

    # Load persisted projects
    app_state = AppState.load()

    # Merge CLI projects with persisted projects (CLI args take precedence but we want union)
    all_projects = []

    # Add persisted projects first
    for p in app_state.projects:
        if p.exists():
            all_projects.append(p)

    # Add CLI args (avoiding duplicates)
    for p in projects:
        p = p.resolve()
        if p not in all_projects:
            all_projects.append(p)

    if no_tui:
        if not all_projects:
            console.print("[bold red]No projects specified for headless mode.[/bold red]")
            return
        asyncio.run(_run_headless(all_projects, max_iterations, branch))
        return

    # Launch TUI app
    app = AgentPumpApp(project_paths=all_projects)
    app.run()


@main.group(name="project")
def project_group() -> None:
    """Manage projects."""
    pass


@project_group.command(name="add")
@click.argument(
    "path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
def add_project(path: Path) -> None:
    """Add a project to be managed."""
    state = AppState.load()
    if state.add_project(path):
        state.save()
        console.print(f"[green]Added project: {path}[/green]")
    else:
        console.print(f"[yellow]Project already managed: {path}[/yellow]")


@project_group.command(name="remove")
@click.argument(
    "path", type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path)
)
def remove_project(path: Path) -> None:
    """Remove a project from management."""
    state = AppState.load()
    if state.remove_project(path):
        state.save()
        console.print(f"[green]Removed project: {path}[/green]")
    else:
        console.print(f"[yellow]Project not found: {path}[/yellow]")


@project_group.command(name="list")
def list_projects() -> None:
    """List managed projects."""
    state = AppState.load()
    if not state.projects:
        console.print("No projects managed.")
        return

    for p in state.projects:
        console.print(str(p))


async def _run_headless(projects: list[Path], max_iterations: int, branch: str | None) -> None:
    """Run workflows in headless mode."""
    from agent_pump.backends.gemini import GeminiBackend
    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow

    for path in projects:
        try:
            console.print(f"[bold green]Starting project: {path}[/bold green]")
            project = Project.from_path(path)
            if branch:
                project.branch = branch

            workflow = ProjectWorkflow(
                project=project,
                backend=GeminiBackend(),
                on_output=lambda line, state, task: console.print(line, end=""),
            )
            await workflow.run(max_iterations=max_iterations)
        except Exception as e:
            console.print(f"[bold red]Error running project {path}: {e}[/bold red]")


# ============================================================================
# Workspace Commands
# ============================================================================


@main.group(name="workspace")
def workspace_group() -> None:
    """Manage workspaces."""
    pass


@workspace_group.command(name="list")
def list_workspaces() -> None:
    """List available workspaces."""
    from agent_pump.models.workspace import Workspace

    workspaces = Workspace.list_workspaces()
    if not workspaces:
        console.print("No workspaces found. Create one with 'agent-pump workspace create <name>'")
        return

    state = AppState.load()
    for name in workspaces:
        if name == state.current_workspace:
            console.print(f"[bold green]* {name}[/bold green] (current)")
        else:
            console.print(f"  {name}")


@workspace_group.command(name="create")
@click.argument("name")
def create_workspace(name: str) -> None:
    """Create a new workspace."""
    from agent_pump.models.workspace import Workspace

    existing = Workspace.list_workspaces()
    if name in existing:
        console.print(f"[yellow]Workspace '{name}' already exists.[/yellow]")
        return

    workspace = Workspace(name=name)
    workspace.save()
    console.print(f"[green]Created workspace: {name}[/green]")


@workspace_group.command(name="switch")
@click.argument("name")
def switch_workspace(name: str) -> None:
    """Switch to a different workspace."""
    from agent_pump.models.workspace import Workspace

    existing = Workspace.list_workspaces()
    if name not in existing:
        console.print(f"[red]Workspace '{name}' not found.[/red]")
        console.print(f"Available: {', '.join(existing) if existing else 'none'}")
        return

    state = AppState.load()
    state.current_workspace = name
    state.save()
    console.print(f"[green]Switched to workspace: {name}[/green]")


@workspace_group.command(name="show")
def show_workspace() -> None:
    """Show details of the current workspace."""
    from agent_pump.models.workspace import Workspace

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    console.print(f"[bold]Workspace: {workspace.name}[/bold]")
    console.print(f"Projects: {len(workspace.projects)}")
    console.print(f"Ideas in queue: {len(workspace.idea_queue)}")
    console.print(f"Created: {workspace.created_at}")
    console.print(f"Last modified: {workspace.last_modified}")

    if workspace.projects:
        console.print("\n[bold]Projects:[/bold]")
        for key, config in workspace.projects.items():
            backends = [b.name for b in config.phase_backends.implementing.backends]
            console.print(f"  {config.name}: {', '.join(backends)}")


# ============================================================================
# Idea Queue Commands
# ============================================================================


@main.group(name="ideas")
def ideas_group() -> None:
    """Manage the idea queue for brainstorming."""
    pass


@ideas_group.command(name="add")
@click.argument("idea")
@click.option("--priority", "-p", default=0, type=int, help="Priority (higher = considered first)")
def add_idea(idea: str, priority: int) -> None:
    """Add an idea to the brainstorming queue."""
    from agent_pump.models.workspace import Workspace

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)
    workspace.add_idea(idea, priority=priority)
    workspace.save()
    console.print(f"[green]Added idea: {idea}[/green]")
    console.print(f"Total ideas in queue: {len(workspace.idea_queue)}")


@ideas_group.command(name="list")
def list_ideas() -> None:
    """List ideas in the queue."""
    from agent_pump.models.workspace import Workspace

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace.idea_queue:
        console.print("No ideas in queue. Add one with 'agent-pump ideas add <idea>'")
        return

    for i, item in enumerate(workspace.idea_queue, 1):
        priority_str = f"[P{item.priority}]" if item.priority > 0 else ""
        console.print(f"{i}. {priority_str} {item.idea}")


@ideas_group.command(name="clear")
@click.confirmation_option(prompt="Are you sure you want to clear all ideas?")
def clear_ideas() -> None:
    """Clear all ideas from the queue."""
    from agent_pump.models.workspace import Workspace

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)
    count = len(workspace.idea_queue)
    workspace.idea_queue = []
    workspace.save()
    console.print(f"[green]Cleared {count} ideas from queue.[/green]")


@ideas_group.command(name="remove")
@click.argument("index", type=int)
def remove_idea(index: int) -> None:
    """Remove an idea by index (1-based)."""
    from agent_pump.models.workspace import Workspace

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if index < 1 or index > len(workspace.idea_queue):
        console.print(f"[red]Invalid index. Must be 1-{len(workspace.idea_queue)}[/red]")
        return

    removed = workspace.idea_queue.pop(index - 1)
    workspace.save()
    console.print(f"[green]Removed: {removed.idea}[/green]")


# ============================================================================
# Verification Commands
# ============================================================================


@main.group(name="verification")
def verification_group() -> None:
    """Manage verification commands for projects."""
    pass


@verification_group.command(name="set-build")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.argument("command")
def set_build_command(project_path: Path, command: str) -> None:
    """Set the build command for a project."""
    config = load_verification_config(project_path)
    config.build_cmd = command
    save_verification_config(project_path, config)
    console.print(f"[green]Set build command for {project_path}: {command}[/green]")


@verification_group.command(name="set-lint")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.argument("command")
def set_lint_command(project_path: Path, command: str) -> None:
    """Set the lint command for a project."""
    config = load_verification_config(project_path)
    config.lint_cmd = command
    save_verification_config(project_path, config)
    console.print(f"[green]Set lint command for {project_path}: {command}[/green]")


@verification_group.command(name="set-test")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.argument("command")
def set_test_command(project_path: Path, command: str) -> None:
    """Set the test command for a project."""
    config = load_verification_config(project_path)
    config.test_cmd = command
    save_verification_config(project_path, config)
    console.print(f"[green]Set test command for {project_path}: {command}[/green]")


@verification_group.command(name="toggle-skip")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.option("--enable/--disable", default=None, help="Enable or disable skipping verification")
def toggle_skip_verification(project_path: Path, enable: bool | None) -> None:
    """Toggle whether to skip verification for a project."""
    config = load_verification_config(project_path)

    if enable is None:
        # Toggle the current value
        config.skip_verification = not config.skip_verification
    else:
        config.skip_verification = enable

    save_verification_config(project_path, config)
    status = "enabled" if config.skip_verification else "disabled"
    console.print(f"[green]Skip verification {status} for {project_path}[/green]")


@verification_group.command(name="show")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
def show_verification_config(project_path: Path) -> None:
    """Show the verification configuration for a project."""
    config = load_verification_config(project_path)

    console.print(f"[bold]Verification configuration for {project_path}:[/bold]")
    console.print(f"  Build command: {config.build_cmd or '[not set]'}")
    console.print(f"  Lint command: {config.lint_cmd or '[not set]'}")
    console.print(f"  Test command: {config.test_cmd or '[not set]'}")
    console.print(f"  Skip verification: {'Yes' if config.skip_verification else 'No'}")


@verification_group.command(name="detect")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
def detect_project_type(project_path: Path) -> None:
    """Detect project type and suggest appropriate verification commands."""
    from agent_pump.models.verification_config import detect_project_type as detect_proj_type

    result = detect_proj_type(project_path)

    console.print(f"[bold]Detected project type: {result.project_type or 'unknown'}[/bold]")
    console.print(f"  Suggested build command: {result.build_cmd or '[none]'}")
    console.print(f"  Suggested lint command: {result.lint_cmd or '[none]'}")
    console.print(f"  Suggested test command: {result.test_cmd or '[none]'}")

    # Ask if user wants to apply the suggestions
    if result.build_cmd or result.lint_cmd or result.test_cmd:
        apply_suggestions = click.confirm("Apply these suggestions to the project configuration?")
        if apply_suggestions:
            config = load_verification_config(project_path)
            if result.build_cmd:
                config.build_cmd = result.build_cmd
            if result.lint_cmd:
                config.lint_cmd = result.lint_cmd
            if result.test_cmd:
                config.test_cmd = result.test_cmd
            save_verification_config(project_path, config)
            console.print("[green]Applied suggested commands to project configuration.[/green]")
