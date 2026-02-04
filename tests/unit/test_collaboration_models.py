"""Tests for collaboration user models."""

from datetime import datetime, timedelta
from uuid import UUID, uuid4

import pytest

from agent_pump.models.collaboration import User, UserPresence, UserRole


class TestUserRole:
    """Tests for UserRole enum."""

    def test_user_role_values(self):
        """Test that UserRole has expected values."""
        assert UserRole.VIEWER.value == "viewer"
        assert UserRole.CONTROLLER.value == "controller"

    def test_user_role_enum_members(self):
        """Test that all expected roles exist."""
        roles = list(UserRole)
        assert len(roles) == 2
        assert UserRole.VIEWER in roles
        assert UserRole.CONTROLLER in roles


class TestUser:
    """Tests for the User model."""

    def test_create_user_defaults(self):
        """Test creating a user with default values."""
        user = User(name="Test User")
        assert user.name == "Test User"
        assert isinstance(user.id, UUID)
        assert user.role == UserRole.VIEWER
        assert user.is_active is True
        assert user.session_id is None
        assert user.project_path is None
        assert isinstance(user.joined_at, datetime)
        assert isinstance(user.last_activity, datetime)

    def test_create_user_with_all_fields(self):
        """Test creating a user with all fields specified."""
        user_id = uuid4()
        joined = datetime.now() - timedelta(hours=1)
        active = datetime.now()

        user = User(
            id=user_id,
            name="Alice",
            role=UserRole.CONTROLLER,
            joined_at=joined,
            last_activity=active,
            session_id="ws_123",
            is_active=True,
            project_path="/projects/my-project",
        )

        assert user.id == user_id
        assert user.name == "Alice"
        assert user.role == UserRole.CONTROLLER
        assert user.joined_at == joined
        assert user.last_activity == active
        assert user.session_id == "ws_123"
        assert user.project_path == "/projects/my-project"

    def test_user_name_stripping(self):
        """Test that whitespace is stripped from user names."""
        user = User(name="  Alice Smith  ")
        assert user.name == "Alice Smith"

    def test_update_activity(self):
        """Test updating user activity timestamp."""
        user = User(name="Test")
        old_activity = user.last_activity

        # Wait a tiny bit to ensure timestamp changes
        import time

        time.sleep(0.01)

        user.update_activity()
        assert user.last_activity > old_activity

    def test_can_control_viewer(self):
        """Test that viewers cannot control."""
        user = User(name="Viewer", role=UserRole.VIEWER)
        assert user.can_control() is False

    def test_can_control_controller(self):
        """Test that controllers can control."""
        user = User(name="Controller", role=UserRole.CONTROLLER)
        assert user.can_control() is True

    def test_to_summary(self):
        """Test user summary serialization."""
        user = User(
            name="Bob",
            role=UserRole.CONTROLLER,
            session_id="ws_456",
            project_path="/projects/test",
        )

        summary = user.to_summary()
        assert summary["id"] == str(user.id)
        assert summary["name"] == "Bob"
        assert summary["role"] == "controller"
        assert summary["is_active"] is True
        assert summary["project_path"] == "/projects/test"


