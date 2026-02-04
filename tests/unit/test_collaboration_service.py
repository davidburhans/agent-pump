"""Tests for collaboration service."""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio

from agent_pump.events.bus import EventBus
from agent_pump.models.collaboration import UserRole
from agent_pump.services.collaboration_service import CollaborationService


class TestCollaborationService:
    """Tests for CollaborationService."""

    @pytest_asyncio.fixture
    async def event_bus(self):
        """Create an event bus for testing."""
        bus = EventBus()
        yield bus

    @pytest_asyncio.fixture
    async def service(self, event_bus):
        """Create a collaboration service for testing."""
        svc = CollaborationService(
            event_bus=event_bus,
            session_timeout_seconds=60.0,
            max_viewers=5,
            max_controllers=2,
        )
        yield svc
        await svc.stop()

    @pytest.mark.asyncio
    async def test_join_session_viewer(self, service, event_bus):
        """Test joining as a viewer."""
        user = await service.join_session(
            user_name="Test User",
            role="viewer",
            session_id="ws_123",
            project_path="/projects/test",
        )

        assert user.name == "Test User"
        assert user.role == UserRole.VIEWER
        assert user.session_id == "ws_123"
        assert user.project_path == "/projects/test"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_join_session_controller(self, service, event_bus):
        """Test joining as a controller."""
        user = await service.join_session(
            user_name="Admin",
            role="controller",
        )

        assert user.role == UserRole.CONTROLLER
        assert user.can_control() is True

    @pytest.mark.asyncio
    async def test_join_session_invalid_role(self, service, event_bus):
        """Test joining with invalid role."""
        with pytest.raises(ValueError, match="Invalid role"):
            await service.join_session(
                user_name="Test",
                role="admin",  # Invalid role
            )

    @pytest.mark.asyncio
    async def test_join_session_viewer_limit(self, service, event_bus):
        """Test viewer limit enforcement."""
        # Add max viewers
        for i in range(5):
            await service.join_session(
                user_name=f"Viewer{i}",
                role="viewer",
                session_id=f"ws_{i}",
            )

        # Next viewer should fail
        with pytest.raises(ValueError, match="Maximum viewer limit"):
            await service.join_session(
                user_name="Extra",
                role="viewer",
            )

    @pytest.mark.asyncio
    async def test_join_session_controller_limit(self, service, event_bus):
        """Test controller limit enforcement."""
        # Add max controllers
        for i in range(2):
            await service.join_session(
                user_name=f"Controller{i}",
                role="controller",
                session_id=f"ws_{i}",
            )

        # Next controller should fail
        with pytest.raises(ValueError, match="Maximum controller limit"):
            await service.join_session(
                user_name="Extra",
                role="controller",
            )

    @pytest.mark.asyncio
    async def test_leave_session(self, service, event_bus):
        """Test leaving a session."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        removed = await service.leave_session(user.id)

        assert removed is not None
        assert removed.name == "Test"
        assert removed.id == user.id

    @pytest.mark.asyncio
    async def test_leave_nonexistent_user(self, service, event_bus):
        """Test leaving a session for non-existent user."""
        removed = await service.leave_session(uuid4())
        assert removed is None

    @pytest.mark.asyncio
    async def test_get_user(self, service, event_bus):
        """Test getting a user by ID."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        found = service.get_user(user.id)
        assert found is not None
        assert found.id == user.id

    @pytest.mark.asyncio
    async def test_get_user_by_session(self, service, event_bus):
        """Test getting a user by session ID."""
        await service.join_session(
            user_name="Test",
            role="viewer",
            session_id="ws_123",
        )

        found = service.get_user_by_session("ws_123")
        assert found is not None
        assert found.name == "Test"

    @pytest.mark.asyncio
    async def test_list_active_users(self, service, event_bus):
        """Test listing active users."""
        await service.join_session(user_name="User1", role="viewer")
        await service.join_session(user_name="User2", role="viewer")

        users = service.list_active_users()
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_update_user_activity(self, service, event_bus):
        """Test updating user activity."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        old_activity = user.last_activity

        # Wait a tiny bit
        await asyncio.sleep(0.01)

        updated = service.update_user_activity(user.id)
        assert updated is not None
        assert updated.last_activity > old_activity

    @pytest.mark.asyncio
    async def test_set_user_project(self, service, event_bus):
        """Test setting user's project."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        updated = service.set_user_project(user.id, "/projects/new")
        assert updated is not None
        assert updated.project_path == "/projects/new"

    @pytest.mark.asyncio
    async def test_list_users_for_project(self, service, event_bus):
        """Test listing users for a specific project."""
        await service.join_session(
            user_name="User1",
            role="viewer",
            project_path="/projects/a",
        )
        await service.join_session(
            user_name="User2",
            role="viewer",
            project_path="/projects/b",
        )

        users_a = service.list_users_for_project("/projects/a")
        assert len(users_a) == 1
        assert users_a[0].name == "User1"

    @pytest.mark.asyncio
    async def test_change_role(self, service, event_bus):
        """Test changing user role."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        updated = await service.change_role(user.id, "controller")
        assert updated is not None
        assert updated.role == UserRole.CONTROLLER

    @pytest.mark.asyncio
    async def test_change_role_invalid(self, service, event_bus):
        """Test changing to invalid role."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        with pytest.raises(ValueError, match="Invalid role"):
            await service.change_role(user.id, "admin")

    @pytest.mark.asyncio
    async def test_change_role_exceeds_limit(self, service, event_bus):
        """Test role change that would exceed controller limit."""
        # Add max controllers
        for i in range(2):
            await service.join_session(
                user_name=f"Controller{i}",
                role="controller",
            )

        user = await service.join_session(
            user_name="Viewer",
            role="viewer",
        )

        with pytest.raises(ValueError, match="Maximum controller limit"):
            await service.change_role(user.id, "controller")

    @pytest.mark.asyncio
    async def test_check_permission_controller(self, service, event_bus):
        """Test that controllers have all permissions."""
        user = await service.join_session(
            user_name="Admin",
            role="controller",
        )

        assert service.check_permission(user.id, "view_projects") is True
        assert service.check_permission(user.id, "inject_ideas") is True
        assert service.check_permission(user.id, "pause_workflow") is True

    @pytest.mark.asyncio
    async def test_check_permission_viewer(self, service, event_bus):
        """Test viewer permissions are limited."""
        user = await service.join_session(
            user_name="Viewer",
            role="viewer",
        )

        assert service.check_permission(user.id, "view_projects") is True
        assert service.check_permission(user.id, "view_logs") is True
        assert service.check_permission(user.id, "inject_ideas") is False
        assert service.check_permission(user.id, "pause_workflow") is False

    @pytest.mark.asyncio
    async def test_check_permission_inactive_user(self, service, event_bus):
        """Test that inactive users have no permissions."""
        user = await service.join_session(
            user_name="Test",
            role="viewer",
        )

        # Mark inactive
        user.is_active = False

        assert service.check_permission(user.id, "view_projects") is False

    @pytest.mark.asyncio
    async def test_check_permission_nonexistent_user(self, service, event_bus):
        """Test permission check for non-existent user."""
        assert service.check_permission(uuid4(), "view_projects") is False

    @pytest.mark.asyncio
    async def test_get_stats(self, service, event_bus):
        """Test getting collaboration statistics."""
        await service.join_session(user_name="User1", role="viewer")
        await service.join_session(user_name="User2", role="controller")

        stats = service.get_stats()

        assert stats["total_users"] == 2
        assert stats["active_users"] == 2
        assert stats["viewers"] == 1
        assert stats["controllers"] == 1
        assert stats["max_viewers"] == 5
        assert stats["max_controllers"] == 2

    @pytest.mark.asyncio
    async def test_duplicate_session_replacement(self, service, event_bus):
        """Test that duplicate session IDs replace existing users."""
        user1 = await service.join_session(
            user_name="Old",
            role="viewer",
            session_id="ws_123",
        )

        user2 = await service.join_session(
            user_name="New",
            role="viewer",
            session_id="ws_123",  # Same session
        )

        # Should only have the new user
        assert service.get_user(user1.id) is None
        assert service.get_user(user2.id) is not None
        assert len(service.list_active_users()) == 1
