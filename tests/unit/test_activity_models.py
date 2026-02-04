"""Tests for activity logging models."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agent_pump.models.activity import (
    Activity,
    ActivityLog,
    ActivityType,
)


class TestActivityType:
    """Tests for ActivityType enum."""

    def test_activity_type_values(self):
        """Test that ActivityType has expected values."""
        assert ActivityType.USER_JOINED.value == "user_joined"
        assert ActivityType.USER_LEFT.value == "user_left"
        assert ActivityType.IDEA_INJECTED.value == "idea_injected"
        assert ActivityType.WORKFLOW_PAUSED.value == "workflow_paused"
        assert ActivityType.GATE_APPROVED.value == "gate_approved"

    def test_all_activity_types_exist(self):
        """Test that all expected activity types exist."""
        expected_types = [
            "user_joined",
            "user_left",
            "user_reconnected",
            "role_changed",
            "idea_injected",
            "idea_processed",
            "workflow_started",
            "workflow_paused",
            "workflow_resumed",
            "workflow_stopped",
            "gate_approved",
            "gate_rejected",
            "gate_timeout",
            "config_changed",
            "backend_changed",
            "prompt_changed",
            "project_added",
            "project_removed",
            "project_selected",
            "verification_started",
            "verification_completed",
            "verification_failed",
        ]

        for type_name in expected_types:
            assert hasattr(ActivityType, type_name.upper())
            assert getattr(ActivityType, type_name.upper()).value == type_name


class TestActivity:
    """Tests for the Activity model."""

    def test_create_activity_defaults(self):
        """Test creating an activity with default values."""
        user_id = uuid4()
        activity = Activity(
            user_id=user_id,
            user_name="Test User",
            action=ActivityType.IDEA_INJECTED,
        )

        assert activity.user_id == user_id
        assert activity.user_name == "Test User"
        assert activity.action == ActivityType.IDEA_INJECTED
        assert isinstance(activity.id, UUID)
        assert activity.project_path is None
        assert activity.details == {}
        assert isinstance(activity.timestamp, datetime)

    def test_create_activity_with_all_fields(self):
        """Test creating an activity with all fields."""
        user_id = uuid4()
        activity_id = uuid4()
        timestamp = datetime.now() - timedelta(hours=1)

        activity = Activity(
            id=activity_id,
            user_id=user_id,
            user_name="Alice",
            action=ActivityType.WORKFLOW_PAUSED,
            project_path="/projects/test",
            details={"reason": "manual", "phase": "implementing"},
            timestamp=timestamp,
        )

        assert activity.id == activity_id
        assert activity.action == ActivityType.WORKFLOW_PAUSED
        assert activity.project_path == "/projects/test"
        assert activity.details == {"reason": "manual", "phase": "implementing"}
        assert activity.timestamp == timestamp

    def test_create_activity_factory(self):
        """Test the create factory method."""
        user_id = uuid4()

        activity = Activity.create(
            user_id=user_id,
            user_name="Bob",
            action=ActivityType.GATE_APPROVED,
            project_path="/projects/my-project",
            details={"gate_id": "123"},
        )

        assert activity.user_id == user_id
        assert activity.user_name == "Bob"
        assert activity.action == ActivityType.GATE_APPROVED
        assert activity.project_path == "/projects/my-project"
        assert activity.details == {"gate_id": "123"}

    def test_create_activity_factory_no_details(self):
        """Test the create factory method without details."""
        user_id = uuid4()

        activity = Activity.create(
            user_id=user_id,
            user_name="Charlie",
            action=ActivityType.USER_JOINED,
        )

        assert activity.details == {}

    def test_to_summary(self):
        """Test activity summary serialization."""
        user_id = uuid4()
        activity = Activity(
            user_id=user_id,
            user_name="Test",
            action=ActivityType.CONFIG_CHANGED,
            project_path="/projects/test",
            details={"key": "value"},
        )

        summary = activity.to_summary()

        assert summary["id"] == str(activity.id)
        assert summary["user_id"] == str(user_id)
        assert summary["user_name"] == "Test"
        assert summary["action"] == "config_changed"
        assert summary["project_path"] == "/projects/test"
        assert summary["details"] == {"key": "value"}
        assert "timestamp" in summary


class TestActivityLog:
    """Tests for the ActivityLog model."""

    def test_create_log_defaults(self):
        """Test creating an empty activity log."""
        log = ActivityLog()
        assert log.activities == []
        assert log.max_size == 1000
        assert log.count == 0

    def test_create_log_with_custom_size(self):
        """Test creating a log with custom max size."""
        log = ActivityLog(max_size=100)
        assert log.max_size == 100

    def test_add_activity(self):
        """Test adding an activity to the log."""
        log = ActivityLog()
        activity = Activity.create(
            user_id=uuid4(),
            user_name="Alice",
            action=ActivityType.IDEA_INJECTED,
        )

        log.add_activity(activity)

        assert log.count == 1
        assert log.activities[0].user_name == "Alice"

    def test_add_activity_trimming(self):
        """Test that old activities are trimmed when exceeding max size."""
        log = ActivityLog(max_size=5)

        # Add 10 activities
        for i in range(10):
            activity = Activity.create(
                user_id=uuid4(),
                user_name=f"User{i}",
                action=ActivityType.IDEA_INJECTED,
            )
            log.add_activity(activity)

        assert log.count == 5
        # Should keep the most recent 5
        assert log.activities[0].user_name == "User5"
        assert log.activities[4].user_name == "User9"

    def test_get_recent(self):
        """Test getting recent activities."""
        log = ActivityLog()

        # Add 10 activities
        for i in range(10):
            activity = Activity.create(
                user_id=uuid4(),
                user_name=f"User{i}",
                action=ActivityType.IDEA_INJECTED,
            )
            log.add_activity(activity)

        recent = log.get_recent(count=3)
        assert len(recent) == 3
        assert recent[0].user_name == "User7"
        assert recent[2].user_name == "User9"

    def test_get_recent_more_than_available(self):
        """Test getting recent when count exceeds available."""
        log = ActivityLog()

        for i in range(3):
            activity = Activity.create(
                user_id=uuid4(),
                user_name=f"User{i}",
                action=ActivityType.IDEA_INJECTED,
            )
            log.add_activity(activity)

        recent = log.get_recent(count=10)
        assert len(recent) == 3

    def test_get_for_project(self):
        """Test getting activities for a specific project."""
        log = ActivityLog()

        # Add activities for different projects
        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Alice",
                action=ActivityType.IDEA_INJECTED,
                project_path="/projects/a",
            )
        )
        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Bob",
                action=ActivityType.IDEA_INJECTED,
                project_path="/projects/b",
            )
        )
        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Charlie",
                action=ActivityType.IDEA_INJECTED,
                project_path="/projects/a",
            )
        )

        project_a_activities = log.get_for_project("/projects/a")
        assert len(project_a_activities) == 2
        assert project_a_activities[0].user_name == "Alice"
        assert project_a_activities[1].user_name == "Charlie"

    def test_get_by_user(self):
        """Test getting activities by a specific user."""
        log = ActivityLog()
        user_id = uuid4()
        other_user_id = uuid4()

        log.add_activity(
            Activity.create(
                user_id=user_id,
                user_name="Alice",
                action=ActivityType.IDEA_INJECTED,
            )
        )
        log.add_activity(
            Activity.create(
                user_id=other_user_id,
                user_name="Bob",
                action=ActivityType.IDEA_INJECTED,
            )
        )
        log.add_activity(
            Activity.create(
                user_id=user_id,
                user_name="Alice",
                action=ActivityType.WORKFLOW_PAUSED,
            )
        )

        user_activities = log.get_by_user(user_id)
        assert len(user_activities) == 2
        assert user_activities[0].action == ActivityType.IDEA_INJECTED
        assert user_activities[1].action == ActivityType.WORKFLOW_PAUSED

    def test_get_by_action(self):
        """Test getting activities of a specific type."""
        log = ActivityLog()

        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Alice",
                action=ActivityType.IDEA_INJECTED,
            )
        )
        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Bob",
                action=ActivityType.WORKFLOW_PAUSED,
            )
        )
        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Charlie",
                action=ActivityType.IDEA_INJECTED,
            )
        )

        idea_activities = log.get_by_action(ActivityType.IDEA_INJECTED)
        assert len(idea_activities) == 2

    def test_get_for_time_range(self):
        """Test getting activities within a time range."""
        log = ActivityLog()

        now = datetime.now()

        # Create activities at different times
        activity1 = Activity.create(
            user_id=uuid4(),
            user_name="Old",
            action=ActivityType.IDEA_INJECTED,
        )
        activity1.timestamp = now - timedelta(hours=2)

        activity2 = Activity.create(
            user_id=uuid4(),
            user_name="Recent",
            action=ActivityType.IDEA_INJECTED,
        )
        activity2.timestamp = now - timedelta(minutes=30)

        activity3 = Activity.create(
            user_id=uuid4(),
            user_name="VeryRecent",
            action=ActivityType.IDEA_INJECTED,
        )
        activity3.timestamp = now - timedelta(minutes=5)

        log.add_activity(activity1)
        log.add_activity(activity2)
        log.add_activity(activity3)

        # Get activities from last hour
        start = now - timedelta(hours=1)
        end = now
        recent_activities = log.get_for_time_range(start, end)

        assert len(recent_activities) == 2
        assert recent_activities[0].user_name == "Recent"
        assert recent_activities[1].user_name == "VeryRecent"

    def test_clear(self):
        """Test clearing all activities."""
        log = ActivityLog()

        for i in range(5):
            log.add_activity(
                Activity.create(
                    user_id=uuid4(),
                    user_name=f"User{i}",
                    action=ActivityType.IDEA_INJECTED,
                )
            )

        assert log.count == 5

        log.clear()

        assert log.count == 0
        assert log.activities == []

    def test_get_activity_summary(self):
        """Test getting activity count summary."""
        log = ActivityLog()

        # Add various activity types
        for _ in range(3):
            log.add_activity(
                Activity.create(
                    user_id=uuid4(),
                    user_name="Test",
                    action=ActivityType.IDEA_INJECTED,
                )
            )

        for _ in range(2):
            log.add_activity(
                Activity.create(
                    user_id=uuid4(),
                    user_name="Test",
                    action=ActivityType.WORKFLOW_PAUSED,
                )
            )

        log.add_activity(
            Activity.create(
                user_id=uuid4(),
                user_name="Test",
                action=ActivityType.USER_JOINED,
            )
        )

        summary = log.get_activity_summary()

        assert summary["idea_injected"] == 3
        assert summary["workflow_paused"] == 2
        assert summary["user_joined"] == 1
        assert len(summary) == 3

    def test_large_log_performance(self):
        """Test that large logs handle trimming correctly."""
        log = ActivityLog(max_size=100)

        # Add 200 activities
        for i in range(200):
            log.add_activity(
                Activity.create(
                    user_id=uuid4(),
                    user_name=f"User{i}",
                    action=ActivityType.IDEA_INJECTED,
                )
            )

        assert log.count == 100
        # Should keep the most recent
        assert log.activities[0].user_name == "User100"
        assert log.activities[99].user_name == "User199"
