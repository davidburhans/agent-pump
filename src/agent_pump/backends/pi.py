"""Pi Coding Agent CLI backend implementation."""

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.utils.subprocess_manager import SubprocessInfo, subprocess_manager
from agent_pump.utils.system import cached_which

logger = logging.getLogger(__name__)


class PiBackend(AgentBackend):
    """
    Backend for the Pi Coding Agent (pi.dev) CLI.

    Uses `pi -p` for non-interactive (print) mode.
    The prompt is passed via stdin to avoid shell escaping issues.
    """

    @property
    def name(self) -> str:
        return "Pi Coding Agent"

    @property
    def command(self) -> str:
        return "pi"

    async def _check_availability(self) -> bool:
        """Check if global pi command is available."""
        available = cached_which(self.command) is not None
        logger.debug(f"Pi Coding Agent availability check: {available}")
        return available

    def get_setup_instructions(self) -> str:
        """Return installation instructions for the Pi Coding Agent."""
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                 Pi Coding Agent CLI Not Found                        ║
╠══════════════════════════════════════════════════════════════════════╣
║ Install using npm:                                                   ║
║                                                                      ║
║    npm install -g @earendil-works/pi-coding-agent                    ║
║                                                                      ║
║ Requirements:                                                        ║
║    - Node.js 20 or higher                                            ║
║                                                                      ║
║ Authentication:                                                      ║
║    Set standard LLM provider keys as environment variables           ║
║    (e.g., ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.)                   ║
║                                                                      ║
║ More info: https://pi.dev                                            ║
╚══════════════════════════════════════════════════════════════════════╝
"""

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
        Execute Pi Coding Agent CLI with the given prompt.

        Uses `pi -p` (print/non-interactive mode) and pipes the prompt via stdin.
        """
        executable = cached_which(self.command)
        if not executable:
            logger.error("Pi Coding Agent CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # pi -p (print/non-interactive mode)
        cmd = [executable, "-p"]

        # Merge extra arguments (e.g. --provider, --model)
        combined_args = []
        if self._extra_args:
            combined_args.extend(self._extra_args)
        if extra_args:
            combined_args.extend(extra_args)

        if combined_args:
            cmd.extend(combined_args)
            logger.debug(f"Applied extra args for Pi: {combined_args}")

        logger.debug(f"Command: {self.command} -p (prompt via stdin, len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command details
        cmd_str = subprocess.list2cmdline(cmd)
        await self.log_command(project_path, "pi_cmd.log", cmd_str, prompt)

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)

        # Strip IDE-related variables to run standalone
        keys_to_remove = [k for k in env if k.startswith(("VSCODE_", "GEMINI_CLI_"))]
        for k in keys_to_remove:
            del env[k]

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

        logger.debug(f"Pi Coding Agent process started with PID: {process.pid}")

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

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    logger.warning(f"Process timeout after {timeout}s, terminating")
                    await subprocess_manager.record_timeout(process.pid)
                    await subprocess_manager.terminate_process(process.pid, process=process)
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
                        logger.debug(
                            f"EOF reached after {line_count} lines, elapsed: {elapsed:.1f}s"
                        )
                        break

                    line_count += 1
                    decoded = line.decode("utf-8", errors="replace")
                    yield decoded

                except TimeoutError:
                    if process.returncode is not None:
                        logger.debug(
                            f"Process exited with code {process.returncode} "
                            f"after {line_count} lines"
                        )
                        break
                    logger.debug(
                        f"Waiting for output... ({elapsed:.1f}s elapsed, {line_count} lines so far)"
                    )
                    continue

        except asyncio.CancelledError:
            logger.info("Pi Coding Agent run cancelled, terminating process")
            await subprocess_manager.record_cancellation(process.pid)
            await subprocess_manager.terminate_process(process.pid, process=process)
            raise
        finally:
            try:
                if process.returncode is None:
                    logger.debug("Terminating process in finally block")
                    await subprocess_manager.terminate_process(process.pid, process=process)

                await process.wait()
                await subprocess_manager.untrack_process(process.pid, process.returncode)
            except Exception as e:
                logger.error(f"Error checking process status: {e}")

            elapsed = time.time() - start_time
            logger.info(
                f"Pi Coding Agent completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
