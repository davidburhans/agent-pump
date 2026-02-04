"""Unit tests for memory profiler."""

import time
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.utils.memory_profiler import (
    MemoryProfiler,
    MemorySnapshot,
    MemoryStats,
)


class TestMemorySnapshot:
    """Tests for MemorySnapshot dataclass."""

    def test_snapshot_creation(self) -> None:
        """Test creating a memory snapshot."""
        snapshot = MemorySnapshot(timestamp=time.time(), rss_mb=100.5, vms_mb=200.5, percent=5.2)
        assert snapshot.rss_mb == 100.5
        assert snapshot.vms_mb == 200.5
        assert snapshot.percent == 5.2
        assert isinstance(snapshot.timestamp, float)


class TestMemoryStats:
    """Tests for MemoryStats dataclass."""

    def test_default_stats(self) -> None:
        """Test default values for stats."""
        stats = MemoryStats()
        assert stats.current is None
        assert stats.peak_rss_mb == 0.0
        assert stats.peak_vms_mb == 0.0
        assert stats.snapshots == []

    def test_stats_with_snapshots(self) -> None:
        """Test stats with snapshots."""
        snapshot1 = MemorySnapshot(timestamp=time.time(), rss_mb=100, vms_mb=200, percent=5.0)
        snapshot2 = MemorySnapshot(timestamp=time.time() + 1, rss_mb=150, vms_mb=250, percent=7.5)

        stats = MemoryStats()
        stats.snapshots = [snapshot1, snapshot2]
        stats.current = snapshot2
        stats.peak_rss_mb = 150
        stats.peak_vms_mb = 250

        assert len(stats.snapshots) == 2
        assert stats.current.rss_mb == 150


