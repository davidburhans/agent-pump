"""OpenCode CLI backend implementation.

OpenCode CLI Reference (https://github.com/opencode-ai/opencode)
================================================================

COMMAND:
    opencode

NON-INTERACTIVE MODE:
    opencode run "Your prompt"
    - Executes a single prompt and exits
    - Output is streamed to stdout

INTERACTIVE MODE:
    opencode
    - Launches the TUI for interactive coding sessions

AGENT MANAGEMENT:
    opencode agent list     - List available agents
    opencode agent create   - Create a custom agent

AUTHENTICATION:
    opencode auth login     - Configure API keys for providers

SUPPORTED PROVIDERS:
    OpenAI, Anthropic Claude, Google Gemini, AWS Bedrock, Groq,
    Azure OpenAI, OpenRouter

INSTALLATION:
    # Install script (recommended)
    curl -fsSL https://raw.githubusercontent.com/opencode-ai/opencode/refs/heads/main/install | bash

    # Homebrew (macOS/Linux)
    brew install opencode

    # Go
    go install github.com/opencode-ai/opencode@latest

CONFIGURATION:
    Create ~/.config/opencode/config.yaml or use OPENCODE_* environment variables
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.utils.system import cached_which

logger = logging.getLogger(__name__)


class OpenCodeBackend(AgentBackend):
    """
    Backend for OpenCode CLI (https://opencode.ai).

    OpenCode is a Go-based AI coding agent with TUI that supports multiple
    AI providers including OpenAI, Anthropic, Google Gemini, and more.

    Uses `opencode run "prompt"` for non-interactive execution.
    """

    @property
    def name(self) -> str:
        return "OpenCode"

    @property
    def command(self) -> str:
        return "opencode"

    def get_context_window_size(self, model: str | None = None) -> int:
        """Get context window size for OpenCode.

        OpenCode supports multiple backends, default to 128K.
        """
        return 128_000

    async def _check_availability(self) -> bool:
        """Check if opencode command is available in PATH."""
        available = cached_which(self.command) is not None
        logger.debug(f"OpenCode availability check: {available}")
        return available

    def get_setup_instructions(self) -> str:
        """Return setup instructions for installing OpenCode CLI."""
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                    OpenCode CLI Not Found                            ║
╠══════════════════════════════════════════════════════════════════════╣
║ Install using one of these methods:                                  ║
║                                                                      ║
║ 1. Install script (recommended):                                     ║
║    curl -fsSL https://raw.githubusercontent.com/opencode-ai/         ║
║    opencode/refs/heads/main/install | bash                           ║
║                                                                      ║
║ 2. Homebrew (macOS/Linux):                                           ║
║    brew install opencode                                             ║
║                                                                      ║
║ 3. Go:                                                               ║
║    go install github.com/opencode-ai/opencode@latest                 ║
║                                                                      ║
║ After installation, run: opencode auth login                         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Execute OpenCode CLI with the given prompt.

        Uses `opencode run "prompt"` for non-interactive mode.
        """
        executable = cached_which(self.command)
        if not executable:
            logger.error("OpenCode CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # Build command: opencode run [extra_args]
        # Prompt is passed via stdin to avoid shell escaping issues and length limits
        cmd = [executable, "run"]

        # Apply extra args (e.g., --agent, --model)
        # Use both instance-level args and method-level args
        combined_args = []
        if self._extra_args:
            combined_args.extend(self._extra_args)
        if extra_args:
            combined_args.extend(extra_args)

        if combined_args:
            cmd.extend(combined_args)
            logger.debug(f"Applied extra args: {combined_args}")

        logger.debug(f"Command: {self.command} run ... (prompt via stdin, len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command for debugging
        cmd_str = subprocess.list2cmdline(cmd)
        await self.log_command(project_path, "opencode_cmd.log", cmd_str, prompt)

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)

        from agent_pump.utils.subprocess_manager import SubprocessInfo, subprocess_manager

        if sys.platform == "win32":
            # CREATE_NO_WINDOW prevents console popups and ensures output goes through pipes
            logger.debug(f"Windows shell command: {cmd_str}")
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                cwd=str(project_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
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

        # Track process for lifecycle management
        await subprocess_manager.track_process(
            process.pid,
            SubprocessInfo(
                pid=process.pid,
                command=cmd_str,
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
                        logger.debug(
                            f"EOF reached after {line_count} lines, elapsed: {elapsed:.1f}s"
                        )
                        break

                    line_count += 1
                    decoded = line.decode("utf-8", errors="replace")
                    if line_count <= 5 or line_count % 50 == 0:
                        logger.debug(f"Line {line_count}: {decoded[:80].strip()}...")

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
            logger.info("Backend run cancelled, terminating process")
            await subprocess_manager.record_cancellation(process.pid)
            await subprocess_manager.terminate_process(process.pid)
            raise
        finally:
            try:
                if process.returncode is None:
                    logger.debug("Terminating process in finally block")
                    await subprocess_manager.terminate_process(process.pid)

                await process.wait()

                # Untrack from manager
                await subprocess_manager.untrack_process(process.pid, process.returncode)
            except Exception as e:
                logger.error(f"Error checking process status: {e}")

            elapsed = time.time() - start_time
            logger.info(
                f"OpenCode CLI completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
