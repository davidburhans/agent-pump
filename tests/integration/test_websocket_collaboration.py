"""Integration tests for WebSocket collaborative features."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from agent_pump.api.server import create_server


class TestWebSocketCollaboration:
    """Integration tests for collaborative mode."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with a known API key."""
        app = create_server(debug=True, api_key="test-key")
        with TestClient(app) as c:
            yield c

    def test_websocket_connects_with_auth(self, client: TestClient) -> None:
        """Test that websocket connects with valid API key."""
        # Note: TestClient handles lifespan startup automatically

        with client.websocket_connect("/ws?api_key=test-key") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert "session_id" in data

    def test_websocket_rejects_invalid_auth(self, client: TestClient) -> None:
        """Test that websocket rejects invalid API key."""
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws?api_key=wrong-key"):
                pass

        # 1008 is Policy Violation
        assert exc.value.code == 1008

    def test_collaboration_mode_enabled(self, client: TestClient) -> None:
        """Test that providing a name enables collaborative mode."""
        with client.websocket_connect("/ws?api_key=test-key&name=Alice&role=viewer") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data.get("collaborative_mode") is True

            user_info = data.get("user")
            assert user_info is not None
            assert user_info["name"] == "Alice"
            assert user_info["role"] == "viewer"

            # Verify user is registered in the service
            # Access the app state via the client's app
            app = client.app
            collab_service = app.state.collaboration_service
            active_users = collab_service.list_active_users()

            assert len(active_users) == 1
            assert active_users[0].name == "Alice"

    def test_collaboration_service_injection(self, client: TestClient) -> None:
        """Test that services are correctly injected into the global manager."""
        from agent_pump.api.routes.websocket import manager

        # Ensure manager has services
        assert manager.collaboration_service is not None
        assert manager.activity_service is not None

        # Ensure they match the app state services
        app = client.app
        assert manager.collaboration_service is app.state.collaboration_service
        assert manager.activity_service is app.state.activity_service
