"""Utility for building the Web UI."""

import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()


class UIBuildError(Exception):
    """Exception raised for UI build errors."""
    pass


def _run_and_stream(args: list[str], cwd: Path, title: str) -> None:
    """
    Run a command and stream its output to the console.

    Args:
        args: Command arguments.
        cwd: Working directory.
        title: Title to display before starting.

    Raises:
        subprocess.CalledProcessError: If the command fails.
    """
    console.print(f"[bold blue]>>> {title}[/bold blue]")

    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=sys.platform == "win32",
        bufsize=1,
    )

    if process.stdout:
        for line in process.stdout:
            # Using dim for streaming output to distinguish from tool output
            console.print(f"[dim]{line.rstrip()}[/dim]")

    return_code = process.wait()
    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, args)


def run_ui_build(force_install: bool = False) -> None:
    """
    Build the React UI.

    Args:
        force_install: Whether to force running npm install even if node_modules exists.

    Raises:
        UIBuildError: If the build fails or requirements are missing.
    """
    # 1. Locate directories
    project_root = Path.cwd()
    ui_dir = project_root / "ui"

    if not ui_dir.exists() or not (ui_dir / "package.json").exists():
        raise UIBuildError(
            f"UI directory not found at {ui_dir}. "
            "Please ensure you are running this command from the project root."
        )

    # 2. Check prerequisites
    if not shutil.which("npm"):
        raise UIBuildError(
            "npm not found. Please install Node.js and npm to build the Web UI.\n"
            "See: https://nodejs.org/"
        )

    if not shutil.which("node"):
        raise UIBuildError("node not found. Please install Node.js.")

    # 3. Install dependencies
    node_modules = ui_dir / "node_modules"
    if force_install or not node_modules.exists():
        try:
            _run_and_stream(["npm", "install"], cwd=ui_dir, title="Installing UI dependencies")
        except subprocess.CalledProcessError:
            raise UIBuildError(
                "npm install failed. Check the output above for details. "
                "Common issues: network problems or conflicting peer dependencies."
            )
    else:
        console.print("[dim]Dependencies already installed. Use --force to reinstall.[/dim]")

    # 4. Run build
    try:
        _run_and_stream(["npm", "run", "build"], cwd=ui_dir, title="Building UI assets")
    except subprocess.CalledProcessError:
        raise UIBuildError(
            "UI build failed. Check the output above for details. "
            "Common issues: syntax errors in TypeScript/React code or "
            "missing environment variables."
        )

    # 5. Verify output
    output_dir = project_root / "src" / "agent_pump" / "api" / "static"
    index_html = output_dir / "index.html"

    if not index_html.exists():
        raise UIBuildError(
            f"Build completed but index.html not found at {index_html}. "
            "Check if 'ui/vite.config.ts' output path matches 'src/agent_pump/api/static'."
        )

    console.print("\n[bold green]✓ UI built successfully![/bold green]")
    console.print(f"[dim]Assets written to: {output_dir}[/dim]")
