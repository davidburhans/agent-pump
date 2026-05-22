"""Unit tests for subprocess manager."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.utils.subprocess_manager import (
    SubprocessInfo,
    SubprocessManager,
    SubprocessMetrics,
)


class TestSubprocessInfo:
    """Tests for SubprocessInfo dataclass."""

    def test_subprocess_info_creation(self) -> None:
        """Test creating SubprocessInfo with all fields."""
        info = SubprocessInfo(
            pid=12345,
            command="gemini --yolo",
            project_path=Path("/test/project"),
            start_time=time.time(),
            timeout=600,
        )
        assert info.pid == 12345
        assert info.command == "gemini --yolo"
        assert info.project_path == Path("/test/project")
        assert isinstance(info.start_time, float)
        assert info.timeout == 600

    def test_subprocess_info_optional_project_path(self) -> None:
        """Test creating SubprocessInfo with None project path."""
        info = SubprocessInfo(
            pid=12345, command="pytest", project_path=None, start_time=time.time(), timeout=300
        )
        assert info.project_path is None


class TestSubprocessManager:
    """Tests for SubprocessManager."""

    @pytest.fixture
    def manager(self) -> SubprocessManager:
        """Create a fresh SubprocessManager instance."""
        return SubprocessManager()

    @pytest.fixture
    def sample_info(self) -> SubprocessInfo:
        """Create sample SubprocessInfo for testing."""
        return SubprocessInfo(
            pid=12345,
            command="gemini --yolo",
            project_path=Path("/test/project"),
            start_time=time.time(),
            timeout=600,
        )

    @pytest.mark.asyncio
    async def test_track_process(
        self, manager: SubprocessManager, sample_info: SubprocessInfo
    ) -> None:
        """Test tracking a new process."""
        await manager.track_process(12345, sample_info)

        assert manager.get_active_count() == 1
        assert manager.metrics.total_spawned == 1
        assert 12345 in manager.metrics.active_processes
        assert manager.metrics.active_processes[12345] == sample_info

    @pytest.mark.asyncio
    async def test_untrack_process(
        self, manager: SubprocessManager, sample_info: SubprocessInfo
    ) -> None:
        """Test untracking a completed process."""
        await manager.track_process(12345, sample_info)
        await manager.untrack_process(12345, exit_code=0)

        assert manager.get_active_count() == 0
        assert manager.metrics.total_completed == 1
        assert 12345 not in manager.metrics.active_processes

    @pytest.mark.asyncio
    async def test_untrack_nonexistent_process(self, manager: SubprocessManager) -> None:
        """Test untracking a process that was never tracked."""
        await manager.untrack_process(99999, exit_code=0)

        assert manager.get_active_count() == 0
        assert manager.metrics.total_completed == 0  # Should not increment

    @pytest.mark.asyncio
    async def test_record_timeout(
        self, manager: SubprocessManager, sample_info: SubprocessInfo
    ) -> None:
        """Test recording a timeout."""
        await manager.track_process(12345, sample_info)
        await manager.record_timeout(12345)

        assert manager.get_active_count() == 0
        assert manager.metrics.total_timeout == 1
        assert 12345 not in manager.metrics.active_processes

    @pytest.mark.asyncio
    async def test_record_cancellation(
        self, manager: SubprocessManager, sample_info: SubprocessInfo
    ) -> None:
        """Test recording a cancellation."""
        await manager.track_process(12345, sample_info)
        await manager.record_cancellation(12345)

        assert manager.get_active_count() == 0
        assert manager.metrics.total_cancelled == 1
        assert 12345 not in manager.metrics.active_processes

    @pytest.mark.asyncio
    async def test_multiple_processes(self, manager: SubprocessManager) -> None:
        """Test tracking multiple processes simultaneously."""
        info1 = SubprocessInfo(
            pid=11111, command="cmd1", project_path=None, start_time=time.time(), timeout=100
        )
        info2 = SubprocessInfo(
            pid=22222, command="cmd2", project_path=None, start_time=time.time(), timeout=200
        )
        info3 = SubprocessInfo(
            pid=33333, command="cmd3", project_path=None, start_time=time.time(), timeout=300
        )

        await manager.track_process(11111, info1)
        await manager.track_process(22222, info2)
        await manager.track_process(33333, info3)

        assert manager.get_active_count() == 3
        assert manager.metrics.total_spawned == 3

        await manager.untrack_process(11111, exit_code=0)
        await manager.record_timeout(22222)

        assert manager.get_active_count() == 1
        assert manager.metrics.total_completed == 1
        assert manager.metrics.total_timeout == 1
        assert 33333 in manager.metrics.active_processes

    @pytest.mark.asyncio
    async def test_get_metrics_returns_copy(
        self, manager: SubprocessManager, sample_info: SubprocessInfo
    ) -> None:
        """Test that get_metrics returns a copy, not a reference."""
        await manager.track_process(12345, sample_info)
        metrics1 = manager.get_metrics()

        # Modify the returned metrics
        metrics1.total_spawned = 999

        # Should not affect the original
        metrics2 = manager.get_metrics()
        assert metrics2.total_spawned == 1

    @pytest.mark.asyncio
    async def test_concurrent_access(self, manager: SubprocessManager) -> None:
        """Test thread-safe concurrent access."""

        async def track_and_untrack(pid: int) -> None:
            info = SubprocessInfo(
                pid=pid, command=f"cmd{pid}", project_path=None, start_time=time.time(), timeout=100
            )
            await manager.track_process(pid, info)
            await asyncio.sleep(0.01)  # Small delay
            await manager.untrack_process(pid, exit_code=0)

        # Run multiple concurrent operations
        tasks = [track_and_untrack(i) for i in range(100)]
        await asyncio.gather(*tasks)

        assert manager.metrics.total_spawned == 100
        assert manager.metrics.total_completed == 100
        assert manager.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_terminate_process_windows_nonblocking(self, manager: SubprocessManager) -> None:
        """Verify that terminate_process uses asyncio.create_subprocess_shell on Windows."""
        pid = 12345

        # Track a dummy process so terminate_process proceeds
        mock_process = MagicMock()
        mock_process.returncode = None
        info = SubprocessInfo(
            pid=pid,
            command="test",
            project_path=None,
            start_time=time.time(),
            timeout=100,
            process=mock_process,
        )
        await manager.track_process(pid, info)

        # Mock asyncio.create_subprocess_shell
        mock_proc = AsyncMock()
        mock_proc.wait = AsyncMock()

        with (
            patch("sys.platform", "win32"),
            patch("subprocess.run") as mock_run,
            patch("asyncio.create_subprocess_shell", return_value=mock_proc) as mock_create_shell,
        ):
            await manager.terminate_process(pid)

            # This confirms the FIX: blocking subprocess.run is NOT called
            mock_run.assert_not_called()

            # This confirms the FIX: asyncio.create_subprocess_shell IS called
            mock_create_shell.assert_called_once()
            args, kwargs = mock_create_shell.call_args
            assert f"taskkill /F /T /PID {pid}" in args[0]
            assert kwargs.get("stdout") == asyncio.subprocess.DEVNULL
            assert kwargs.get("stderr") == asyncio.subprocess.DEVNULL

    @pytest.mark.asyncio
    async def test_cleanup_parallel(self, manager: SubprocessManager) -> None:
        """Verify that cleanup executes terminate_process sequentially (concurrently awaited)."""
        pids = [1001, 1002, 1003]

        # Track dummy processes
        for pid in pids:
            mock_process = MagicMock()
            mock_process.returncode = None

            # Define async side effect to avoid RuntimeWarning about unawaited coroutine
            async def sleep_wait():
                await asyncio.sleep(0.1)

            mock_process.wait = AsyncMock(side_effect=sleep_wait)

            info = SubprocessInfo(
                pid=pid,
                command=f"test{pid}",
                project_path=None,
                start_time=time.time(),
                timeout=100,
                process=mock_process,
            )
            await manager.track_process(pid, info)

        # Patch terminate_process to simulate slow operation
        original_terminate = manager.terminate_process

        async def slow_terminate(pid):
            await asyncio.sleep(0.1)  # Simulate delay
            await original_terminate(pid)

        # Patch on the instance
        with (
            patch("agent_pump.utils.subprocess_manager.sys.platform", "linux"),
            patch.object(manager, "terminate_process", side_effect=slow_terminate),
        ):
            start_time = time.time()
            await manager.cleanup()
            duration = time.time() - start_time

            print(f"Cleanup took {duration:.2f}s")
            assert duration < 0.35, f"Cleanup took {duration:.2f}s, expected < 0.35s (parallel)"
            assert duration > 0.09, "Cleanup too fast, did it really sleep?"


class TestSubprocessMetrics:
    """Tests for SubprocessMetrics dataclass."""

    def test_default_metrics(self) -> None:
        """Test default values for metrics."""
        metrics = SubprocessMetrics()
        assert metrics.total_spawned == 0
        assert metrics.total_completed == 0
        assert metrics.total_timeout == 0
        assert metrics.total_cancelled == 0
        assert metrics.active_processes == {}

    def test_metrics_with_processes(self) -> None:
        """Test metrics with active processes."""
        info1 = SubprocessInfo(
            pid=11111, command="cmd1", project_path=None, start_time=time.time(), timeout=100
        )
        info2 = SubprocessInfo(
            pid=22222, command="cmd2", project_path=None, start_time=time.time(), timeout=200
        )

        metrics = SubprocessMetrics(
            total_spawned=5,
            total_completed=3,
            total_timeout=1,
            total_cancelled=1,
            active_processes={11111: info1, 22222: info2},
        )

        assert len(metrics.active_processes) == 2
        assert metrics.active_processes[11111].command == "cmd1"
