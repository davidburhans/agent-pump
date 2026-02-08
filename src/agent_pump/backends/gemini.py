"""Gemini CLI backend implementation."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.utils.system import cached_which

logger = logging.getLogger(__name__)


class GeminiBackend(AgentBackend):
    """Backend for Google's Gemini CLI (gemini-cli)."""

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def command(self) -> str:
        return "gemini"

    def get_context_window_size(self, model: str | None = None) -> int:
        """Get context window size for Gemini models.

        Gemini Flash: 1M tokens
        Gemini Pro: 2M tokens
        """
        if model:
            model_lower = model.lower()
            if "pro" in model_lower or "ultra" in model_lower:
                return 2_000_000
            elif "flash" in model_lower:
                return 1_000_000
        return 1_000_000  # Default to Flash size

    async def _check_availability(self) -> bool:
        """Check if gemini command is available."""
        available = cached_which(self.command) is not None
        logger.debug(f"Gemini CLI availability check: {available}")
        return available

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
        Execute gemini-cli with the given prompt.

        Uses --yolo for non-interactive mode only if auto_approve is True.
        """
        executable = cached_which(self.command)
        if not executable:
            logger.error("Gemini CLI not found in PATH")
            yield (
                f"[ERROR] Command '{self.command}' not found in PATH. "
                "Please install the backend tool.\n"
            )
            return

        # Use --yolo for auto-approval mode if requested
        # Pass prompt via stdin to avoid shell escaping issues and length limits
        cmd = [
            executable,
        ]

        if auto_approve:
            cmd.append("--yolo")
        else:
            logger.info("Running Gemini without --yolo (auto-approve disabled)")
            # We might yield a warning to the user
            yield "[WARNING] Auto-approve disabled. Agent may stall if it requests confirmation.\n"

        if verbose:
            cmd.append("--verbose")

        # Apply extra args (e.g., --model gemini-2.5-flash)
        combined_args = []
        if self._extra_args:
            combined_args.extend(self._extra_args)
        if extra_args:
            combined_args.extend(extra_args)

        if combined_args:
            cmd.extend(combined_args)
            logger.debug(f"Applied extra args: {combined_args}")
        logger.debug(f"Command: {cmd[0]} --yolo (prompt via stdin)")

        start_time = time.time()
        line_count = 0

        import subprocess
        import sys

        # Build the full command string for logging
        # Note: subprocess.list2cmdline handles quoting for Windows
        cmd_str = subprocess.list2cmdline(cmd)

        # Log full command to file for debugging
        await self.log_command(project_path, "gemini_cmd.log", cmd_str, prompt)

        import os

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)  # Help some tools detect the correct cwd

        # Inject communication config
        extra_env = self.get_communication_env(str(project_path))
        env.update(extra_env)

        # Strip IDE-related variables to prevent "Directory mismatch" errors
        # This effectively forces Gemini CLI into "standalone" mode for external projects
        keys_to_remove = [k for k in env if k.startswith(("GEMINI_CLI_", "VSCODE_"))]
        for k in keys_to_remove:
            del env[k]

        logger.debug(f"cleaned env vars: {keys_to_remove}")

        from agent_pump.utils.subprocess_manager import SubprocessInfo, subprocess_manager

        process = None
        try:
            # Use create_subprocess_exec to avoid shell command injection
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # Track process for lifecycle management
            await subprocess_manager.track_process(
                process.pid,
                SubprocessInfo(
                    pid=process.pid,
                    command=" ".join(cmd),
                    project_path=project_path,
                    start_time=start_time,
                    timeout=timeout,
                    process=process,
                ),
            )

            logger.debug(f"Process started with PID: {process.pid}")

            # Write prompt to stdin
            if process.stdin:
                try:
                    logger.debug("Writing prompt to stdin...")
                    process.stdin.write(prompt.encode("utf-8"))
                    await asyncio.wait_for(process.stdin.drain(), timeout=30.0)
                    process.stdin.close()
                    await process.stdin.wait_closed()
                    logger.debug("Prompt written and stdin closed")
                except Exception as e:
                    logger.error(f"Failed to write to stdin: {e}")
                    yield f"[ERROR] Failed to write prompt to backend: {e}\n"
                    return

            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Process timeout after {timeout}s, terminating")
                    await subprocess_manager.record_timeout(process.pid)
                    await subprocess_manager.terminate_process(process.pid)
                    yield f"\n[TIMEOUT] Process terminated after {timeout} seconds\n"
                    break

                if process.stdout is None:
                    logger.error("Process stdout is None")
                    break

                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=1.0,
                    )

                    if not line:
                        # Empty line means EOF - process has finished
                        logger.debug(
                            f"EOF reached after {line_count} lines, elapsed: {elapsed:.1f}s"
                        )
                        break

                    line_count += 1
                    decoded = line.decode("utf-8", errors="replace")
                    if line_count <= 5 or line_count % 50 == 0:
                        logger.debug(f"Line {line_count}: {decoded[:80].strip()}...")

                    # Check for directory mismatch error and provide hint
                    if "Directory mismatch" in decoded and "IDEClient" in decoded:
                        yield decoded
                        yield (
                            f"\n[HINT] The Gemini backend requires the project ({project_path}) "
                            "to be open in your IDE.\n"
                        )
                        yield (
                            "       Please open this folder in your IDE workspace and try again.\n"
                        )
                    else:
                        yield decoded

                except TimeoutError:
                    # No output for 1 second, check if process is still running
                    if process.returncode is not None:
                        logger.debug(
                            f"Process exited with code {process.returncode} "
                            f"after {line_count} lines"
                        )
                        break
                    # Process still running, continue waiting for output
                    logger.debug(
                        f"Waiting for output... ({elapsed:.1f}s elapsed, {line_count} lines so far)"
                    )
                    continue

        except asyncio.CancelledError:
            if process:
                logger.info("Backend run cancelled, terminating process")
                await subprocess_manager.record_cancellation(process.pid)
                await subprocess_manager.terminate_process(process.pid)
            raise
        finally:
            # Ensure process is terminated and resources released
            if process:
                try:
                    if process.returncode is None:
                        logger.debug("Terminating process in finally block")
                        await subprocess_manager.terminate_process(process.pid)

                        # Fallback: manually terminate if manager didn't (e.g. if tracking failed)
                        if process.returncode is None:
                            try:
                                process.terminate()
                            except OSError:
                                pass

                    # Always wait to ensure pipes/transports are closed
                    await process.wait()

                    # Untrack from manager
                    await subprocess_manager.untrack_process(process.pid, process.returncode)

                except Exception as e:
                    logger.error(f"Error during process cleanup: {e}")

                elapsed = time.time() - start_time
                logger.info(
                    f"Gemini CLI completed: {line_count} lines in {elapsed:.1f}s, "
                    f"exit code: {process.returncode}"
                )
