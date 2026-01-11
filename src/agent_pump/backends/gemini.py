"""Gemini CLI backend implementation."""

import asyncio
import shutil
import time
from pathlib import Path
from typing import AsyncIterator

from agent_pump.backends.base import AgentBackend


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
        return shutil.which(self.command) is not None

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
    ) -> AsyncIterator[str]:
        """
        Execute gemini-cli with the given prompt.

        Uses --yolo for non-interactive mode and --checkpointing for safety.
        """
        cmd = [
            self.command,
            "--yolo",
            "--checkpointing",
            "--prompt",
            prompt,
        ]

        start_time = time.time()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        try:
            while True:
                if time.time() - start_time > timeout:
                    process.terminate()
                    yield f"\n[TIMEOUT] Process terminated after {timeout} seconds\n"
                    break

                if process.stdout is None:
                    break

                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=1.0,
                )

                if not line:
                    break

                yield line.decode("utf-8", errors="replace")

        except asyncio.TimeoutError:
            # No output for 1 second, check if process is still running
            if process.returncode is not None:
                pass  # Process has ended
        except asyncio.CancelledError:
            process.terminate()
            raise
        finally:
            # Ensure process is terminated
            if process.returncode is None:
                process.terminate()
                await process.wait()
