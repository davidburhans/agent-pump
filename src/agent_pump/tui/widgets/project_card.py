"""Project card widget for displaying project status."""

from datetime import datetime

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

    # Class-level toggle: False = elapsed time, True = time remaining
    show_time_remaining: bool = False
    # Default timeout in seconds (30 minutes)
    DEFAULT_TIMEOUT: int = 1800
    # States where project is stopped/inactive (timer should not run)
    STOPPED_STATES: set = {
        ProjectStatus.IDLE,
        ProjectStatus.PAUSED,
        ProjectStatus.COMPLETED,
        ProjectStatus.ERROR,
    }

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

    def __init__(self, project: Project, timeout: int | None = None, **kwargs):
        """
        Initialize the project card.

        Args:
            project: The project to display
            timeout: Phase timeout in seconds (for time remaining display)
        """
        super().__init__(**kwargs)
        self.project = project
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.can_focus = True
        self._timer_handle = None  # Track timer for cleanup

    def compose(self) -> ComposeResult:
        """Create the card content."""
        yield Static(self.project.name, classes="project-name")
        yield Static(self._format_status(), classes="project-status")
        yield Static(self._format_feature(), classes="project-feature")
        yield Static(self._format_progress(), classes="project-progress")

    def _is_active_state(self) -> bool:
        """Check if project is in an active working state (timer should run)."""
        return self.project.status not in self.STOPPED_STATES

    def on_mount(self) -> None:
        """Start periodic timer refresh when mounted (only if in active state)."""
        # Only start timer if project is in an active working state
        if self._is_active_state():
            self._timer_handle = self.set_interval(1.0, self._refresh_timer)

    def on_unmount(self) -> None:
        """Clean up timer when card is removed."""
        if self._timer_handle:
            self._timer_handle.stop()
            self._timer_handle = None

    def _update_timer_state(self) -> None:
        """Start or stop the timer based on project state."""
        should_run = self._is_active_state()
        timer_running = self._timer_handle is not None

        if should_run and not timer_running:
            # Start timer
            self._timer_handle = self.set_interval(1.0, self._refresh_timer)
        elif not should_run and self._timer_handle:
            # Stop timer
            self._timer_handle.stop()
            self._timer_handle = None

    def _format_status(self) -> str:
        """Format the status line with icon and color."""
        icon = STATUS_ICONS.get(self.project.status, "•")
        color = STATUS_COLORS.get(self.project.status, "white")
        status_text = self.project.status.value.capitalize()

        # Add verification indicator if verification commands are configured
        verification_indicator = ""
        if (
            self.project.config.build_cmd
            or self.project.config.lint_cmd
            or self.project.config.test_cmd
        ):
            verification_indicator = " 🔧"  # Gear icon indicates verification is configured

        # Add elapsed time in current state
        elapsed = self._format_elapsed_time()
        elapsed_display = f" ({elapsed})" if elapsed else ""

        status_line = (
            f"[{color}]{icon} {status_text}{verification_indicator}{elapsed_display}[/{color}]"
        )

        # Add granular activity if available
        if self.project.current_activity and self._is_active_state():
            # Truncate if too long (e.g. > 50 chars)
            activity = self.project.current_activity
            if len(activity) > 50:
                activity = activity[:47] + "..."
            status_line += f"\n[dim]   ↳ {activity}[/dim]"

        return status_line

    def _format_elapsed_time(self) -> str:
        """Format the elapsed time since state changed or time remaining."""
        if not self.project.state_changed_at:
            return ""

        # Only show timer for active working states, not stopped states
        stopped_states = {
            ProjectStatus.IDLE,
            ProjectStatus.PAUSED,
            ProjectStatus.COMPLETED,
            ProjectStatus.ERROR,
        }
        if self.project.status in stopped_states:
            return ""

        elapsed = datetime.now() - self.project.state_changed_at
        total_seconds = int(elapsed.total_seconds())

        if total_seconds < 0:
            return ""

        if ProjectCard.show_time_remaining:
            # Show time remaining until timeout
            remaining = self.timeout - total_seconds
            if remaining <= 0:
                return "⏱️ TIMEOUT"
            return self._format_time_value(remaining, prefix="⏳ ")
        else:
            # Show elapsed time
            return self._format_time_value(total_seconds, prefix="⏱️ ")

    def _format_time_value(self, total_seconds: int, prefix: str = "") -> str:
        """Format a time value in human-readable format."""
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{prefix}{hours}h {minutes}m"
        elif minutes > 0:
            return f"{prefix}{minutes}m {seconds}s"
        else:
            return f"{prefix}{seconds}s"

    @classmethod
    def toggle_time_mode(cls) -> None:
        """Toggle between showing elapsed time and time remaining."""
        cls.show_time_remaining = not cls.show_time_remaining

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

        # Build verification status indicator
        verification_parts = []
        if self.project.config.skip_verification:
            verification_parts.append("verification: skipped")
        else:
            verification_parts.append("verification: enabled")

        if self.project.config.build_cmd:
            verification_parts.append(f"build: {self.project.config.build_cmd}")
        if self.project.config.lint_cmd:
            verification_parts.append(f"lint: {self.project.config.lint_cmd}")
        if self.project.config.test_cmd:
            verification_parts.append(f"test: {self.project.config.test_cmd}")

        verification_info = (
            ", ".join(verification_parts) if verification_parts else "verification: none"
        )

        if total == 0:
            return f"No features processed yet | {verification_info}"

        return (
            f"✓ {completed} completed | "
            f"✗ {failed} failed | "
            f"🔄 {self.project.iteration_count} iterations | "
            f"{verification_info}"
        )

    def refresh_content(self) -> None:
        """Refresh the card content."""
        # Update timer state based on project status
        self._update_timer_state()

        # Update status
        status_widget = self.query_one(".project-status", Static)
        status_widget.update(self._format_status())

        # Update feature
        feature_widget = self.query_one(".project-feature", Static)
        feature_widget.update(self._format_feature())

        # Update progress
        progress_widget = self.query_one(".project-progress", Static)
        progress_widget.update(self._format_progress())

    def _refresh_timer(self) -> None:
        """Refresh just the status line to update the elapsed timer."""
        try:
            status_widget = self.query_one(".project-status", Static)
            status_widget.update(self._format_status())
        except Exception:
            # Widget may not be mounted yet
            pass

    def on_click(self) -> None:
        """Handle click events."""
        self.post_message(self.Selected(self.project, self))
