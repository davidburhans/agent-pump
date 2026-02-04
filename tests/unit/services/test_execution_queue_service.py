"""Unit tests for ExecutionQueueService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.execution_queue import (
    ExecutionQueueConfig,
    ExecutionQueueItem,
    QueuePriority,
    QueueStatus,
)
from agent_pump.models.workspace import Workspace
from agent_pump.services.execution_queue_service import ExecutionQueueService


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def workflow_service():
    """Create a mock workflow service."""
    service = MagicMock()
    service.start_project = AsyncMock(return_value=True)
    return service


@pytest.fixture
def execution_queue_service(event_bus, workflow_service):
    """Create an execution queue service with mocked workflow service."""
    service = ExecutionQueueService(event_bus, workflow_service)
    return service


@pytest.fixture
def workspace(tmp_path):
    """Create a test workspace."""
    return Workspace(name="test-workspace")


@pytest.fixture
def project_paths(tmp_path):
    """Create test project paths."""
    return {
        "project1": tmp_path / "project1",
        "project2": tmp_path / "project2",
        "project3": tmp_path / "project3",
        "project4": tmp_path / "project4",
    }


class TestExecutionQueueServiceEnqueue:
    """Tests for enqueueing projects."""

    @pytest.mark.asyncio
    async def test_enqueue_project_starts_immediately_when_slots_available(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that enqueueing starts project immediately when slots are available."""
        path = project_paths["project1"]

        success, message = await execution_queue_service.enqueue_project(workspace, path)

        assert success is True
        assert "started immediately" in message.lower()
        # Project was started, so not in queue anymore
        assert workspace.get_queue_position(path) is None

    @pytest.mark.asyncio
    async def test_enqueue_project_queues_when_limit_reached(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that enqueueing adds project to queue when limit reached."""
        # Set limit to 1 and disable auto-start to test queueing
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # First project marked as active
        workspace.queue_project(path1, QueuePriority.MEDIUM)
        workspace.mark_project_active(path1)

        # Second project should be queued
        success, message = await execution_queue_service.enqueue_project(workspace, path2)

        assert success is True
        assert "position" in message.lower()
        assert workspace.get_queue_position(path2) == 1

    @pytest.mark.asyncio
    async def test_enqueue_with_high_priority(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test enqueueing with high priority."""
        # Disable auto-start to test priority in queue
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )
        path = project_paths["project1"]

        # First mark a project as active to fill the slot
        other_path = project_paths["project2"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        success, message = await execution_queue_service.enqueue_project(
            workspace, path, priority=QueuePriority.HIGH
        )

        assert success is True
        queued = workspace.get_queued_projects()
        assert len(queued) == 1
        assert queued[0].priority == QueuePriority.HIGH

    @pytest.mark.asyncio
    async def test_enqueue_already_active_fails(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that enqueueing an already active project fails."""
        path = project_paths["project1"]

        # First, manually mark as active
        workspace.queue_project(path, QueuePriority.MEDIUM)
        workspace.mark_project_active(path)

        success, message = await execution_queue_service.enqueue_project(workspace, path)

        assert success is False
        assert "already running" in message.lower()

    @pytest.mark.asyncio
    async def test_enqueue_already_queued_updates_priority(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that enqueueing an already queued project updates priority."""
        # Disable auto-start to keep project in queue
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )
        path = project_paths["project1"]

        # Fill the slot
        other_path = project_paths["project2"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # First enqueue with medium priority
        await execution_queue_service.enqueue_project(workspace, path, QueuePriority.MEDIUM)

        # Enqueue again with high priority
        success, message = await execution_queue_service.enqueue_project(
            workspace, path, QueuePriority.HIGH
        )

        assert success is True
        assert "updated" in message.lower()
        queued = workspace.get_queued_projects()
        assert queued[0].priority == QueuePriority.HIGH


class TestExecutionQueueServiceDequeue:
    """Tests for dequeuing projects."""

    @pytest.mark.asyncio
    async def test_dequeue_removes_project(self, execution_queue_service, workspace, project_paths):
        """Test that dequeueing removes project from queue."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )
        path = project_paths["project1"]

        # Fill the slot
        other_path = project_paths["project2"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Queue the project we want to dequeue
        await execution_queue_service.enqueue_project(workspace, path)

        success, message = await execution_queue_service.dequeue_project(workspace, path)

        assert success is True
        assert "removed" in message.lower()
        assert workspace.get_queue_position(path) is None

    @pytest.mark.asyncio
    async def test_dequeue_active_project_fails(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that dequeueing an active project fails."""
        path = project_paths["project1"]

        # Mark as active
        workspace.queue_project(path, QueuePriority.MEDIUM)
        workspace.mark_project_active(path)

        success, message = await execution_queue_service.dequeue_project(workspace, path)

        assert success is False
        assert "active" in message.lower()

    @pytest.mark.asyncio
    async def test_dequeue_not_in_queue_fails(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that dequeueing a project not in queue fails."""
        path = project_paths["project1"]

        success, message = await execution_queue_service.dequeue_project(workspace, path)

        assert success is False
        assert "not found" in message.lower()


class TestExecutionQueueServicePriority:
    """Tests for priority ordering."""

    @pytest.mark.asyncio
    async def test_priority_ordering_high_first(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that high priority projects come before medium/low."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]
        path3 = project_paths["project3"]

        # Fill the slot
        other_path = project_paths["project4"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Enqueue in order: medium, high, low
        await execution_queue_service.enqueue_project(workspace, path1, QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, path2, QueuePriority.HIGH)
        await execution_queue_service.enqueue_project(workspace, path3, QueuePriority.LOW)

        queued = workspace.get_queued_projects()

        # Should be ordered: high (path2), medium (path1), low (path3)
        assert len(queued) == 3
        assert queued[0].project_path == path2
        assert queued[1].project_path == path1
        assert queued[2].project_path == path3

    @pytest.mark.asyncio
    async def test_equal_priority_fifo_order(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that equal priority projects maintain FIFO order."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]
        path3 = project_paths["project3"]

        # Fill the slot
        other_path = project_paths["project4"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Enqueue in order
        await execution_queue_service.enqueue_project(workspace, path1, QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, path2, QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, path3, QueuePriority.MEDIUM)

        queued = workspace.get_queued_projects()

        assert len(queued) == 3
        assert queued[0].project_path == path1
        assert queued[1].project_path == path2
        assert queued[2].project_path == path3


class TestExecutionQueueServiceConcurrencyLimits:
    """Tests for concurrency limit enforcement."""

    @pytest.mark.asyncio
    async def test_concurrency_limit_enforced(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that concurrency limits are enforced."""
        # Set limit to 2
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=False
        )

        # Manually set up: 1 active, then queue 2 more
        path_active = project_paths["project1"]
        workspace.queue_project(path_active, QueuePriority.MEDIUM)
        workspace.mark_project_active(path_active)

        path2 = project_paths["project2"]
        path3 = project_paths["project3"]

        # These should be queued since slot limit reached
        success2, _ = await execution_queue_service.enqueue_project(workspace, path2)
        success3, msg3 = await execution_queue_service.enqueue_project(workspace, path3)

        assert success2 is True
        assert success3 is True
        assert workspace.get_queue_position(path2) == 1
        assert workspace.get_queue_position(path3) == 2

    @pytest.mark.asyncio
    async def test_can_project_start_under_limit(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test can_project_start when under limit."""
        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=3)
        path = project_paths["project1"]

        can_start, reason = execution_queue_service.can_project_start(workspace, path)

        assert can_start is True
        assert "can start" in reason.lower()

    @pytest.mark.asyncio
    async def test_can_project_start_at_limit(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test can_project_start when at limit."""
        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=1)
        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Mark first as active
        workspace.queue_project(path1, QueuePriority.MEDIUM)
        workspace.mark_project_active(path1)

        can_start, reason = execution_queue_service.can_project_start(workspace, path2)

        assert can_start is False
        assert "limit reached" in reason.lower()

    @pytest.mark.asyncio
    async def test_unlimited_concurrency(self, execution_queue_service, workspace, project_paths):
        """Test that max_concurrent=0 means unlimited."""
        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=0)

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Should be able to start both
        await execution_queue_service.enqueue_project(workspace, path1)
        can_start, _ = execution_queue_service.can_project_start(workspace, path2)

        assert can_start is True


class TestExecutionQueueServiceAutoStart:
    """Tests for auto-start behavior."""

    @pytest.mark.asyncio
    async def test_auto_start_next_project(self, execution_queue_service, workspace, project_paths):
        """Test that next project auto-starts when slot becomes available."""
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=True
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Start first project
        await execution_queue_service.enqueue_project(workspace, path1)
        workspace.mark_project_active(path1)

        # Queue second
        await execution_queue_service.enqueue_project(workspace, path2)

        # Mark first as completed
        await execution_queue_service.on_project_completed(workspace, path1)

        # Second should have been started
        execution_queue_service.workflow_service.start_project.assert_called_with(path2)

    @pytest.mark.asyncio
    async def test_auto_start_disabled(self, execution_queue_service, workspace, project_paths):
        """Test that auto-start can be disabled."""
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Queue two projects (will both stay queued with auto_start=False and limit=1)
        await execution_queue_service.enqueue_project(workspace, path1)
        await execution_queue_service.enqueue_project(workspace, path2)

        # Mark first as completed (but auto_start is disabled)
        workspace.mark_project_active(path1)
        await execution_queue_service.on_project_completed(workspace, path1)

        # Second should NOT have been started
        execution_queue_service.workflow_service.start_project.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_next_queued_project(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test explicitly starting next queued project."""
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Start first project
        await execution_queue_service.enqueue_project(workspace, path1)
        workspace.mark_project_active(path1)

        # Queue second
        await execution_queue_service.enqueue_project(workspace, path2)

        # Manually start next
        started_path = await execution_queue_service.start_next_queued_project(workspace)

        assert started_path == path2


class TestExecutionQueueServiceCancel:
    """Tests for cancelling queued projects."""

    @pytest.mark.asyncio
    async def test_cancel_queued_project(self, execution_queue_service, workspace, project_paths):
        """Test cancelling a queued project."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )
        path = project_paths["project1"]

        # Fill the slot
        other_path = project_paths["project2"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        await execution_queue_service.enqueue_project(workspace, path)

        success, message = await execution_queue_service.cancel_queued_project(workspace, path)

        assert success is True
        assert "cancelled" in message.lower()

        # Verify it's marked as cancelled
        for item in workspace.execution_queue:
            if item.project_path == path:
                assert item.status == QueueStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_not_in_queue_fails(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that cancelling a project not in queue fails."""
        path = project_paths["project1"]

        success, message = await execution_queue_service.cancel_queued_project(workspace, path)

        assert success is False
        assert "not found" in message.lower()


class TestExecutionQueueServicePriorityUpdate:
    """Tests for updating project priority."""

    @pytest.mark.asyncio
    async def test_update_priority_changes_position(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that updating priority changes queue position."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Fill the slot
        other_path = project_paths["project3"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Queue with equal priority
        await execution_queue_service.enqueue_project(workspace, path1, QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, path2, QueuePriority.MEDIUM)

        # Update second to high priority
        success, message = await execution_queue_service.update_project_priority(
            workspace, path2, QueuePriority.HIGH
        )

        assert success is True
        assert "priority" in message.lower()

        # Should now be first
        queued = workspace.get_queued_projects()
        assert queued[0].project_path == path2

    @pytest.mark.asyncio
    async def test_update_priority_active_project_fails(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that updating priority of active project fails."""
        path = project_paths["project1"]

        # Mark as active
        workspace.queue_project(path, QueuePriority.MEDIUM)
        workspace.mark_project_active(path)

        success, message = await execution_queue_service.update_project_priority(
            workspace, path, QueuePriority.HIGH
        )

        assert success is False
        assert "active" in message.lower()


class TestExecutionQueueServiceQueueStatus:
    """Tests for queue status reporting."""

    @pytest.mark.asyncio
    async def test_get_queue_status(self, execution_queue_service, workspace, project_paths):
        """Test getting queue status."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=False
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Set up: 1 active, 1 queued
        workspace.queue_project(path1, QueuePriority.MEDIUM)
        workspace.mark_project_active(path1)
        await execution_queue_service.enqueue_project(workspace, path2)

        status = execution_queue_service.get_queue_status(workspace)

        assert "config" in status
        assert "stats" in status
        assert "active_projects" in status
        assert "queued_projects" in status
        assert status["stats"]["active"] == 1
        assert status["stats"]["queued"] == 1

    @pytest.mark.asyncio
    async def test_get_project_queue_info(self, execution_queue_service, workspace, project_paths):
        """Test getting info for specific project."""
        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path = project_paths["project1"]

        # Fill the slot
        other_path = project_paths["project2"]
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        await execution_queue_service.enqueue_project(workspace, path, QueuePriority.HIGH)

        info = execution_queue_service.get_project_queue_info(workspace, path)

        assert info is not None
        assert info["status"] == "queued"
        assert info["priority"] == "HIGH"
        assert info["position"] == 1
        assert "queued_at" in info
        assert "wait_time_seconds" in info

    @pytest.mark.asyncio
    async def test_get_project_queue_info_not_in_queue(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test getting info for project not in queue."""
        path = project_paths["project1"]

        info = execution_queue_service.get_project_queue_info(workspace, path)

        assert info is None


class TestExecutionQueueServiceFailureHandling:
    """Tests for handling project failures."""

    @pytest.mark.asyncio
    async def test_on_project_failed_marks_failed(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that on_project_failed marks project as failed."""
        path = project_paths["project1"]

        workspace.queue_project(path, QueuePriority.MEDIUM)
        workspace.mark_project_active(path)

        await execution_queue_service.on_project_failed(workspace, path)

        for item in workspace.execution_queue:
            if item.project_path == path:
                assert item.status == QueueStatus.FAILED

    @pytest.mark.asyncio
    async def test_on_project_failed_triggers_next(
        self, execution_queue_service, workspace, project_paths
    ):
        """Test that failure triggers next project."""
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=True
        )

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        await execution_queue_service.enqueue_project(workspace, path1)
        workspace.mark_project_active(path1)
        await execution_queue_service.enqueue_project(workspace, path2)

        # Mark first as failed
        await execution_queue_service.on_project_failed(workspace, path1)

        # Second should have been started
        execution_queue_service.workflow_service.start_project.assert_called_with(path2)


class TestExecutionQueueServiceCleanup:
    """Tests for queue cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_completed_items(self, execution_queue_service, workspace, project_paths):
        """Test that old completed items are cleaned up."""
        from datetime import datetime, timedelta

        path1 = project_paths["project1"]
        path2 = project_paths["project2"]

        # Add completed items with old timestamps
        old_item = ExecutionQueueItem(
            project_path=path1,
            status=QueueStatus.COMPLETED,
            queued_at=datetime.now() - timedelta(hours=2),
        )
        recent_item = ExecutionQueueItem(
            project_path=path2,
            status=QueueStatus.COMPLETED,
            queued_at=datetime.now() - timedelta(minutes=30),
        )

        workspace.execution_queue.append(old_item)
        workspace.execution_queue.append(recent_item)

        # Clean up items older than 1 hour
        removed = workspace.cleanup_completed_queue_items(max_age_hours=1)

        assert removed == 1
        assert len(workspace.execution_queue) == 1
        assert workspace.execution_queue[0].project_path == path2
