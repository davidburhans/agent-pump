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
import shutil
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from agent_pump.backends.base import AgentBackend

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

    async def is_available(self) -> bool:
        """Check if opencode command is available in PATH."""
        available = shutil.which(self.command) is not None
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
    ) -> AsyncIterator[str]:
        """
        Execute OpenCode CLI with the given prompt.

        Uses `opencode run "prompt"` for non-interactive mode.
        """
        executable = shutil.which(self.command)
        if not executable:
            logger.error("OpenCode CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # Build command: opencode run "prompt"
        cmd = [executable, "run", prompt]

        # Apply extra args (e.g., --agent, --model)
        if extra_args:
            cmd.extend(extra_args)
            logger.debug(f"Applied extra args: {extra_args}")

        logger.debug(f"Command: {self.command} run <prompt> (len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command for debugging
        cmd_str = subprocess.list2cmdline(cmd)
        log_file = project_path / ".agent-pump" / "opencode_cmd.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}]\n")
                f.write("Command: opencode run <prompt>\n")
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
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(project_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )

        logger.debug(f"Process started with PID: {process.pid}")

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
                f"OpenCode CLI completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