class TestUserPresence:
    """Tests for the UserPresence model."""

    def test_create_presence(self):
        """Test creating empty user presence."""
        presence = UserPresence()
        assert presence.users == []
        assert presence.total_count == 0
        assert presence.active_count == 0
        assert presence.controller_count == 0
        assert presence.viewer_count == 0

    def test_add_user(self):
        """Test adding a user to presence."""
        presence = UserPresence()
        user = User(name="Alice", session_id="ws_1")

        presence.add_user(user)

        assert len(presence.users) == 1
        assert presence.users[0].name == "Alice"
        assert presence.total_count == 1
        assert presence.active_count == 1

    def test_add_user_duplicate_session(self):
        """Test that adding user with same session replaces old user."""
        presence = UserPresence()
        user1 = User(name="Alice", session_id="ws_1")
        user2 = User(name="Bob", session_id="ws_1")  # Same session

        presence.add_user(user1)
        presence.add_user(user2)

        assert len(presence.users) == 1
        assert presence.users[0].name == "Bob"

    def test_remove_user(self):
        """Test removing a user by ID."""
        presence = UserPresence()
        user = User(name="Alice")
        presence.add_user(user)

        removed = presence.remove_user(user.id)

        assert removed is not None
        assert removed.name == "Alice"
        assert len(presence.users) == 0

    def test_remove_nonexistent_user(self):
        """Test removing a user that doesn't exist."""
        presence = UserPresence()
        removed = presence.remove_user(uuid4())
        assert removed is None

    def test_get_by_id(self):
        """Test getting user by ID."""
        presence = UserPresence()
        user = User(name="Alice")
        presence.add_user(user)

        found = presence.get_by_id(user.id)
        assert found is not None
        assert found.name == "Alice"

    def test_get_by_id_not_found(self):
        """Test getting user by ID that doesn't exist."""
        presence = UserPresence()
        found = presence.get_by_id(uuid4())
        assert found is None

    def test_get_by_session_id(self):
        """Test getting user by session ID."""
        presence = UserPresence()
        user = User(name="Alice", session_id="ws_123")
        presence.add_user(user)

        found = presence.get_by_session_id("ws_123")
        assert found is not None
        assert found.name == "Alice"

    def test_get_active_users(self):
        """Test getting only active users."""
        presence = UserPresence()

        active_user = User(name="Alice", is_active=True)
        inactive_user = User(name="Bob", is_active=False)

        presence.add_user(active_user)
        presence.add_user(inactive_user)

        active = presence.get_active_users()
        assert len(active) == 1
        assert active[0].name == "Alice"

    def test_get_controllers(self):
        """Test getting controller users."""
        presence = UserPresence()

        controller = User(name="Admin", role=UserRole.CONTROLLER)
        viewer = User(name="User", role=UserRole.VIEWER)

        presence.add_user(controller)
        presence.add_user(viewer)

        controllers = presence.get_controllers()
        assert len(controllers) == 1
        assert controllers[0].name == "Admin"
        assert presence.controller_count == 1

    def test_get_viewers(self):
        """Test getting viewer users."""
        presence = UserPresence()

        controller = User(name="Admin", role=UserRole.CONTROLLER)
        viewer = User(name="User", role=UserRole.VIEWER)

        presence.add_user(controller)
        presence.add_user(viewer)

        viewers = presence.get_viewers()
        assert len(viewers) == 1
        assert viewers[0].name == "User"
        assert presence.viewer_count == 1  # Only 1 viewer user

    def test_update_user_activity(self):
        """Test updating a user's activity."""
        presence = UserPresence()
        user = User(name="Alice")
        presence.add_user(user)

        old_activity = user.last_activity

        import time

        time.sleep(0.01)

        updated = presence.update_user_activity(user.id)

        assert updated is not None
        assert updated.last_activity > old_activity

    def test_set_user_project(self):
        """Test setting a user's current project."""
        presence = UserPresence()
        user = User(name="Alice")
        presence.add_user(user)

        updated = presence.set_user_project(user.id, "/projects/test")

        assert updated is not None
        assert updated.project_path == "/projects/test"

    def test_get_users_for_project(self):
        """Test getting users viewing a specific project."""
        presence = UserPresence()

        user1 = User(name="Alice", project_path="/projects/a", is_active=True)
        user2 = User(name="Bob", project_path="/projects/b", is_active=True)
        user3 = User(name="Charlie", project_path="/projects/a", is_active=False)  # Inactive

        presence.add_user(user1)
        presence.add_user(user2)
        presence.add_user(user3)

        project_a_users = presence.get_users_for_project("/projects/a")
        assert len(project_a_users) == 1
        assert project_a_users[0].name == "Alice"

    def test_clear_inactive_users(self):
        """Test clearing inactive users."""
        presence = UserPresence()

        # Create an old inactive user
        old_user = User(name="Old")
        old_user.last_activity = datetime.now() - timedelta(seconds=400)
        old_user.is_active = False

        # Create a recent user
        recent_user = User(name="Recent")
        recent_user.last_activity = datetime.now() - timedelta(seconds=10)

        presence.add_user(old_user)
        presence.add_user(recent_user)

        removed = presence.clear_inactive_users(timeout_seconds=300)

        # Old user should be marked inactive (but still in list)
        assert len(removed) == 1
        assert removed[0].name == "Old"
        assert old_user.is_active is False

        # Recent user should still be active
        assert recent_user.is_active is True

    def test_multiple_users(self):
        """Test managing multiple users."""
        presence = UserPresence()

        for i in range(10):
            role = UserRole.CONTROLLER if i < 3 else UserRole.VIEWER
            user = User(name=f"User{i}", role=role, session_id=f"ws_{i}")
            presence.add_user(user)

        assert presence.total_count == 10
        assert presence.active_count == 10
        assert presence.controller_count == 3  # Only 3 controllers out of 10 users
        assert presence.viewer_count == 7

        # Get only controllers
        controllers = presence.get_controllers()
        assert len(controllers) == 3

        # Get only viewers
        viewers = presence.get_viewers()
        assert len(viewers) == 7
