"""OpenCode backend placeholder - for future implementation."""

from collections.abc import AsyncIterator
from pathlib import Path

from agent_pump.backends.base import AgentBackend


class OpenCodeBackend(AgentBackend):
    """
    Backend for OpenCode CLI.

    This is a placeholder for future implementation.
    """

    @property
    def name(self) -> str:
        return "OpenCode"

    @property
    def command(self) -> str:
        return "opencode"

    async def is_available(self) -> bool:
        """OpenCode is not yet available."""
        return False

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
    ) -> AsyncIterator[str]:
        """Not implemented yet."""
        raise NotImplementedError("OpenCode backend is not yet implemented")
        yield  # Make this a generator
