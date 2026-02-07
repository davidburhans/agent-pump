"""CLI entry point for agent-pump."""

import asyncio
import sys
import warnings
from pathlib import Path
from typing import Any

import click

# Suppress ResourceWarning for unclosed subprocess transports on Windows
# These often occur during rapid shutdown even when resources are being reaped
if sys.platform == "win32":
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed transport.*")
from rich.console import Console

from agent_pump.models.app_state import AppState
from agent_pump.utils.verification import load_verification_config, save_verification_config

console = Console()


@click.group(
    invoke_without_command=True,
    name="agent-pump",
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run without the TUI (headless mode)",
)
@click.option(
    "--web",
    is_flag=True,
    help="Start the HTTP server instead of the TUI",
)
@click.option(
    "--web-port",
    default=8000,
    type=int,
    help="Port for the HTTP server (default: 8000)",
    metavar="PORT",
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
@click.option(
    "--no-autoload",
    is_flag=True,
    help="Do not automatically load projects from the current workspace",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with verbose logging",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview actions without making changes (dry-run mode)",
)
@click.version_option()
@click.pass_context
def main(
    ctx: click.Context,
    no_tui: bool,
    web: bool,
    web_port: int,
    max_iterations: int,
    branch: str | None,
    no_autoload: bool,
    debug: bool,
    dry_run: bool,
) -> None:
    """
    Agent Pump - Automated AI coding agent orchestrator.

    Run gemini-cli in a loop to implement features from ROADMAP.md.

    \b
    Examples:
        agent-pump ./my-project
        agent-pump ./project1 ./project2
        agent-pump --branch feature/dev ./my-project
        agent-pump --debug ./my-project
    """
    # Configure logging early based on debug flag
    from agent_pump.utils.logging_config import configure_logging

    if debug:
        configure_logging(level="DEBUG", structured=False)
        console.print("[bold yellow]Debug mode enabled - verbose logging active[/bold yellow]")
    else:
        configure_logging(level="INFO", structured=False)

    if ctx.invoked_subcommand is not None:
        return

    # Parse projects from extra args
    projects = tuple(Path(p) for p in ctx.args)

    # Load persisted projects
    app_state = AppState.load()

    # Merge CLI projects with persisted projects (CLI args take precedence but we want union)
    all_projects = []

    # Add persisted projects from workspace first (if autoload enabled)
    if not no_autoload:
        from agent_pump.models.workspace import Workspace

        workspace = Workspace.load(app_state.current_workspace)
        for path_str in workspace.projects:
            p = Path(path_str)
            if p.exists():
                all_projects.append(p)

    # Add CLI args (avoiding duplicates)
    for p in projects:
        p = p.resolve()
        if p not in all_projects:
            all_projects.append(p)

    if web:
        # Validate port range
        if not (1024 <= web_port <= 65535):
            console.print(
                f"[bold red]Invalid port: {web_port}. Must be between 1024 and 65535.[/bold red]"
            )
            return

        # Start HTTP server
        from agent_pump.utils.subprocess_manager import subprocess_manager

        async def _run_web_with_cleanup():
            try:
                await _run_web_server(web_port)
            finally:
                await subprocess_manager.cleanup()

        asyncio.run(_run_web_with_cleanup())
        return

    if dry_run:
        console.print("[bold yellow]Dry-run mode enabled - no changes will be made[/bold yellow]")

    if no_tui:
        if not all_projects:
            console.print("[bold red]No projects specified for headless mode.[/bold red]")
            return

        from agent_pump.utils.subprocess_manager import subprocess_manager

        async def _run_headless_with_cleanup():
            try:
                await _run_headless(all_projects, max_iterations, branch, dry_run)
            finally:
                await subprocess_manager.cleanup()

        asyncio.run(_run_headless_with_cleanup())
        return

    # Launch TUI app
    from agent_pump.tui.app import AgentPumpApp

    app = AgentPumpApp(project_paths=all_projects, dry_run=dry_run)
    app.run()


@main.command(name="init")
@click.argument(
    "path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing files")
@click.option("--example", "-e", is_flag=True, help="Create example project structure")
def init_project(path: Path, force: bool, example: bool) -> None:
    """
    Initialize a new project for Agent Pump.

    Creates a ROADMAP.md file with a sample feature and optional configuration.

    \b
    Examples:
        agent-pump init
        agent-pump init ./my-project
        agent-pump init --example ./demo-project
    """
    roadmap_path = path / "ROADMAP.md"
    config_dir = path / ".agent-pump"
    config_path = config_dir / "config.yml"

    if path == Path("."):
        path = Path.cwd()

    if not path.exists():
        console.print(f"[red]Error: Directory does not exist: {path}[/red]")
        sys.exit(1)

    if path == Path.cwd():
        display_path = "current directory"
    else:
        display_path = str(path)

    console.print(f"[bold]Initializing Agent Pump in {display_path}...[/bold]")

    created = []

    if roadmap_path.exists() and not force:
        console.print("[yellow]ROADMAP.md already exists (use --force to overwrite)[/yellow]")
    else:
        if example:
            sample_roadmap = """# Project Roadmap

## Current Sprint

### :red_circle: Add Login Page
Create a login page with email and password fields.

**Requirements:**
- Email validation
- Password strength indicator
- Show/hide password toggle
- Form validation with error messages

**Acceptance Criteria:**
- User can enter email and password
- Email format is validated
- Password strength is shown
- Login button is disabled until valid input

### :yellow_circle: Add User Registration
Create a user registration form with email, password, and confirmation.

## Backlog

### Add Social Login
- Google OAuth integration
- GitHub OAuth integration
- Account linking options
"""
        else:
            sample_roadmap = """# Project Roadmap

## Current Sprint

### :red_circle: Your First Feature
Describe what you want to build here.

**Requirements:**
- List your requirements
- Be specific about what needs to be built

**Acceptance Criteria:**
- Define what done looks like
- List testable conditions

## Backlog

### Future Feature 1
Description of another feature to build later.

### Future Feature 2
Description of another feature to build later.
"""
        roadmap_path.write_text(sample_roadmap)
        created.append("ROADMAP.md")
        console.print("[green]Created ROADMAP.md[/green]")

    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        created.append(".agent-pump/")

    if config_path.exists() and not force:
        console.print(
            "[yellow].agent-pump/config.yml already exists (use --force to overwrite)[/yellow]"
        )
    else:
        sample_config = """# Agent Pump Configuration
# Generated by `agent-pump init`

# Backend configuration
backends:
  default: gemini
  gemini:
    model: gemini-2.5-pro
    temperature: 0.7

# Budget settings (in USD)
budget:
  enabled: true
  weekly_limit: 50.00
  monthly_limit: 200.00
  action_on_exceeded: warn

# Workflow settings
workflow:
  auto_continue: true
  max_iterations: 10

# Verification commands (customize for your project)
verification:
  test_command: uv run pytest
  lint_command: uv run ruff check .
  build_command: uv run pyright
"""
        config_path.write_text(sample_config)
        created.append(".agent-pump/config.yml")
        console.print("[green]Created .agent-pump/config.yml[/green]")

    if created:
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  1. Edit ROADMAP.md to describe your feature")
        console.print("  2. Configure your API keys (see BACKEND_SETUP.md)")
        console.print("  3. Run: [cyan]uv run agent-pump[/cyan]")
        console.print()
        console.print("[bold]Keyboard shortcuts:[/bold]")
        console.print("  [cyan]a[/cyan] - Add project")
        console.print("  [cyan]s[/cyan] - Start workflow")
        console.print("  [cyan]?[/cyan] - Chat with AI")
        console.print("  [cyan]Ctrl+P[/cyan] - Command palette")
    else:
        console.print("[yellow]No new files created.[/yellow]")


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


@project_group.command(name="bootstrap")
@click.argument(
    "path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.option(
    "--backend",
    default="gemini",
    type=click.Choice(["gemini", "claude", "qwen", "opencode"]),
    help="AI backend to use for analysis",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing files",
)
def bootstrap_project(path: Path, backend: str, dry_run: bool) -> None:
    """Bootstrap a project with AI-generated ROADMAP.md and BEST_PRACTICES.md.

    Analyzes the project structure and uses an AI backend to generate
    appropriate documentation files for agent-pump to work with.
    """
    import asyncio

    from agent_pump.backends import get_backend
    from agent_pump.events.bus import EventBus
    from agent_pump.services.bootstrap_service import BootstrapService

    async def _run_bootstrap() -> None:
        from agent_pump.utils.subprocess_manager import subprocess_manager

        try:
            event_bus = EventBus()
            service = BootstrapService(event_bus)
            backend_instance = get_backend(backend)

            console.print(f"[bold blue]Bootstrapping project: {path}[/bold blue]")
            console.print(f"[dim]Using backend: {backend}[/dim]")

            if dry_run:
                console.print("[yellow]Dry run mode - no files will be written[/yellow]")

            result = await service.bootstrap_project(
                project_path=path,
                backend=backend_instance,
                dry_run=dry_run,
            )

            if result.success:
                console.print("[bold green]Bootstrap complete![/bold green]")
                if result.files_written:
                    console.print("[bold]Files created:[/bold]")
                    for f in result.files_written:
                        console.print(f"  ✓ {f}")
                elif dry_run:
                    console.print("\n[bold]Generated ROADMAP.md:[/bold]")
                    if result.roadmap_content:
                        preview = (
                            result.roadmap_content[:500] + "..."
                            if len(result.roadmap_content) > 500
                            else result.roadmap_content
                        )
                        console.print(preview)
                    console.print("\n[bold]Generated BEST_PRACTICES.md:[/bold]")
                    if result.best_practices_content:
                        preview = (
                            result.best_practices_content[:500] + "..."
                            if len(result.best_practices_content) > 500
                            else result.best_practices_content
                        )
                        console.print(preview)
            else:
                console.print(f"[bold red]Bootstrap failed: {result.error_message}[/bold red]")
        finally:
            await subprocess_manager.cleanup()

    try:
        asyncio.run(_run_bootstrap())
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")


@project_group.command(name="list")
def list_projects() -> None:
    """List managed projects."""
    state = AppState.load()
    if not state.projects:
        console.print("No projects managed.")
        return

    for p in state.projects:
        console.print(str(p))


async def _run_headless(
    projects: list[Path], max_iterations: int, branch: str | None, dry_run: bool = False
) -> None:
    """Run workflows in headless mode."""
    from agent_pump.backends.gemini import GeminiBackend
    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow

    for path in projects:
        try:
            if dry_run:
                console.print(f"[bold yellow][DRY RUN] Previewing project: {path}[/bold yellow]")
            else:
                console.print(f"[bold green]Starting project: {path}[/bold green]")
            project = Project.from_path(path)
            if branch:
                project.branch = branch

            workflow = ProjectWorkflow(
                project=project,
                backend=GeminiBackend(),
                on_output=lambda line, state, task: console.print(line, end=""),
                dry_run=dry_run,
            )
            await workflow.run(max_iterations=max_iterations)

            # Print dry-run report if in dry-run mode
            if dry_run:
                report = workflow.get_dry_run_report()
                if report:
                    console.print(report.format_console_output())
        except Exception as e:
            console.print(f"[bold red]Error running project {path}: {e}[/bold red]")


async def _run_web_server(port: int) -> None:
    """Run the HTTP server with uvicorn."""
    import signal
    import sys

    try:
        import uvicorn

        from agent_pump.api.server import create_server
    except ImportError as e:
        console.print(f"[bold red]Failed to import server dependencies: {e}[/bold red]")
        console.print(
            "[yellow]Make sure you have installed the package with web dependencies:[/yellow]"
        )
        console.print("  uv pip install -e .")
        return

    # Create server instance
    server_app = create_server(debug=True)

    # Configure uvicorn
    config = uvicorn.Config(
        app=server_app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True,
    )

    server = uvicorn.Server(config)

    # Handle shutdown signals
    def signal_handler(sig: int, frame: Any) -> None:
        console.print("\n[yellow]Received shutdown signal, stopping server...[/yellow]")
        server.should_exit = True

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start server
    console.print(f"[bold green]Starting Agent Pump HTTP Server on port {port}[/bold green]")
    console.print(f"[blue]Health check: http://127.0.0.1:{port}/health[/blue]")
    console.print(f"[blue]API docs: http://127.0.0.1:{port}/docs[/blue]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        await server.serve()
    except Exception as e:
        console.print(f"[bold red]Server error: {e}[/bold red]")
        sys.exit(1)

    console.print("[green]Server stopped.[/green]")


# ============================================================================
# UI Commands
# ============================================================================


@main.group(name="ui")
def ui_group() -> None:
    """Manage the Web UI."""
    pass


@ui_group.command(name="build")
@click.option(
    "--force",
    is_flag=True,
    help="Force re-installation of dependencies (npm install)",
)
def build_ui(force: bool) -> None:
    """Build the React frontend."""
    from agent_pump.utils.ui_build import UIBuildError, run_ui_build

    try:
        run_ui_build(force_install=force)
    except UIBuildError as e:
        console.print(f"[bold red]Error building UI: {e}[/bold red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")
        sys.exit(1)


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


@workspace_group.command(name="delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this workspace?")
def delete_workspace(name: str) -> None:
    """Delete a workspace."""
    from agent_pump.models.workspace import Workspace

    existing = Workspace.list_workspaces()
    if name not in existing:
        console.print(f"[red]Workspace '{name}' not found.[/red]")
        return

    state = AppState.load()
    if name == state.current_workspace:
        console.print(
            "[yellow]Cannot delete the current workspace.[/yellow]\n"
            "Switch to a different workspace first:\n"
            "  agent-pump workspace switch <other-workspace>"
        )
        return

    if Workspace.delete(name):
        console.print(f"[green]Deleted workspace: {name}[/green]")
    else:
        console.print(f"[red]Failed to delete workspace: {name}[/red]")


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


# ============================================================================
# Health Check Command
# ============================================================================


@main.command(name="health")
def health_check() -> None:
    """Check system health and resource usage."""
    from agent_pump.utils.memory_profiler import memory_profiler
    from agent_pump.utils.subprocess_manager import subprocess_manager
    from agent_pump.utils.timeout_tracker import timeout_tracker

    console.print("[bold green]Agent Pump Health Check[/bold green]\n")

    # Memory usage
    memory_profiler.enable()
    snapshot = memory_profiler.take_snapshot()

    if snapshot:
        console.print("[bold]Memory Usage:[/bold]")
        console.print(f"  RSS: {snapshot.rss_mb:.1f} MB")
        console.print(f"  VMS: {snapshot.vms_mb:.1f} MB")
        console.print(f"  Percent: {snapshot.percent:.1f}%")

        # Check for memory leaks
        leak_info = memory_profiler.detect_leak()
        if leak_info and leak_info.get("detected"):
            growth = leak_info["growth_percent"]
            console.print(f"[yellow]  Potential memory leak: {growth:.1f}% growth[/yellow]")
    else:
        console.print("[dim]Memory profiling not available (psutil not installed)[/dim]")

    # Subprocess stats
    console.print("\n[bold]Subprocess Statistics:[/bold]")
    metrics = subprocess_manager.get_metrics()
    console.print(f"  Active: {len(metrics.active_processes)}")
    console.print(f"  Total Spawned: {metrics.total_spawned}")
    console.print(f"  Total Completed: {metrics.total_completed}")
    console.print(f"  Total Timeout: {metrics.total_timeout}")
    console.print(f"  Total Cancelled: {metrics.total_cancelled}")

    # Timeout patterns
    patterns = timeout_tracker.get_timeout_patterns()
    if "total_timeouts" in patterns and patterns["total_timeouts"] > 0:
        console.print("\n[bold]Timeout Patterns:[/bold]")
        console.print(f"  Total Timeouts: {patterns['total_timeouts']}")
        for timeout_type, stats in patterns.get("by_type", {}).items():
            console.print(
                f"  {timeout_type}: {stats['count']} (avg: {stats['average_duration']:.1f}s)"
            )
    else:
        console.print("\n[dim]No timeout patterns recorded[/dim]")

    console.print("\n[green]Health check complete[/green]")


# ============================================================================
# Metrics Commands
# ============================================================================


@main.group(name="metrics")
def metrics_group():
    """View and export productivity metrics."""
    pass


@metrics_group.command(name="show")
@click.option(
    "--period",
    default="day",
    type=click.Choice(["day", "week", "month"]),
    help="Time period for summary (default: day)",
)
@click.option(
    "--workspace",
    default="default",
    help="Workspace name (default: default)",
)
def metrics_show(period: str, workspace: str) -> None:
    """Display productivity metrics summary."""
    from agent_pump.models.metrics import WorkspaceMetrics

    console.print(f"[bold green]📊 Metrics Dashboard - {workspace}[/bold green]\n")

    # Load metrics for the workspace
    metrics = WorkspaceMetrics.load(workspace)

    if not metrics.projects:
        console.print("[dim]No metrics data available. Run some projects first![/dim]")
        return

    # Display summary
    summary = metrics.get_summary_by_period(period)

    console.print(f"[bold]Summary by {period}:[/bold]")
    console.print(f"  Total Features: {metrics.total_features_completed}")
    console.print(f"  Successful: {metrics.total_features_successful}")
    console.print(f"  Failed: {metrics.total_features_failed}")
    success_rate = (
        metrics.total_features_successful / max(metrics.total_features_completed, 1) * 100
    )
    console.print(f"  Success Rate: {success_rate:.1f}%")
    console.print(f"  Avg Duration: {metrics.average_feature_duration_seconds / 60:.1f} minutes")

    # Display period breakdown
    if summary:
        console.print(f"\n[bold]Breakdown by {period}:[/bold]")
        for period_key, data in sorted(summary.items()):
            console.print(f"\n  {period_key}:")
            console.print(f"    Features: {data['features_completed']}")
            console.print(f"    Duration: {data['total_duration_seconds'] / 60:.1f} minutes")
            if data["verification_commands"] > 0:
                rate = data["verification_successful"] / data["verification_commands"] * 100
                console.print(f"    Verification: {rate:.1f}%")

    # Display per-project stats
    console.print("\n[bold]Per-Project Stats:[/bold]")
    for path_str, project_metrics in metrics.projects.items():
        success_rate = (
            project_metrics.total_features_successful
            / max(project_metrics.total_features_completed, 1)
            * 100
        )
        console.print(f"\n  {project_metrics.project_name}:")
        console.print(f"    Features: {project_metrics.total_features_completed}")
        console.print(f"    Success Rate: {success_rate:.1f}%")
        console.print(
            f"    Avg Duration: {project_metrics.average_feature_duration_seconds / 60:.1f}m"
        )


@metrics_group.command(name="export")
@click.option(
    "--format",
    "export_format",
    default="json",
    type=click.Choice(["json", "csv"]),
    help="Export format (default: json)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: auto-generated)",
)
@click.option(
    "--workspace",
    default="default",
    help="Workspace name (default: default)",
)
def metrics_export(export_format: str, output: str | None, workspace: str) -> None:
    """Export metrics data to a file."""
    from datetime import datetime
    from pathlib import Path

    from agent_pump.models.metrics import WorkspaceMetrics

    metrics = WorkspaceMetrics.load(workspace)

    # Generate filename if not provided
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = f"agent-pump-metrics-{workspace}-{timestamp}.{export_format}"

    output_path = Path(output)

    try:
        if export_format == "json":
            data = metrics.model_dump_json(indent=2)
            output_path.write_text(data, encoding="utf-8")
        else:  # csv
            data = metrics.export_to_csv()
            output_path.write_text(data, encoding="utf-8")

        console.print(f"[green]✓ Metrics exported to {output_path.absolute()}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")


@metrics_group.command(name="clear")
@click.option(
    "--workspace",
    default="default",
    help="Workspace name (default: default)",
)
@click.confirmation_option(prompt="Are you sure you want to clear all metrics data?")
def metrics_clear(workspace: str) -> None:
    """Clear all metrics data for a workspace."""
    from pathlib import Path

    metrics_path = Path.home() / ".config" / "agent-pump" / f"metrics_{workspace}.json"

    if metrics_path.exists():
        metrics_path.unlink()
        console.print(f"[green]✓ Metrics cleared for workspace: {workspace}[/green]")
    else:
        console.print(f"[dim]No metrics data found for workspace: {workspace}[/dim]")


# ============================================================================
# Template Commands
# ============================================================================


@main.group(name="template")
def template_group() -> None:
    """Manage project templates."""
    pass


@template_group.command(name="list")
def list_templates() -> None:
    """List all available templates."""
    from agent_pump.events.bus import EventBus
    from agent_pump.services.template_service import TemplateService

    event_bus = EventBus()
    service = TemplateService(event_bus)
    templates = service.list_templates()

    if not templates:
        console.print("No templates available.")
        return

    # Group by category
    builtin = [t for t in templates if t.category == "built-in"]
    user = [t for t in templates if t.category == "user"]

    if builtin:
        console.print("[bold]Built-in Templates:[/bold]")
        for t in builtin:
            console.print(f"  {t.name}: {t.description}")

    if user:
        console.print("\n[bold]User Templates:[/bold]")
        for t in user:
            console.print(f"  {t.name}: {t.description}")


@template_group.command(name="save")
@click.argument(
    "project_path", type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path)
)
@click.argument("name")
@click.option("--description", "-d", default="", help="Template description")
def save_template(project_path: Path, name: str, description: str) -> None:
    """Save a project's configuration as a template."""
    from agent_pump.events.bus import EventBus
    from agent_pump.models.app_state import AppState
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.template_service import TemplateService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)
    event_bus = EventBus()
    service = TemplateService(event_bus, workspace)

    try:
        template = service.save_project_as_template(project_path, name, description)
        console.print(f"[green]✓ Saved template: {template.name}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Failed to save template: {e}[/red]")


