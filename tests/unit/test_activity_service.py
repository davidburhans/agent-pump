"""Tests for activity service."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from agent_pump.events.bus import EventBus
from agent_pump.models.activity import ActivityType
from agent_pump.services.activity_service import ActivityService


class TestActivityService:
    """Tests for ActivityService."""

    @pytest_asyncio.fixture
    async def event_bus(self):
        """Create an event bus for testing."""
        bus = EventBus()
        yield bus

    @pytest_asyncio.fixture
    async def service(self, event_bus):
        """Create an activity service for testing."""
        svc = ActivityService(
            event_bus=event_bus,
            max_history=100,
        )
        yield svc

    @pytest.mark.asyncio
    async def test_log_activity(self, service, event_bus):
        """Test logging an activity."""
        user_id = uuid4()

        activity = await service.log_activity(
            user_id=user_id,
            user_name="Test User",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/test",
            details={"idea": "Add feature"},
        )

        assert activity.user_id == user_id
        assert activity.user_name == "Test User"
        assert activity.action == ActivityType.IDEA_INJECTED
        assert activity.project_path == "/projects/test"
        assert activity.details == {"idea": "Add feature"}

    @pytest.mark.asyncio
    async def test_log_activity_no_details(self, service, event_bus):
        """Test logging activity without details."""
        activity = await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.USER_JOINED,
        )

        assert activity.details == {}

    @pytest.mark.asyncio
    async def test_get_recent_activities(self, service, event_bus):
        """Test getting recent activities."""
        user_id = uuid4()

        # Log multiple activities
        for i in range(5):
            await service.log_activity(
                user_id=user_id,
                user_name=f"User{i}",
                action=ActivityType.IDEA_INJECTED,
            )

        activities = service.get_recent_activities(count=3)

        assert len(activities) == 3
        # Should return most recent
        assert activities[-1].user_name == "User4"

    @pytest.mark.asyncio
    async def test_get_recent_with_filters(self, service, event_bus):
        """Test getting activities with filters."""
        user1_id = uuid4()
        user2_id = uuid4()

        await service.log_activity(
            user_id=user1_id,
            user_name="User1",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/a",
        )
        await service.log_activity(
            user_id=user2_id,
            user_name="User2",
            action=ActivityType.WORKFLOW_PAUSED,
            project_path="/projects/b",
        )

        # Filter by project
        activities = service.get_recent_activities(project_path="/projects/a")
        assert len(activities) == 1
        assert activities[0].project_path == "/projects/a"

        # Filter by user
        activities = service.get_recent_activities(user_id=user2_id)
        assert len(activities) == 1
        assert activities[0].user_id == user2_id

        # Filter by action
        activities = service.get_recent_activities(action=ActivityType.IDEA_INJECTED)
        assert len(activities) == 1
        assert activities[0].action == ActivityType.IDEA_INJECTED

    @pytest.mark.asyncio
    async def test_get_activities_since(self, service, event_bus):
        """Test getting activities since a specific time."""
        # Log an old activity
        old_activity = await service.log_activity(
            user_id=uuid4(),
            user_name="Old",
            action=ActivityType.IDEA_INJECTED,
        )
        old_activity.timestamp = datetime.now() - timedelta(hours=2)

        # Log recent activities
        await service.log_activity(
            user_id=uuid4(),
            user_name="Recent1",
            action=ActivityType.IDEA_INJECTED,
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="Recent2",
            action=ActivityType.IDEA_INJECTED,
        )

        since = datetime.now() - timedelta(minutes=30)
        activities = service.get_activities_since(since)

        assert len(activities) == 2

    @pytest.mark.asyncio
    async def test_get_activities_for_project(self, service, event_bus):
        """Test getting activities for a specific project."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="User1",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/a",
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="User2",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/b",
        )

        activities = service.get_activities_for_project("/projects/a")

        assert len(activities) == 1
        assert activities[0].project_path == "/projects/a"

    @pytest.mark.asyncio
    async def test_get_activities_by_user(self, service, event_bus):
        """Test getting activities by a specific user."""
        user_id = uuid4()

        await service.log_activity(
            user_id=user_id,
            user_name="Target",
            action=ActivityType.IDEA_INJECTED,
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="Other",
            action=ActivityType.IDEA_INJECTED,
        )

        activities = service.get_activities_by_user(user_id)

        assert len(activities) == 1
        assert activities[0].user_name == "Target"

    @pytest.mark.asyncio
    async def test_get_activities_by_type(self, service, event_bus):
        """Test getting activities of a specific type."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.WORKFLOW_PAUSED,
        )

        activities = service.get_activities_by_type(ActivityType.IDEA_INJECTED)

        assert len(activities) == 1
        assert activities[0].action == ActivityType.IDEA_INJECTED

    @pytest.mark.asyncio
    async def test_get_activity_summary(self, service, event_bus):
        """Test getting activity summary."""
        # Log various activities
        for _ in range(3):
            await service.log_activity(
                user_id=uuid4(),
                user_name="Test",
                action=ActivityType.IDEA_INJECTED,
            )
        for _ in range(2):
            await service.log_activity(
                user_id=uuid4(),
                user_name="Test",
                action=ActivityType.WORKFLOW_PAUSED,
            )

        summary = service.get_activity_summary()

        assert summary["total_count"] == 5
        assert summary["by_type"]["idea_injected"] == 3
        assert summary["by_type"]["workflow_paused"] == 2

    @pytest.mark.asyncio
    async def test_get_activity_summary_for_project(self, service, event_bus):
        """Test getting activity summary for a specific project."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/a",
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/b",
        )

        summary = service.get_activity_summary(project_path="/projects/a")

        assert summary["total_count"] == 1

    @pytest.mark.asyncio
    async def test_clear_history(self, service, event_bus):
        """Test clearing activity history."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
        )

        assert service.activity_count == 1

        service.clear_history()

        assert service.activity_count == 0

    @pytest.mark.asyncio
    async def test_export_activities_json(self, service, event_bus):
        """Test exporting activities as JSON."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
            details={"test": "data"},
        )

        exported = service.export_activities(format="json")

        assert exported["count"] == 1
        assert "activities" in exported
        assert "exported_at" in exported

    @pytest.mark.asyncio
    async def test_export_activities_with_project_filter(self, service, event_bus):
        """Test exporting activities with project filter."""
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/a",
        )
        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/b",
        )

        exported = service.export_activities(
            format="json",
            project_path="/projects/a",
        )

        assert exported["count"] == 1

    @pytest.mark.asyncio
    async def test_activity_count_property(self, service, event_bus):
        """Test activity_count property."""
        assert service.activity_count == 0

        await service.log_activity(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.IDEA_INJECTED,
        )

        assert service.activity_count == 1

    @pytest.mark.asyncio
    async def test_max_history_property(self, service, event_bus):
        """Test max_history property."""
        assert service.max_history == 100

    @pytest.mark.asyncio
    async def test_log_rollover(self, service, event_bus):
        """Test that old activities are removed when exceeding max_history."""
        # Log more activities than max_history
        for i in range(150):
            await service.log_activity(
                user_id=uuid4(),
                user_name=f"User{i}",
                action=ActivityType.IDEA_INJECTED,
            )

        # Should only have most recent 100
        assert service.activity_count == 100

        # Check that most recent are kept
        activities = service.get_recent_activities(count=10)
        assert activities[-1].user_name == "User149"
