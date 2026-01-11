"""Workflow panel widget for displaying workflow diagrams."""

import logging

from rich.text import Text
from textual.widgets import Static

from agent_pump.orchestrator.workflow import ProjectWorkflow

logger = logging.getLogger(__name__)


class WorkflowPanel(Static):
    """Component to display the workflow state diagram."""

    DEFAULT_CSS = """
    WorkflowPanel {
        width: 100%;
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the workflow panel."""
        super().__init__(**kwargs)
        self.workflow: ProjectWorkflow | None = None

    def set_workflow(self, workflow: ProjectWorkflow | None) -> None:
        """Set the workflow to display."""
        logger.debug(f"WorkflowPanel.set_workflow called with: {workflow}")
        self.workflow = workflow
        self.refresh_diagram()

    def refresh_diagram(self) -> None:
        """Refresh the displayed diagram."""
        if not self.workflow:
            self.update("No active project selected")
            return

        try:
            diagram = self.workflow.get_ascii_diagram()
            logger.debug(f"Got diagram with {len(diagram)} chars")
            self.update(Text(diagram))
        except Exception as e:
            logger.exception("Failed to generate workflow diagram")
            self.update(f"Error: {e}")
