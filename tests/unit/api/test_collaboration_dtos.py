"""Tests for collaboration API DTOs."""

from datetime import datetime, timedelta
from uuid import uuid4

from agent_pump.api.schemas import (
    ActivityDTO,
    ActivityFilterRequest,
    ChangeRoleRequest,
    CollaborativeSessionDTO,
    JoinSessionRequest,
    UserDTO,
    UserPresenceDTO,
)
from agent_pump.models.activity import Activity, ActivityType
from agent_pump.models.collaboration import User, UserPresence, UserRole


class TestUserDTO:
    """Tests for UserDTO."""

    def test_from_internal_defaults(self):
        """Test converting a User to UserDTO."""
        user = User(name="Test User", role=UserRole.VIEWER)
        dto = UserDTO.from_internal(user)

        assert dto.id == str(user.id)
        assert dto.name == "Test User"
        assert dto.role == "viewer"
        assert dto.is_active is True
        assert dto.project_path is None
        assert dto.joined_at == user.joined_at.isoformat()
        assert dto.last_activity == user.last_activity.isoformat()

    def test_from_internal_controller(self):
        """Test converting a controller User to UserDTO."""
        user = User(name="Admin", role=UserRole.CONTROLLER, session_id="ws_123")
        dto = UserDTO.from_internal(user)

        assert dto.name == "Admin"
        assert dto.role == "controller"
        assert dto.is_active is True

    def test_from_internal_with_project(self):
        """Test converting a User viewing a project."""
        user = User(
            name="Alice",
            role=UserRole.VIEWER,
            project_path="/projects/test",
        )
        dto = UserDTO.from_internal(user)

        assert dto.project_path == "/projects/test"


class TestUserPresenceDTO:
    """Tests for UserPresenceDTO."""

    def test_from_internal_empty(self):
        """Test converting empty UserPresence."""
        presence = UserPresence()
        dto = UserPresenceDTO.from_internal(presence)

        assert dto.users == []
        assert dto.total_viewers == 0
        assert dto.total_controllers == 0

    def test_from_internal_with_users(self):
        """Test converting UserPresence with users."""
        presence = UserPresence()

        # Add users
        controller = User(name="Admin", role=UserRole.CONTROLLER)
        viewer1 = User(name="User1", role=UserRole.VIEWER)
        viewer2 = User(name="User2", role=UserRole.VIEWER)

        presence.add_user(controller)
        presence.add_user(viewer1)
        presence.add_user(viewer2)

        dto = UserPresenceDTO.from_internal(presence)

        assert len(dto.users) == 3
        assert dto.total_viewers == 2
        assert dto.total_controllers == 1

    def test_from_internal_inactive_users_filtered(self):
        """Test that inactive users are not included."""
        presence = UserPresence()

        active_user = User(name="Active", role=UserRole.VIEWER, is_active=True)
        inactive_user = User(name="Inactive", role=UserRole.VIEWER, is_active=False)

        presence.add_user(active_user)
        presence.add_user(inactive_user)

        dto = UserPresenceDTO.from_internal(presence)

        # Only active users should be in the list
        assert len(dto.users) == 1
        assert dto.users[0].name == "Active"
        # But counts include all (since they're still tracked)
        assert dto.total_viewers == 2


class TestActivityDTO:
    """Tests for ActivityDTO."""

    def test_from_internal(self):
        """Test converting an Activity to ActivityDTO."""
        user_id = uuid4()
        activity = Activity.create(
            user_id=user_id,
            user_name="Test User",
            action=ActivityType.IDEA_INJECTED,
            project_path="/projects/test",
            details={"idea": "Add feature X"},
        )

        dto = ActivityDTO.from_internal(activity)

        assert dto.id == str(activity.id)
        assert dto.user_id == str(user_id)
        assert dto.user_name == "Test User"
        assert dto.action == "idea_injected"
        assert dto.project_path == "/projects/test"
        assert dto.details == {"idea": "Add feature X"}
        assert dto.timestamp == activity.timestamp.isoformat()

    def test_from_internal_no_project(self):
        """Test converting an Activity without project path."""
        activity = Activity.create(
            user_id=uuid4(),
            user_name="Test",
            action=ActivityType.USER_JOINED,
        )

        dto = ActivityDTO.from_internal(activity)

        assert dto.project_path is None
        assert dto.details == {}


class TestCollaborativeSessionDTO:
    """Tests for CollaborativeSessionDTO."""

    def test_create_session(self):
        """Test creating a session DTO."""
        now = datetime.now()
        dto = CollaborativeSessionDTO(
            session_id="session_123",
            project_path="/projects/test",
            users=[],
            started_at=now.isoformat(),
            activity_count=5,
        )

        assert dto.session_id == "session_123"
        assert dto.project_path == "/projects/test"
        assert dto.users == []
        assert dto.started_at == now.isoformat()
        assert dto.activity_count == 5

    def test_create_session_no_project(self):
        """Test creating a session DTO without project."""
        dto = CollaborativeSessionDTO(
            session_id="session_456",
            started_at=datetime.now().isoformat(),
        )

        assert dto.session_id == "session_456"
        assert dto.project_path is None
        assert dto.activity_count == 0


class TestJoinSessionRequest:
    """Tests for JoinSessionRequest."""

    def test_join_as_viewer(self):
        """Test join request as viewer."""
        req = JoinSessionRequest(user_name="Alice")

        assert req.user_name == "Alice"
        assert req.role == "viewer"
        assert req.project_path is None

    def test_join_as_controller(self):
        """Test join request as controller."""
        req = JoinSessionRequest(
            user_name="Bob",
            role="controller",
            project_path="/projects/test",
        )

        assert req.user_name == "Bob"
        assert req.role == "controller"
        assert req.project_path == "/projects/test"


class TestChangeRoleRequest:
    """Tests for ChangeRoleRequest."""

    def test_change_role(self):
        """Test role change request."""
        user_id = str(uuid4())
        req = ChangeRoleRequest(
            user_id=user_id,
            new_role="controller",
        )

        assert req.user_id == user_id
        assert req.new_role == "controller"


class TestActivityFilterRequest:
    """Tests for ActivityFilterRequest."""

    def test_default_filter(self):
        """Test default filter request."""
        req = ActivityFilterRequest()

        assert req.project_path is None
        assert req.user_id is None
        assert req.action is None
        assert req.limit == 50
        assert req.since is None

    def test_full_filter(self):
        """Test filter with all fields."""
        since = datetime.now() - timedelta(hours=1)
        req = ActivityFilterRequest(
            project_path="/projects/test",
            user_id="user_123",
            action="idea_injected",
            limit=100,
            since=since.isoformat(),
        )

        assert req.project_path == "/projects/test"
        assert req.user_id == "user_123"
        assert req.action == "idea_injected"
        assert req.limit == 100
        assert req.since == since.isoformat()
