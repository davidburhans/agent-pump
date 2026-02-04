"""Unit tests for timeout tracker."""

import time
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.utils.timeout_tracker import (
    TimeoutEvent,
    TimeoutTracker,
    TimeoutType,
)


class TestTimeoutType:
    """Tests for TimeoutType enum."""

    def test_timeout_types_exist(self) -> None:
        """Test that all expected timeout types exist."""
        assert TimeoutType.BACKEND_EXECUTION.value == "backend_execution"
        assert TimeoutType.VERIFICATION_BUILD.value == "verification_build"
        assert TimeoutType.VERIFICATION_LINT.value == "verification_lint"
        assert TimeoutType.VERIFICATION_TEST.value == "verification_test"
        assert TimeoutType.WORKFLOW_PHASE.value == "workflow_phase"


class TestTimeoutEvent:
    """Tests for TimeoutEvent dataclass."""

    def test_timeout_event_creation(self) -> None:
        """Test creating a timeout event."""
        event = TimeoutEvent(
            timestamp=time.time(),
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini_backend",
            timeout_seconds=600,
            duration_before_timeout=605.5,
            project_name="test_project",
            context={"phase": "implementing"},
        )
        assert event.timeout_type == TimeoutType.BACKEND_EXECUTION
        assert event.operation_name == "gemini_backend"
        assert event.timeout_seconds == 600
        assert event.duration_before_timeout == 605.5
        assert event.project_name == "test_project"
        assert event.context == {"phase": "implementing"}

    def test_timeout_event_optional_fields(self) -> None:
        """Test creating event with optional fields."""
        event = TimeoutEvent(
            timestamp=time.time(),
            timeout_type=TimeoutType.VERIFICATION_TEST,
            operation_name="pytest",
            timeout_seconds=300,
            duration_before_timeout=300.0,
            project_name=None,
            context={},
        )
        assert event.project_name is None
        assert event.context == {}


