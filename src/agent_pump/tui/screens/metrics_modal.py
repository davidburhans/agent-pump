"""Modal for displaying metrics dashboard."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Select, TabbedContent, TabPane

from agent_pump.models.metrics import MetricsSnapshot
from agent_pump.services.metrics_service import MetricsService


class MetricsModal(ModalScreen[None]):
    """Modal to display metrics and analytics dashboard."""

    DEFAULT_CSS = """
    MetricsModal {
        align: center middle;
    }

    #metrics-container {
        width: 90%;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #metrics-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #controls-row {
        height: auto;
        margin-bottom: 1;
    }

    #period-selector {
        width: 30;
    }

    #metrics-tabs {
        height: 1fr;
    }

    .stats-grid {
        grid-size: 2;
        grid-gutter: 1;
        margin: 1 0;
    }

    .stat-box {
        border: solid $primary;
        padding: 1;
        text-align: center;
    }

    .stat-label {
        text-style: bold;
        color: $text-muted;
    }

    .stat-value {
        text-style: bold;
        color: $success;
        text-align: center;
    }

    .button-row {
        align: center middle;
        margin-top: 1;
        height: auto;
    }

    DataTable {
        height: 1fr;
    }
    """

    def __init__(self, metrics_service: MetricsService | None = None):
        """Initialize the modal."""
        super().__init__()
        self.metrics_service = metrics_service
        self._current_period: str = "day"
        self._snapshot: MetricsSnapshot | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical(id="metrics-container"):
            yield Label("📊 Metrics & Analytics Dashboard", id="metrics-title")

            # Controls row
            with Horizontal(id="controls-row"):
                yield Select(
                    [("Daily", "day"), ("Weekly", "week"), ("Monthly", "month")],
                    id="period-selector",
                    value="day",
                    allow_blank=False,
                )

            # Tabs for different views
            with TabbedContent(id="metrics-tabs"):
                with TabPane("Summary", id="tab-summary"):
                    yield from self._compose_summary_tab()

                with TabPane("Features", id="tab-features"):
                    yield from self._compose_features_tab()

                with TabPane("Phases", id="tab-phases"):
                    yield from self._compose_phases_tab()

            # Button row
            with Horizontal(classes="button-row"):
                yield Button("📥 Export JSON", id="export-json-btn", variant="primary")
                yield Button("📄 Export CSV", id="export-csv-btn", variant="primary")
                yield Button("Close", id="close-btn", variant="error")

    def _compose_summary_tab(self) -> ComposeResult:
        """Compose the summary tab content."""
        yield Vertical(
            Label("Total Features", classes="stat-label"),
            Label("0", id="total-features", classes="stat-value"),
            classes="stat-box",
        )
        yield Vertical(
            Label("Successful", classes="stat-label"),
            Label("0", id="successful-features", classes="stat-value"),
            classes="stat-box",
        )
        yield Vertical(
            Label("Failed", classes="stat-label"),
            Label("0", id="failed-features", classes="stat-value"),
            classes="stat-box",
        )
        yield Vertical(
            Label("Success Rate", classes="stat-label"),
            Label("0%", id="success-rate", classes="stat-value"),
            classes="stat-box",
        )
        yield Vertical(
            Label("Avg Duration", classes="stat-label"),
            Label("0s", id="avg-duration", classes="stat-value"),
            classes="stat-box",
        )
        yield Vertical(
            Label("Verification Rate", classes="stat-label"),
            Label("0%", id="verification-rate", classes="stat-value"),
            classes="stat-box",
        )

    def _compose_features_tab(self) -> ComposeResult:
        """Compose the features tab content."""
        table = DataTable(id="features-table")
        table.add_columns("Feature", "Project", "Completed", "Duration", "Status")
        yield table

    def _compose_phases_tab(self) -> ComposeResult:
        """Compose the phases tab content."""
        table = DataTable(id="phase-table")
        table.add_columns("Phase", "Avg Duration", "Total Time")
        yield table

    def on_mount(self) -> None:
        """Load metrics data when modal is mounted."""
        self._load_metrics()

    def _load_metrics(self) -> None:
        """Load and display metrics data."""
        if self.metrics_service is None:
            # Try to get from app state
            try:

                app = self.app
                if hasattr(app, "metrics_service"):
                    self.metrics_service = app.metrics_service
            except Exception:
                pass

        if self.metrics_service:
            self._snapshot = self.metrics_service.get_snapshot(period=self._current_period)
            self._update_display()

    def _update_display(self) -> None:
        """Update the display with current metrics."""
        if self._snapshot is None:
            return

        # Update summary tab
        self._update_summary_tab()

        # Update features tab
        self._update_features_tab()

        # Update phases tab
        self._update_phases_tab()

    def _update_summary_tab(self) -> None:
        """Update the summary tab with current data."""
        if self._snapshot is None:
            return

        total_label = self.query_one("#total-features", Label)
        successful_label = self.query_one("#successful-features", Label)
        failed_label = self.query_one("#failed-features", Label)
        success_rate_label = self.query_one("#success-rate", Label)
        avg_duration_label = self.query_one("#avg-duration", Label)
        verification_rate_label = self.query_one("#verification-rate", Label)

        total_label.update(str(self._snapshot.total_features))
        successful_label.update(str(self._snapshot.successful_features))
        failed_label.update(str(self._snapshot.failed_features))

        success_rate = (
            (self._snapshot.successful_features / self._snapshot.total_features * 100)
            if self._snapshot.total_features > 0
            else 0
        )
        success_rate_label.update(f"{success_rate:.1f}%")

        avg_mins = self._snapshot.average_duration_seconds / 60
        avg_duration_label.update(f"{avg_mins:.1f}m")

        verification_rate_label.update(f"{self._snapshot.verification_success_rate * 100:.1f}%")

    def _update_features_tab(self) -> None:
        """Update the features table with current data."""
        if self._snapshot is None:
            return

        table = self.query_one("#features-table", DataTable)
        table.clear()

        for feature in self._snapshot.recent_features:
            status = "✅" if feature.success else "❌"
            duration_mins = feature.total_duration_seconds / 60
            completed_str = feature.completed_at.strftime("%Y-%m-%d %H:%M")
            table.add_row(
                feature.name,
                str(feature.project_path.name),
                completed_str,
                f"{duration_mins:.1f}m",
                status,
            )

    def _update_phases_tab(self) -> None:
        """Update the phases table with current data."""
        if self._snapshot is None:
            return

        table = self.query_one("#phase-table", DataTable)
        table.clear()

        for phase, duration in self._snapshot.phase_durations.items():
            duration_mins = duration / 60
            table.add_row(
                phase.capitalize(),
                f"{duration_mins:.1f}m",
                f"{duration_mins:.1f}m",  # Total is same as avg for now
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle period selector changes."""
        if isinstance(event.value, str):
            self._current_period = event.value
            self._load_metrics()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "close-btn":
            self.dismiss(None)
        elif button_id == "export-json-btn":
            self._export_json()
        elif button_id == "export-csv-btn":
            self._export_csv()

    def _export_json(self) -> None:
        """Export metrics as JSON."""
        if self.metrics_service is None:
            return

        try:
            from pathlib import Path

            json_data = self.metrics_service.export_to_json()
            timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"agent-pump-metrics-{timestamp}.json"

            # Save to current directory
            Path(filename).write_text(json_data, encoding="utf-8")

            # Show success message
            self.notify(f"Metrics exported to {filename}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    def _export_csv(self) -> None:
        """Export metrics as CSV."""
        if self.metrics_service is None:
            return

        try:
            from pathlib import Path

            csv_data = self.metrics_service.export_to_csv()
            timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"agent-pump-metrics-{timestamp}.csv"

            # Save to current directory
            Path(filename).write_text(csv_data, encoding="utf-8")

            # Show success message
            self.notify(f"Metrics exported to {filename}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")
