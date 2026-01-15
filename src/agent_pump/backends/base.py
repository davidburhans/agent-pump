"""Abstract base class for AI coding agent backends."""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result of an agent invocation."""

    success: bool
    output: str
    exit_code: int
    duration_seconds: float


class BackendError(Exception):
    """Base exception for backend errors."""

    pass


class AgentBackend(ABC):
    """
    Abstract base class for AI coding agent backends.

    Implement this class to add support for new AI coding agents
    like Claude Code, OpenCode, Aider, etc.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name for this backend (e.g., 'Gemini CLI')."""
        ...

    @property
    @abstractmethod
    def command(self) -> str:
        """The command to invoke this backend (e.g., 'gemini')."""
        ...

    @abstractmethod
    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Execute the agent with the given prompt, yielding output lines.

        Args:
            project_path: The project directory to run in
            prompt: The prompt to send to the agent
            timeout: Maximum time in seconds before terminating
            verbose: whether to run the agent in verbose mode
            extra_args: Additional command-line arguments for the backend

        Yields:
            Lines of output from the agent
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Check if this backend is installed and configured.

        Returns:
            True if the backend can be used, False otherwise
        """
        ...

    def get_branch_prompt(self, branch: str | None) -> str:
        """
        Get prompt instructions for branch handling.

        Args:
            branch: Optional branch name to work on

        Returns:
            Prompt text for branch instructions, or empty string if no branch
        """
        if not branch:
            return ""
        return f"""
IMPORTANT: All work must be done on branch '{branch}'.
Before starting, run: git checkout {branch} || git checkout -b {branch}
Ensure you are on this branch before making any changes.
"""

    def get_setup_instructions(self) -> str:
        """
        Get setup instructions for installing this backend.

        Override this method to provide backend-specific installation instructions.

        Returns:
            Installation instructions string for display to users
        """
        return f"Please install '{self.command}' and ensure it is available in your PATH."

    async def log_command(
        self,
        project_path: Path,
        log_filename: str,
        command_display: str,
        prompt: str,
    ) -> None:
        """
        Log the command execution details to a file asynchronously.

        Args:
            project_path: The project directory.
            log_filename: The name of the log file.
            command_display: The command string to log.
            prompt: The prompt text.
        """

        def _write_log() -> str:
            log_file = project_path / ".agent-pump" / log_filename
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                from datetime import datetime

                f.write(f"\n[{datetime.now().isoformat()}]\n")
                f.write(f"Command: {command_display}\n")
                f.write(f"Prompt length: {len(prompt)} chars\n")
                f.write(f"Working directory: {project_path}\n")
                f.write(f"Prompt preview:\n{prompt[:200]}...\n")
            return str(log_file)

        try:
            log_path = await asyncio.to_thread(_write_log)
            logger.info(f"Full command logged to {log_path}")
        except Exception as e:
            logger.error(f"Failed to log command: {e}")