@template_group.command(name="delete")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to delete this template?")
def delete_template(name: str) -> None:
    """Delete a user-created template."""
    from agent_pump.events.bus import EventBus
    from agent_pump.services.template_service import TemplateService

    event_bus = EventBus()
    service = TemplateService(event_bus)

    if service.delete_template(name):
        console.print(f"[green]✓ Deleted template: {name}[/green]")
    else:
        console.print(
            f"[red]✗ Failed to delete template (may be built-in or not found): {name}[/red]"
        )


@template_group.command(name="show")
@click.argument("name")
def show_template(name: str) -> None:
    """Show details of a template."""
    from agent_pump.events.bus import EventBus
    from agent_pump.services.template_service import TemplateService

    event_bus = EventBus()
    service = TemplateService(event_bus)
    template = service.get_template(name)

    if not template:
        console.print(f"[red]Template not found: {name}[/red]")
        return

    console.print(f"[bold]{template.name}[/bold]")
    console.print(f"  Description: {template.description}")
    console.print(f"  Category: {template.category}")
    console.print(f"  Version: {template.version}")
    if template.tags:
        console.print(f"  Tags: {', '.join(template.tags)}")
    if template.author:
        console.print(f"  Author: {template.author}")
    console.print(f"  Created: {template.created_at}")
    console.print(f"  Updated: {template.updated_at}")

    # Show configuration summary
    config = template.config
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Backend: {config.backend}")
    console.print(f"  Workflow: {config.workflow_name}")
    console.print(f"  Max Iterations: {config.workflow_max_iterations}")
    console.print(f"  Timeout: {config.workflow_timeout}s")

    if config.verification:
        console.print("\n[bold]Verification Commands:[/bold]")
        if config.verification.build_cmd:
            console.print(f"  Build: {config.verification.build_cmd}")
        if config.verification.lint_cmd:
            console.print(f"  Lint: {config.verification.lint_cmd}")
        if config.verification.test_cmd:
            console.print(f"  Test: {config.verification.test_cmd}")


