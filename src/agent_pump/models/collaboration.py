"""Collaborative user models for agent-pump."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """Role of a user in collaborative mode."""

    VIEWER = "viewer"
    CONTROLLER = "controller"


class User(BaseModel):
    """Represents a user in collaborative mode."""

    id: UUID = Field(default_factory=uuid4, description="Unique user identifier")
    name: str = Field(description="Display name for the user")
    role: UserRole = Field(default=UserRole.VIEWER, description="User role")
    joined_at: datetime = Field(default_factory=datetime.now, description="When user joined")
    last_activity: datetime = Field(
        default_factory=datetime.now, description="Last activity timestamp"
    )
    session_id: str | None = Field(default=None, description="WebSocket session ID if connected")
    is_active: bool = Field(default=True, description="Whether user is currently connected")
    project_path: str | None = Field(
        default=None, description="Project the user is currently viewing"
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()

    def can_control(self) -> bool:
        """Check if user has controller permissions."""
        return self.role == UserRole.CONTROLLER

    def to_summary(self) -> dict[str, Any]:
        """Return a summary dict for serialization."""
        return {
            "id": str(self.id),
            "name": self.name,
            "role": self.role.value,
            "is_active": self.is_active,
            "project_path": self.project_path,
        }


class UserPresence(BaseModel):
    """Tracks presence information for all users."""

    users: list[User] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_user(self, user: User) -> None:
        """Add a user to presence tracking."""
        # Check if user already exists by session_id
        existing = self.get_by_session_id(user.session_id) if user.session_id else None
        if existing:
            # Update existing user
            self.remove_user(existing.id)

        self.users.append(user)
        self.updated_at = datetime.now()

    def remove_user(self, user_id: UUID) -> User | None:
        """Remove a user by ID and return the removed user."""
        for i, user in enumerate(self.users):
            if user.id == user_id:
                self.users.pop(i)
                self.updated_at = datetime.now()
                return user
        return None

    def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        for user in self.users:
            if user.id == user_id:
                return user
        return None

    def get_by_session_id(self, session_id: str) -> User | None:
        """Get a user by session ID."""
        for user in self.users:
            if user.session_id == session_id:
                return user
        return None

    def get_active_users(self) -> list[User]:
        """Get all currently active users."""
        return [u for u in self.users if u.is_active]

    def get_controllers(self) -> list[User]:
        """Get all users with controller role."""
        return [u for u in self.users if u.role == UserRole.CONTROLLER]

    def get_viewers(self) -> list[User]:
        """Get all users with viewer role."""
        return [u for u in self.users if u.role == UserRole.VIEWER]

    def update_user_activity(self, user_id: UUID) -> User | None:
        """Update a user's last activity timestamp."""
        user = self.get_by_id(user_id)
        if user:
            user.update_activity()
            self.updated_at = datetime.now()
        return user

    def set_user_project(self, user_id: UUID, project_path: str | None) -> User | None:
        """Set the project a user is viewing."""
        user = self.get_by_id(user_id)
        if user:
            user.project_path = project_path
            user.update_activity()
            self.updated_at = datetime.now()
        return user

    def get_users_for_project(self, project_path: str) -> list[User]:
        """Get all users viewing a specific project."""
        return [u for u in self.users if u.is_active and u.project_path == project_path]

    def clear_inactive_users(self, timeout_seconds: float = 300.0) -> list[User]:
        """Remove users who have been inactive for longer than timeout."""
        now = datetime.now()
        removed = []
        for user in list(self.users):
            if not user.is_active or (now - user.last_activity).total_seconds() > timeout_seconds:
                if user.is_active:
                    user.is_active = False
                removed.append(user)
        self.updated_at = now
        return removed

    @property
    def total_count(self) -> int:
        """Total number of users."""
        return len(self.users)

    @property
    def active_count(self) -> int:
        """Number of active users."""
        return len(self.get_active_users())

    @property
    def controller_count(self) -> int:
        """Number of users with controller role."""
        return len(self.get_controllers())

    @property
    def viewer_count(self) -> int:
        """Number of users with viewer role."""
        return len(self.get_viewers())
