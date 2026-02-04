"""Unit tests for ExecutionQueue models."""

from datetime import datetime, timedelta

from agent_pump.models.execution_queue import (
    ExecutionQueueConfig,
    ExecutionQueueItem,
    QueuePriority,
    QueueStatus,
)


class TestQueuePriority:
    """Tests for QueuePriority enum."""

    def test_priority_values(self):
        """Test that priority values are correct."""
        assert QueuePriority.LOW == 1
        assert QueuePriority.MEDIUM == 2
        assert QueuePriority.HIGH == 3

    def test_priority_ordering(self):
        """Test that priorities can be compared."""
        assert QueuePriority.HIGH > QueuePriority.MEDIUM
        assert QueuePriority.MEDIUM > QueuePriority.LOW
        assert QueuePriority.HIGH > QueuePriority.LOW


class TestQueueStatus:
    """Tests for QueueStatus enum."""

    def test_status_values(self):
        """Test that status values are correct."""
        assert QueueStatus.QUEUED == "queued"
        assert QueueStatus.ACTIVE == "active"
        assert QueueStatus.COMPLETED == "completed"
        assert QueueStatus.FAILED == "failed"
        assert QueueStatus.CANCELLED == "cancelled"


class TestExecutionQueueItem:
    """Tests for ExecutionQueueItem model."""

    def test_create_default(self, tmp_path):
        """Test creating an item with default values."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path)

        assert item.project_path == path
        assert item.priority == QueuePriority.MEDIUM
        assert item.status == QueueStatus.QUEUED
        assert item.position == 0
        assert item.queued_at is not None
        assert item.started_at is None

    def test_create_with_custom_values(self, tmp_path):
        """Test creating an item with custom values."""
        path = tmp_path / "project"
        now = datetime.now()
        item = ExecutionQueueItem(
            project_path=path,
            priority=QueuePriority.HIGH,
            status=QueueStatus.ACTIVE,
            position=5,
            queued_at=now,
        )

        assert item.project_path == path
        assert item.priority == QueuePriority.HIGH
        assert item.status == QueueStatus.ACTIVE
        assert item.position == 5
        assert item.queued_at == now

    def test_mark_active(self, tmp_path):
        """Test marking an item as active."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED)

        active_item = item.mark_active()

        assert active_item.status == QueueStatus.ACTIVE
        assert active_item.started_at is not None
        assert active_item.project_path == path  # Other fields unchanged

    def test_mark_completed(self, tmp_path):
        """Test marking an item as completed."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.ACTIVE)

        completed_item = item.mark_completed()

        assert completed_item.status == QueueStatus.COMPLETED
        assert completed_item.project_path == path

    def test_mark_failed(self, tmp_path):
        """Test marking an item as failed."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.ACTIVE)

        failed_item = item.mark_failed()

        assert failed_item.status == QueueStatus.FAILED

    def test_mark_cancelled(self, tmp_path):
        """Test marking an item as cancelled."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED)

        cancelled_item = item.mark_cancelled()

        assert cancelled_item.status == QueueStatus.CANCELLED

    def test_update_priority(self, tmp_path):
        """Test updating priority."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, priority=QueuePriority.LOW)

        updated_item = item.update_priority(QueuePriority.HIGH)

        assert updated_item.priority == QueuePriority.HIGH
        assert updated_item.project_path == path  # Other fields unchanged

    def test_is_active_property(self, tmp_path):
        """Test the is_active property."""
        path = tmp_path / "project"

        active_item = ExecutionQueueItem(project_path=path, status=QueueStatus.ACTIVE)
        assert active_item.is_active is True

        queued_item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED)
        assert queued_item.is_active is False

        completed_item = ExecutionQueueItem(project_path=path, status=QueueStatus.COMPLETED)
        assert completed_item.is_active is False

    def test_is_pending_property(self, tmp_path):
        """Test the is_pending property."""
        path = tmp_path / "project"

        queued_item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED)
        assert queued_item.is_pending is True

        active_item = ExecutionQueueItem(project_path=path, status=QueueStatus.ACTIVE)
        assert active_item.is_pending is False

        completed_item = ExecutionQueueItem(project_path=path, status=QueueStatus.COMPLETED)
        assert completed_item.is_pending is False

    def test_wait_time_seconds_while_queued(self, tmp_path):
        """Test wait time calculation while queued."""
        path = tmp_path / "project"
        # Create item that was queued 5 minutes ago
        queued_at = datetime.now() - timedelta(minutes=5)
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED, queued_at=queued_at)

        wait_time = item.wait_time_seconds

        # Should be approximately 300 seconds (5 minutes), allow some tolerance
        assert 295 <= wait_time <= 305

    def test_wait_time_seconds_when_active(self, tmp_path):
        """Test wait time calculation when active."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.ACTIVE)

        wait_time = item.wait_time_seconds

        assert wait_time == 0.0

    def test_execution_time_seconds_when_active(self, tmp_path):
        """Test execution time calculation when active."""
        path = tmp_path / "project"
        started_at = datetime.now() - timedelta(minutes=3)
        item = ExecutionQueueItem(
            project_path=path, status=QueueStatus.ACTIVE, started_at=started_at
        )

        exec_time = item.execution_time_seconds

        # Should be approximately 180 seconds (3 minutes), allow some tolerance
        assert exec_time is not None
        assert 175 <= exec_time <= 185

    def test_execution_time_seconds_when_queued(self, tmp_path):
        """Test execution time calculation when not active."""
        path = tmp_path / "project"
        item = ExecutionQueueItem(project_path=path, status=QueueStatus.QUEUED)

        exec_time = item.execution_time_seconds

        assert exec_time is None

    def test_serialization_roundtrip(self, tmp_path):
        """Test that item can be serialized and deserialized."""
        path = tmp_path / "project"
        original = ExecutionQueueItem(
            project_path=path,
            priority=QueuePriority.HIGH,
            status=QueueStatus.ACTIVE,
            position=1,
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = ExecutionQueueItem.model_validate(data)

        assert restored.project_path == original.project_path
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.position == original.position


class TestExecutionQueueConfig:
    """Tests for ExecutionQueueConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ExecutionQueueConfig()

        assert config.max_concurrent == 3
        assert config.auto_start_queued is True

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ExecutionQueueConfig(max_concurrent=5, auto_start_queued=False)

        assert config.max_concurrent == 5
        assert config.auto_start_queued is False

    def test_has_limit_with_positive_value(self):
        """Test has_limit property with positive value."""
        config = ExecutionQueueConfig(max_concurrent=3)

        assert config.has_limit is True

    def test_has_limit_with_zero(self):
        """Test has_limit property with zero (unlimited)."""
        config = ExecutionQueueConfig(max_concurrent=0)

        assert config.has_limit is False

    def test_validation_max_concurrent_non_negative(self):
        """Test that max_concurrent must be non-negative."""
        # Should work with 0
        config = ExecutionQueueConfig(max_concurrent=0)
        assert config.max_concurrent == 0

        # Should work with positive
        config = ExecutionQueueConfig(max_concurrent=5)
        assert config.max_concurrent == 5

    def test_serialization_roundtrip(self):
        """Test that config can be serialized and deserialized."""
        original = ExecutionQueueConfig(max_concurrent=10, auto_start_queued=False)

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = ExecutionQueueConfig.model_validate(data)

        assert restored.max_concurrent == original.max_concurrent
        assert restored.auto_start_queued == original.auto_start_queued