@template_group.command(name="apply")
@click.argument("template_name")
@click.argument(
    "project_path", type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path)
)
@click.option(
    "--create", "-c", is_flag=True, help="Create the project directory if it doesn't exist"
)
def apply_template(template_name: str, project_path: Path, create: bool) -> None:
    """Apply a template to a project."""
    from agent_pump.events.bus import EventBus
    from agent_pump.models.app_state import AppState
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.template_service import TemplateService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)
    event_bus = EventBus()
    service = TemplateService(event_bus, workspace)

    template = service.get_template(template_name)
    if not template:
        console.print(f"[red]Template not found: {template_name}[/red]")
        return

    if create:
        success = service.create_project_from_template(template, project_path)
        if success:
            console.print(f"[green]✓ Created project from template: {project_path}[/green]")
        else:
            console.print("[red]✗ Failed to create project[/red]")
    else:
        if not project_path.exists():
            console.print(f"[red]Project path does not exist: {project_path}[/red]")
            console.print("Use --create flag to create the directory.")
            return

        success = service.apply_template_to_project(template, project_path)
        if success:
            console.print(f"[green]✓ Applied template '{template_name}' to {project_path}[/green]")
        else:
            console.print("[red]✗ Failed to apply template[/red]")


# ============================================================================
# Cost Tracking Commands
# ============================================================================


