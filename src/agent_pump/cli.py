"""CLI entry point for agent-pump."""

from pathlib import Path

import click
from rich.console import Console

from agent_pump.tui.app import AgentPumpApp

console = Console()


@click.command()
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
        console.print("[yellow]Headless mode not yet implemented[/yellow]")
        console.print("Use the TUI for now: remove --no-tui flag")
        return

    # Launch TUI app
    app = AgentPumpApp(project_paths=list(projects))
    app.run()


if __name__ == "__main__":
    main()
