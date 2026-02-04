"""Qwen Code CLI backend implementation.

Qwen Code CLI Reference (https://github.com/QwenLM/qwen-code)
==============================================================

COMMAND:
    qwen

NON-INTERACTIVE MODE:
    Prompt is passed via stdin (similar to Gemini CLI)
    echo "Your prompt" | qwen

INTERACTIVE MODE:
    qwen
    - Launches TUI for interactive coding sessions

AUTHENTICATION:
    Option 1: Qwen OAuth (free tier: 2000 requests/day)
              Run 'qwen' and follow OAuth prompts
    Option 2: OpenAI-compatible API key
              Set OPENAI_API_KEY environment variable

SUPPORTED MODELS:
    - Qwen3-Coder (optimized, default)
    - Any OpenAI-compatible model via OpenRouter, etc.

INSTALLATION:
    # npm (recommended)
    npm install -g @qwen-code/qwen-code@latest

    # Homebrew (macOS/Linux)
    brew install qwen-code

    Requirements: Node.js 20+

FEATURES:
    - AI-powered code generation, debugging, refactoring
    - Agentic workflows (PR handling, rebasing, test generation)
    - Integrated web search via Qwen OAuth
    - Interactive approval for code changes
    - Cross-platform (Windows, macOS, Linux)

RATE LIMITS:
    Watch for: "request limit", "daily limit", "quota exceeded"
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


class QwenBackend(AgentBackend):
    """
    Backend for Qwen Code CLI (https://github.com/QwenLM/qwen-code).

    Qwen Code is an AI coding agent optimized for Qwen3-Coder models,
    supporting agentic programming workflows directly in the terminal.

    Uses stdin to pass prompts (similar to Gemini CLI).
    """

    @property
    def name(self) -> str:
        return "Qwen Code"

    @property
    def command(self) -> str:
        return "qwen"

    def get_context_window_size(self, model: str | None = None) -> int:
        """Get context window size for Qwen models.

        Qwen 3 Coder: 128K tokens
        """
        return 128_000

    async def _check_availability(self) -> bool:
        """Check if qwen command is available in PATH."""
        available = cached_which(self.command) is not None
        logger.debug(f"Qwen Code availability check: {available}")
        return available

    def get_setup_instructions(self) -> str:
        """Return setup instructions for installing Qwen Code CLI."""
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                     Qwen Code CLI Not Found                          ║
╠══════════════════════════════════════════════════════════════════════╣
║ Install using one of these methods:                                  ║
║                                                                      ║
║ 1. npm (recommended):                                                ║
║    npm install -g @qwen-code/qwen-code@latest                        ║
║                                                                      ║
║ 2. Homebrew (macOS/Linux):                                           ║
║    brew install qwen-code                                            ║
║                                                                      ║
║ Requirements:                                                        ║
║    - Node.js 20 or higher                                            ║
║                                                                      ║
║ Authentication:                                                      ║
║    Option 1: Run 'qwen' and follow Qwen OAuth prompts                ║
║              (Free tier: 2000 requests/day)                          ║
║    Option 2: Set OPENAI_API_KEY for OpenAI-compatible models         ║
║                                                                      ║
║ More info: https://github.com/QwenLM/qwen-code                       ║
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
        Execute Qwen Code CLI with the given prompt.

        Prompt is passed via stdin for reliable operation.
        """
        executable = cached_which(self.command)
        if not executable:
            logger.error("Qwen Code CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # Build command: qwen --yolo (prompt via stdin)
        # Note: While 'qwen -h' suggests positional arguments for non-interactive mode,
        # we stick to passing prompt via stdin + --yolo for stability and to avoid
        # command-line length limits on Windows.
        cmd = [executable, "--yolo"]

        # Apply extra args (e.g., --model)
        # Apply extra args (e.g., --model)
        combined_args = []
        if self._extra_args:
            combined_args.extend(self._extra_args)
        if extra_args:
            combined_args.extend(extra_args)

        if combined_args:
            cmd.extend(combined_args)
            logger.debug(f"Applied extra args: {combined_args}")

        logger.debug(f"Command: {self.command} --yolo (prompt via stdin, len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command for debugging
        cmd_str = subprocess.list2cmdline(cmd)
        await self.log_command(project_path, "qwen_cmd.log", cmd_str, prompt)

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)

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
            process.terminate()
            raise
        finally:
            try:
                if process.returncode is None:
                    logger.debug("Terminating process in finally block")
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                await process.wait()
            except Exception as e:
                logger.error(f"Error checking process status: {e}")

            elapsed = time.time() - start_time
            logger.info(
                f"Qwen Code CLI completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
