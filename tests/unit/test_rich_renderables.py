from unittest.mock import MagicMock

from rich.panel import Panel
from rich.text import Text

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.tui.screens.project_summary_modal import ProjectSummaryModal
from agent_pump.tui.widgets.log_panel import LogPanel


class TestRichRenderables:
    """Test suite for rich renderable enhancements."""

    def test_log_panel_write_text(self):
        """Test writing simple text to LogPanel."""
        panel = LogPanel()
        panel.scroll_home = MagicMock()
        panel.scroll_end = MagicMock()

        panel.write("Hello World")

        assert len(panel.log_entries) == 1
        entry = panel.log_entries[0]
        assert entry.message == "Hello World"
        assert isinstance(entry.renderable, Text)
        # Check timestamp prefix
        assert "Hello World" in str(entry.renderable)

    def test_log_panel_write_panel_wrapping(self):
        """Test that specific messages are wrapped in Panels."""
        panel = LogPanel()
        panel.scroll_home = MagicMock()
        panel.scroll_end = MagicMock()

        # Phase start
        panel.write("Starting planning phase...")
        entry = panel.log_entries[0]
        assert isinstance(entry.renderable, Panel)
        assert entry.renderable.style == "blue"

        # Error
        panel.write("[ERROR] Something went wrong")
        entry = panel.log_entries[1]
        assert isinstance(entry.renderable, Panel)
        assert entry.renderable.style == "red"

    def test_project_summary_modal(self):
        """Test ProjectSummaryModal composition."""
        project = MagicMock(spec=Project)
        project.name = "Test Project"
        project.status = ProjectStatus.IDLE
        project.current_feature = None
        project.completed_features = ["Feature A"]
        project.failed_features = []
        project.iteration_count = 5
        project.backend = "gemini"
        project.branch = "main"

        modal = ProjectSummaryModal(project)
        # We can't easily test the visual output of the table without running the app,
        # but we can ensure it initializes without error.
        assert modal.project == project
