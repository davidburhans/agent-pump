"""Unit tests for WebSocket endpoint."""

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    app = create_server(debug=True)
    return TestClient(app)


class TestWebSocketEndpoint:
    """Tests for the WebSocket endpoint."""

    def test_websocket_connection_established(self, client: TestClient) -> None:
        """Test that WebSocket connection can be established."""
        with client.websocket_connect("/ws"):
            # Connection should be established
            pass  # Connection context manager handles this

    def test_websocket_receives_connected_message(self, client: TestClient) -> None:
        """Test that client receives connection confirmation."""
        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()

            assert data["type"] == "connected"
            assert "message" in data

    def test_websocket_echoes_messages(self, client: TestClient) -> None:
        """Test that server echoes messages back."""
        with client.websocket_connect("/ws") as websocket:
            # Receive initial connection message
            websocket.receive_json()

            # Send a test message
            test_message = "Hello, Agent Pump!"
            websocket.send_text(test_message)

            # Receive echo
            response = websocket.receive_json()

            assert response["type"] == "echo"
            assert response["received"] == test_message

    def test_websocket_handles_multiple_messages(self, client: TestClient) -> None:
        """Test that server can handle multiple messages in one session."""
        with client.websocket_connect("/ws") as websocket:
            # Receive initial connection message
            websocket.receive_json()

            messages = ["Message 1", "Message 2", "Message 3"]

            for msg in messages:
                websocket.send_text(msg)
                response = websocket.receive_json()

                assert response["type"] == "echo"
                assert response["received"] == msg

    def test_websocket_disconnect_cleanup(self, client: TestClient) -> None:
        """Test that disconnect is handled cleanly."""
        with client.websocket_connect("/ws") as websocket:
            # Receive initial connection message
            websocket.receive_json()

            # Connection will be closed when exiting context
            pass

        # Should reach here without exceptions
        assert True
