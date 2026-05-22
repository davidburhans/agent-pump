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

    def test_get_general_settings(self, client_setup):
        client, service, workspace, mock_save = client_setup
        workspace.notifications_enabled = True

        response = client.get("/settings/general")
        assert response.status_code == 200
        assert response.json()["notificationsEnabled"] is True

    def test_update_general_settings(self, client_setup):
        client, service, workspace, mock_save = client_setup
        workspace.notifications_enabled = True

        payload = {"notificationsEnabled": False}
        response = client.put("/settings/general", json=payload)
        assert response.status_code == 200
        assert response.json()["notificationsEnabled"] is False
        assert workspace.notifications_enabled is False
        mock_save.assert_called_once()

    @patch("agent_pump.utils.notifier.Notifier.test")
    def test_test_notification(self, mock_notifier_test, client_setup):
        client, _, _, _ = client_setup
        response = client.post("/settings/test-notification")
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_notifier_test.assert_called_once()

    def test_save_backend_preset(self, client_setup):
        client, service, workspace, mock_save = client_setup

        preset_payload = {
            "name": "MyCoolPreset",
            "backends": {
                "backends": [
                    {
                        "name": "gemini",
                        "args": ["--temp", "0.7"],
                        "timeout": 30,
                        "concurrencyLimit": 4,
                    }
                ]
            }
        }


        response = client.post("/settings/presets", json=preset_payload)
        assert response.status_code == 200
        assert response.json()["name"] == "MyCoolPreset"
        assert response.json()["backends"]["backends"][0]["name"] == "gemini"

        # Verify workspace has it
        assert "MyCoolPreset" in workspace.backend_presets
        preset = workspace.backend_presets["MyCoolPreset"]
        assert preset.name == "MyCoolPreset"
        assert preset.backends.backends[0].name == "gemini"
        assert preset.backends.backends[0].args == ["--temp", "0.7"]
        assert preset.backends.backends[0].timeout == 30
        assert preset.backends.backends[0].concurrency_limit == 4
        mock_save.assert_called_once()
