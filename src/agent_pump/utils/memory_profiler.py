"""Memory profiling and leak detection utilities."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""

    timestamp: float
    rss_mb: float  # Resident set size in MB
    vms_mb: float  # Virtual memory size in MB
    percent: float  # Memory percentage used


@dataclass
class MemoryStats:
    """Memory statistics over time."""

    current: MemorySnapshot | None = None
    peak_rss_mb: float = 0.0
    peak_vms_mb: float = 0.0
    snapshots: list[MemorySnapshot] = field(default_factory=list)


class MemoryProfiler:
    """Memory usage tracking and leak detection."""

    def __init__(self, max_snapshots: int = 100):
        self.max_snapshots = max_snapshots
        self.stats = MemoryStats()
        self._enabled = False

    def enable(self) -> None:
        """Enable memory profiling."""
        try:
            import psutil  # type: ignore  # noqa: F401

            self._enabled = True
        except ImportError:
            logger.warning("psutil not available, memory profiling disabled")
            self._enabled = False

    def disable(self) -> None:
        """Disable memory profiling."""
        self._enabled = False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def take_snapshot(self) -> MemorySnapshot | None:
        """Take a memory snapshot."""
        if not self._enabled:
            return None

        try:
            import psutil  # type: ignore

            process = psutil.Process()
            mem_info = process.memory_info()
            mem_percent = process.memory_percent()

            snapshot = MemorySnapshot(
                timestamp=time.time(),
                rss_mb=mem_info.rss / 1024 / 1024,
                vms_mb=mem_info.vms / 1024 / 1024,
                percent=mem_percent,
            )

            self.stats.current = snapshot
            self.stats.peak_rss_mb = max(self.stats.peak_rss_mb, snapshot.rss_mb)
            self.stats.peak_vms_mb = max(self.stats.peak_vms_mb, snapshot.vms_mb)

            self.stats.snapshots.append(snapshot)
            if len(self.stats.snapshots) > self.max_snapshots:
                self.stats.snapshots.pop(0)

            return snapshot
        except Exception as e:
            logger.error(f"Failed to take memory snapshot: {e}")
            return None

    def detect_leak(self, window_size: int = 10) -> dict[str, Any] | None:
        """Detect potential memory leaks."""
        if len(self.stats.snapshots) < window_size * 2:
            return None

        recent = self.stats.snapshots[-window_size:]
        older = self.stats.snapshots[-window_size * 2 : -window_size]

        recent_avg = sum(s.rss_mb for s in recent) / window_size
        older_avg = sum(s.rss_mb for s in older) / window_size

        growth = recent_avg - older_avg
        growth_percent = (growth / older_avg) * 100 if older_avg > 0 else 0

        if growth_percent > 20:  # 20% growth threshold
            return {
                "detected": True,
                "growth_mb": growth,
                "growth_percent": growth_percent,
                "older_avg_mb": older_avg,
                "recent_avg_mb": recent_avg,
                "recommendation": "Consider restarting the application",
            }

        return {"detected": False}

    def get_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        return self.stats


# Global instance
memory_profiler = MemoryProfiler()
