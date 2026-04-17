"""Tests for settings API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from agent_pump.api.middleware.cors import get_cors_config
from agent_pump.api.routes.settings import router
from agent_pump.models.workspace import ModelCatalog, Workspace
from agent_pump.services.workspace_service import WorkspaceService


@pytest.fixture
def client_setup():
    """Create a test client with mocked workspace service."""
    app = FastAPI()
    cors_config = get_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)
    app.include_router(router)

    # Create a proper mock workspace service
    service = MagicMock(spec=WorkspaceService)

    workspace = Workspace(name="test_workspace")
    workspace.model_catalog = ModelCatalog(backends={"openai": ["gpt-4", "gpt-3.5-turbo"]})

    service.get_current_workspace.return_value = workspace
    app.state.workspace_service = service

    with patch('agent_pump.models.workspace.Workspace.save') as mock_save:
        yield TestClient(app), service, workspace, mock_save


class TestSettingsAPI:
    """Tests for settings endpoints."""

    def test_get_model_catalog(self, client_setup):
        client, service, workspace, mock_save = client_setup

        response = client.get("/settings/model-catalog")
        assert response.status_code == 200

        data = response.json()
        assert "backends" in data
        assert "openai" in data["backends"]
        assert len(data["backends"]["openai"]) == 2
        assert "gpt-4" in data["backends"]["openai"]

    def test_update_model_catalog(self, client_setup):
        client, service, workspace, mock_save = client_setup

        update_data = {
            "backends": {
                "anthropic": ["claude-3.5-sonnet", "claude-3-opus"]
            }
        }

        response = client.put("/settings/model-catalog", json=update_data)
        assert response.status_code == 200

        data = response.json()
        assert "backends" in data
        assert "anthropic" in data["backends"]
        assert "openai" not in data["backends"]

        # Verify workspace was updated and saved
        assert "anthropic" in workspace.model_catalog.backends
        mock_save.assert_called_once()
