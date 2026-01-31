from unittest.mock import MagicMock, patch
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workflow_snapshot import WorkflowSnapshot
from agent_pump.models.state import WorkflowState

class TestWorkflowSnapshot:
    """Tests for workflow snapshot generation."""

    def test_get_snapshot_idle(self):
        """Test snapshot in idle state."""
from pathlib import Path

class TestWorkflowSnapshot:
    """Tests for workflow snapshot generation."""

    def test_get_snapshot_idle(self):
        """Test snapshot in idle state."""
        project = MagicMock(spec=Project)
        project.name = "Test Project"
        project.path = Path("/tmp/project")
        project.config = MagicMock()
        
        # Mock workflow definition
        # Mock workflow definition
        workflow_def = MagicMock()
        phase1 = MagicMock()
        phase1.name = "planning"
        phase1.icon = "P"
        workflow_def.phases = [phase1]
        
        with patch("agent_pump.models.state.WorkflowState.load", return_value=None):
            workflow = ProjectWorkflow(project, workflow_def=workflow_def)
            # Mock state since machine is complex to setup fully in unit test without running it
            workflow.state = "idle"
            
            snapshot = workflow.get_snapshot()
            
            assert isinstance(snapshot, WorkflowSnapshot)
            assert snapshot.current_state == "idle"
            assert len(snapshot.nodes) == 3 # Idle, Planning, Completed
            
            # Check Idle node
            assert snapshot.nodes[0].id == "idle"
            assert snapshot.nodes[0].status == "active"
            
            # Check Planning node
            assert snapshot.nodes[1].id == "planning"
            assert snapshot.nodes[1].status == "pending"

    def test_get_snapshot_active(self):
        """Test snapshot in active phase."""
from pathlib import Path

class TestWorkflowSnapshot:
    """Tests for workflow snapshot generation."""

    def test_get_snapshot_idle(self):
        """Test snapshot in idle state."""
        project = MagicMock(spec=Project)
        project.name = "Test Project"
        project.path = Path("/tmp/project")
        project.config = MagicMock()
        
        # Mock workflow definition
        workflow_def = MagicMock()
        phase1 = MagicMock()
        phase1.name = "planning"
        phase1.icon = "P"
        workflow_def.phases = [phase1]
        
        with patch("agent_pump.models.state.WorkflowState.load", return_value=None):
            workflow = ProjectWorkflow(project, workflow_def=workflow_def)
            workflow.state = "planning"
            
            snapshot = workflow.get_snapshot()
            
            # Idle should be completed
            assert snapshot.nodes[0].id == "idle"
            assert snapshot.nodes[0].status == "completed"
            
            # Planning should be active
            assert snapshot.nodes[1].id == "planning"
            assert snapshot.nodes[1].status == "active"
            assert snapshot.nodes[1].is_active is True

    def test_get_snapshot_completed(self):
        """Test snapshot in completed state."""
from pathlib import Path

class TestWorkflowSnapshot:
    """Tests for workflow snapshot generation."""

    def test_get_snapshot_idle(self):
        """Test snapshot in idle state."""
        project = MagicMock(spec=Project)
        project.name = "Test Project"
        project.path = Path("/tmp/project")
        project.config = MagicMock()
        
        # Mock workflow definition
        workflow_def = MagicMock()
        phase1 = MagicMock()
        phase1.name = "planning"
        phase1.icon = "P"
        workflow_def.phases = [phase1]
        
        with patch("agent_pump.models.state.WorkflowState.load", return_value=None):
            workflow = ProjectWorkflow(project, workflow_def=workflow_def)
            workflow.state = "completed"
            
            snapshot = workflow.get_snapshot()
            
            # Planning should be completed
            assert snapshot.nodes[1].status == "completed"
            
            # Done node should be active/completed
            assert snapshot.nodes[2].id == "completed"
            assert snapshot.nodes[2].status == "active" # Based on logic in get_snapshot
