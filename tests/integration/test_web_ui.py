"""Integration tests for Web UI serving."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import create_server

app = create_server(autoload_projects=False)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_serve_index_html(client):
    """Test that the root path serves index.html."""
    # Ensure static file exists for test
    static_path = Path("src/agent_pump/api/static")
    index_path = static_path / "index.html"

    if not index_path.exists():
        pytest.skip("UI not built, skipping UI serving test")

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_serve_assets(client):
    """Test serving assets."""
    static_path = Path("src/agent_pump/api/static")
    if not static_path.exists():
        pytest.skip("UI not built")

    # Find a js file in assets
    assets_dir = static_path / "assets"
    if not assets_dir.exists():
        pytest.skip("No assets dir")

    js_files = list(assets_dir.glob("*.js"))
    if not js_files:
        pytest.skip("No JS files in assets")

    js_file = js_files[0]
    response = client.get(f"/assets/{js_file.name}")
    assert response.status_code == 200
    content_type = response.headers["content-type"]
    assert "application/javascript" in content_type or "text/javascript" in content_type


def test_spa_catch_all(client):
    """Test that unknown routes return index.html (SPA routing)."""
    static_path = Path("src/agent_pump/api/static/index.html")
    if not static_path.exists():
        pytest.skip("UI not built")

    response = client.get("/some/deep/route")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<!doctype html>" in response.text.lower()


def test_api_bypass(client):
    """Test that /api routes are NOT caught by SPA catch-all."""
    # /api/health is not valid, but /health is.
    # Projects router is at /api/projects

    # Check /health (root router)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Check /api/projects
    # Since auth is enabled by default, this should return 401
    # This confirms it is NOT serving the SPA HTML (which would be 200 OK)
    response = client.get("/api/projects")
    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"
