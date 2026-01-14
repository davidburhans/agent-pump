from pathlib import Path

import pytest

from agent_pump.config import Config, WorkflowConfig
from agent_pump.models.workspace import BackendInstance, IdeaQueueItem, ProjectConfig


def test_backend_instance_timeout():
    """Test BackendInstance timeout field."""
    # Default is None
    b = BackendInstance(name="gemini")
    assert b.timeout is None

    # explicit value
    b2 = BackendInstance(name="gemini", timeout=300)
    assert b2.timeout == 300

    # serialization
    data = b2.model_dump()
    assert data["timeout"] == 300

    # deserialization
    b3 = BackendInstance.model_validate(data)
    assert b3.timeout == 300


def test_workflow_config_default_timeout():
    """Test default timeout is updated to 1800."""
    wc = WorkflowConfig()
    assert wc.timeout == 1800


def test_project_config_idea_queue():
    """Test ProjectConfig idea queue."""
    pc = ProjectConfig(path=Path("/tmp/test"))
    assert pc.idea_queue == []

    item = IdeaQueueItem(idea="test idea")
    pc.idea_queue.append(item)

    assert len(pc.idea_queue) == 1
    assert pc.idea_queue[0].idea == "test idea"

    # Serialization round trip
    data = pc.model_dump()
    pc2 = ProjectConfig.model_validate(data)
    assert len(pc2.idea_queue) == 1
    assert pc2.idea_queue[0].idea == "test idea"


@pytest.mark.asyncio
async def test_workflow_initialization_with_config():
    """Test ProjectWorkflow receives config."""
    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow

    project = Project(path=Path("/tmp/test"), name="test")
    config = Config(workflow=WorkflowConfig(timeout=999))

    wf = ProjectWorkflow(project=project, config=config)
    assert wf.config is not None
    assert wf.config.workflow.timeout == 999

    # Verify run_phase picks up the timeout (mocking backend)
    # This involves mocking _get_backend_for_phase and the backend itself
    # which is strictly unit testing verify what we changed.
