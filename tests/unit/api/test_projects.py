"""Tests for projects API routes."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from agent_pump.api.middleware.cors import get_cors_config
from agent_pump.api.routes.projects import normalize_path, router
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.services.project_service import ProjectService


def test_normalize_path_wsl():
    """Test normalizing WSL paths."""
    # Test standard WSL path
    path = normalize_path("mnt/c/Users/Dave/project")
    assert str(path).lower() == str(Path("C:/Users/Dave/project").resolve()).lower()

    # Test with double-encoded slashes
    path = normalize_path("mnt%2Fc%2FUsers%2FDave%2Fproject")
    assert str(path).lower() == str(Path("C:/Users/Dave/project").resolve()).lower()

    # Test with leading slashes
    path = normalize_path("///mnt/c/project")
    assert str(path).lower() == str(Path("C:/project").resolve()).lower()


def test_normalize_path_windows():
    """Test normalizing Windows paths."""
    path = normalize_path("c:/Users/Dave/project")
    assert str(path).lower() == str(Path("C:/Users/Dave/project").resolve()).lower()

    path = normalize_path("C:\\Users\\Dave\\project")
    assert str(path).lower() == str(Path("C:/Users/Dave/project").resolve()).lower()

    # Test fallback
    path = normalize_path("some/relative/path")
    assert str(path) == str(Path("some/relative/path").resolve())


@pytest.fixture
def client_setup():
    """Create a test client with mocked project service."""
    app = FastAPI()
    cors_config = get_cors_config()
    app.add_middleware(CORSMiddleware, **cors_config)
    app.include_router(router)

    service = MagicMock(spec=ProjectService)
    app.state.project_service = service

    wf_service = MagicMock()
    wf_service.start_project = AsyncMock()
    wf_service.stop_project = AsyncMock()
    wf_service.reset_project = AsyncMock()
    app.state.workflow_service = wf_service

    return TestClient(app), service


class TestProjectsAPI:
    """Tests for projects endpoints."""

    def test_list_projects(self, client_setup):
        client, service = client_setup

        project1 = Project(
            path=Path("/test/project1"), name="Project 1", status=ProjectStatus.IDLE
        )
        project2 = Project(
            path=Path("/test/project2"), name="Project 2", status=ProjectStatus.PLANNING
        )
        service.list_projects.return_value = [project1, project2]

        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["path"] == str(Path("/test/project1"))
        assert data[1]["path"] == str(Path("/test/project2"))
        assert data[1]["state"] == "planning"

    def test_get_project_workflow_success(self, client_setup):
        client, service = client_setup

        # Setup mock workflow
        test_path = Path("C:/test/project")

        # Use MagicMock without spec so we don't hit AttributeError for undefined attributes
        mock_workflow = MagicMock()
        mock_workflow.state = "planning"
        mock_workflow.project.state_changed_at = datetime.now()
        mock_workflow.machine.get_triggers.return_value = ["implement", "skip"]
        mock_workflow.workflow_def = None

        service.workflows = {test_path: mock_workflow}

        # Test exact match (double encoded for path params with slashes)
        encoded_path = "C:%252Ftest%252Fproject"
        response = client.get(f"/projects/{encoded_path}/workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["currentState"] == "planning"
        assert "implement" in data["availableTransitions"]

    def test_get_project_workflow_wsl_match(self, client_setup):
        client, service = client_setup

        # Setup mock workflow with Windows path
        test_path = Path("C:/test/project")

        mock_workflow = MagicMock()
        mock_workflow.state = "implementing"
        mock_workflow.project.state_changed_at = None
        mock_workflow.machine.get_triggers.return_value = []
        mock_workflow.workflow_def = None

        service.workflows = {test_path: mock_workflow}

        # Test WSL path
        encoded_path = "mnt%252Fc%252Ftest%252Fproject"
        response = client.get(f"/projects/{encoded_path}/workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["currentState"] == "implementing"

    def test_get_project_workflow_not_found(self, client_setup):
        client, service = client_setup

        service.workflows = {}

        response = client.get("/projects/unknown%252Fpath/workflow")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_start_project_success(self, client_setup):
        client, service = client_setup
        wf_service = client.app.state.workflow_service

        test_path = Path("C:/test/project")
        service.workflows = {test_path: MagicMock()}
        wf_service.start_project.return_value = True

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "started" in data["message"]
        wf_service.start_project.assert_called_once_with(test_path)

    def test_start_project_failed(self, client_setup):
        client, service = client_setup
        wf_service = client.app.state.workflow_service

        test_path = Path("C:/test/project")
        service.workflows = {test_path: MagicMock()}
        wf_service.start_project.return_value = False

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "failed" in data["message"].lower()

    def test_stop_project_success(self, client_setup):
        client, service = client_setup
        wf_service = client.app.state.workflow_service

        test_path = Path("C:/test/project")
        service.workflows = {test_path: MagicMock()}
        wf_service.stop_project.return_value = True

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stopped" in data["message"]
        wf_service.stop_project.assert_called_once_with(test_path)

    def test_reset_project_success(self, client_setup):
        client, service = client_setup
        wf_service = client.app.state.workflow_service

        test_path = Path("C:/test/project")
        service.workflows = {test_path: MagicMock()}
        wf_service.reset_project.return_value = True

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "reset" in data["message"]
        wf_service.reset_project.assert_called_once_with(test_path)

    def test_skip_project_feature_success(self, client_setup):
        client, service = client_setup

        test_path = Path("C:/test/project")
        mock_workflow = MagicMock()
        mock_workflow.project.current_feature = "My Feature"
        mock_workflow.project.failed_features = []
        mock_workflow.is_running.return_value = True
        mock_workflow.on_state_change = MagicMock()
        service.workflows = {test_path: mock_workflow}

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/skip")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "skipped" in data["message"]

        assert mock_workflow.project.current_feature is None
        assert "My Feature" in mock_workflow.project.failed_features
        mock_workflow.cancel.assert_called_once()
        mock_workflow.on_state_change.assert_called_once()

    def test_skip_project_feature_no_active_feature(self, client_setup):
        client, service = client_setup

        test_path = Path("C:/test/project")
        mock_workflow = MagicMock()
        mock_workflow.project.current_feature = None
        service.workflows = {test_path: mock_workflow}

        encoded_path = "C:%252Ftest%252Fproject"
        response = client.post(f"/projects/{encoded_path}/skip")
        assert response.status_code == 400
        assert "no feature in progress" in response.json()["detail"].lower()

