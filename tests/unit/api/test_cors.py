"""Unit tests for CORS middleware."""

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    app = create_server(debug=True)
    return TestClient(app)


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present_on_response(self, client: TestClient) -> None:
        """Test that CORS headers are present on responses."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        # Check for Access-Control-Allow-Origin header
        assert "access-control-allow-origin" in response.headers

    def test_cors_preflight_request_succeeds(self, client: TestClient) -> None:
        """Test that preflight OPTIONS requests work correctly."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200

    def test_cors_allows_localhost_origin(self, client: TestClient) -> None:
        """Test that localhost origins are allowed."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_127_0_0_1_origin(self, client: TestClient) -> None:
        """Test that 127.0.0.1 origins are allowed."""
        response = client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_exposes_required_headers(self, client: TestClient) -> None:
        """Test that required headers are exposed."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        # Check for exposed headers
        exposed = response.headers.get("access-control-expose-headers", "")
        assert "X-Request-ID" in exposed or "x-request-id" in exposed.lower()

    def test_cors_allows_credentials(self, client: TestClient) -> None:
        """Test that credentials are allowed."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        allow_credentials = response.headers.get("access-control-allow-credentials", "")
        assert allow_credentials.lower() == "true"

    def test_cors_headers_present_on_401_response(self, client: TestClient) -> None:
        """Test that CORS headers are present on 401 Unauthorized responses."""
        # Make a request to a protected endpoint without the API key
        response = client.get(
            "/api/projects",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 401
        assert "access-control-allow-origin" in response.headers
