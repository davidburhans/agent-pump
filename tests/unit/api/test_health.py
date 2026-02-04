"""Unit tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient

from agent_pump import __version__
from agent_pump.api.server import create_server


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    app = create_server(debug=True)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test that GET /health returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_expected_fields(self, client: TestClient) -> None:
        """Test that response contains expected fields."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "uptimeSeconds" in data
        assert "resources" in data
        assert "subprocesses" in data
        assert "eventQueueDepth" in data

    def test_health_status_is_ok(self, client: TestClient) -> None:
        """Test that status field is 'ok'."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "ok"

    def test_health_version_matches_package(self, client: TestClient) -> None:
        """Test that version matches package version."""
        response = client.get("/health")
        data = response.json()

        assert data["version"] == __version__

    def test_health_timestamp_is_iso_format(self, client: TestClient) -> None:
        """Test that timestamp is in ISO format."""
        from datetime import datetime

        response = client.get("/health")
        data = response.json()

        # Should not raise if valid ISO format
        datetime.fromisoformat(data["timestamp"])

    def test_health_uptime_is_positive_when_server_running(self, client: TestClient) -> None:
        """Test that uptime is positive when server is running."""
        response = client.get("/health")
        data = response.json()

        # Uptime should be a positive number or None if startup not complete
        if data["uptimeSeconds"] is not None:
            assert data["uptimeSeconds"] >= 0