@main.group(name="cost")
def cost_group() -> None:
    """Manage cost tracking and view spending."""
    pass


@cost_group.command(name="show")
@click.argument(
    "project_path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
)
@click.option(
    "--period",
    type=click.Choice(["daily", "weekly", "monthly"]),
    help="Filter costs by time period",
)
def cost_show(project_path: Path | None, period: str | None) -> None:
    """Show cost summary for workspace or specific project."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    if project_path:
        # Show costs for specific project
        costs = cost_service.get_project_costs(project_path)
        console.print(f"[bold]Costs for project: {project_path}[/bold]")
    elif period:
        # Show costs for specific period
        from agent_pump.models.cost_tracking import BudgetPeriod

        period_enum = BudgetPeriod(period)
        period_costs = cost_service.get_period_costs(period_enum)
        console.print(f"[bold]Costs for {period} period[/bold]")
        console.print(f"  Total Cost: ${period_costs.total_cost:.4f}")
        console.print(f"  Total Tokens: {period_costs.total_tokens:,}")
        console.print(f"  Records: {period_costs.record_count}")
        return
    else:
        # Show workspace-wide costs
        costs = cost_service.get_workspace_costs()
        console.print(f"[bold]Workspace Costs: {workspace.name}[/bold]")

    console.print(f"  Total Cost: ${costs.total_cost:.4f}")
    console.print(f"  Total Tokens: {costs.total_tokens:,}")
    console.print(f"  Records: {costs.record_count}")


@cost_group.command(name="export")
@click.option(
    "--format",
    "export_format",
    default="json",
    type=click.Choice(["json", "csv"]),
    help="Export format (default: json)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (default: auto-generated)",
)
def cost_export(export_format: str, output: str | None) -> None:
    """Export cost records to a file."""
    from datetime import datetime
    from pathlib import Path

    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    # Generate filename if not provided
    if not output:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = f"agent-pump-costs-{workspace.name}-{timestamp}.{export_format}"

    output_path = Path(output)

    try:
        data = cost_service.export_costs(export_format)
        output_path.write_text(data, encoding="utf-8")
        console.print(f"[green]✓ Costs exported to {output_path.absolute()}[/green]")
    except Exception as e:
        console.print(f"[red]✗ Export failed: {e}[/red]")


@cost_group.command(name="reset")
@click.argument(
    "project_path",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
)
@click.confirmation_option(prompt="Are you sure you want to reset cost records?")
def cost_reset(project_path: Path | None) -> None:
    """Reset cost records for a project or all projects."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    if project_path:
        cost_service.reset_costs_for_project(project_path)
        console.print(f"[green]✓ Reset costs for project: {project_path}[/green]")
    else:
        cost_service.reset_all_costs()
        console.print(f"[green]✓ Reset all costs for workspace: {workspace.name}[/green]")


