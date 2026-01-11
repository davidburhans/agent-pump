"""CLI entry point for agent-pump."""

from pathlib import Path

import click
from rich.console import Console

from agent_pump.tui.app import AgentPumpApp

console = Console()


@click.command(name="agent-pump")
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
def main(
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
    if no_tui:
        import asyncio
        asyncio.run(_run_headless(list(projects), max_iterations, branch))
        return

    # Launch TUI app
    app = AgentPumpApp(project_paths=list(projects))
    app.run()


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


if __name__ == "__main__":
    main()
