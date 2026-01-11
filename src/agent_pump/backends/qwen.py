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
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from agent_pump.backends.base import AgentBackend

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

    async def is_available(self) -> bool:
        """Check if qwen command is available in PATH."""
        available = shutil.which(self.command) is not None
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
    ) -> AsyncIterator[str]:
        """
        Execute Qwen Code CLI with the given prompt.

        Prompt is passed via stdin for reliable operation.
        """
        executable = shutil.which(self.command)
        if not executable:
            logger.error("Qwen Code CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # Build command: qwen (prompt via stdin)
        cmd = [executable]

        # Apply extra args (e.g., --model)
        if extra_args:
            cmd.extend(extra_args)
            logger.debug(f"Applied extra args: {extra_args}")

        logger.debug(f"Command: {self.command} (prompt via stdin, len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command for debugging
        cmd_str = subprocess.list2cmdline(cmd)
        log_file = project_path / ".agent-pump" / "qwen_cmd.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}]\n")
                f.write(f"Command: {cmd_str}\n")
                f.write(f"Prompt length: {len(prompt)} chars\n")
                f.write(f"Working directory: {project_path}\n")
                f.write(f"Prompt preview:\n{prompt[:200]}...\n")
            logger.info(f"Full command logged to {log_file}")
        except Exception as e:
            logger.error(f"Failed to log command: {e}")

        # Prepare environment
        env = os.environ.copy()
        env["PWD"] = str(project_path)

        if sys.platform == "win32":
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
                        logger.debug(
                            f"EOF reached after {line_count} lines, "
                            f"elapsed: {elapsed:.1f}s"
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
                        f"Waiting for output... ({elapsed:.1f}s elapsed, "
                        f"{line_count} lines so far)"
                    )
                    continue

        except asyncio.CancelledError:
            logger.info("Backend run cancelled, terminating process")
            process.terminate()
            raise
        finally:
            if process.returncode is None:
                logger.debug("Terminating process in finally block")
                process.terminate()
                await process.wait()

            elapsed = time.time() - start_time
            logger.info(
                f"Qwen Code CLI completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