@cost_group.command(name="breakdown")
@click.option(
    "--by",
    type=click.Choice(["phase", "backend"]),
    default="phase",
    help="Group costs by phase or backend",
)
def cost_breakdown(by: str) -> None:
    """Show cost breakdown by phase or backend."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    if by == "phase":
        breakdown = cost_service.get_cost_breakdown_by_phase()
        console.print("[bold]Cost Breakdown by Phase:[/bold]")
    else:
        breakdown = cost_service.get_cost_breakdown_by_backend()
        console.print("[bold]Cost Breakdown by Backend:[/bold]")

    if not breakdown:
        console.print("[dim]No cost data available.[/dim]")
        return

    for name, summary in breakdown.items():
        console.print(f"\n  {name}:")
        console.print(f"    Cost: ${summary.total_cost:.4f}")
        console.print(f"    Tokens: {summary.total_tokens:,}")
        console.print(f"    Records: {summary.record_count}")


# ============================================================================
# Budget Commands
# ============================================================================


@main.group(name="budget")
def budget_group() -> None:
    """Manage budget limits and settings."""
    pass


@budget_group.command(name="show")
def budget_show() -> None:
    """Show current budget status and limits."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    status = cost_service.get_budget_status()

    console.print(f"[bold]Budget Status for {workspace.name}:[/bold]")
    console.print(f"  Enabled: {'Yes' if status['enabled'] else 'No'}")
    console.print(f"  Action on exceeded: {status['action_on_exceeded']}")

    for period in ["daily", "weekly", "monthly"]:
        limit_key = f"{period}_limit"
        spent_key = f"{period}_spent"
        remaining_key = f"{period}_remaining"
        exceeded_key = f"{period}_exceeded"

        limit = status.get(limit_key)
        spent = status.get(spent_key, 0)
        remaining = status.get(remaining_key)
        exceeded = status.get(exceeded_key, False)

        if limit is not None:
            color = "red" if exceeded else "green"
            console.print(f"\n  [{color}]{period.title()}:[/{color}]")
            console.print(f"    Limit: ${limit:.2f}")
            console.print(f"    Spent: ${spent:.4f}")
            if remaining is not None:
                console.print(f"    Remaining: ${remaining:.4f}")


