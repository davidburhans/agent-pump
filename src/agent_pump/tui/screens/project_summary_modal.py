"""Modal for displaying project summary."""

from rich.table import Table
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from agent_pump.models.project import Project


class ProjectSummaryModal(ModalScreen[None]):
    """Modal to display a rich summary table for a project."""

    DEFAULT_CSS = """
    ProjectSummaryModal {
        align: center middle;
    }

    #summary-container {
        width: 80%;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    .button-row {
        align: center middle;
        margin-top: 1;
    }
    """

    def __init__(self, project: Project):
        """Initialize the modal."""
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        """Compose the content."""
        table = Table(title=f"Project Summary: {self.project.name}", expand=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Status", self.project.status.value.upper())
        table.add_row("Current Feature", self.project.current_feature or "None")
        table.add_row("Completed Features", str(len(self.project.completed_features)))
        table.add_row("Failed Features", str(len(self.project.failed_features)))
        table.add_row("Iterations", str(self.project.iteration_count))
        table.add_row("Backend", self.project.backend)
        table.add_row("Branch", self.project.branch or "main")
        
        # Add list of completed features if any
        if self.project.completed_features:
            table.add_section()
            features_str = "\n".join([f"• {f}" for f in self.project.completed_features[-5:]])
            if len(self.project.completed_features) > 5:
                features_str += "\n... (and more)"
            table.add_row("Recent Completions", features_str)

        with Vertical(id="summary-container"):
            yield Static(table)
            yield Vertical(
                Button("Close", id="btn-close", variant="primary"),
                classes="button-row"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)
