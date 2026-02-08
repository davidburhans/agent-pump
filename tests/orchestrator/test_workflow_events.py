import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from agent_pump.models.project import Project
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.events.bus import EventBus
from agent_pump.events.models import WorkflowCompletedEvent, WorkflowFailedEvent
import asyncio

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
    return project

@pytest.fixture
def event_bus():
    bus = MagicMock(spec=EventBus)
    bus.publish = AsyncMock()
    return bus

@pytest.fixture
def workflow(mock_project, event_bus):
    # Mock WorkflowState.load to return None so it creates fresh state
    with patch("agent_pump.models.state.WorkflowState.load", return_value=None):
        with patch("agent_pump.models.state.WorkflowState.save"):
            wf = ProjectWorkflow(project=mock_project, event_bus=event_bus)
            yield wf

@pytest.mark.asyncio
async def test_emit_completed_event(workflow, event_bus):
    # Manually trigger state change logic
    # We need to mock 'state' attribute which transitions usually handles
    workflow.state = "completed"

    # We also need to set workflow_state.current_state as _after_state_change reads it as old_state
    workflow.workflow_state.current_state = "committing"

    workflow._after_state_change()

    # Wait for async tasks to complete
    if workflow._pending_publish_tasks:
        await asyncio.gather(*workflow._pending_publish_tasks)

    calls = event_bus.publish.call_args_list
    completed_event_emitted = False
    for call in calls:
        event = call[0][0]
        if isinstance(event, WorkflowCompletedEvent):
            completed_event_emitted = True
            assert event.project_name == "test-project"
            assert event.feature_name == "test-feature"

    assert completed_event_emitted

@pytest.mark.asyncio
async def test_emit_failed_event(workflow, event_bus):
    workflow.state = "error"
    workflow.workflow_state.current_state = "implementing"

    workflow._after_state_change()

    # Wait for async tasks to complete
    if workflow._pending_publish_tasks:
        await asyncio.gather(*workflow._pending_publish_tasks)

    calls = event_bus.publish.call_args_list
    failed_event_emitted = False
    for call in calls:
        event = call[0][0]
        if isinstance(event, WorkflowFailedEvent):
            failed_event_emitted = True
            assert event.project_name == "test-project"
            assert event.error == "Workflow entered error state"

    assert failed_event_emitted