@budget_group.command(name="set")
@click.option("--daily", type=float, help="Daily budget limit in USD")
@click.option("--weekly", type=float, help="Weekly budget limit in USD")
@click.option("--monthly", type=float, help="Monthly budget limit in USD")
@click.option(
    "--action",
    type=click.Choice(["pause", "warn", "ignore"]),
    help="Action to take when budget is exceeded",
)
def budget_set(
    daily: float | None, weekly: float | None, monthly: float | None, action: str | None
) -> None:
    """Set budget limits for the workspace."""
    from agent_pump.models.cost_tracking import BudgetAction, BudgetConfig
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    # Get current config and update
    current_config = cost_service._budget_config

    new_config = BudgetConfig(
        enabled=True,
        daily_limit=daily if daily is not None else current_config.daily_limit,
        weekly_limit=weekly if weekly is not None else current_config.weekly_limit,
        monthly_limit=monthly if monthly is not None else current_config.monthly_limit,
        action_on_exceeded=BudgetAction(action) if action else current_config.action_on_exceeded,
    )

    cost_service.update_budget_config(new_config)
    console.print("[green]✓ Budget configuration updated[/green]")


@budget_group.command(name="enable")
def budget_enable() -> None:
    """Enable budget enforcement."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    current_config = cost_service._budget_config
    new_config = current_config.model_copy(update={"enabled": True})
    cost_service.update_budget_config(new_config)
    console.print("[green]✓ Budget enforcement enabled[/green]")


@budget_group.command(name="disable")
def budget_disable() -> None:
    """Disable budget enforcement."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.services.cost_tracking_service import CostTrackingService

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    if not workspace:
        console.print(f"[red]Workspace '{state.current_workspace}' not found.[/red]")
        sys.exit(1)

    cost_service = CostTrackingService(workspace)

    current_config = cost_service._budget_config
    new_config = current_config.model_copy(update={"enabled": False})
    cost_service.update_budget_config(new_config)
    console.print("[green]✓ Budget enforcement disabled[/green]")