class TestTimeoutTracker:
    """Tests for TimeoutTracker."""

    @pytest.fixture
    def tracker(self) -> TimeoutTracker:
        """Create a fresh TimeoutTracker instance."""
        return TimeoutTracker(max_history=50)

    def test_initial_state(self, tracker: TimeoutTracker) -> None:
        """Test initial state of tracker."""
        assert tracker.max_history == 50
        assert tracker.history == []
        assert tracker._pending_operations == {}

    def test_start_operation(self, tracker: TimeoutTracker) -> None:
        """Test starting an operation tracking."""
        tracker.start_operation(
            operation_id="op1",
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini_backend",
            timeout_seconds=600,
            project_name="test_project",
            context={"phase": "planning"},
        )

        assert "op1" in tracker._pending_operations
        assert tracker._pending_operations["op1"]["operation_name"] == "gemini_backend"
        assert tracker._pending_operations["op1"]["timeout_type"] == TimeoutType.BACKEND_EXECUTION

    def test_start_operation_minimal(self, tracker: TimeoutTracker) -> None:
        """Test starting operation with minimal fields."""
        tracker.start_operation(
            operation_id="op2",
            timeout_type=TimeoutType.WORKFLOW_PHASE,
            operation_name="verification",
            timeout_seconds=300,
        )

        assert "op2" in tracker._pending_operations
        assert tracker._pending_operations["op2"]["project_name"] is None
        assert tracker._pending_operations["op2"]["context"] == {}

    def test_record_timeout(self, tracker: TimeoutTracker) -> None:
        """Test recording a timeout."""
        tracker.start_operation(
            operation_id="op1",
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini_backend",
            timeout_seconds=600,
            project_name="test_project",
        )

        # Wait a bit to ensure duration > 0
        time.sleep(0.01)
        tracker.record_timeout("op1")

        assert "op1" not in tracker._pending_operations
        assert len(tracker.history) == 1
        assert tracker.history[0].timeout_type == TimeoutType.BACKEND_EXECUTION
        assert tracker.history[0].operation_name == "gemini_backend"
        assert tracker.history[0].project_name == "test_project"

    def test_record_timeout_unknown_operation(self, tracker: TimeoutTracker) -> None:
        """Test recording timeout for unknown operation."""
        tracker.record_timeout("unknown_op")

        assert len(tracker.history) == 0

    def test_complete_operation_success(self, tracker: TimeoutTracker) -> None:
        """Test completing an operation successfully."""
        tracker.start_operation(
            operation_id="op1",
            timeout_type=TimeoutType.VERIFICATION_TEST,
            operation_name="pytest",
            timeout_seconds=300,
        )

        time.sleep(0.01)
        tracker.complete_operation("op1", success=True)

        assert "op1" not in tracker._pending_operations
        # Successful completion should not add to history
        assert len(tracker.history) == 0

    def test_complete_operation_failure(self, tracker: TimeoutTracker) -> None:
        """Test completing an operation with failure."""
        tracker.start_operation(
            operation_id="op1",
            timeout_type=TimeoutType.VERIFICATION_BUILD,
            operation_name="npm_build",
            timeout_seconds=120,
        )

        time.sleep(0.01)
        tracker.complete_operation("op1", success=False)

        assert "op1" not in tracker._pending_operations
        # Failed completion should not add to history (only timeouts are recorded)
        assert len(tracker.history) == 0

    def test_history_rotation(self, tracker: TimeoutTracker) -> None:
        """Test that old history entries are removed."""
        tracker = TimeoutTracker(max_history=5)

        # Add more events than max_history
        for i in range(10):
            op_id = f"op{i}"
            tracker.start_operation(
                operation_id=op_id,
                timeout_type=TimeoutType.BACKEND_EXECUTION,
                operation_name=f"backend_{i}",
                timeout_seconds=600,
            )
            tracker.record_timeout(op_id)

        assert len(tracker.history) == 5
        # Should keep the most recent
        assert tracker.history[-1].operation_name == "backend_9"

    def test_get_timeout_patterns_empty(self, tracker: TimeoutTracker) -> None:
        """Test pattern analysis with no timeouts."""
        patterns = tracker.get_timeout_patterns()
        assert "message" in patterns
        assert patterns["message"] == "No timeouts recorded"

    def test_get_timeout_patterns_with_data(self, tracker: TimeoutTracker) -> None:
        """Test pattern analysis with timeout data."""
        # Add timeouts of different types
        for i in range(5):
            tracker.start_operation(
                operation_id=f"backend_op{i}",
                timeout_type=TimeoutType.BACKEND_EXECUTION,
                operation_name="gemini",
                timeout_seconds=600,
                project_name="project_a" if i < 3 else "project_b",
            )
            tracker.record_timeout(f"backend_op{i}")

        for i in range(3):
            tracker.start_operation(
                operation_id=f"test_op{i}",
                timeout_type=TimeoutType.VERIFICATION_TEST,
                operation_name="pytest",
                timeout_seconds=300,
                project_name="project_c",
            )
            tracker.record_timeout(f"test_op{i}")

        patterns = tracker.get_timeout_patterns()

        assert patterns["total_timeouts"] == 8
        assert "by_type" in patterns
        assert patterns["by_type"]["backend_execution"]["count"] == 5
        assert patterns["by_type"]["verification_test"]["count"] == 3
        assert patterns["by_type"]["backend_execution"]["most_common_project"] == "project_a"

    def test_get_timeout_patterns_average_duration(self, tracker: TimeoutTracker) -> None:
        """Test that average duration is calculated correctly."""
        # Manually add events with specific durations
        event1 = TimeoutEvent(
            timestamp=time.time(),
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini",
            timeout_seconds=600,
            duration_before_timeout=600.0,
            project_name="test",
        )
        event2 = TimeoutEvent(
            timestamp=time.time(),
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini",
            timeout_seconds=600,
            duration_before_timeout=605.0,
            project_name="test",
        )
        tracker.history = [event1, event2]

        patterns = tracker.get_timeout_patterns()
        avg_duration = patterns["by_type"]["backend_execution"]["average_duration"]
        assert avg_duration == 602.5

    def test_multiple_pending_operations(self, tracker: TimeoutTracker) -> None:
        """Test tracking multiple operations simultaneously."""
        tracker.start_operation(
            operation_id="op1",
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini_1",
            timeout_seconds=600,
        )
        tracker.start_operation(
            operation_id="op2",
            timeout_type=TimeoutType.BACKEND_EXECUTION,
            operation_name="gemini_2",
            timeout_seconds=600,
        )
        tracker.start_operation(
            operation_id="op3",
            timeout_type=TimeoutType.VERIFICATION_TEST,
            operation_name="pytest",
            timeout_seconds=300,
        )

        assert len(tracker._pending_operations) == 3

        tracker.record_timeout("op2")
        assert len(tracker._pending_operations) == 2
        assert "op1" in tracker._pending_operations
        assert "op3" in tracker._pending_operations

        tracker.complete_operation("op1")
        assert len(tracker._pending_operations) == 1

    def test_complete_unknown_operation(self, tracker: TimeoutTracker) -> None:
        """Test completing an operation that doesn't exist."""
        # Should not raise an error
        tracker.complete_operation("nonexistent", success=True)
        assert len(tracker._pending_operations) == 0
