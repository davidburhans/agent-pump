"""Fallback backend runner - tries backends in order until one succeeds."""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from agent_pump.backends.base import AgentBackend

if TYPE_CHECKING:
    from agent_pump.models.workspace import BackendInstance

logger = logging.getLogger(__name__)

# Indicators that suggest quota/rate limit issues
# Includes patterns for multiple providers:
# - General patterns (quota, rate limit, 429, capacity)
# - Anthropic/Claude patterns (overloaded, credit balance)
# - OpenAI patterns (insufficient_quota, billing)
# - Qwen patterns (daily limit, request limit)
QUOTA_ERROR_INDICATORS = [
    # General patterns
    "quota exceeded",
    "rate limit",
    "429",
    "resource exhausted",
    "out of tokens",
    "too many requests",
    "capacity",
    "throttl",  # throttled, throttling
    # Anthropic/Claude-specific
    "rate_limit_error",
    "overloaded_error",
    "overloaded",
    "api_error",
    "credit balance",
    "usage limit",
    # OpenAI-compatible (used by OpenCode, Qwen with OpenRouter)
    "insufficient_quota",
    "billing",
    "exceeded your current quota",
    "rate_limit_exceeded",
    # Qwen-specific
    "request limit",
    "daily limit",
    "free tier limit",
    # Google/Gemini-specific
    "quota_exceeded",
    "rateLimitExceeded",
    "RESOURCE_EXHAUSTED",
    "context_length_exceeded",
    "context window is full",
]


class FallbackBackendRunner:
    """
    Runs backends in order until one succeeds.

    Falls back to the next backend when:
    - Current backend is not available
    - Current backend hits quota/rate limits
    - Current backend throws an exception
    """

    def __init__(
        self,
        backends: list[AgentBackend],
        backend_args: list[list[str]] | None = None,
    ):
        """
        Initialize with a list of backends to try in order.

        Args:
            backends: List of backend instances to try (first is primary)
            backend_args: Optional list of args per backend (parallel to backends list)
        """
        if not backends:
            raise ValueError("At least one backend is required")
        self.backends = backends
        self.backend_args = backend_args or [[] for _ in backends]

    @classmethod
    def from_config(cls, backend_instances: list["BackendInstance"]) -> "FallbackBackendRunner":
        """
        Create from BackendInstance configs.

        Args:
            backend_instances: List of BackendInstance with name and args
        """
        from agent_pump.backends import get_backend

        backends = []
        backend_args = []
        for instance in backend_instances:
            backends.append(get_backend(instance.name))
            backend_args.append(instance.args)

        return cls(backends=backends, backend_args=backend_args)

    @property
    def name(self) -> str:
        """Display name showing all backends in the chain."""
        names = [b.name for b in self.backends]
        return " → ".join(names)

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """
        Try each backend in order until one succeeds.

        Args:
            project_path: Project directory to run in
            prompt: Prompt to send to the agent
            timeout: Timeout per backend attempt
            verbose: Whether to run in verbose mode
            extra_args: Additional args (merged with backend-specific args)

        Yields:
            Lines of output from the successful backend
        """
        last_error: Exception | None = None
        backends_tried = 0

        for i, backend in enumerate(self.backends):
            backends_tried += 1
            is_last = i == len(self.backends) - 1

            # Merge backend-specific args with any passed-in extra_args
            args_for_backend = list(self.backend_args[i]) if i < len(self.backend_args) else []
            if extra_args:
                args_for_backend.extend(extra_args)

            # Check availability
            try:
                available = await backend.is_available()
                if not available:
                    logger.warning(f"Backend {backend.name} not available")
                    yield f"[FALLBACK] {backend.name} not available"
                    if not is_last:
                        yield ", trying next...\n"
                    else:
                        yield "\n"
                    continue
            except Exception as e:
                logger.warning(f"Error checking {backend.name} availability: {e}")
                yield f"[FALLBACK] {backend.name} availability check failed: {e}\n"
                continue

            # Try running this backend
            args_display = f" (args: {args_for_backend})" if args_for_backend else ""
            logger.info(f"Using backend: {backend.name}{args_display}")
            yield f"[BACKEND] Using {backend.name}{args_display}\n"

            try:
                hit_quota = False
                # pyright doesn't fully understand abstract async generators
                async for line in backend.run(  # type: ignore[reportGeneralTypeIssues]
                    project_path, prompt, timeout, verbose, extra_args=args_for_backend
                ):
                    # Check for quota/rate limit errors in output
                    if self._is_quota_error(line):
                        logger.warning(f"Quota error detected from {backend.name}: {line.strip()}")
                        hit_quota = True
                        yield f"[FALLBACK] {backend.name} quota/rate limit detected\n"
                        break
                    yield line

                if hit_quota:
                    # Try next backend
                    continue

                # Completed successfully - we're done
                logger.info(f"Backend {backend.name} completed successfully")
                return

            except Exception as e:
                last_error = e
                logger.exception(f"Backend {backend.name} failed with error")
                yield f"[FALLBACK] {backend.name} failed: {e}"
                if not is_last:
                    yield ", trying next...\n"
                else:
                    yield "\n"
                continue

        # All backends failed
        if last_error:
            yield f"[ERROR] All {backends_tried} backends failed. Last error: {last_error}\n"
        else:
            yield f"[ERROR] No backends available (tried {backends_tried})\n"

    def _is_quota_error(self, line: str) -> bool:
        """Check if output indicates a quota/rate limit error."""
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in QUOTA_ERROR_INDICATORS)