# ============================================================================
# Workflow Commands
# ============================================================================


@main.group(name="workflow")
def workflow_group() -> None:
    """Manage workflows for projects."""
    pass


@workflow_group.command(name="list")
def workflow_list() -> None:
    """List all available workflows (default + custom)."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.orchestrator.workflow_definition import DEFAULT_WORKFLOW

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    # Start with default workflow
    workflows: dict[str, str] = {"default": DEFAULT_WORKFLOW.description}

    # Add custom workflows from workspace
    for name, definition in workspace.workflow_definitions.items():
        workflows[name] = definition.get("description", "No description")

    if not workflows:
        console.print("[yellow]No workflows found.[/yellow]")
        return

    console.print(f"[bold]Available Workflows ({len(workflows)}):[/bold]\n")
    for name, desc in sorted(workflows.items()):
        is_default = name == "default"
        is_current_workflow = False
        if workspace.workflow_definitions:
            is_current_workflow = any(
                config.workflow_name == name for config in workspace.projects.values()
            )

        prefix = "[*] " if is_current_workflow else "    "
        default_marker = " (default)" if is_default else ""
        console.print(f"{prefix}[bold cyan]{name}[/bold cyan]{default_marker}")
        if desc:
            console.print(f"       {desc}")


@workflow_group.command(name="info")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
def workflow_info(path: Path) -> None:
    """Show workflow details for a project."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.orchestrator.workflow_definition import get_workflow

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    config = workspace.get_project_config(path)
    if not config:
        console.print(f"[red]Project '{path}' not found in workspace.[/red]")
        sys.exit(1)

    workflow_name = getattr(config, "workflow_name", "default")
    try:
        workflow = get_workflow(workflow_name, workspace.workflow_definitions)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        console.print("[yellow]Showing default workflow instead[/yellow]")
        workflow = get_workflow("default")

    console.print(f"[bold]Project:[/bold] {config.name}")
    console.print(f"[bold]Path:[/bold] {path.resolve()}")

    workflow_name_str = workflow_name if workflow_name == "default" else f"{workflow_name} (custom)"
    console.print(f"[bold]Current Workflow:[/bold] {workflow.name} ({workflow_name_str})")

    if workflow.description:
        console.print("\n[bold]Description:[/bold]")
        console.print(f"  {workflow.description}")

    console.print(f"\n[bold]Phases ({len(workflow.phases)}):[/bold]")
    for i, phase in enumerate(workflow.phases, 1):
        console.print(f"\n  [bold]{i}. {phase.name}[/bold]")
        if phase.icon:
            console.print(f"     Icon: {phase.icon}")
        if phase.description:
            console.print(f"     Description: {phase.description}")
        console.print(f"     On Success: {phase.on_success}")
        if phase.on_failure:
            console.print(f"     On Failure: {phase.on_failure}")

    console.print("\n[bold]Transitions:[/bold]")
    transitions = workflow.get_transitions()
    for t in transitions:
        trigger = t.get("trigger", "?")
        source = t.get("source", "?")
        dest = t.get("dest", "?")
        console.print(f"  {source} --[{trigger}]--> {dest}")


