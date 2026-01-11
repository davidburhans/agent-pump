"""Global backend availability tracking.

This module provides cached availability checking for backends, allowing
the workflow to pre-check which engines are available at startup and skip
unavailable ones immediately at runtime without waiting for failures.

Usage:
    from agent_pump.backends.availability import BackendAvailability

    # Get singleton instance
    avail = BackendAvailability.instance()

    # Refresh all backend availability (call at startup)
    await avail.refresh_all()

    # Check if a backend is available (instant, cached)
    if avail.is_available("gemini"):
        ...

    # Get list of available backends
    available = avail.get_available_backends()
"""

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from agent_pump.backends.base import AgentBackend

logger = logging.getLogger(__name__)


def _get_backend_registry() -> dict[str, type["AgentBackend"]]:
    """Lazy import to avoid circular dependency."""
    from agent_pump.backends import BACKEND_REGISTRY
    return BACKEND_REGISTRY


class BackendStatus(NamedTuple):
    """Status of a backend's availability."""

    name: str
    available: bool
    last_checked: datetime
    error_message: str | None = None


class BackendAvailability:
    """
    Singleton for tracking global backend availability.

    Caches availability status to avoid repeated filesystem/subprocess checks.
    Call refresh_all() at startup or when you want to re-check availability.
    """

    _instance: "BackendAvailability | None" = None

    def __init__(self) -> None:
        self._status: dict[str, BackendStatus] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def instance(cls) -> "BackendAvailability":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    async def refresh_all(self) -> dict[str, BackendStatus]:
        """
        Refresh availability status for all registered backends.

        Returns:
            Dictionary of backend name to status
        """
        async with self._lock:
            tasks = []
            registry = _get_backend_registry()
            for name, backend_cls in registry.items():
                tasks.append(self._check_backend(name, backend_cls))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, BackendStatus):
                    self._status[result.name] = result
                    if result.available:
                        logger.info(f"Backend '{result.name}' is available")
                    else:
                        logger.debug(
                            f"Backend '{result.name}' not available: "
                            f"{result.error_message or 'not found'}"
                        )

            return self._status.copy()

    async def _check_backend(
        self, name: str, backend_cls: type["AgentBackend"]
    ) -> BackendStatus:
        """Check availability for a single backend."""
        try:
            backend = backend_cls()
            available = await backend.is_available()
            return BackendStatus(
                name=name,
                available=available,
                last_checked=datetime.now(),
                error_message=None if available else f"{backend.command} not found in PATH",
            )
        except Exception as e:
            logger.warning(f"Error checking {name} availability: {e}")
            return BackendStatus(
                name=name,
                available=False,
                last_checked=datetime.now(),
                error_message=str(e),
            )

    async def refresh_one(self, name: str) -> BackendStatus | None:
        """Refresh availability for a single backend."""
        registry = _get_backend_registry()
        if name not in registry:
            logger.warning(f"Unknown backend: {name}")
            return None

        async with self._lock:
            status = await self._check_backend(name, registry[name])
            self._status[name] = status
            return status

    def is_available(self, name: str) -> bool:
        """
        Check if a backend is available (cached).

        Returns False if the backend hasn't been checked yet.
        Call refresh_all() first to populate the cache.
        """
        if name not in self._status:
            return False
        return self._status[name].available

    def get_status(self, name: str) -> BackendStatus | None:
        """Get the full status for a backend."""
        return self._status.get(name)

    def get_available_backends(self) -> list[str]:
        """Get list of available backend names."""
        return [name for name, status in self._status.items() if status.available]

    def get_unavailable_backends(self) -> list[str]:
        """Get list of unavailable backend names."""
        return [name for name, status in self._status.items() if not status.available]

    def get_all_status(self) -> dict[str, BackendStatus]:
        """Get status for all backends."""
        return self._status.copy()

    def get_setup_instructions(self, name: str) -> str | None:
        """Get setup instructions for an unavailable backend."""
        registry = _get_backend_registry()
        if name not in registry:
            return None

        backend = registry[name]()
        return backend.get_setup_instructions()


async def check_all_backends() -> dict[str, BackendStatus]:
    """
    Convenience function to check all backend availability.

    Returns:
        Dictionary of backend name to status
    """
    return await BackendAvailability.instance().refresh_all()


def get_available_backend_names() -> list[str]:
    """
    Get list of available backend names (cached).

    Call check_all_backends() first to populate the cache.
    """
    return BackendAvailability.instance().get_available_backends()
