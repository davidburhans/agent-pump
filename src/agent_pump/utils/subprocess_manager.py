"""Subprocess lifecycle management and monitoring."""

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SubprocessInfo:
    """Information about a managed subprocess."""

    pid: int
    command: str
    project_path: Path | None
    start_time: float
    timeout: int
    process: asyncio.subprocess.Process | None = None
    cleanup_cmd: list[str] | None = None


@dataclass
class SubprocessMetrics:
    """Metrics for subprocess execution."""

    total_spawned: int = 0
    total_completed: int = 0
    total_timeout: int = 0
    total_cancelled: int = 0
    active_processes: dict[int, SubprocessInfo] = field(default_factory=dict)


class SubprocessManager:
    """Central manager for all subprocess lifecycle tracking."""

    def __init__(self) -> None:
        self.metrics = SubprocessMetrics()
        self._lock = asyncio.Lock()

    async def track_process(self, pid: int, info: SubprocessInfo) -> None:
        """Register a new subprocess for tracking."""
        async with self._lock:
            self.metrics.active_processes[pid] = info
            self.metrics.total_spawned += 1
            logger.debug(f"Tracking subprocess PID={pid}, command={info.command[:50]}...")

    async def untrack_process(self, pid: int, exit_code: int | None = None) -> None:
        """Unregister a completed subprocess."""
        async with self._lock:
            if pid in self.metrics.active_processes:
                info = self.metrics.active_processes.pop(pid)
                self.metrics.total_completed += 1
                duration = time.time() - info.start_time
                logger.debug(
                    f"Subprocess PID={pid} completed: "
                    f"exit_code={exit_code}, duration={duration:.1f}s"
                )

    async def record_timeout(self, pid: int) -> None:
        """Record a subprocess timeout."""
        async with self._lock:
            self.metrics.total_timeout += 1
            if pid in self.metrics.active_processes:
                info = self.metrics.active_processes.pop(pid)
                logger.warning(f"Subprocess PID={pid} timed out after {info.timeout}s")

    async def record_cancellation(self, pid: int) -> None:
        """Record a subprocess cancellation."""
        async with self._lock:
            self.metrics.total_cancelled += 1
            if pid in self.metrics.active_processes:
                info = self.metrics.active_processes.pop(pid)
                duration = time.time() - info.start_time
                logger.debug(f"Subprocess PID={pid} cancelled after {duration:.1f}s")

    def get_active_count(self) -> int:
        """Get count of currently active subprocesses."""
        return len(self.metrics.active_processes)

    def get_metrics(self) -> SubprocessMetrics:
        """Get current metrics (returns a copy)."""
        return SubprocessMetrics(
            total_spawned=self.metrics.total_spawned,
            total_completed=self.metrics.total_completed,
            total_timeout=self.metrics.total_timeout,
            total_cancelled=self.metrics.total_cancelled,
            active_processes=dict(self.metrics.active_processes),
        )

    async def terminate_process(
        self,
        pid: int,
        timeout: float = 2.0,
        process: asyncio.subprocess.Process | None = None,
        cleanup_cmd: list[str] | None = None,
    ) -> None:
        """
        Terminate a subprocess robustly.

        On Windows, this kills the entire process tree to handle shell wrappers.
        On other platforms, it sends SIGTERM, waits, and then SIGKILL if needed.
        """
        # Only hold lock for retrieval
        async with self._lock:
            info = self.metrics.active_processes.get(pid)

        # Determine which process object to use
        target_process = None
        if info and info.process:
            target_process = info.process
        elif process:
            target_process = process

        if not target_process:
            return

        if target_process.returncode is not None:
            # Already exited
            return

        logger.debug(f"Terminating subprocess PID={pid} (Platform: {sys.platform})")

        # Execute cleanup command if present
        cmd_to_run = cleanup_cmd
        if not cmd_to_run and info and info.cleanup_cmd:
            cmd_to_run = info.cleanup_cmd

        if cmd_to_run:
            try:
                logger.debug(f"Executing cleanup command for PID={pid}: {cmd_to_run}")
                cleanup_proc = await asyncio.create_subprocess_exec(
                    *cmd_to_run,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(cleanup_proc.wait(), timeout=5.0)
            except Exception as e:
                logger.warning(f"Failed to execute cleanup command for PID={pid}: {e}")

        try:
            # 1. Attempt termination (SIGTERM)
            if sys.platform == "win32":
                # On Windows, terminate() only kills the shell wrapper.
                # force kill the process tree to get the actual agent process.
                try:
                    # Use asyncio.create_subprocess_shell for non-blocking execution
                    proc = await asyncio.create_subprocess_shell(
                        f"taskkill /F /T /PID {pid}",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.wait()
                except Exception as e:
                    logger.warning(f"Failed to run taskkill for PID {pid}: {e}")
                    # Fallback to standard terminate
                    target_process.terminate()
            else:
                target_process.terminate()

            # 2. Wait for exit with timeout
            try:
                await asyncio.wait_for(target_process.wait(), timeout=timeout)
                return
            except TimeoutError:
                logger.warning(
                    f"Process {pid} did not exit after {timeout}s (SIGTERM), "
                    "forcing kill (SIGKILL)..."
                )

            # 3. Force Kill (SIGKILL) if still running
            try:
                target_process.kill()
                # Give it a moment to die
                await asyncio.wait_for(target_process.wait(), timeout=timeout)
            except TimeoutError:
                logger.error(f"Process {pid} failed to die even after SIGKILL!")
            except ProcessLookupError:
                # Process already gone
                pass
            except Exception as e:
                logger.error(f"Error killing process {pid}: {e}")

        except Exception as e:
            logger.error(f"Error terminating process {pid}: {e}")

    async def cleanup(self) -> None:
        """Terminate and wait for all active subprocesses."""
        async with self._lock:
            # Use a copy of keys to avoid modification during iteration
            pids = list(self.metrics.active_processes.keys())

        if not pids:
            return

        logger.info(f"Cleaning up {len(pids)} active subprocesses...")

        # Request termination for all in parallel
        if pids:
            await asyncio.gather(
                *(self.terminate_process(pid) for pid in pids), return_exceptions=True
            )

        # Capture processes to wait on
        processes_to_wait = []
        async with self._lock:
            for pid in pids:
                info = self.metrics.active_processes.get(pid)
                if info and info.process and info.process.returncode is None:
                    processes_to_wait.append((pid, info.process))

        if not processes_to_wait:
            return

        async def wait_and_kill(pid, proc):
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except (TimeoutError, ProcessLookupError, AttributeError):
                try:
                    if proc.returncode is None:
                        logger.debug(f"Killing subprocess PID={pid} (timeout)")
                        proc.kill()
                        await proc.wait()
                except Exception:
                    pass

            # Untrack explicitly
            await self.untrack_process(pid, proc.returncode)

        # Execute waits in parallel
        await asyncio.gather(
            *(wait_and_kill(pid, proc) for pid, proc in processes_to_wait),
            return_exceptions=True,
        )

        logger.info("Subprocess cleanup complete")


# Global instance
subprocess_manager = SubprocessManager()
