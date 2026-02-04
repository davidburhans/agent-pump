"""Activity logging service for collaborative mode."""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from agent_pump.events.bus import EventBus
from agent_pump.events.models import ActivityLoggedEvent
from agent_pump.models.activity import Activity, ActivityLog, ActivityType
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class ActivityService(BaseService):
    """Service for logging and managing collaborative activities."""

    def __init__(
        self,
        event_bus: EventBus,
        max_history: int = 1000,
    ) -> None:
        """
        Initialize the activity service.

        Args:
            event_bus: The event bus for publishing events.
            max_history: Maximum number of activities to retain.
        """
        super().__init__(event_bus)
        self._activity_log = ActivityLog(max_size=max_history)

    async def log_activity(
        self,
        user_id: UUID,
        user_name: str,
        action: ActivityType,
        project_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Activity:
        """
        Log a collaborative activity.

        Args:
            user_id: The ID of the user performing the action.
            user_name: The display name of the user.
            action: The type of activity.
            project_path: Optional project path.
            details: Optional additional context.

        Returns:
            The created Activity.
        """
        activity = Activity.create(
            user_id=user_id,
            user_name=user_name,
            action=action,
            project_path=project_path,
            details=details or {},
        )

        self._activity_log.add_activity(activity)

        logger.debug(f"Activity logged: {action.value} by {user_name} (Project: {project_path})")

        # Publish event for real-time updates
        await self.event_bus.publish(
            ActivityLoggedEvent(
                activity_id=str(activity.id),
                user_id=str(user_id),
                user_name=user_name,
                action=action.value,
                project_path=project_path,
                details=activity.details,
            )
        )

        return activity

    def get_recent_activities(
        self,
        count: int = 50,
        project_path: str | None = None,
        user_id: UUID | None = None,
        action: ActivityType | None = None,
    ) -> list[Activity]:
        """
        Get recent activities with optional filtering.

        Args:
            count: Maximum number of activities to return.
            project_path: Optional filter by project.
            user_id: Optional filter by user.
            action: Optional filter by action type.

        Returns:
            List of matching activities.
        """
        activities = self._activity_log.activities

        # Apply filters
        if project_path:
            activities = [a for a in activities if a.project_path == project_path]

        if user_id:
            activities = [a for a in activities if a.user_id == user_id]

        if action:
            activities = [a for a in activities if a.action == action]

        # Return most recent
        return activities[-count:]

    def get_activities_since(
        self,
        since: datetime,
        project_path: str | None = None,
    ) -> list[Activity]:
        """
        Get activities since a specific time.

        Args:
            since: Timestamp to get activities from.
            project_path: Optional filter by project.

        Returns:
            List of activities since the given time.
        """
        activities = self._activity_log.get_for_time_range(
            start=since,
            end=datetime.now(),
        )

        if project_path:
            activities = [a for a in activities if a.project_path == project_path]

        return activities

    def get_activities_for_project(
        self,
        project_path: str,
        count: int = 50,
    ) -> list[Activity]:
        """Get recent activities for a specific project."""
        return self._activity_log.get_for_project(project_path, count)

    def get_activities_by_user(
        self,
        user_id: UUID,
        count: int = 50,
    ) -> list[Activity]:
        """Get recent activities by a specific user."""
        return self._activity_log.get_by_user(user_id, count)

    def get_activities_by_type(
        self,
        action: ActivityType,
        count: int = 50,
    ) -> list[Activity]:
        """Get recent activities of a specific type."""
        return self._activity_log.get_by_action(action, count)

    def get_activity_summary(
        self,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Get a summary of activities.

        Args:
            project_path: Optional filter by project.

        Returns:
            Dictionary with activity counts and statistics.
        """
        if project_path:
            activities = [
                a for a in self._activity_log.activities if a.project_path == project_path
            ]
        else:
            activities = self._activity_log.activities

        summary: dict[str, int] = {}
        for activity in activities:
            action_key = activity.action.value
            summary[action_key] = summary.get(action_key, 0) + 1

        return {
            "total_count": len(activities),
            "by_type": summary,
            "time_range": {
                "start": activities[0].timestamp.isoformat() if activities else None,
                "end": activities[-1].timestamp.isoformat() if activities else None,
            },
        }

    def clear_history(self) -> None:
        """Clear all activity history."""
        self._activity_log.clear()
        logger.info("Activity history cleared")

    def export_activities(
        self,
        format: str = "json",
        project_path: str | None = None,
        since: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Export activities in the specified format.

        Args:
            format: Export format ("json" or "dict").
            project_path: Optional filter by project.
            since: Optional filter by time.

        Returns:
            Exported activities in the requested format.
        """
        if since:
            activities = self.get_activities_since(since, project_path)
        elif project_path:
            activities = self.get_activities_for_project(project_path)
        else:
            activities = self._activity_log.activities

        if format == "json":
            return {
                "activities": [a.to_summary() for a in activities],
                "exported_at": datetime.now().isoformat(),
                "count": len(activities),
            }
        else:
            return {
                "activities": activities,
                "exported_at": datetime.now(),
                "count": len(activities),
            }

    @property
    def activity_count(self) -> int:
        """Total number of activities logged."""
        return self._activity_log.count

    @property
    def max_history(self) -> int:
        """Maximum activity history size."""
        return self._activity_log.max_size
