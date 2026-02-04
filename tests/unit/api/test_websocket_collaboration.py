"""Tests for enhanced WebSocket connection manager with collaborative mode."""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketState

from agent_pump.api.routes.websocket import ConnectionManager
from agent_pump.models.activity import ActivityType
from agent_pump.models.collaboration import User, UserRole


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.client_state = WebSocketState.CONNECTED
        self.sent_messages = []
        self.closed = False

    async def accept(self):
        pass

    async def send_json(self, message):
        self.sent_messages.append(message)

    async def send_text(self, text):
        self.sent_messages.append(json.loads(text))

    async def receive_text(self):
        return json.dumps({"type": "heartbeat"})


class TestConnectionManager:
    """Tests for ConnectionManager."""

    @pytest.fixture
    def mock_collab_service(self):
        """Create a mock collaboration service."""
        service = MagicMock()
        service.join_session = AsyncMock(
            return_value=User(
                name="Test",
                role=UserRole.VIEWER,
                session_id="ws_123",
            )
        )
        service.leave_session = AsyncMock()
        service.get_user = MagicMock(return_value=None)
        service.update_user_activity = MagicMock()
        service.set_user_project = MagicMock()
        return service

    @pytest.fixture
    def mock_activity_service(self):
        """Create a mock activity service."""
        service = MagicMock()
        service.log_activity = AsyncMock()
        return service

    @pytest.fixture
    def manager(self, mock_collab_service, mock_activity_service):
        """Create a connection manager with mock services."""
        mgr = ConnectionManager()
        mgr.set_services(mock_collab_service, mock_activity_service)
        return mgr

    @pytest.mark.asyncio
    async def test_connect_without_collaboration(self, manager):
        """Test basic connection without collaborative mode."""
        ws = MockWebSocket()

        user_info = await manager.connect(ws, "session_123")

        assert user_info is None
        assert "session_123" in manager.active_connections
        assert len(manager.active_connections) == 1

    @pytest.mark.asyncio
    async def test_connect_with_collaboration(self, manager, mock_collab_service):
        """Test connection with collaborative mode enabled."""
        ws = MockWebSocket()

        user_info = await manager.connect(
            ws,
            "session_123",
            user_name="Alice",
            role="viewer",
            project_path="/projects/test",
        )

        assert user_info is not None
        assert user_info["name"] == "Test"
        assert user_info["role"] == "viewer"
        assert "session_123" in manager.user_sessions
        mock_collab_service.join_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_logs_activity(self, manager, mock_activity_service):
        """Test that connecting logs a USER_JOINED activity."""
        ws = MockWebSocket()

        await manager.connect(
            ws,
            "session_123",
            user_name="Alice",
            role="viewer",
            project_path="/projects/test",
        )

        mock_activity_service.log_activity.assert_called_once()
        call_args = mock_activity_service.log_activity.call_args
        assert call_args[1]["action"] == ActivityType.USER_JOINED

    @pytest.mark.asyncio
    async def test_disconnect(self, manager):
        """Test disconnection cleanup."""
        ws = MockWebSocket()
        await manager.connect(ws, "session_123")

        manager.disconnect("session_123")

        assert "session_123" not in manager.active_connections
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_join_room(self, manager):
        """Test joining a room."""
        manager.join_room("session_123", "room_a")

        assert "room_a" in manager.rooms
        assert "session_123" in manager.rooms["room_a"]

    @pytest.mark.asyncio
    async def test_leave_room(self, manager):
        """Test leaving a room."""
        manager.join_room("session_123", "room_a")
        manager.leave_room("session_123", "room_a")

        assert "room_a" not in manager.rooms

    @pytest.mark.asyncio
    async def test_send_message(self, manager):
        """Test sending message to specific client."""
        ws = MockWebSocket()
        await manager.connect(ws, "session_123")

        success = await manager.send_message("session_123", {"type": "test"})

        assert success is True
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "test"

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent(self, manager):
        """Test sending message to non-existent session."""
        success = await manager.send_message("nonexistent", {"type": "test"})

        assert success is False

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """Test broadcasting to all clients."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        await manager.connect(ws1, "session_1")
        await manager.connect(ws2, "session_2")

        await manager.broadcast({"type": "update"})

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_broadcast_to_room(self, manager):
        """Test broadcasting to room members only."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()
        await manager.connect(ws1, "session_1")
        await manager.connect(ws2, "session_2")
        await manager.connect(ws3, "session_3")

        manager.join_room("session_1", "room_a")
        manager.join_room("session_2", "room_a")
        manager.join_room("session_3", "room_b")

        await manager.broadcast_to_room("room_a", {"type": "update"})

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert len(ws3.sent_messages) == 0  # Not in room_a

    @pytest.mark.asyncio
    async def test_handle_heartbeat(self, manager, mock_collab_service):
        """Test handling heartbeat message."""
        ws = MockWebSocket()
        await manager.connect(ws, "session_123")
        user_id = uuid4()
        manager.user_sessions["session_123"] = str(user_id)

        # Set up mock to return a user for the heartbeat handler
        mock_collab_service.get_user = MagicMock(
            return_value=User(name="TestUser", role=UserRole.VIEWER)
        )

        await manager.handle_message(
            "session_123",
            {"type": "heartbeat"},
        )

        mock_collab_service.update_user_activity.assert_called_once()
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "heartbeat_ack"

    @pytest.mark.asyncio
    async def test_handle_message_no_permission(self, manager, mock_collab_service):
        """Test message handling without permission."""
        # Create user without controller role
        user = User(name="Viewer", role=UserRole.VIEWER)
        mock_collab_service.get_user = MagicMock(return_value=user)

        ws = MockWebSocket()
        await manager.connect(ws, "session_123")
        manager.user_sessions["session_123"] = str(user.id)

        await manager.handle_message(
            "session_123",
            {"type": "pause_workflow"},
        )

        # Should receive error
        assert any(
            msg.get("type") == "error" and "Insufficient permissions" in msg.get("message", "")
            for msg in ws.sent_messages
        )

    @pytest.mark.asyncio
    async def test_set_services(self, manager, mock_collab_service, mock_activity_service):
        """Test setting services after initialization."""
        new_mgr = ConnectionManager()

        assert new_mgr.collaboration_service is None
        assert new_mgr.activity_service is None

        new_mgr.set_services(mock_collab_service, mock_activity_service)

        assert new_mgr.collaboration_service is mock_collab_service
        assert new_mgr.activity_service is mock_activity_service

    @pytest.mark.asyncio
    async def test_connect_with_role_limits(self, manager, mock_collab_service):
        """Test that role limits are enforced on connect."""
        # Simulate limit exceeded
        mock_collab_service.join_session = AsyncMock(
            side_effect=ValueError("Maximum viewer limit (5) reached")
        )

        ws = MockWebSocket()

        # Should still connect but without collaborative features
        user_info = await manager.connect(
            ws,
            "session_123",
            user_name="Alice",
            role="viewer",
        )

        assert user_info is None
        assert "session_123" in manager.active_connections


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint function."""

    @pytest.mark.asyncio
    async def test_websocket_basic_connection(self):
        """Test basic WebSocket connection handling."""
        # This is more of an integration test - we'll test the manager functions instead
        pass

    @pytest.mark.skip(reason="Integration test - requires full FastAPI setup")
    async def test_websocket_full_flow(self):
        """Full WebSocket flow test."""
        pass
