from unittest.mock import MagicMock

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workflow_snapshot import NodeSnapshot
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.workflow_panel import WorkflowNode


class TestAccessibility:
    """Test suite for accessibility improvements."""

    def test_workflow_node_accessible_name(self):
        """Test WorkflowNode accessible name."""
        snapshot = NodeSnapshot(id="planning", label="Planning", icon="P", status="pending")
        node = WorkflowNode(snapshot)
        assert node.accessible_name == "Planning Phase: Pending"

        # Test generic node (idle)
        snapshot_idle = NodeSnapshot(id="idle", label="Idle", icon="⏹", status="pending")
        node_idle = WorkflowNode(snapshot_idle)
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
