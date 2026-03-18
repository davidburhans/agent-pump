"""Unit tests for API schemas."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from agent_pump.api.schemas import (
    EdgeSnapshot,
    LogEntryDTO,
    NodeSnapshot,
    ProjectStatusDTO,
    WorkflowStateDTO,
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


class MockPhase:
    def __init__(self, name):
        self.name = name
        self.on_success = "next"
        self.on_failure = "error"


class MockWorkflowDefinition:
    def __init__(self):
        self.phases = [MockPhase("planning"), MockPhase("implementing")]
        self.initial_state = "idle"
        self.terminal_states = ["completed", "error"]

    def get_states(self):
        return ["idle", "planning", "implementing", "completed", "error"]

    def get_transitions(self):
        return [
            {"source": "idle", "dest": "planning", "trigger": "start"},
            {"source": "planning", "dest": "implementing", "trigger": "planning_complete"},
        ]


class MockWorkflow:
    def __init__(self, project=None, state="idle"):
        self.project = project or MockProject()
        self.state = state
        self.machine = MagicMock()
        self.machine.get_triggers.return_value = ["plan", "stop"]
        self.workflow_def = MockWorkflowDefinition()


class MockLogEntry:
    def __init__(self, message="test"):
        self.timestamp = "12:00:00"
        self.message = message
        self.project_path = Path("/tmp/test")
        self.state = "idle"
        self.task = "Running"


def test_project_status_dto_creation():
    """Test basic creation."""
    dto = ProjectStatusDTO(name="Test", path=Path("/tmp"), state="idle", iteration=1)
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
        nodes=[NodeSnapshot(name="A", is_active=True, position=(0, 0))],
        edges=[EdgeSnapshot(source="A", target="B")],
    )
    assert len(dto.nodes) == 1
    assert len(dto.edges) == 1
    assert dto.nodes[0].name == "A"


def test_workflow_state_from_internal():
    """Test conversion from internal workflow."""
    workflow = MockWorkflow(state="planning")
    dto = WorkflowStateDTO.from_internal(workflow)

    assert dto.current_state == "planning"
    assert "plan" in dto.available_transitions

    # Verify nodes
    assert len(dto.nodes) > 0
    node_names = [n.name for n in dto.nodes]
    assert "idle" in node_names
    assert "planning" in node_names
    assert "implementing" in node_names
    assert "completed" in node_names

    # Check active state
    active_node = next(n for n in dto.nodes if n.is_active)
    assert active_node.name == "planning"

    # Check completed state (idle should be completed as we are in planning)
    idle_node = next(n for n in dto.nodes if n.name == "idle")
    assert idle_node.is_completed

    # Verify edges
    assert len(dto.edges) > 0
    sources = [e.source for e in dto.edges]
    assert "idle" in sources
    assert "planning" in sources


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
    dto = ProjectStatusDTO(name="Test", path=Path("/tmp"), state="idle", time_in_state=10.5)
    data = dto.model_dump(by_alias=True)
    assert "timeInState" in data
    assert "currentFeature" in data
