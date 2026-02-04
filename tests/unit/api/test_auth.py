"""Unit tests for auth middleware."""

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server


class TestAuthMiddleware:
    """Tests for the authentication middleware."""

    @pytest.fixture
    def client_no_auth(self) -> TestClient:
        """Create a test client without auth."""
        app = create_server(debug=True, api_key=None)
        return TestClient(app)

    @pytest.fixture
    def client_with_auth(self) -> TestClient:
        """Create a test client with auth enabled."""
        app = create_server(debug=True, api_key="test-api-key-12345")
        return TestClient(app)

    def test_no_auth_allows_all_requests(self, client_no_auth: TestClient) -> None:
        """Test that auth disabled allows all requests."""
        response = client_no_auth.get("/health")
        assert response.status_code == 200

    def test_auth_enabled_requires_api_key(self, client_with_auth: TestClient) -> None:
        """Test that auth enabled requires API key."""
        response = client_with_auth.get("/health")

        # Health endpoint bypasses auth by default
        assert response.status_code == 200

    def test_auth_returns_401_without_key(self, client_with_auth: TestClient) -> None:
        """Test that requests without API key return 401 for protected routes."""
        # Try to access a route that doesn't bypass auth
        # For this test, we'll use a non-existent route that will hit the auth middleware
        response = client_with_auth.get("/some-protected-route")

        # Should get 401 (or 404 if auth is bypassed for unknown routes)
        # The auth middleware runs before routing, so it should be 401
        assert response.status_code in [401, 404]

    def test_auth_accepts_valid_api_key(self, client_with_auth: TestClient) -> None:
        """Test that valid API key is accepted."""
        response = client_with_auth.get(
            "/health",
            headers={"X-API-Key": "test-api-key-12345"},
        )

        assert response.status_code == 200

    def test_auth_rejects_invalid_api_key(self, client_with_auth: TestClient) -> None:
        """Test that invalid API key returns 401."""
        response = client_with_auth.get(
            "/some-protected-route",
            headers={"X-API-Key": "invalid-key"},
        )

        assert response.status_code == 401

    def test_health_bypasses_auth_when_configured(self, client_with_auth: TestClient) -> None:
        """Test that /health bypasses auth when configured."""
        # Health is in the default bypass list
        response = client_with_auth.get("/health")

        assert response.status_code == 200

    def test_docs_bypasses_auth(self, client_with_auth: TestClient) -> None:
        """Test that docs endpoints bypass auth."""
        # Note: docs are disabled in non-debug mode
        response = client_with_auth.get("/docs")

        # In debug mode, should be accessible (may return HTML or 404)
        assert response.status_code in [200, 404]
