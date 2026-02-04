from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.backends.base import AgentBackend
from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    PhaseBackends,
    ProjectConfig,
    Workspace,
)
from agent_pump.orchestrator.workflow import ProjectWorkflow


@pytest.fixture
def mock_workspace():
    """Mock workspace with just enough config."""
    ws = MagicMock(spec=Workspace)
    ws.backend_presets = {}
    return ws


@pytest.fixture
def project_config():
    """Basic project config."""
    return ProjectConfig(
        path=Path("/tmp/test"),
        name="Test Project",
        phase_backends=PhaseBackends(),
    )


@pytest.fixture
def mock_project():
    """Mock Project object."""
    proj = MagicMock()
    proj.path = Path("/tmp/test")
    proj.name = "Test Project"
    return proj


def test_fallback_project_default(mock_workspace, project_config, mock_project):
    """Test that project default chain is used when phase config is missing."""
    # Setup project default chain
    default_backend = BackendInstance(
        name="qwen", args=["--model", "qwen-2.5-coder"], concurrency_limit=0
    )
    project_config.default_chain = BackendFallback(backends=[default_backend])

    # Ensure phase backend is empty for planning
    project_config.phase_backends.planning = BackendFallback(backends=[])

    # Pass project_config explicitly
    workflow = ProjectWorkflow(mock_project, mock_workspace, project_config=project_config)

    # This should return a runner configured for qwen
    # We need to mock get_backend to verify
    with patch("agent_pump.orchestrator.workflow.get_backend") as mock_get_backend:
        mock_backend = MagicMock()
        mock_get_backend.return_value = mock_backend

        result = workflow._get_backend_for_phase("planning")

        mock_get_backend.assert_called_with("qwen")
        assert result == mock_backend
        assert cast(AgentBackend, result)._extra_args == ["--model", "qwen-2.5-coder"]


@patch("agent_pump.orchestrator.workflow.get_backend")


def test_get_backend_for_phase_logic(


    mock_get_backend, mock_workspace, project_config, mock_project


):


    """Detailed logic test."""


    workflow = ProjectWorkflow(mock_project, mock_workspace, project_config=project_config)





    # 1. Test Fallback to Project Default


    # Setup default chain


    default_inst = BackendInstance(


        name="default_backend", args=["--arg1"], concurrency_limit=0


    )


    project_config.default_chain = BackendFallback(backends=[default_inst])


    # Empty phase


    project_config.phase_backends.planning = BackendFallback(backends=[])





    mock_backend = MagicMock()


    mock_get_backend.return_value = mock_backend





    # Act


    result = workflow._get_backend_for_phase("planning")





    # Assert


    mock_get_backend.assert_called_with("default_backend")


    assert result == mock_backend


    assert cast(Any, result)._extra_args == ["--arg1"]





    # 2. Test Phase Override


    # Setup phase specific


    phase_inst = BackendInstance(name="phase_backend", args=["--arg2"], concurrency_limit=0)


    project_config.phase_backends.implementing = BackendFallback(backends=[phase_inst])





    # Act


    result = workflow._get_backend_for_phase("implementing")





    # Assert


    mock_get_backend.assert_called_with("phase_backend")


    assert cast(Any, result)._extra_args == ["--arg2"]





    # 3. Test Fallback to Hard Defaults (if project default is None)


    project_config.default_chain = None


    project_config.phase_backends.verifying = BackendFallback(backends=[])





    result = workflow._get_backend_for_phase("verifying")


    assert (


        result == workflow.backend


    )  # Should be the default Gemini backend of the workflow instance
