"""Interfaces for core orchestration components."""

from abc import abstractmethod
from typing import Any, Protocol, runtime_checkable

from agent_pump.models.checkpoint import Checkpoint


@runtime_checkable
class TokenCountingService(Protocol):
    """Service for counting tokens."""

    @abstractmethod
    def count_tokens(self, text: str, backend: str, model: str | None = None) -> int:
        """Count tokens for the given text."""
        ...


@runtime_checkable
class PromptLoaderService(Protocol):
    """Service for loading and building prompts."""

    @abstractmethod
    async def build_prompt(
        self,
        state: str,
        backend: str,
        default_prompt: str,
        context: dict[str, str] | None = None,
    ) -> str:
        """Build a prompt for the given state and backend."""
        ...


@runtime_checkable
class VerificationRunner(Protocol):
    """Service for running verification commands."""

    @abstractmethod
    async def run_all(self) -> dict[str, Any]:
        """Run all configured verification commands."""
        ...

    @abstractmethod
    async def run_command(self, command: str) -> Any:
        """Run a specific verification command."""
        ...


@runtime_checkable
class CheckpointManager(Protocol):
    """Service for managing project checkpoints."""

    @abstractmethod
    def create_checkpoint(
        self,
        phase: str,
        feature_name: str | None,
        description: str,
        auto_created: bool = False,
    ) -> Checkpoint:
        """Create a new checkpoint."""
        ...

    @abstractmethod
    def rollback_to_checkpoint(
        self,
        checkpoint: Checkpoint,
        create_backup_branch: bool = True,
    ) -> bool:
        """Rollback to a specific checkpoint."""
        ...
