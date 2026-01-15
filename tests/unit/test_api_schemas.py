"""Unit tests for API schemas."""

from unittest.mock import MagicMock
from pathlib import Path
from datetime import datetime

import pytest
from pydantic import ValidationError

from agent_pump.api.schemas import (
    ProjectStatusDTO,
    WorkflowStateDTO,
    LogEntryDTO,
    NodeSnapshot,
    EdgeSnapshot,
    BackendConfigDTO,
)

# Mock internal models
class MockProject:
    def __init__(self, name="Test", path="/tmp/test", status="planning"):
        self.name = name
        self.path = Path(path)
        self.status = status
        self.current_feature = "Feature A"
        self.current_activity = "Coding"
        self.iteration_count = 5
        self.state_changed_at = datetime.now()

class MockWorkflow:
    def __init__(self, project=None, state="idle"):
        self.project = project or MockProject()
        self.state = state
        self.machine = MagicMock()
        self.machine.get_triggers.return_value = ["plan", "stop"]

class MockLogEntry:
    def __init__(self, message="test"):
        self.timestamp = "12:00:00"
        self.message = message
        self.project_path = Path("/tmp/test")
        self.state = "idle"
        self.task = "Running"

def test_project_status_dto_creation():
    """Test basic creation."""
    dto = ProjectStatusDTO(
        name="Test",
        path=Path("/tmp"),
        state="idle",
        iteration=1
    )
    assert dto.name == "Test"
    assert dto.state == "idle"

def test_project_status_from_internal():
    """Test conversion from internal model."""
    project = MockProject()
    dto = ProjectStatusDTO.from_internal(project)

    assert dto.name == "Test"
    assert dto.state == "planning"
    assert dto.current_feature == "Feature A"
    assert dto.time_in_state >= 0.0

def test_workflow_state_dto_structure():
    """Test workflow state structure."""
    dto = WorkflowStateDTO(
        current_state="planning",
        available_transitions=["next", "prev"],
        nodes=[
            NodeSnapshot(name="A", is_active=True, position=(0,0))
        ],
        edges=[
            EdgeSnapshot(source="A", target="B")
        ]
    )
    assert len(dto.nodes) == 1
    assert len(dto.edges) == 1
    assert dto.nodes[0].name == "A"

def test_workflow_state_from_internal():
    """Test conversion from internal workflow."""
    workflow = MockWorkflow()
    dto = WorkflowStateDTO.from_internal(workflow)

    assert dto.current_state == "idle"
    assert "plan" in dto.available_transitions
    # Nodes/edges are empty placeholders for now
    assert isinstance(dto.nodes, list)

def test_log_entry_level_inference():
    """Test log level inference."""
    entry = MockLogEntry(message="[ERROR] critical failure")
    dto = LogEntryDTO.from_internal(entry)
    assert dto.level == "ERROR"

    entry_warn = MockLogEntry(message="Just a warning")
    dto_warn = LogEntryDTO.from_internal(entry_warn)
    assert dto_warn.level == "WARNING"

    entry_info = MockLogEntry(message="Normal info")
    dto_info = LogEntryDTO.from_internal(entry_info)
    assert dto_info.level == "INFO"

def test_serialization_camel_case():
    """Test that models serialize to camelCase."""
    dto = ProjectStatusDTO(
        name="Test",
        path=Path("/tmp"),
        state="idle",
        time_in_state=10.5
    )
    data = dto.model_dump(by_alias=True)
    assert "timeInState" in data
    assert "currentFeature" in data
