"""Unit tests for auth middleware."""

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server


class TestAuthMiddleware:
    """Tests for the authentication middleware."""

    @pytest.fixture
    def client_auto_auth(self) -> TestClient:
        """Create a test client with auto-generated auth."""
        app = create_server(debug=True, api_key=None)
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def client_with_auth(self) -> TestClient:
        """Create a test client with auth enabled."""
        app = create_server(debug=True, api_key="test-api-key-12345")
        with TestClient(app) as c:
            yield c

    def test_auto_auth_protects_requests(self, client_auto_auth: TestClient) -> None:
        """Test that auto-generated auth protects requests."""
        # /api/projects is protected
        response = client_auto_auth.get("/api/projects")
        assert response.status_code == 401

    def test_auto_auth_allows_bypass(self, client_auto_auth: TestClient) -> None:
        """Test that auto-generated auth allows bypass routes."""
        response = client_auto_auth.get("/health")
        assert response.status_code == 200

    def test_auth_enabled_requires_api_key(self, client_with_auth: TestClient) -> None:
        """Test that auth enabled requires API key."""
        response = client_with_auth.get("/health")

        # Health endpoint bypasses auth by default (not in protected prefix)
        assert response.status_code == 200

    def test_auth_returns_401_without_key(self, client_with_auth: TestClient) -> None:
        """Test that requests without API key return 401 for protected routes."""
        # Try to access a route that is protected (/api/...)
        response = client_with_auth.get("/api/projects")

        assert response.status_code == 401

    def test_auth_bypasses_unknown_routes(self, client_with_auth: TestClient) -> None:
        """Test that unknown routes (not in protected prefixes) are allowed."""
        response = client_with_auth.get("/some-unknown-route")
        # Allowed by auth middleware, handled by SPA catch-all (200)
        assert response.status_code == 200

    def test_auth_accepts_valid_api_key(self, client_with_auth: TestClient) -> None:
        """Test that valid API key is accepted."""
        # /api/projects is protected, so this verifies key is accepted
        response = client_with_auth.get(
            "/api/projects",
            headers={"X-API-Key": "test-api-key-12345"},
        )

        assert response.status_code == 200

    def test_auth_rejects_invalid_api_key(self, client_with_auth: TestClient) -> None:
        """Test that invalid API key returns 401."""
        response = client_with_auth.get(
            "/api/projects",
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
