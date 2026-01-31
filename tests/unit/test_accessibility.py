import pytest
from textual.widgets import Label, Button
from agent_pump.tui.widgets.workflow_panel import WorkflowNode
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.orchestrator.workflow_definition import WorkflowPhase
from unittest.mock import MagicMock

class TestAccessibility:
    """Test suite for accessibility improvements."""
    
    def test_workflow_node_accessible_name(self):
        """Test WorkflowNode accessible name."""
        phase = WorkflowPhase(name="planning", icon="P", on_success="next_phase")
        node = WorkflowNode(phase)
        assert node.accessible_name == "Planning Phase: Pending"
        
        # Test generic node (string)
        node_idle = WorkflowNode("idle")
        assert node_idle.accessible_name == "Idle Phase: Pending"

    def test_project_card_accessible_name(self):
        """Test ProjectCard accessible name."""
        project = MagicMock(spec=Project)
        project.name = "Test Project"
        project.status = ProjectStatus.PLANNING
        project.state_changed_at = None
        project.current_feature = None
        project.completed_features = []
        project.failed_features = []
        project.iteration_count = 0
        project.config = MagicMock()
        project.config.build_cmd = None
        project.config.lint_cmd = None
        project.config.test_cmd = None
        project.config.skip_verification = False
        
        card = ProjectCard(project)
        assert card.accessible_name == "Project Test Project: planning"

    def test_log_panel_accessible_name(self):
        """Test LogPanel accessible name."""
        panel = LogPanel()
        # Mock scroll methods to avoid NoActiveAppError
        panel.scroll_home = MagicMock()
        panel.scroll_end = MagicMock()
        
        assert panel.accessible_name == "Activity Log Panel"
        
        # Test update with filter
        mock_path = MagicMock()
        mock_path.name = "MyProject"
        panel.set_filter(mock_path)
        assert panel.accessible_name == "Activity Log Panel: Project MyProject"
