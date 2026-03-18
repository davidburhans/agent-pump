from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.state import WorkflowState
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.orchestrator.workflow_definition import DEFAULT_WORKFLOW


@pytest.fixture
def mock_project():
    project = MagicMock(spec=Project)
    project.path = Path("/tmp/test")
    project.name = "test-project"
    project.current_feature = "test-feature"
    project.completed_features = []
    project.failed_features = []
    project.min_execution_time_seconds = 0
    project.config = MagicMock()
    project.status = ProjectStatus.IDLE
    return project


@pytest.fixture
def workflow(mock_project):
    with patch("agent_pump.models.state.WorkflowState.load", return_value=None):
        with patch("agent_pump.models.state.WorkflowState.save"):
            wf = ProjectWorkflow(project=mock_project, workflow_def=DEFAULT_WORKFLOW)
            # Create fresh state
            wf.workflow_state = WorkflowState(project_path=mock_project.path)
            yield wf


@pytest.mark.asyncio
async def test_failure_transition_to_troubleshooting(workflow):
    """Test that failure in a phase transitions to troubleshooting."""
    # Set initial state
    workflow.machine.set_state("planning")
    workflow.workflow_state.current_state = "planning"

    # Check that 'planning_failed' trigger leads to 'troubleshooting'
    workflow.planning_failed()

    assert workflow.state == "troubleshooting"
    assert workflow.project.status == ProjectStatus.TROUBLESHOOTING


@pytest.mark.asyncio
async def test_retry_last_phase(workflow):
    """Test that retry_last_phase transitions back to the failed phase."""
    # Setup troubleshooting state
    workflow.machine.set_state("troubleshooting")
    workflow.workflow_state.current_state = "troubleshooting"
    workflow.workflow_state.last_failed_phase = "planning"
    workflow.workflow_state.last_error = "Some error"

    workflow.retry_last_phase()

    assert workflow.state == "planning"
    assert workflow.workflow_state.last_error is None
    assert workflow.workflow_state.last_failed_phase is None