class TestMemoryProfiler:
    """Tests for MemoryProfiler."""

    @pytest.fixture
    def profiler(self) -> MemoryProfiler:
        """Create a fresh MemoryProfiler instance."""
        return MemoryProfiler(max_snapshots=50)

    def test_initial_state(self, profiler: MemoryProfiler) -> None:
        """Test initial state of profiler."""
        assert not profiler.is_enabled
        assert profiler.max_snapshots == 50

    def test_enable_without_psutil(self, profiler: MemoryProfiler) -> None:
        """Test enable when psutil is not available."""
        with patch.dict("sys.modules", {"psutil": None}):
            profiler.enable()
            assert not profiler.is_enabled

    def test_enable_with_psutil(self, profiler: MemoryProfiler) -> None:
        """Test enable when psutil is available."""
        mock_psutil = MagicMock()
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            assert profiler.is_enabled

    def test_disable(self, profiler: MemoryProfiler) -> None:
        """Test disabling profiler."""
        mock_psutil = MagicMock()
        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            assert profiler.is_enabled
            profiler.disable()
            assert not profiler.is_enabled

    def test_take_snapshot_when_disabled(self, profiler: MemoryProfiler) -> None:
        """Test taking snapshot when profiler is disabled."""
        snapshot = profiler.take_snapshot()
        assert snapshot is None

    def test_take_snapshot_success(self, profiler: MemoryProfiler) -> None:
        """Test successful snapshot."""
        mock_process = MagicMock()
        mock_process.memory_info.return_value = MagicMock(
            rss=104857600, vms=209715200
        )  # 100MB, 200MB
        mock_process.memory_percent.return_value = 5.5

        mock_psutil = MagicMock()
        mock_psutil.Process.return_value = mock_process

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            snapshot = profiler.take_snapshot()

            assert snapshot is not None
            assert snapshot.rss_mb == 100.0
            assert snapshot.vms_mb == 200.0
            assert snapshot.percent == 5.5
            assert len(profiler.stats.snapshots) == 1

    def test_take_snapshot_exception(self, profiler: MemoryProfiler) -> None:
        """Test snapshot handling exceptions."""
        mock_psutil = MagicMock()
        mock_psutil.Process.side_effect = Exception("Test error")

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            snapshot = profiler.take_snapshot()
            assert snapshot is None

    def test_snapshot_rotation(self) -> None:
        """Test that old snapshots are removed when max is reached."""
        # Create a profiler with small max_snapshots for this specific test
        profiler = MemoryProfiler(max_snapshots=10)
        mock_process = MagicMock()
        mock_psutil = MagicMock()
        mock_psutil.Process.return_value = mock_process

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            # Take more snapshots than max_snapshots
            for _ in range(15):
                mock_process.memory_info.return_value = MagicMock(rss=104857600, vms=209715200)
                mock_process.memory_percent.return_value = 5.0
                profiler.take_snapshot()
                time.sleep(0.001)  # Small delay to ensure different timestamps

            assert len(profiler.stats.snapshots) == 10  # Max snapshots

    def test_peak_tracking(self, profiler: MemoryProfiler) -> None:
        """Test that peak values are tracked correctly."""
        values = [
            (104857600, 209715200, 5.0),  # 100MB, 200MB
            (157286400, 262144000, 7.5),  # 150MB, 250MB
            (125829120, 220200960, 6.0),  # 120MB, 210MB (lower than peak)
        ]

        mock_psutil = MagicMock()

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()

            for rss, vms, percent in values:
                mock_process = MagicMock()
                mock_process.memory_info.return_value = MagicMock(rss=rss, vms=vms)
                mock_process.memory_percent.return_value = percent
                mock_psutil.Process.return_value = mock_process

                profiler.take_snapshot()

            assert profiler.stats.peak_rss_mb == 150.0
            assert profiler.stats.peak_vms_mb == 250.0

    def test_detect_leak_insufficient_data(self, profiler: MemoryProfiler) -> None:
        """Test leak detection with insufficient data."""
        result = profiler.detect_leak()
        assert result is None

    def test_detect_leak_no_leak(self, profiler: MemoryProfiler) -> None:
        """Test leak detection when no leak is present."""
        mock_process = MagicMock()
        mock_psutil = MagicMock()
        mock_psutil.Process.return_value = mock_process

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()

            # Create stable memory usage (no growth)
            # Need at least window_size * 2 + 1 = 21 snapshots for reliable detection
            for i in range(21):
                mock_process.memory_info.return_value = MagicMock(
                    rss=104857600, vms=209715200
                )  # 100MB stable
                mock_process.memory_percent.return_value = 5.0
                profiler.take_snapshot()

            result = profiler.detect_leak()
            assert result is not None
            assert result["detected"] is False

    def test_detect_leak_with_growth(self, profiler: MemoryProfiler) -> None:
        """Test leak detection with memory growth."""
        mock_process = MagicMock()
        mock_psutil = MagicMock()
        mock_psutil.Process.return_value = mock_process

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()

            # Create growing memory usage (50% growth)
            # Need at least window_size * 2 + 1 = 21 snapshots for reliable detection
            for i in range(21):
                # First 11: 100MB, Next 10: 150MB (50% growth)
                size = 104857600 if i < 11 else 157286400
                mock_process.memory_info.return_value = MagicMock(rss=size, vms=209715200)
                mock_process.memory_percent.return_value = 5.0 + (i * 0.1)
                profiler.take_snapshot()

            result = profiler.detect_leak()
            assert result is not None
            assert result["detected"] is True
            assert result["growth_percent"] > 20  # Should detect > 20% growth

    def test_get_stats(self, profiler: MemoryProfiler) -> None:
        """Test getting stats."""
        mock_process = MagicMock()
        mock_process.memory_info.return_value = MagicMock(rss=104857600, vms=209715200)
        mock_process.memory_percent.return_value = 5.0

        mock_psutil = MagicMock()
        mock_psutil.Process.return_value = mock_process

        with patch.dict("sys.modules", {"psutil": mock_psutil}):
            profiler.enable()
            profiler.take_snapshot()

            stats = profiler.get_stats()
            assert stats.current is not None
            assert stats.current.rss_mb == 100.0
            assert len(stats.snapshots) == 1

    def test_custom_max_snapshots(self) -> None:
        """Test custom max snapshots setting."""
        profiler = MemoryProfiler(max_snapshots=50)
        assert profiler.max_snapshots == 50
