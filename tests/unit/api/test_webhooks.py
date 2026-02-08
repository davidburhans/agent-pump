"""Unit tests for webhook routes."""

import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agent_pump.api.server import app
from agent_pump.models.project import ProjectStatus
from agent_pump.models.webhook_config import WebhookConfig
from agent_pump.models.workspace import ProjectConfig, Workspace

client = TestClient(app)

@pytest.fixture
def mock_app_state():
    """Mock app state with services."""
    app.state.workspace_service = MagicMock()
    app.state.project_service = MagicMock()

    # Default workspace with enabled webhooks
    workspace = Workspace(name="test")
    workspace.webhook_config = WebhookConfig(enabled=True, secret_key="secret")
    app.state.workspace_service.get_current_workspace.return_value = workspace

    return app.state

def generate_github_signature(secret: str, body: bytes) -> str:
    """Generate GitHub signature."""
    sha = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sha}"

def generate_slack_signature(secret: str, timestamp: str, body: bytes) -> str:
    """Generate Slack signature."""
    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    sha = hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    return f"v0={sha}"

def test_webhook_disabled(mock_app_state):
    """Test webhook disabled."""
    mock_app_state.workspace_service.get_current_workspace().webhook_config.enabled = False
    response = client.post("/api/trigger/github", json={})
    assert response.status_code == 503
    assert response.json()["detail"] == "Webhooks disabled"

def test_webhook_invalid_source(mock_app_state):
    """Test invalid source."""
    response = client.post("/api/trigger/invalid", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "Source not allowed"

def test_github_webhook_invalid_signature(mock_app_state):
    """Test GitHub webhook with invalid signature."""
    payload = {"foo": "bar"}
    headers = {
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": "sha256=invalid"
    }
    response = client.post("/api/trigger/github", json=payload, headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid GitHub signature"

def test_github_webhook_valid_signature_ignored_branch(mock_app_state):
    """Test GitHub webhook valid signature but ignored branch."""
    payload = {"ref": "refs/heads/feature", "repository": {"full_name": "owner/repo"}}
    body = json.dumps(payload).encode()
    signature = generate_github_signature("secret", body)

    headers = {
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": signature
    }

    response = client.post("/api/trigger/github", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert "not in auto_trigger_branches" in response.json()["reason"]

def test_github_webhook_success(mock_app_state):
    """Test GitHub webhook success trigger."""
    # Setup project config
    workspace = mock_app_state.workspace_service.get_current_workspace()
    proj_config = ProjectConfig(path=Path("/tmp/proj"))
    proj_config.github_integration.owner = "owner"
    proj_config.github_integration.repo = "repo"
    workspace.projects["/tmp/proj"] = proj_config

    # Setup payload
    payload = {"ref": "refs/heads/main", "repository": {"full_name": "owner/repo"}}
    body = json.dumps(payload).encode()
    signature = generate_github_signature("secret", body)

    headers = {
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": signature
    }

    with patch("agent_pump.api.routes.webhooks.start_workflow_task") as mock_task:
        # We patch the task function because BackgroundTasks doesn't run immediately in TestClient sometimes?
        # Actually TestClient runs BackgroundTasks after request.
        # But mocking add_task logic is harder without integration.
        # Wait, if we use TestClient, we can inspect background_tasks?
        # Or easier: patch background_tasks.add_task inside the route? No, that's passed as arg.
        # Patching `start_workflow_task` is better as we can verify it was called.
        pass

    # Since start_workflow_task is async, we can't easily mock it as sync function if called by BackgroundTasks?
    # BackgroundTasks expects async or sync.
    # We'll just rely on mocking `ProjectService.add_project` and `ProjectService.workflows`.

    mock_app_state.project_service.add_project = AsyncMock()
    mock_workflow = MagicMock()
    mock_workflow.is_running.return_value = False
    mock_workflow.project.status = ProjectStatus.IDLE
    mock_workflow.run = AsyncMock()
    mock_app_state.project_service.workflows = {Path("/tmp/proj"): mock_workflow}

    # IMPORTANT: background tasks execution in tests requires explicit handling or just asserting the response logic
    # TestClient DOES execute background tasks.

    response = client.post("/api/trigger/github", content=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "triggered"
    assert response.json()["project"] == str(Path("/tmp/proj"))

    # Since TestClient runs background tasks, we should verify calls
    mock_app_state.project_service.add_project.assert_called_with(Path("/tmp/proj"))
    mock_workflow.run.assert_called_once()

def test_slack_webhook_success(mock_app_state):
    """Test Slack webhook success."""
    # Setup project config
    workspace = mock_app_state.workspace_service.get_current_workspace()
    proj_config = ProjectConfig(path=Path("/tmp/proj"), name="myproj")
    workspace.projects["/tmp/proj"] = proj_config

    # Setup payload (form data)
    form_data = {"command": "/agent-pump", "text": "start myproj"}
    # Manually construct body for signature (URL encoded form)
    from urllib.parse import urlencode
    body = urlencode(form_data).encode()

    timestamp = "1234567890"
    signature = generate_slack_signature("secret", timestamp, body)

    headers = {
        "X-Slack-Signature": signature,
        "X-Slack-Request-Timestamp": timestamp,
        "Content-Type": "application/x-www-form-urlencoded"
    }

    mock_app_state.project_service.add_project = AsyncMock()
    mock_workflow = MagicMock()
    mock_workflow.is_running.return_value = False
    mock_workflow.run = AsyncMock()
    mock_app_state.project_service.workflows = {Path("/tmp/proj"): mock_workflow}

    # Send raw body to ensure signature matches
    response = client.post("/api/trigger/slack", content=body, headers=headers)
    assert response.status_code == 200
    assert "Triggered workflow for project 'myproj'" in response.json()["text"]

    mock_app_state.project_service.add_project.assert_called_with(Path("/tmp/proj"))
    mock_workflow.run.assert_called_once()
