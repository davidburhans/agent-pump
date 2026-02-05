"""Subprocess lifecycle management and monitoring."""

import asyncio
import logging
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

    async def terminate_process(self, pid: int) -> None:
        """
        Terminate a subprocess robustly.

        On Windows, this kills the entire process tree to handle shell wrappers.
        On other platforms, it sends SIGTERM.
        """
        import subprocess
        import sys

        async with self._lock:
            info = self.metrics.active_processes.get(pid)
            if not info or not info.process:
                return

            if info.process.returncode is not None:
                # Already exited
                return

            logger.debug(f"Terminating subprocess PID={pid} (Platform: {sys.platform})")

            try:
                if sys.platform == "win32":
                    # On Windows, terminate() only kills the shell wrapper.
                    # force kill the process tree to get the actual agent process.
                    try:
                        subprocess.run(
                            f"taskkill /F /T /PID {pid}",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to run taskkill for PID {pid}: {e}")
                        # Fallback to standard terminate
                        info.process.terminate()
                else:
                    info.process.terminate()

                # We don't wait here, we let the cleanup loop or the specific backend handler wait
            except Exception as e:
                logger.error(f"Error terminating process {pid}: {e}")

    async def cleanup(self) -> None:
        """Terminate and wait for all active subprocesses."""
        # Use a copy of keys to avoid modification during iteration
        pids = list(self.metrics.active_processes.keys())

        if not pids:
            return

        logger.info(f"Cleaning up {len(pids)} active subprocesses...")

        # Request termination for all
        for pid in pids:
            await self.terminate_process(pid)

        # Wait for all processes to exit
        # We need to re-acquire info because terminate_process releases lock
        for pid in pids:
            # Check if still active/tracked
            # We access metrics.active_processes directly but we should probably take a lock
            # However, during shutdown/cleanup we might be less strict or we can just try-except
            pass

        async with self._lock:
            # Now wait for them all to actually die
            remaining_pids = list(self.metrics.active_processes.keys())
            for pid in remaining_pids:
                info = self.metrics.active_processes.get(pid)
                if not info or not info.process:
                    continue

                try:
                    await asyncio.wait_for(info.process.wait(), timeout=2.0)
                except (TimeoutError, ProcessLookupError, AttributeError):
                    try:
                        if info.process and info.process.returncode is None:
                            logger.debug(f"Killing subprocess PID={pid} (timeout)")
                            info.process.kill()
                            await info.process.wait()
                    except (ProcessLookupError, AttributeError):
                        pass

                # Remove from tracking
                self.metrics.active_processes.pop(pid, None)

            logger.info("Subprocess cleanup complete")


# Global instance
subprocess_manager = SubprocessManager()
