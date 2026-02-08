"""
Backend wrapper that enforces concurrency limits.
"""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.backends.lock_manager import BackendLockManager

logger = logging.getLogger(__name__)


class LockingBackendWrapper(AgentBackend):
    """
    Wraps an AgentBackend and enforces a global lock/semaphore during execution.
    """

    def __init__(self, wrapped: AgentBackend, key: str, limit: int):
        self._wrapped = wrapped
        self._key = key
        self._limit = limit

    @property
    def name(self) -> str:
        return self._wrapped.name

    @property
    def command(self) -> str:
        return self._wrapped.command

    # Propagate extra args if present (Duck typing support for wrapped backend properties)
    @property
    def _extra_args(self) -> list[str] | None:
        return getattr(self._wrapped, "_extra_args", None)

    @_extra_args.setter
    def _extra_args(self, value: list[str] | None):
        if hasattr(self._wrapped, "_extra_args"):
            self._wrapped._extra_args = value  # type: ignore

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
        auto_approve: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Execute the agent with concurrency locking.
        """
        logger.info(f"Adding request to backend queue for {self._key} (limit={self._limit})...")

        async with BackendLockManager.get_lock(self._key, self._limit):
            logger.info(f"Acquired lock for {self._key}. Running backend...")
            try:
                # pyright ignores for abstract generator propagation
                async for line in self._wrapped.run(  # type: ignore
                    project_path,
                    prompt,
                    timeout,
                    verbose,
                    extra_args,
                    auto_approve=auto_approve,
                ):
                    yield line
            finally:
                logger.info(f"Releasing lock for {self._key}")

    async def is_available(self) -> bool:
        return await self._wrapped.is_available()

    async def _check_availability(self) -> bool:
        # Should not be called directly usually, but if so, delegate
        return await self._wrapped._check_availability()  # type: ignore

    # Delegate helper methods
    def get_branch_prompt(self, branch: str | None) -> str:
        return self._wrapped.get_branch_prompt(branch)

    def get_setup_instructions(self) -> str:
        return self._wrapped.get_setup_instructions()

    async def log_command(
        self,
        project_path: Path,
        log_filename: str,
        command_display: str,
        prompt: str,
    ) -> None:
        await self._wrapped.log_command(project_path, log_filename, command_display, prompt)
