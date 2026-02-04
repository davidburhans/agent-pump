"""Integration tests for Execution Queue functionality."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.execution_queue import QueuePriority, QueueStatus
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
    """Create an execution queue service."""
    service = ExecutionQueueService(event_bus, workflow_service)
    return service


@pytest.fixture
def workspace(tmp_path):
    """Create a test workspace with multiple projects."""
    ws = Workspace(name="test-workspace")
    return ws


@pytest.fixture
def sample_projects(tmp_path):
    """Create sample project paths."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    return {
        "project1": projects_dir / "project1",
        "project2": projects_dir / "project2",
        "project3": projects_dir / "project3",
        "project4": projects_dir / "project4",
        "project5": projects_dir / "project5",
    }


class TestExecutionQueueWorkflow:
    """End-to-end tests for execution queue workflow."""

    @pytest.mark.asyncio
    async def test_full_queue_workflow(self, execution_queue_service, workspace, sample_projects):
        """Test complete queue workflow: enqueue, start, complete, trigger next."""
        # Set concurrency limit to 2
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=True
        )

        path1 = sample_projects["project1"]
        path2 = sample_projects["project2"]
        path3 = sample_projects["project3"]

        # Enqueue three projects (first 2 start immediately due to auto_start)
        success1, _ = await execution_queue_service.enqueue_project(workspace, path1)
        success2, _ = await execution_queue_service.enqueue_project(workspace, path2)
        success3, msg3 = await execution_queue_service.enqueue_project(workspace, path3)

        # First two should start immediately (slots available)
        # Third should be queued (limit reached)
        assert success1 is True
        assert success2 is True
        assert success3 is True
        assert "queued" in msg3.lower() or "position" in msg3.lower()

        # Mark first 2 as active to track them
        workspace.mark_project_active(path1)
        workspace.mark_project_active(path2)

        # Verify queue state
        assert workspace.get_active_projects_count() == 2
        assert workspace.get_queue_position(path3) == 1

        # Reset mock to track only the next call
        execution_queue_service.workflow_service.start_project.reset_mock()

        # Simulate completion of first project
        await execution_queue_service.on_project_completed(workspace, path1)

        # Third project should have been auto-started
        execution_queue_service.workflow_service.start_project.assert_called_once_with(path3)

    @pytest.mark.asyncio
    async def test_priority_affects_execution_order(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that priority affects which projects start first."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start to test priority in queue
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path_active = sample_projects["project4"]  # Will be active, not queued
        path1 = sample_projects["project1"]  # Will be queued as MEDIUM
        path2 = sample_projects["project2"]  # Will be queued as HIGH
        path3 = sample_projects["project3"]  # Will be queued as LOW

        # Mark one as active to fill the slot
        workspace.queue_project(path_active, QueuePriority.MEDIUM)
        workspace.mark_project_active(path_active)

        # Enqueue in order: medium, high, low
        await execution_queue_service.enqueue_project(workspace, path1, QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, path2, QueuePriority.HIGH)
        await execution_queue_service.enqueue_project(workspace, path3, QueuePriority.LOW)

        # Verify queue order: high (path2), medium (path1), low (path3)
        queued = workspace.get_queued_projects()
        assert len(queued) == 3
        assert queued[0].project_path == path2
        assert queued[1].project_path == path1
        assert queued[2].project_path == path3

        # Now enable auto-start and complete active project
        workspace.execution_queue_config.auto_start_queued = True
        await execution_queue_service.on_project_completed(workspace, path_active)

        # Verify path2 (high priority) was started first
        execution_queue_service.workflow_service.start_project.assert_called_once_with(path2)

    @pytest.mark.asyncio
    async def test_multiple_projects_complete_trigger_multiple_starts(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that completing multiple projects triggers multiple new starts."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start initially to fill queue
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=False
        )

        paths = [sample_projects[f"project{i}"] for i in range(1, 6)]

        # Manually set first 2 as active
        workspace.queue_project(paths[0], QueuePriority.MEDIUM)
        workspace.queue_project(paths[1], QueuePriority.MEDIUM)
        workspace.mark_project_active(paths[0])
        workspace.mark_project_active(paths[1])

        # Queue remaining 3 projects
        for path in paths[2:]:
            await execution_queue_service.enqueue_project(workspace, path)

        # Verify 3 are queued
        assert len(workspace.get_queued_projects()) == 3

        # Enable auto-start
        workspace.execution_queue_config.auto_start_queued = True

        # Complete both active projects
        await execution_queue_service.on_project_completed(workspace, paths[0])
        await execution_queue_service.on_project_completed(workspace, paths[1])

        # Two more should have been started
        assert execution_queue_service.workflow_service.start_project.call_count == 2


class TestExecutionQueuePersistence:
    """Tests for queue persistence across operations."""

    @pytest.mark.asyncio
    async def test_queue_persists_in_workspace(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that queue state persists in workspace model."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start to keep project in queue
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path = sample_projects["project1"]
        other_path = sample_projects["project2"]

        # Fill the slot
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Enqueue project
        await execution_queue_service.enqueue_project(workspace, path, QueuePriority.HIGH)

        # Verify in workspace queue
        assert len(workspace.execution_queue) == 2  # 1 active + 1 queued
        queued_items = [item for item in workspace.execution_queue if item.is_pending]
        assert len(queued_items) == 1
        assert queued_items[0].project_path == path
        assert queued_items[0].priority == QueuePriority.HIGH

        # Verify position tracking
        position = workspace.get_queue_position(path)
        assert position == 1

    @pytest.mark.asyncio
    async def test_queue_order_preserved_after_operations(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that queue order is preserved after various operations."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        paths = [sample_projects[f"project{i}"] for i in range(1, 4)]
        other_path = sample_projects["project4"]

        # Fill the slot
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Enqueue with different priorities
        await execution_queue_service.enqueue_project(workspace, paths[0], QueuePriority.MEDIUM)
        await execution_queue_service.enqueue_project(workspace, paths[1], QueuePriority.LOW)
        await execution_queue_service.enqueue_project(workspace, paths[2], QueuePriority.HIGH)

        # Get ordered queue
        queued = workspace.get_queued_projects()

        # Verify correct order: high (paths[2]), medium (paths[0]), low (paths[1])
        assert queued[0].project_path == paths[2]
        assert queued[1].project_path == paths[0]
        assert queued[2].project_path == paths[1]

    @pytest.mark.asyncio
    async def test_completed_items_remain_until_cleanup(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that completed items stay in queue until explicitly cleaned up."""
        path = sample_projects["project1"]

        # Enqueue and complete
        workspace.queue_project(path, QueuePriority.MEDIUM)
        workspace.mark_project_active(path)
        workspace.mark_project_completed(path)

        # Should still be in queue (with completed status)
        assert len(workspace.execution_queue) == 1
        assert workspace.execution_queue[0].status == QueueStatus.COMPLETED


class TestExecutionQueueErrorHandling:
    """Tests for error handling in execution queue."""

    @pytest.mark.asyncio
    async def test_failed_project_triggers_next(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that failed project triggers next project start."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=True
        )

        path1 = sample_projects["project1"]
        path2 = sample_projects["project2"]

        await execution_queue_service.enqueue_project(workspace, path1)
        workspace.mark_project_active(path1)
        await execution_queue_service.enqueue_project(workspace, path2)

        # Mark first as failed
        await execution_queue_service.on_project_failed(workspace, path1)

        # Second should have been started
        execution_queue_service.workflow_service.start_project.assert_called_with(path2)

    @pytest.mark.asyncio
    async def test_start_failure_marks_failed(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that failure to start a project marks it as failed."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=1)

        # Make workflow service fail to start
        execution_queue_service.workflow_service.start_project = AsyncMock(return_value=False)

        path = sample_projects["project1"]

        await execution_queue_service.enqueue_project(workspace, path)

        # Try to start it (should fail)
        result = await execution_queue_service._start_queued_project(workspace, path)

        assert result is False

        # Verify marked as failed
        for item in workspace.execution_queue:
            if item.project_path == path:
                assert item.status == QueueStatus.FAILED

    @pytest.mark.asyncio
    async def test_duplicate_enqueue_updates_priority(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that enqueuing duplicate project updates priority."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path = sample_projects["project1"]
        other_path = sample_projects["project2"]

        # Fill the slot
        workspace.queue_project(other_path, QueuePriority.MEDIUM)
        workspace.mark_project_active(other_path)

        # Enqueue with medium priority
        await execution_queue_service.enqueue_project(workspace, path, QueuePriority.MEDIUM)

        # Enqueue again with high priority
        success, message = await execution_queue_service.enqueue_project(
            workspace, path, QueuePriority.HIGH
        )

        assert success is True
        assert "updated" in message.lower()

        # Should only have one item in queue for this path
        path_items = [item for item in workspace.execution_queue if item.project_path == path]
        assert len(path_items) == 1
        assert path_items[0].priority == QueuePriority.HIGH


class TestExecutionQueueConcurrencyScenarios:
    """Tests for various concurrency scenarios."""

    @pytest.mark.asyncio
    async def test_zero_limit_allows_unlimited(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that max_concurrent=0 allows unlimited concurrent projects."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=0)

        paths = [sample_projects[f"project{i}"] for i in range(1, 5)]

        # All projects should be able to start
        for path in paths:
            can_start, _ = execution_queue_service.can_project_start(workspace, path)
            assert can_start is True

    @pytest.mark.asyncio
    async def test_serial_execution_with_limit_one(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that limit=1 enforces serial execution."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(max_concurrent=1)

        path1 = sample_projects["project1"]
        path2 = sample_projects["project2"]

        # Start first project
        await execution_queue_service.enqueue_project(workspace, path1)
        workspace.mark_project_active(path1)

        # Second project should not be able to start
        can_start, reason = execution_queue_service.can_project_start(workspace, path2)
        assert can_start is False
        assert "limit reached" in reason.lower()

    @pytest.mark.asyncio
    async def test_auto_start_disabled_respects_limit(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that disabling auto-start respects concurrency limit."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path1 = sample_projects["project1"]
        path2 = sample_projects["project2"]

        # Queue both (both stay queued with auto_start=False and limit=1)
        await execution_queue_service.enqueue_project(workspace, path1)
        await execution_queue_service.enqueue_project(workspace, path2)

        # Mark first as active
        workspace.mark_project_active(path1)

        # Complete first - second should NOT auto-start
        await execution_queue_service.on_project_completed(workspace, path1)

        # Verify second wasn't started
        execution_queue_service.workflow_service.start_project.assert_not_called()


class TestExecutionQueueStatusReporting:
    """Tests for queue status reporting."""

    @pytest.mark.asyncio
    async def test_queue_status_includes_all_info(
        self, execution_queue_service, workspace, sample_projects
    ):
        """Test that queue status includes all expected information."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Set up: 1 active, 1 queued
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=2, auto_start_queued=False
        )

        path1 = sample_projects["project1"]
        path2 = sample_projects["project2"]

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
    async def test_project_queue_info(self, execution_queue_service, workspace, sample_projects):
        """Test getting info for specific project."""
        from agent_pump.models.execution_queue import ExecutionQueueConfig

        # Disable auto-start
        workspace.execution_queue_config = ExecutionQueueConfig(
            max_concurrent=1, auto_start_queued=False
        )

        path = sample_projects["project1"]
        other_path = sample_projects["project2"]

        # Fill the slot
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
