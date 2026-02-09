"""Secure command execution utility."""

import asyncio
import logging
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

from agent_pump.utils.subprocess_manager import SubprocessInfo, subprocess_manager

logger = logging.getLogger(__name__)


class SecureExecutor:
    """Execute commands securely, either on host or in Docker sandbox."""

    @staticmethod
    async def execute_command(
        command: str | list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
        timeout: int = 120,
        sandbox: bool = False,
        sandbox_image: str | None = None,
        network_access: bool = True,
        working_dir_rel: str | None = None,
    ) -> tuple[bool, str, str, int | None, float]:
        """
        Execute a command and return (success, stdout, stderr, exit_code, duration).

        Args:
            command: Command string or list of arguments.
            cwd: Working directory (absolute path on host).
            env: Environment variables.
            timeout: Execution timeout in seconds.
            sandbox: Whether to execute in Docker sandbox.
            sandbox_image: Docker image to use (required if sandbox=True).
            network_access: Whether to allow network access in sandbox.
            working_dir_rel: Working directory relative to project root (for sandbox).

        Returns:
            Tuple of (success, stdout, stderr, exit_code, duration).
        """
        start_time = time.time()

        # Normalize command to list
        if isinstance(command, str):
            cmd_args = shlex.split(command)
        else:
            cmd_args = command

        if not cmd_args:
            return True, "", "", 0, 0.0

        project_path = cwd.resolve()

        # Prepare environment
        full_env = os.environ.copy() if not sandbox else {}
        if env:
            full_env.update(env)

        process = None

        try:
            if sandbox:
                # Docker Execution
                if not sandbox_image:
                    # Default fallback if not provided
                    sandbox_image = "python:3.11-slim"

                docker_cmd = shutil.which("docker")
                if not docker_cmd:
                    return (
                        False,
                        "",
                        "Error: Sandbox required but docker is not available.",
                        None,
                        time.time() - start_time,
                    )

                # Construct docker command
                # Ensure path is compatible with Docker mount syntax
                mount_path = str(project_path)

                # Basic Windows path normalization for Docker Desktop
                if sys.platform == "win32":
                    mount_path = mount_path.replace("\\", "/")

                docker_args = [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{mount_path}:/app",
                    "-w",
                    f"/app/{working_dir_rel}" if working_dir_rel else "/app",
                ]

                if not network_access:
                    docker_args.append("--network=none")

                # Pass environment variables
                if env:
                    for k, v in env.items():
                        docker_args.extend(["-e", f"{k}={v}"])

                docker_args.append(sandbox_image)

                # Adjust command to run inside container
                # Replace host python with container python if applicable
                final_cmd_parts = []
                for part in cmd_args:
                    if part == sys.executable:
                        final_cmd_parts.append("python")
                    else:
                        final_cmd_parts.append(part)

                docker_args.extend(final_cmd_parts)

                exec_cmd = docker_args
                exec_cwd = None # docker command runs from where? usually fine from anywhere, but let's say cwd
                exec_env = None # env vars passed via -e

                logger.info(f"Executing sandboxed command: {' '.join(docker_args)}")

            else:
                # Host Execution
                exec_cmd = cmd_args
                exec_cwd = project_path
                exec_env = full_env
                logger.info(f"Executing host command: {' '.join(cmd_args)} in {exec_cwd}")

            # Execute
            if sandbox:
                 process = await asyncio.create_subprocess_exec(
                    *exec_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    # No cwd/env needed as docker handles it
                )
            else:
                 # Platform-specific flags
                 creationflags = 0
                 if sys.platform == "win32":
                     import subprocess
                     creationflags = subprocess.CREATE_NO_WINDOW

                 process = await asyncio.create_subprocess_exec(
                    *exec_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=exec_cwd,
                    env=exec_env,
                    creationflags=creationflags,
                )

            # Track process
            await subprocess_manager.track_process(
                process.pid,
                SubprocessInfo(
                    pid=process.pid,
                    command=" ".join(cmd_args) if not sandbox else " ".join(exec_cmd),
                    project_path=project_path,
                    start_time=start_time,
                    timeout=timeout,
                    process=process,
                ),
            )

            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            # Untrack
            await subprocess_manager.untrack_process(process.pid, process.returncode)

            stdout_str = stdout_data.decode() if stdout_data else ""
            stderr_str = stderr_data.decode() if stderr_data else ""

            duration = time.time() - start_time
            exit_code = process.returncode
            success = exit_code == 0

            return success, stdout_str, stderr_str, exit_code, duration

        except asyncio.TimeoutError:
            if process:
                # Terminate first while still tracked
                await subprocess_manager.terminate_process(process.pid, process=process)
                # Record timeout
                await subprocess_manager.record_timeout(process.pid)

            duration = time.time() - start_time
            return False, "", f"Command timed out after {timeout}s", None, duration

        except asyncio.CancelledError:
            if process:
                await subprocess_manager.terminate_process(process.pid, process=process)
                await subprocess_manager.record_cancellation(process.pid)
            raise

        except Exception as e:
            if process and process.returncode is None:
                await subprocess_manager.terminate_process(process.pid, process=process)
                await subprocess_manager.untrack_process(process.pid)

            duration = time.time() - start_time
            return False, "", f"Execution error: {str(e)}", None, duration
