"""Gemini CLI backend implementation."""

import asyncio
import logging
import shutil
import time
from collections.abc import AsyncIterator
from pathlib import Path

from agent_pump.backends.base import AgentBackend

logger = logging.getLogger(__name__)


class GeminiBackend(AgentBackend):
    """Backend for Google's Gemini CLI (gemini-cli)."""

    @property
    def name(self) -> str:
        return "Gemini CLI"

    @property
    def command(self) -> str:
        return "gemini"

    async def is_available(self) -> bool:
        """Check if gemini command is available."""
        available = shutil.which(self.command) is not None
        logger.debug(f"Gemini CLI availability check: {available}")
        return available

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
    ) -> AsyncIterator[str]:
        """
        Execute gemini-cli with the given prompt.

        Uses --yolo for non-interactive mode (auto-approve all actions).
        """
        executable = shutil.which(self.command)
        if not executable:
            logger.error("Gemini CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH. Please install the backend tool.\n"
            return

        # Use --yolo for auto-approval mode
        # Pass prompt via stdin to avoid shell escaping issues and length limits
        cmd = [
            executable,
            "--yolo",
        ]

        if verbose:
            cmd.append("--verbose")

        logger.info(f"Starting Gemini CLI in {project_path}")
        logger.debug(f"Command: {cmd[0]} --yolo (prompt via stdin)")

        start_time = time.time()
        line_count = 0

        import subprocess
        import sys

        # Build the full command string for logging
        # Note: subprocess.list2cmdline handles quoting for Windows
        cmd_str = subprocess.list2cmdline(cmd)

        # Log full command to file for debugging
        log_file = project_path / ".agent-pump" / "gemini_cmd.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                from datetime import datetime
                f.write(f"\n[{datetime.now().isoformat()}]\n")
                f.write(f"Command: {cmd_str}\n")
                f.write(f"Prompt length: {len(prompt)} chars\n")
                f.write(f"Working directory: {project_path}\n")
                # Write preview of prompt
                f.write(f"Prompt preview:\n{prompt[:200]}...\n")
            logger.info(f"Full command logged to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

        import os

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)  # Help some tools detect the correct cwd

        # Strip IDE-related variables to prevent "Directory mismatch" errors
        # This effectively forces Gemini CLI into "standalone" mode for external projects
        keys_to_remove = [k for k in env if k.startswith(("GEMINI_CLI_", "VSCODE_"))]
        for k in keys_to_remove:
            del env[k]

        logger.debug(f"cleaned env vars: {keys_to_remove}")

        if sys.platform == "win32":
            # On Windows, we use the shell to properly execute .CMD/.BAT files
            logger.debug(f"Windows shell command: {cmd_str}")
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                cwd=str(project_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

        logger.debug(f"Process started with PID: {process.pid}")

        # Write prompt to stdin
        if process.stdin:
            try:
                logger.debug("Writing prompt to stdin...")
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                logger.debug("Prompt written and stdin closed")
            except Exception as e:
                logger.error(f"Failed to write to stdin: {e}")

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Process timeout after {timeout}s, terminating")
                    process.terminate()
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
                        logger.debug(f"EOF reached after {line_count} lines, elapsed: {elapsed:.1f}s")
                        break

                    line_count += 1
                    decoded = line.decode("utf-8", errors="replace")
                    if line_count <= 5 or line_count % 50 == 0:
                        logger.debug(f"Line {line_count}: {decoded[:80].strip()}...")

                    # Check for directory mismatch error and provide hint
                    if "Directory mismatch" in decoded and "IDEClient" in decoded:
                        yield decoded
                        yield f"\n[HINT] The Gemini backend requires the project ({project_path}) to be open in your IDE.\n"
                        yield "       Please open this folder in your IDE workspace and try again.\n"
                    else:
                        yield decoded

                except TimeoutError:
                    # No output for 1 second, check if process is still running
                    if process.returncode is not None:
                        logger.debug(f"Process exited with code {process.returncode} after {line_count} lines")
                        break
                    # Process still running, continue waiting for output
                    logger.debug(f"Waiting for output... ({elapsed:.1f}s elapsed, {line_count} lines so far)")
                    continue

        except asyncio.CancelledError:
            logger.info("Backend run cancelled, terminating process")
            process.terminate()
            raise
        finally:
            # Ensure process is terminated
            if process.returncode is None:
                logger.debug("Terminating process in finally block")
                process.terminate()
                await process.wait()

            elapsed = time.time() - start_time
            logger.info(f"Gemini CLI completed: {line_count} lines in {elapsed:.1f}s, exit code: {process.returncode}")
