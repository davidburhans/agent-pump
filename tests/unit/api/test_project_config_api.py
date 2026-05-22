"""Unit tests for the project configuration and backend configuration API endpoints."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from agent_pump.api.middleware.cors import get_cors_config
from agent_pump.api.routes.projects import router
from agent_pump.config import Config
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    PhaseBackends,
)
from agent_pump.models.workspace import (
    ProjectConfig as WorkspaceProjectConfig,
)
from agent_pump.services.project_service import ProjectService


@pytest.fixture
def client_setup():
    """Set up fastapi test client and mock services."""
    app = FastAPI()
    cors_config = get_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)
    app.include_router(router)

    # Mock ProjectService
    project_service = MagicMock(spec=ProjectService)
    project_service.projects = {}
    project_service.workflows = {}

    # Mock Workspace
    workspace = MagicMock()
    workspace.backend_presets = {}
    workspace.projects = {}
    project_service.workspace = workspace

    app.state.project_service = project_service

    return TestClient(app), project_service, workspace


class TestProjectConfigAPI:
    """Tests for project configuration API endpoints."""

    @patch("agent_pump.config.Config.load")
    def test_get_project_config(self, mock_config_load, client_setup):
        client, _, _ = client_setup

        # Set up mock config
        mock_config = Config()
        mock_config.backend = "claude"
        mock_config.workflow.max_iterations = 25
        mock_config.workflow.timeout = 3600
        mock_config.workflow.branch = "feature-custom"
        mock_config.verification.build_cmd = "npm run build"
        mock_config.verification.lint_cmd = "npm run lint"
        mock_config.verification.test_cmd = "npm test"
        mock_config.verification.coverage_cmd = "npm run cov"
        mock_config.verification.coverage_threshold = 85.0
        mock_config.verification.skip_verification = False
        mock_config.verification.sandbox_image = "node:20"

        mock_config_load.return_value = mock_config

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.get(f"/projects/{encoded_path}/config")
        assert response.status_code == 200

        data = response.json()
        assert data["backend"] == "claude"
        assert data["workflow"]["maxIterations"] == 25
        assert data["workflow"]["timeout"] == 3600
        assert data["workflow"]["branch"] == "feature-custom"
        assert data["verification"]["buildCmd"] == "npm run build"
        assert data["verification"]["lintCmd"] == "npm run lint"
        assert data["verification"]["testCmd"] == "npm test"
        assert data["verification"]["coverageCmd"] == "npm run cov"
        assert data["verification"]["coverageThreshold"] == 85.0
        assert data["verification"]["skipVerification"] is False
        assert data["verification"]["sandboxImage"] == "node:20"

        mock_config_load.assert_called_once_with(Path("C:/test/project").resolve())

    @patch("agent_pump.config.Config.load")
    @patch("agent_pump.config.Config.save")
    def test_update_project_config(self, mock_config_save, mock_config_load, client_setup):
        client, project_service, _ = client_setup

        # Setup mock project and workflow
        project_path = Path("C:/test/project").resolve()
        mock_project = Project(path=project_path, name="Test Project", status=ProjectStatus.IDLE)
        project_service.projects = {project_path: mock_project}

        mock_workflow = MagicMock()
        project_service.workflows = {project_path: mock_workflow}

        mock_config = Config()
        mock_config_load.return_value = mock_config

        update_payload = {
            "backend": "gemini",
            "workflow": {
                "maxIterations": 12,
                "timeout": 2000,
                "branch": "main",
            },
            "verification": {
                "buildCmd": "cargo build",
                "lintCmd": "cargo clippy",
                "testCmd": "cargo test",
                "coverageCmd": None,
                "coverageThreshold": 90.0,
                "skipVerification": True,
                "sandboxImage": None,
            },
        }

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.put(f"/projects/{encoded_path}/config", json=update_payload)
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify config updates
        assert mock_config.backend == "gemini"
        assert mock_config.workflow.max_iterations == 12
        assert mock_config.workflow.timeout == 2000
        assert mock_config.workflow.branch == "main"
        assert mock_config.verification.build_cmd == "cargo build"
        assert mock_config.verification.lint_cmd == "cargo clippy"
        assert mock_config.verification.test_cmd == "cargo test"
        assert mock_config.verification.coverage_cmd is None
        assert mock_config.verification.coverage_threshold == 90.0
        assert mock_config.verification.skip_verification is True
        assert mock_config.verification.sandbox_image is None

        # Verify mock save was called
        mock_config_save.assert_called_once()

        # Verify in-memory project was updated
        assert mock_project.backend == "gemini"
        assert mock_project.branch == "main"
        assert mock_project.config.skip_verification is True

        # Verify in-memory workflow was updated
        assert mock_workflow.config == mock_config

    def test_get_project_backends(self, client_setup):
        client, _, workspace = client_setup

        project_path = Path("C:/test/project").resolve()
        project_config = WorkspaceProjectConfig(path=project_path)
        project_config.default_chain = BackendFallback(
            backends=[
                BackendInstance(name="gemini", args=["--temp", "0.2"]),
                BackendInstance(name="claude", timeout=120),
            ]
        )
        project_config.phase_backends = PhaseBackends(
            defaults=BackendFallback(backends=[]),
            planning=BackendFallback(backends=[BackendInstance(name="opencode")]),
            implementing=BackendFallback(backends=[]),
            verifying=BackendFallback(backends=[]),
            brainstorming=BackendFallback(backends=[]),
            committing=BackendFallback(backends=[]),
        )

        workspace.get_project_config.return_value = project_config

        # Add a mock preset
        mock_preset = MagicMock()
        mock_preset.name = "StrongPreset"
        mock_preset.backends = BackendFallback(backends=[BackendInstance(name="gemini-heavy")])
        workspace.backend_presets = {"StrongPreset": mock_preset}

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.get(f"/projects/{encoded_path}/backends")
        assert response.status_code == 200

        data = response.json()

        # Check default chain
        assert len(data["defaultChain"]["backends"]) == 2
        assert data["defaultChain"]["backends"][0]["name"] == "gemini"
        assert data["defaultChain"]["backends"][0]["args"] == ["--temp", "0.2"]
        assert data["defaultChain"]["backends"][1]["name"] == "claude"
        assert data["defaultChain"]["backends"][1]["timeout"] == 120

        # Check phase specific backends
        assert data["phaseBackends"]["planning"]["backends"][0]["name"] == "opencode"
        assert len(data["phaseBackends"]["implementing"]["backends"]) == 0

        # Check presets
        assert len(data["presets"]) == 1
        assert data["presets"][0]["name"] == "StrongPreset"
        assert data["presets"][0]["backends"]["backends"][0]["name"] == "gemini-heavy"

    def test_update_project_backends(self, client_setup):
        client, project_service, workspace = client_setup

        project_path = Path("C:/test/project").resolve()
        project_config = WorkspaceProjectConfig(path=project_path)
        workspace.get_project_config.return_value = project_config

        mock_workflow = MagicMock()
        project_service.workflows = {project_path: mock_workflow}

        payload = {
            "defaultChain": {
                "backends": [
                    {"name": "claude", "args": [], "timeout": 300, "concurrencyLimit": 2}
                ]
            },
            "phaseBackends": {
                "defaults": {"backends": []},
                "planning": {
                    "backends": [
                        {"name": "gemini", "args": [], "timeout": None, "concurrencyLimit": 1}
                    ]
                },
                "implementing": {"backends": []},
                "verifying": {"backends": []},
                "brainstorming": {"backends": []},
                "committing": {"backends": []},
            },
        }

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.put(f"/projects/{encoded_path}/backends", json=payload)
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify saved model structure
        assert len(project_config.default_chain.backends) == 1
        assert project_config.default_chain.backends[0].name == "claude"
        assert project_config.default_chain.backends[0].timeout == 300
        assert project_config.default_chain.backends[0].concurrency_limit == 2

        assert len(project_config.phase_backends.planning.backends) == 1
        assert project_config.phase_backends.planning.backends[0].name == "gemini"

        # Verify workspace save was called
        workspace.save.assert_called_once()

        # Verify in-memory workflow was updated
        assert mock_workflow.phase_backends == project_config.phase_backends
        assert mock_workflow.project_config == project_config
