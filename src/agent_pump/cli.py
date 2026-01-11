"""CLI entry point for agent-pump."""

import asyncio
from pathlib import Path

import click
from rich.console import Console

from agent_pump.models.app_state import AppState
from agent_pump.tui.app import AgentPumpApp

console = Console()


@click.group(invoke_without_command=True, name="agent-pump")
@click.argument(
    "projects",
    nargs=-1,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
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

    # Merge CLI projects with persisted projects (CLI args take precedence in order but we want union)
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
@click.argument("path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
def add_project(path: Path) -> None:
    """Add a project to be managed."""
    state = AppState.load()
    if state.add_project(path):
        state.save()
        console.print(f"[green]Added project: {path}[/green]")
    else:
        console.print(f"[yellow]Project already managed: {path}[/yellow]")


@project_group.command(name="remove")
@click.argument("path", type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path))
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
                on_output=lambda line: console.print(line, end=""),
            )
            await workflow.run(max_iterations=max_iterations)
        except Exception as e:
            console.print(f"[bold red]Error running project {path}: {e}[/bold red]")
