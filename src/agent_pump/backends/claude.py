"""Claude Code CLI backend implementation.

Claude Code CLI Reference (https://docs.anthropic.com/claude-code)
===================================================================

COMMAND:
    claude

NON-INTERACTIVE MODE (Print Mode):
    claude -p "Your prompt"
    claude --print "Your prompt"
    - Executes a single query and prints the response
    - Ideal for scripting, automation, and CI/CD pipelines

    Output formats (--output-format):
        text         - Plain text output (default)
        json         - Structured JSON with result, session ID, metadata
        stream-json  - Newline-delimited JSON for real-time streaming

    Example:
        claude -p "Summarize this project" --output-format json

INTERACTIVE MODE:
    claude
    - Starts an interactive chat session

PIPING CONTENT:
    cat logs.txt | claude -p "Explain these errors"
    git diff | claude -p "Review these changes"

SESSION CONTINUATION:
    claude --continue          - Continue the previous session
    claude --resume SESSION_ID - Resume a specific session

TOOL ALLOWLISTING:
    claude --allowedTools tool1,tool2   - Auto-approve specific tools

AUTHENTICATION:
    - Set ANTHROPIC_API_KEY environment variable
    - Or run: claude auth login

INSTALLATION:
    npm install -g @anthropic-ai/claude-code

    Requirements: Node.js 18+

RATE LIMITS:
    Watch for: "rate_limit_error", "overloaded_error", "credit balance"
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator
from datetime import datetime
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.utils.system import cached_which

logger = logging.getLogger(__name__)


class ClaudeBackend(AgentBackend):
    """
    Backend for Anthropic's Claude Code CLI.

    Uses `claude -p "prompt"` for non-interactive execution with
    print mode. Supports stream-json output format for real-time streaming.
    """

    @property
    def name(self) -> str:
        return "Claude Code"

    @property
    def command(self) -> str:
        return "claude"

    async def is_available(self) -> bool:
        """Check if claude command is available in PATH."""
        available = cached_which(self.command) is not None
        logger.debug(f"Claude Code availability check: {available}")
        return available

    def get_setup_instructions(self) -> str:
        """Return setup instructions for installing Claude Code CLI."""
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                    Claude Code CLI Not Found                         ║
╠══════════════════════════════════════════════════════════════════════╣
║ Install using npm:                                                   ║
║                                                                      ║
║    npm install -g @anthropic-ai/claude-code                          ║
║                                                                      ║
║ Requirements:                                                        ║
║    - Node.js 18 or higher                                            ║
║                                                                      ║
║ Authentication:                                                      ║
║    Option 1: Set ANTHROPIC_API_KEY environment variable              ║
║    Option 2: Run 'claude auth login'                                 ║
║                                                                      ║
║ More info: https://docs.anthropic.com/claude-code                    ║
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
        Execute Claude Code CLI with the given prompt.

        Uses `claude -p "prompt"` for non-interactive (print) mode.
        The prompt is passed via stdin to avoid shell escaping issues.
        """
        executable = cached_which(self.command)
        if not executable:
            logger.error("Claude Code CLI not found in PATH")
            yield f"[ERROR] Command '{self.command}' not found in PATH.\n"
            yield self.get_setup_instructions()
            return

        # Build command: claude -p (prompt via stdin)
        # Using --output-format text for simple streaming
        cmd = [executable, "-p"]

        # Apply extra args (e.g., --output-format, --allowedTools)
        if extra_args:
            cmd.extend(extra_args)
            logger.debug(f"Applied extra args: {extra_args}")

        logger.debug(f"Command: {self.command} -p (prompt via stdin, len={len(prompt)})")

        start_time = time.time()
        line_count = 0

        # Log command for debugging
        cmd_str = subprocess.list2cmdline(cmd)
        await self.log_command(project_path, "claude_cmd.log", cmd_str, prompt)

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
            if process.returncode is None:
                logger.debug("Terminating process in finally block")
                process.terminate()
                await process.wait()

            elapsed = time.time() - start_time
            logger.info(
                f"Claude Code CLI completed: {line_count} lines in {elapsed:.1f}s, "
                f"exit code: {process.returncode}"
            )