class TestExecutionQueueItemSorting:
    """Tests for sorting queue items."""

    def test_sort_by_priority_descending(self, tmp_path):
        """Test sorting by priority (highest first)."""
        items = [
            ExecutionQueueItem(
                project_path=tmp_path / "low", priority=QueuePriority.LOW, position=1
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "high", priority=QueuePriority.HIGH, position=2
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "medium", priority=QueuePriority.MEDIUM, position=3
            ),
        ]

        # Sort by priority descending, then position ascending
        sorted_items = sorted(items, key=lambda x: (-x.priority.value, x.position))

        assert sorted_items[0].priority == QueuePriority.HIGH
        assert sorted_items[1].priority == QueuePriority.MEDIUM
        assert sorted_items[2].priority == QueuePriority.LOW

    def test_sort_equal_priority_by_position(self, tmp_path):
        """Test FIFO ordering for equal priorities."""
        items = [
            ExecutionQueueItem(
                project_path=tmp_path / "second", priority=QueuePriority.MEDIUM, position=2
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "first", priority=QueuePriority.MEDIUM, position=1
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "third", priority=QueuePriority.MEDIUM, position=3
            ),
        ]

        # Sort by priority descending, then position ascending
        sorted_items = sorted(items, key=lambda x: (-x.priority.value, x.position))

        assert sorted_items[0].project_path.name == "first"
        assert sorted_items[1].project_path.name == "second"
        assert sorted_items[2].project_path.name == "third"

    def test_complex_sorting(self, tmp_path):
        """Test complex sorting scenario with mixed priorities."""
        items = [
            ExecutionQueueItem(
                project_path=tmp_path / "m1", priority=QueuePriority.MEDIUM, position=1
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "l1", priority=QueuePriority.LOW, position=1
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "h1",
                priority=QueuePriority.HIGH,
                position=2,  # Higher position but higher priority
            ),
            ExecutionQueueItem(
                project_path=tmp_path / "m2", priority=QueuePriority.MEDIUM, position=2
            ),
        ]

        # Sort by priority descending, then position ascending
        sorted_items = sorted(items, key=lambda x: (-x.priority.value, x.position))

        # Should be: high (h1), medium with pos 1 (m1), medium with pos 2 (m2), low (l1)
        assert sorted_items[0].project_path.name == "h1"
        assert sorted_items[1].project_path.name == "m1"
        assert sorted_items[2].project_path.name == "m2"
        assert sorted_items[3].project_path.name == "l1"
