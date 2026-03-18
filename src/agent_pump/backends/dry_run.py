"""Dry-run backend wrapper for intercepting and logging backend calls."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import TYPE_CHECKING

from agent_pump.backends.base import AgentBackend
from agent_pump.utils.dry_run import DryRunContext, OperationType

if TYPE_CHECKING:
    from agent_pump.models.dry_run_report import DryRunReport

logger = logging.getLogger(__name__)


# Token and cost estimation constants (approximate values)
TOKENS_PER_CHAR = 0.25  # Very rough estimate: ~4 chars per token
DEFAULT_OUTPUT_TOKENS = 4000  # Assume 4k output tokens per invocation

# Cost per 1K tokens (USD) - approximate rates
COST_RATES = {
    "gemini": {"input": 0.000125, "output": 0.000375},  # Gemini 1.5 Flash
    "claude": {"input": 0.003, "output": 0.015},  # Claude 3.5 Sonnet
    "qwen": {"input": 0.0005, "output": 0.001},  # Approximate
    "opencode": {"input": 0.0, "output": 0.0},  # Local model
}


class DryRunBackend(AgentBackend):
    """
    Backend wrapper that intercepts calls for dry-run mode.

    Logs what would be executed without actually running commands,
    and estimates token usage and costs.
    """

    def __init__(
        self,
        wrapped_backend: AgentBackend,
        dry_run_context: DryRunContext,
        report: DryRunReport | None = None,
    ) -> None:
        """
        Initialize the dry-run backend wrapper.

        Args:
            wrapped_backend: The actual backend to wrap
            dry_run_context: The dry-run context for tracking
            report: Optional report to populate with data
        """
        self._wrapped = wrapped_backend
        self._context = dry_run_context
        self._report = report
        self._name = f"dry-run-{wrapped_backend.name}"

    @property
    def name(self) -> str:
        """Return the backend name."""
        return self._name

    @property
    def command(self) -> str:
        """Return the wrapped backend's command."""
        return self._wrapped.command

    async def _check_availability(self) -> bool:
        """Check if the wrapped backend is available."""
        return await self._wrapped.is_available()

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
        Run the backend in dry-run mode.

        Instead of executing, logs the command and yields simulated output.

        Args:
            project_path: Path to the project
            prompt: The prompt to send to the agent
            timeout: Timeout in seconds (ignored in dry-run)
            verbose: Whether to run in verbose mode (ignored in dry-run)
            extra_args: Additional command-line arguments
            auto_approve: Whether to allow dangerous actions without confirmation

        Yields:
            Simulated output lines
        """
        if not self._context.enabled:
            # If dry-run is not enabled, delegate to wrapped backend
            async for line in self._wrapped.run(
                project_path,
                prompt,
                timeout,
                verbose,
                extra_args,
                auto_approve=auto_approve,
            ):
                yield line
            return

        # Build command representation
        cmd_parts = [self._wrapped.name]
        if auto_approve:
            cmd_parts.append("--yolo")
        if extra_args:
            cmd_parts.extend(extra_args)
        if verbose:
            cmd_parts.append("--verbose")
        command = " ".join(cmd_parts)

        # Estimate tokens and cost
        prompt_length = len(prompt)
        estimated_input_tokens = int(prompt_length * TOKENS_PER_CHAR)
        estimated_output_tokens = DEFAULT_OUTPUT_TOKENS
        estimated_total_tokens = estimated_input_tokens + estimated_output_tokens

        # Calculate cost
        backend_name = self._wrapped.name
        rates = COST_RATES.get(backend_name, COST_RATES["gemini"])
        input_cost = (estimated_input_tokens / 1000) * rates["input"]
        output_cost = (estimated_output_tokens / 1000) * rates["output"]
        estimated_cost = input_cost + output_cost

        # Track the operation
        would_execute = self._context.would_execute(
            OperationType.BACKEND_COMMAND,
            f"execute {backend_name} backend with {prompt_length} char prompt",
            details={
                "backend_name": backend_name,
                "command": command,
                "prompt_length": prompt_length,
                "estimated_input_tokens": estimated_input_tokens,
                "estimated_output_tokens": estimated_output_tokens,
                "timeout": timeout,
                "verbose": verbose,
                "extra_args": extra_args or [],
                "auto_approve": auto_approve,
            },
            estimated_tokens=estimated_total_tokens,
            estimated_cost=estimated_cost,
        )

        # Also update report if available
        if self._report:
            # Determine phase from prompt content (best effort)
            phase = self._detect_phase_from_prompt(prompt)
            self._report.add_backend_invocation(
                backend_name=backend_name,
                command=command,
                prompt_length=prompt_length,
                estimated_tokens=estimated_total_tokens,
                estimated_cost_usd=estimated_cost,
                phase=phase,
            )

        if would_execute:
            # Should not happen in dry-run mode, but handle just in case
            async for line in self._wrapped.run(
                project_path,
                prompt,
                timeout,
                verbose,
                extra_args,
                auto_approve=auto_approve,
            ):
                yield line
        else:
            # Yield dry-run simulation output
            yield f"\n[DRY RUN] Would execute: {command}\n"
            yield f"[DRY RUN] Prompt length: {prompt_length} characters\n"
            yield f"[DRY RUN] Estimated tokens: {estimated_total_tokens:,}\n"
            yield f"[DRY RUN] Estimated cost: ${estimated_cost:.4f} USD\n"
            yield "[DRY RUN] Backend output would appear here...\n"
            yield "[DRY RUN] (Skipping actual execution)\n\n"

    def _detect_phase_from_prompt(self, prompt: str) -> str | None:
        """Attempt to detect the workflow phase from prompt content."""
        prompt_lower = prompt.lower()

        if "plan" in prompt_lower and "implement" not in prompt_lower:
            return "planning"
        elif "implement" in prompt_lower or "code" in prompt_lower:
            return "implementing"
        elif "verif" in prompt_lower or "test" in prompt_lower or "lint" in prompt_lower:
            return "verifying"
        elif "brainstorm" in prompt_lower or "idea" in prompt_lower:
            return "brainstorming"
        elif "commit" in prompt_lower or "git" in prompt_lower:
            return "committing"

        return None

    async def log_command(
        self,
        project_path: Path,
        log_filename: str,
        command_display: str,
        prompt: str,
    ) -> str | None:
        """
        Log command to file in dry-run mode.

        Instead of writing to a file, just tracks that it would be logged.
        """
        if not self._context.enabled:
            return await self._wrapped.log_command(
                project_path, log_filename, command_display, prompt
            )

        log_file = project_path / ".agent-pump" / log_filename

        # Track that we would write this log
        self._context.would_execute(
            OperationType.FILE_WRITE,
            f"write backend log: {log_file}",
            details={
                "log_file": str(log_file),
                "backend": self._wrapped.name,
                "command": command_display,
                "prompt_length": len(prompt),
            },
        )

        # Return simulated log file path
        return str(log_file)


def wrap_backend_for_dry_run(
    backend: AgentBackend,
    dry_run_context: DryRunContext,
    report: DryRunReport | None = None,
) -> AgentBackend:
    """
    Wrap a backend for dry-run mode if enabled.

    Args:
        backend: The backend to potentially wrap
        dry_run_context: The dry-run context
        report: Optional report to populate

    Returns:
        Either the original backend or a DryRunBackend wrapper
    """
    if dry_run_context.enabled:
        return DryRunBackend(backend, dry_run_context, report)
    return backend
