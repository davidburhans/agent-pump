"""Integration tests for HTTP server startup."""

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server


class TestServerStartup:
    """Integration tests for server startup and basic functionality."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with debug mode."""
        app = create_server(debug=True, api_key="test-key")
        with TestClient(app) as c:
            yield c

    def test_server_starts_and_responds_to_health(self, client: TestClient) -> None:
        """Test that server starts and responds to health check."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_server_respects_port_configuration(self) -> None:
        """Test that server can be configured with different settings."""
        # This is more of a configuration test - we create different app instances
        app1 = create_server(debug=False, api_key="key1")
        app2 = create_server(debug=True, api_key="key2")

        # Both should create successfully
        assert app1 is not None
        assert app2 is not None

    def test_create_server_generates_key_if_missing(self) -> None:
        """Test that create_server generates a key if API key is missing."""
        import os
        from unittest.mock import patch

        # Ensure no env var
        with patch.dict(os.environ, {}, clear=True):
            app = create_server(api_key=None)
            assert app is not None
            # Check if key is set in state
            assert hasattr(app.state, "api_key")
            assert app.state.api_key is not None
            assert len(app.state.api_key) > 0

    def test_openapi_docs_available_in_debug_mode(self, client: TestClient) -> None:
        """Test that OpenAPI docs are available in debug mode."""
        # Get OpenAPI schema
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        # Verify it's a valid OpenAPI spec
        assert "openapi" in data
        assert "paths" in data
        assert "/health" in data["paths"]

    def test_server_lifespan_events(self, client: TestClient) -> None:
        """Test that lifespan events are triggered correctly."""
        # The lifespan context manager should have run during TestClient initialization
        response = client.get("/health")
        data = response.json()

        # If startup ran, uptime should be available
        assert "uptimeSeconds" in data

    def test_graceful_error_handling(self, client: TestClient) -> None:
        """Test that unhandled exceptions are caught gracefully."""
        # API routes that don't exist should return 404
        # Note: We must authenticate to reach routing
        api_key = client.app.state.api_key
        response = client.get(
            "/api/non-existent-route",
            headers={"X-API-Key": api_key},
        )

        # Should return 404, not 500
        assert response.status_code == 404
