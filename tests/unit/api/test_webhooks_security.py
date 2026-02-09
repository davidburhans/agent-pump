
import pytest
import hmac
import hashlib
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from agent_pump.api.server import app
from agent_pump.models.webhook_config import WebhookConfig
from agent_pump.models.workspace import Workspace

client = TestClient(app)

@pytest.fixture
def mock_app_state(monkeypatch):
    """Mock the app state dependencies safely."""

    mock_workspace_service = MagicMock()
    mock_project_service = MagicMock()

    # Safely patch the app.state attributes
    # We assume app.state is an object where we can set attributes
    monkeypatch.setattr(app.state, "workspace_service", mock_workspace_service, raising=False)
    monkeypatch.setattr(app.state, "project_service", mock_project_service, raising=False)

    return mock_workspace_service

def test_webhook_no_secret_key(mock_app_state):
    """Test that requests are rejected with 500 if no secret key is configured."""
    workspace = Workspace(name="test_ws")
    workspace.webhook_config = WebhookConfig(enabled=True, secret_key=None)
    mock_app_state.get_current_workspace.return_value = workspace

    response = client.post(
        "/api/trigger/github",
        json={"ref": "refs/heads/main"},
        headers={"X-GitHub-Event": "push"}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Webhooks configuration error: No secret key set"

def test_webhook_invalid_signature_github(mock_app_state):
    """Test that requests with invalid signatures are rejected (GitHub)."""
    secret = "my_secret"
    workspace = Workspace(name="test_ws")
    workspace.webhook_config = WebhookConfig(enabled=True, secret_key=secret)
    mock_app_state.get_current_workspace.return_value = workspace

    response = client.post(
        "/api/trigger/github",
        json={"ref": "refs/heads/main"},
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=invalid_signature"
        }
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid GitHub signature"

def test_webhook_valid_signature_github(mock_app_state):
    """Test that requests with valid signatures are accepted (GitHub)."""
    secret = "my_secret"
    workspace = Workspace(name="test_ws")
    workspace.webhook_config = WebhookConfig(enabled=True, secret_key=secret)
    mock_app_state.get_current_workspace.return_value = workspace

    payload = b'{"ref": "refs/heads/main"}'
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/trigger/github",
        content=payload,
        headers={
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": f"sha256={signature}",
            "Content-Type": "application/json"
        }
    )

    # 200 means accepted/ignored, or triggered.
    # Since we didn't setup a project to match, it should be ignored or 200.
    # The endpoint returns a dict, so 200 is expected.
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"

def test_webhook_valid_signature_custom(mock_app_state):
    """Test that requests with valid signatures are accepted (Custom)."""
    secret = "my_secret"
    workspace = Workspace(name="test_ws")
    workspace.webhook_config = WebhookConfig(enabled=True, secret_key=secret)
    mock_app_state.get_current_workspace.return_value = workspace

    payload = b'{"some": "data"}'
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/trigger/custom",
        content=payload,
        headers={
            "X-Signature": signature
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "received"
