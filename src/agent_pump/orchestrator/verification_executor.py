"""Verification executor for running custom build, lint, and test commands."""

import asyncio
import logging
from pathlib import Path
from typing import NamedTuple

from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.tool_security import ToolSecurityConfig
from agent_pump.utils.execution import SecureExecutor

logger = logging.getLogger(__name__)


class VerificationResult(NamedTuple):
    """Result of a verification command execution."""

    success: bool
    command: str
    stdout: str
    stderr: str
    exit_code: int | None
    duration: float


class VerificationExecutor:
    """Execute custom verification commands (build, lint, test) asynchronously."""

    def __init__(
        self,
        project_path: Path,
        config: VerificationConfig | None = None,
        tool_security_config: ToolSecurityConfig | None = None,
    ):
        """
        Initialize the verification executor.

        Args:
            project_path: Path to the project directory
            config: Verification configuration (uses defaults if None)
            tool_security_config: Tool security configuration
        """
        self.project_path = project_path
        self.config = config or VerificationConfig()
        self.tool_security_config = tool_security_config or ToolSecurityConfig()

    async def run_command(self, cmd: str, timeout: int = 120) -> VerificationResult:
        """
        Run a single command asynchronously.

        Args:
            cmd: Command to execute
            timeout: Timeout in seconds

        Returns:
            VerificationResult with execution details
        """
        if not cmd:
            return VerificationResult(
                success=True, command=cmd, stdout="", stderr="", exit_code=0, duration=0.0
            )

        logger.info(f"Running verification command: {cmd}")

        # Determine sandbox usage
        # Verification commands are essentially "tools" and should respect tool security policy
        sandbox = not self.tool_security_config.allow_unsandboxed_tools

        if sandbox:
            logger.info("Enforcing sandbox for verification command due to security policy.")

        try:
            success, stdout, stderr, exit_code, duration = await SecureExecutor.execute_command(
                command=cmd,
                cwd=self.project_path,
                timeout=timeout,
                sandbox=sandbox,
                sandbox_image=None,  # Use default
            )

            logger.info(
                f"Command completed: {cmd} (exit code: {exit_code}, duration: {duration:.2f}s)"
            )

            return VerificationResult(
                success=success,
                command=cmd,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
            )

        except Exception as e:
            logger.error(f"Error running command {cmd}: {e}")

            return VerificationResult(
                success=False,
                command=cmd,
                stdout="",
                stderr=str(e),
                exit_code=None,
                duration=0.0,
            )

    async def run_build(self, timeout: int = 120) -> VerificationResult:
        """Run the build command."""
        if not self.config.build_cmd:
            logger.debug("No build command configured, skipping")
            return VerificationResult(
                success=True,
                command="",
                stdout="No build command configured",
                stderr="",
                exit_code=0,
                duration=0.0,
            )

        return await self.run_command(self.config.build_cmd, timeout)

    async def run_lint(self, timeout: int = 120) -> VerificationResult:
        """Run the lint command."""
        if not self.config.lint_cmd:
            logger.debug("No lint command configured, skipping")
            return VerificationResult(
                success=True,
                command="",
                stdout="No lint command configured",
                stderr="",
                exit_code=0,
                duration=0.0,
            )

        return await self.run_command(self.config.lint_cmd, timeout)

    async def run_test(self, timeout: int = 300) -> VerificationResult:
        """Run the test command."""
        if not self.config.test_cmd:
            logger.debug("No test command configured, skipping")
            return VerificationResult(
                success=True,
                command="",
                stdout="No test command configured",
                stderr="",
                exit_code=0,
                duration=0.0,
            )

        return await self.run_command(self.config.test_cmd, timeout)

    async def run_coverage(self, timeout: int = 300) -> VerificationResult:
        """Run the coverage command."""
        if not self.config.coverage_cmd:
            logger.debug("No coverage command configured, skipping")
            return VerificationResult(
                success=True,
                command="",
                stdout="No coverage command configured",
                stderr="",
                exit_code=0,
                duration=0.0,
            )

        return await self.run_command(self.config.coverage_cmd, timeout)

    async def run_all(self, timeout_per_command: int = 120) -> dict[str, VerificationResult]:
        """
        Run all verification commands sequentially.

        Args:
            timeout_per_command: Timeout in seconds for each command

        Returns:
            Dictionary mapping command type to result
        """
        results = {}

        if self.config.skip_verification:
            logger.info("Skipping verification phase as configured")
            results["build"] = VerificationResult(
                success=True,
                command="",
                stdout="Verification skipped as configured",
                stderr="",
                exit_code=0,
                duration=0.0,
            )
            results["lint"] = results["build"]
            results["test"] = results["build"]
            results["coverage"] = results["build"]
            return results

        # Run build, lint, and test in sequence
        results["build"] = await self.run_build(timeout_per_command)
        if not results["build"].success:
            logger.warning("Build failed, skipping lint and test")
            results["lint"] = VerificationResult(
                success=False,
                command="",
                stdout="Build failed, skipping lint",
                stderr="",
                exit_code=0,
                duration=0.0,
            )
            results["test"] = VerificationResult(
                success=False,
                command="",
                stdout="Build failed, skipping test",
                stderr="",
                exit_code=0,
                duration=0.0,
            )
            results["coverage"] = VerificationResult(
                success=False,
                command="",
                stdout="Build failed, skipping coverage",
                stderr="",
                exit_code=0,
                duration=0.0,
            )
            return results

        results["lint"] = await self.run_lint(timeout_per_command)
        results["test"] = await self.run_test(timeout_per_command * 2)  # Tests might take longer
        results["coverage"] = await self.run_coverage(
            timeout_per_command * 2
        )  # Coverage might take longer

        return results
