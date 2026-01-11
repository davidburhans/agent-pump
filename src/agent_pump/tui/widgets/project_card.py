"""Project card widget for displaying project status."""

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Static

from agent_pump.models.project import Project, ProjectStatus

STATUS_COLORS = {
    ProjectStatus.IDLE: "white",
    ProjectStatus.PLANNING: "yellow",
    ProjectStatus.IMPLEMENTING: "cyan",
    ProjectStatus.BRAINSTORMING: "magenta",
    ProjectStatus.COMMITTING: "green",
    ProjectStatus.PAUSED: "dim",
    ProjectStatus.ERROR: "red",
    ProjectStatus.COMPLETED: "green bold",
}

STATUS_ICONS = {
    ProjectStatus.IDLE: "⏸",
    ProjectStatus.PLANNING: "📋",
    ProjectStatus.IMPLEMENTING: "🔨",
    ProjectStatus.BRAINSTORMING: "💡",
    ProjectStatus.COMMITTING: "📤",
    ProjectStatus.PAUSED: "⏸",
    ProjectStatus.ERROR: "❌",
    ProjectStatus.COMPLETED: "✅",
}


class ProjectCard(Static):
    """A card widget displaying project status."""

    DEFAULT_CSS = """
    ProjectCard {
        width: 100%;
        height: auto;
        min-height: 5;
        margin: 1 0;
        padding: 1 2;
        background: $surface;
        border: solid $primary-background;
    }

    ProjectCard:hover {
        border: solid $primary;
    }

    ProjectCard:focus {
        border: double $primary;
    }

    ProjectCard.selected {
        border: double $secondary;
        background: $surface-lighten-1;
    }

    ProjectCard .project-name {
        text-style: bold;
    }

    ProjectCard .project-status {
        margin-top: 1;
    }

    ProjectCard .project-feature {
        color: $text-muted;
    }

    ProjectCard .project-progress {
        color: $text-muted;
        margin-top: 1;
    }
    """

    class Selected(Message):
        """Message emitted when card is selected."""

        def __init__(self, project: Project, card: "ProjectCard") -> None:
            self.project = project
            self.card = card
            super().__init__()

    def __init__(self, project: Project, **kwargs):
        """
        Initialize the project card.

        Args:
            project: The project to display
        """
        super().__init__(**kwargs)
        self.project = project
        self.can_focus = True

    def compose(self) -> ComposeResult:
        """Create the card content."""
        yield Static(self.project.name, classes="project-name")
        yield Static(self._format_status(), classes="project-status")
        yield Static(self._format_feature(), classes="project-feature")
        yield Static(self._format_progress(), classes="project-progress")

    def _format_status(self) -> str:
        """Format the status line with icon and color."""
        icon = STATUS_ICONS.get(self.project.status, "•")
        color = STATUS_COLORS.get(self.project.status, "white")
        status_text = self.project.status.value.capitalize()
        return f"[{color}]{icon} {status_text}[/{color}]"

    def _format_feature(self) -> str:
        """Format the current feature line."""
        if self.project.current_feature:
            return f"Working on: {self.project.current_feature}"
        return "No active feature"

    def _format_progress(self) -> str:
        """Format the progress line."""
        completed = len(self.project.completed_features)
        failed = len(self.project.failed_features)
        total = completed + failed + (1 if self.project.current_feature else 0)

        if total == 0:
            return "No features processed yet"

        return f"✓ {completed} completed | ✗ {failed} failed | 🔄 {self.project.iteration_count} iterations"

    def refresh_content(self) -> None:
        """Refresh the card content."""
        # Update status
        status_widget = self.query_one(".project-status", Static)
        status_widget.update(self._format_status())

        # Update feature
        feature_widget = self.query_one(".project-feature", Static)
        feature_widget.update(self._format_feature())

        # Update progress
        progress_widget = self.query_one(".project-progress", Static)
        progress_widget.update(self._format_progress())

    def on_click(self) -> None:
        """Handle click events."""
        self.post_message(self.Selected(self.project, self))