@workflow_group.command(name="select")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.argument("workflow_name")
def workflow_select(path: Path, workflow_name: str) -> None:
    """Select a workflow for a project."""
    from agent_pump.models.workspace import Workspace
    from agent_pump.orchestrator.workflow_definition import get_workflow

    state = AppState.load()
    workspace = Workspace.load(state.current_workspace)

    config = workspace.get_project_config(path)
    if not config:
        console.print(f"[red]Project '{path}' not found in workspace.[/red]")
        sys.exit(1)

    # Validate workflow exists
    try:
        get_workflow(workflow_name, workspace.workflow_definitions)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        available = ["default"] + list(workspace.workflow_definitions.keys())
        console.print(f"[yellow]Available workflows: {', '.join(available)}[/yellow]")
        sys.exit(1)

    # Update project config
    original_name = getattr(config, "workflow_name", "default")
    config.workflow_name = workflow_name
    workspace.save()

    msg = f"Changed workflow for '{config.name}' from '{original_name}' to '{workflow_name}'"
    console.print(f"[green]✓ {msg}[/green]")


@main.command(name="ask")
@click.argument("query")
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=False,
    default=Path("."),
)
def ask(query: str, path: Path) -> None:
    """Ask a question about the project."""
    import asyncio

    from agent_pump.events.bus import EventBus
    from agent_pump.services.chat_service import ChatService

    async def _run_chat() -> None:
        from agent_pump.utils.subprocess_manager import subprocess_manager

        try:
            event_bus = EventBus()
            service = ChatService(event_bus)

            console.print(f"[bold blue]Chatting with project: {path}[/bold blue]")
            console.print(f"[dim]Question: {query}[/dim]\n")

            console.print("[bold]Assistant:[/bold]", end=" ")

            async for chunk in service.chat_stream(query, path):
                console.print(chunk, end="")
            console.print()  # Newline at end
        finally:
            await subprocess_manager.cleanup()

    try:
        asyncio.run(_run_chat())
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
