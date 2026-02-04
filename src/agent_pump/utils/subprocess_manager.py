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
                logger.info(
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
                logger.info(f"Subprocess PID={pid} cancelled after {duration:.1f}s")

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


# Global instance
subprocess_manager = SubprocessManager()
