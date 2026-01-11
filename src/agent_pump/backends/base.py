"""Abstract base class for AI coding agent backends."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


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
    ) -> AsyncIterator[str]:
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
