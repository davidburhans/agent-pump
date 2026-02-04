"""Collaboration service for managing user sessions and presence."""

import asyncio
import logging
from typing import Any
from uuid import UUID

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    RoleChangedEvent,
    UserJoinedEvent,
    UserLeftEvent,
)
from agent_pump.models.collaboration import User, UserPresence, UserRole
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class CollaborationService(BaseService):
    """Service for managing collaborative user sessions."""

    def __init__(
        self,
        event_bus: EventBus,
        session_timeout_seconds: float = 300.0,
        max_viewers: int = 10,
        max_controllers: int = 3,
    ) -> None:
        """
        Initialize the collaboration service.

        Args:
            event_bus: The event bus for publishing events.
            session_timeout_seconds: Seconds before inactive users are considered disconnected.
            max_viewers: Maximum number of concurrent viewers allowed.
            max_controllers: Maximum number of concurrent controllers allowed.
        """
        super().__init__(event_bus)
        self._presence = UserPresence()
        self._session_timeout = session_timeout_seconds
        self._max_viewers = max_viewers
        self._max_controllers = max_controllers
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the collaboration service and background cleanup."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Collaboration service started")

    async def stop(self) -> None:
        """Stop the collaboration service and cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Collaboration service stopped")

    async def join_session(
        self,
        user_name: str,
        role: str = "viewer",
        session_id: str | None = None,
        project_path: str | None = None,
    ) -> User:
        """
        Join a collaborative session.

        Args:
            user_name: Display name for the user.
            role: User role ("viewer" or "controller").
            session_id: Optional WebSocket session ID.
            project_path: Optional project the user is viewing.

        Returns:
            The created User object.

        Raises:
            ValueError: If role is invalid or limits exceeded.
        """
        # Validate role
        try:
            user_role = UserRole(role.lower())
        except ValueError:
            raise ValueError(f"Invalid role: {role}. Must be 'viewer' or 'controller'")

        # Check limits
        if user_role == UserRole.VIEWER:
            if len(self._presence.get_viewers()) >= self._max_viewers:
                raise ValueError(f"Maximum viewer limit ({self._max_viewers}) reached")
        elif user_role == UserRole.CONTROLLER:
            if len(self._presence.get_controllers()) >= self._max_controllers:
                raise ValueError(f"Maximum controller limit ({self._max_controllers}) reached")

        # Create user
        user = User(
            name=user_name,
            role=user_role,
            session_id=session_id,
            project_path=project_path,
            is_active=True,
        )

        # Add to presence
        self._presence.add_user(user)

        logger.info(
            f"User joined: {user_name} ({user_role.value}) "
            f"Session: {session_id}, Project: {project_path}"
        )

        # Publish event
        await self.event_bus.publish(
            UserJoinedEvent(
                user_id=str(user.id),
                user_name=user_name,
                role=user_role.value,
                session_id=session_id or "",
                project_path=project_path,
            )
        )

        return user

    async def leave_session(self, user_id: UUID) -> User | None:
        """
        Leave a collaborative session.

        Args:
            user_id: The ID of the user leaving.

        Returns:
            The removed User or None if not found.
        """
        user = self._presence.remove_user(user_id)
        if user:
            logger.info(f"User left: {user.name} (ID: {user_id})")

            await self.event_bus.publish(
                UserLeftEvent(
                    user_id=str(user.id),
                    user_name=user.name,
                    session_id=user.session_id or "",
                )
            )

        return user

    def get_user(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        return self._presence.get_by_id(user_id)

    def get_user_by_session(self, session_id: str) -> User | None:
        """Get a user by session ID."""
        return self._presence.get_by_session_id(session_id)

    def list_active_users(self) -> list[User]:
        """List all active users."""
        return self._presence.get_active_users()

    def list_users_for_project(self, project_path: str) -> list[User]:
        """List all users viewing a specific project."""
        return self._presence.get_users_for_project(project_path)

    def update_user_activity(self, user_id: UUID) -> User | None:
        """Update a user's last activity timestamp."""
        return self._presence.update_user_activity(user_id)

    def set_user_project(self, user_id: UUID, project_path: str | None) -> User | None:
        """Set the project a user is viewing."""
        return self._presence.set_user_project(user_id, project_path)

    async def change_role(
        self, user_id: UUID, new_role: str, changed_by: UUID | None = None
    ) -> User | None:
        """
        Change a user's role.

        Args:
            user_id: The ID of the user to change.
            new_role: The new role ("viewer" or "controller").
            changed_by: Optional ID of the user making the change.

        Returns:
            The updated User or None if not found.

        Raises:
            ValueError: If role is invalid or controller limit would be exceeded.
        """
        # Validate role
        try:
            role = UserRole(new_role.lower())
        except ValueError:
            raise ValueError(f"Invalid role: {new_role}")

        user = self._presence.get_by_id(user_id)
        if not user:
            return None

        old_role = user.role

        # Check controller limit if promoting to controller
        if role == UserRole.CONTROLLER and old_role != UserRole.CONTROLLER:
            if len(self._presence.get_controllers()) >= self._max_controllers:
                raise ValueError(
                    f"Maximum controller limit ({self._max_controllers}) would be exceeded"
                )

        user.role = role
        user.update_activity()

        logger.info(
            f"Role changed: {user.name} from {old_role.value} to {role.value} (by: {changed_by})"
        )

        await self.event_bus.publish(
            RoleChangedEvent(
                user_id=str(user_id),
                old_role=old_role.value,
                new_role=role.value,
                changed_by=str(changed_by) if changed_by else "system",
            )
        )

        return user

    def check_permission(self, user_id: UUID, action: str) -> bool:
        """
        Check if a user has permission to perform an action.

        Args:
            user_id: The ID of the user.
            action: The action to check permission for.

        Returns:
            True if permitted, False otherwise.
        """
        user = self._presence.get_by_id(user_id)
        if not user or not user.is_active:
            return False

        # Controllers can do everything
        if user.role == UserRole.CONTROLLER:
            return True

        # Viewers can only view
        viewer_actions = {
            "view_projects",
            "view_logs",
            "view_activity",
            "view_presence",
        }

        return action in viewer_actions

    def get_presence_info(self) -> UserPresence:
        """Get the current user presence information."""
        return self._presence

    async def _cleanup_loop(self) -> None:
        """Background task to clean up inactive users."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                removed = self._presence.clear_inactive_users(self._session_timeout)
                for user in removed:
                    if user.is_active:  # Was marked inactive
                        logger.info(f"User marked inactive: {user.name} (timeout)")
                        await self.event_bus.publish(
                            UserLeftEvent(
                                user_id=str(user.id),
                                user_name=user.name,
                                session_id=user.session_id or "",
                            )
                        )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get collaboration statistics."""
        return {
            "total_users": self._presence.total_count,
            "active_users": self._presence.active_count,
            "viewers": self._presence.viewer_count,
            "controllers": self._presence.controller_count,
            "max_viewers": self._max_viewers,
            "max_controllers": self._max_controllers,
            "session_timeout_seconds": self._session_timeout,
        }
