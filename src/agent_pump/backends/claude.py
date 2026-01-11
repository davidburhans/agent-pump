"""Claude Code backend placeholder - for future implementation."""

from pathlib import Path
from typing import AsyncIterator

from agent_pump.backends.base import AgentBackend


class ClaudeBackend(AgentBackend):
    """
    Backend for Anthropic's Claude Code CLI.

    This is a placeholder for future implementation when Claude Code
    becomes available as a CLI tool.
    """

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def command(self) -> str:
        return "claude"  # Hypothetical command name

    async def is_available(self) -> bool:
        """Claude Code is not yet available."""
        return False

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
    ) -> AsyncIterator[str]:
        """Not implemented yet."""
        raise NotImplementedError("Claude Code backend is not yet implemented")
        yield  # Make this a generator
