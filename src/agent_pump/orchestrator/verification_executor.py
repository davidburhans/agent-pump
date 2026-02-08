"""Verification executor for running custom build, lint, and test commands."""

import asyncio
import logging
import shlex
from pathlib import Path
from typing import NamedTuple

from agent_pump.models.verification_config import VerificationConfig

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

    def __init__(self, project_path: Path, config: VerificationConfig | None = None):
        """
        Initialize the verification executor.

        Args:
            project_path: Path to the project directory
            config: Verification configuration (uses defaults if None)
        """
        self.project_path = project_path
        self.config = config or VerificationConfig()

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

        start_time = asyncio.get_event_loop().time()

        try:
            # Split the command into shell arguments using POSIX mode
            # Note: Commands with Windows paths should use forward slashes for compatibility
            shell_cmd = shlex.split(cmd)
            executable = shell_cmd[0]
            args = shell_cmd[1:] if len(shell_cmd) > 1 else []

            # Create the subprocess with platform-specific flags
            import subprocess
            import sys
            import time

            from agent_pump.utils.subprocess_manager import SubprocessInfo, subprocess_manager

            if sys.platform == "win32":
                # CREATE_NO_WINDOW prevents console popups and ensures output goes through pipes
                proc = await asyncio.create_subprocess_exec(
                    executable,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_path,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    executable,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_path,
                )

            # Track process for lifecycle management
            await subprocess_manager.track_process(
                proc.pid,
                SubprocessInfo(
                    pid=proc.pid,
                    command=cmd,
                    project_path=self.project_path,
                    start_time=time.time(),
                    timeout=timeout,
                    process=proc,
                ),
            )

            try:
                # Wait for the process to complete with timeout
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

                duration = asyncio.get_event_loop().time() - start_time
                exit_code = proc.returncode

                # Decode output
                stdout_str = stdout.decode() if stdout else ""
                stderr_str = stderr.decode() if stderr else ""

                success = exit_code == 0

                logger.info(
                    f"Command completed: {cmd} (exit code: {exit_code}, duration: {duration:.2f}s)"
                )

                # Untrack from manager
                await subprocess_manager.untrack_process(proc.pid, exit_code)

                return VerificationResult(
                    success=success,
                    command=cmd,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=exit_code,
                    duration=duration,
                )

            except TimeoutError:
                # Record timeout
                await subprocess_manager.record_timeout(proc.pid)

                # Terminate the process if it times out
                proc.terminate()
                try:
                    # Give it a moment to terminate gracefully
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except TimeoutError:
                    # Force kill if it doesn't terminate
                    proc.kill()
                    await proc.wait()

                # Ensure it is untracked
                await subprocess_manager.untrack_process(proc.pid)

                duration = asyncio.get_event_loop().time() - start_time
                logger.warning(f"Command timed out after {timeout}s: {cmd}")

                return VerificationResult(
                    success=False,
                    command=cmd,
                    stdout="",
                    stderr=f"Command timed out after {timeout} seconds",
                    exit_code=None,
                    duration=duration,
                )
            except asyncio.CancelledError:
                # Record cancellation
                await subprocess_manager.record_cancellation(proc.pid)
                proc.terminate()
                await proc.wait()
                await subprocess_manager.untrack_process(proc.pid)
                raise

        except FileNotFoundError:
            duration = asyncio.get_event_loop().time() - start_time
            logger.error(f"Command not found: {cmd}")

            return VerificationResult(
                success=False,
                command=cmd,
                stdout="",
                stderr=f"Command not found: {cmd}",
                exit_code=None,
                duration=duration,
            )

        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            logger.error(f"Error running command {cmd}: {e}")

            return VerificationResult(
                success=False,
                command=cmd,
                stdout="",
                stderr=str(e),
                exit_code=None,
                duration=duration,
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
