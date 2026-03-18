from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from agent_pump.models.schedule import Schedule, ScheduleType
from agent_pump.scheduling.scheduler import WorkflowScheduler


class ScheduleModal(ModalScreen[Schedule | None]):
    """Modal for configuring project schedule."""

    CSS = """
    ScheduleModal {
        align: center middle;
    }

    #schedule-dialog {
        width: 60;
        height: auto;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    .title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #dialog-buttons {
        grid-size: 3 1;
        grid-gutter: 1;
        grid-columns: 1fr 1fr 1fr;
        margin-top: 1;
    }

    .hidden {
        display: none;
    }

    .help-text {
        color: $text-muted;
        text-style: italic;
        margin-bottom: 1;
    }

    Label {
        margin-top: 1;
    }
    """

    def __init__(
        self,
        project_id: str,
        scheduler: WorkflowScheduler,
        schedule: Schedule | None = None,
    ) -> None:
        """Initialize the modal."""
        super().__init__()
        self.project_id = project_id
        self.scheduler = scheduler
        self.existing_schedule = schedule
        self.current_type = schedule.schedule_type if schedule else ScheduleType.CRON

    def compose(self) -> ComposeResult:
        """Compose the modal UI."""
        with Vertical(id="schedule-dialog"):
            yield Label("Configure Workflow Schedule", classes="title")

            # Type selection
            yield Label("Schedule Type:")
            yield Select(
                options=[
                    ("Cron (Periodic)", ScheduleType.CRON.value),
                    ("Interval (Every N minutes)", ScheduleType.INTERVAL.value),
                ],
                value=self.current_type.value,
                id="schedule_type",
                allow_blank=False,
            )

            with Vertical(id="cron-config"):
                yield Label("Cron Expression:")
                yield Input(
                    placeholder="0 2 * * * (min hour dom month dow)",
                    value=self.existing_schedule.cron_expression
                    if self.existing_schedule
                    and self.existing_schedule.schedule_type == ScheduleType.CRON
                    else "0 2 * * *",
                    id="cron_expression",
                )
                yield Static(
                    "Examples: '0 2 * * *' (2am daily), '0 0 * * 1-5' (midnight weekdays)",
                    classes="help-text",
                )

            with Vertical(id="interval-config", classes="hidden"):
                yield Label("Interval (minutes):")
                yield Input(
                    placeholder="60",
                    value=str(self.existing_schedule.interval_minutes)
                    if self.existing_schedule
                    and self.existing_schedule.schedule_type == ScheduleType.INTERVAL
                    else "60",
                    id="interval_minutes",
                    type="integer",
                )

            yield Label("Constraints:")
            yield Checkbox(
                "Only during working hours (9am-5pm)",
                value=self.existing_schedule.working_hours_only
                if self.existing_schedule
                else False,
                id="working_hours",
            )

            yield Checkbox(
                "Enabled",
                value=self.existing_schedule.enabled if self.existing_schedule else True,
                id="enabled",
            )

            with Grid(id="dialog-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button(
                    "Delete", variant="error", id="delete", disabled=self.existing_schedule is None
                )
                yield Button("Save", variant="primary", id="save")

    def on_mount(self) -> None:
        """Handle mount."""
        self.update_visibility()

    @on(Select.Changed, "#schedule_type")
    def on_type_changed(self, event: Select.Changed) -> None:
        """Handle schedule type change."""
        if event.value != Select.BLANK:
            self.current_type = ScheduleType(event.value)
            self.update_visibility()

    def update_visibility(self) -> None:
        """Update visibility of config sections."""
        cron_config = self.query_one("#cron-config")
        interval_config = self.query_one("#interval-config")

        if self.current_type == ScheduleType.CRON:
            cron_config.remove_class("hidden")
            interval_config.add_class("hidden")
        else:
            cron_config.add_class("hidden")
            interval_config.remove_class("hidden")

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        """Cancel changes."""
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    async def action_save(self) -> None:
        """Save schedule."""
        try:
            # Gather data
            cron_expr = self.query_one("#cron_expression", Input).value
            interval_mins_str = self.query_one("#interval_minutes", Input).value
            working_hours = self.query_one("#working_hours", Checkbox).value
            enabled = self.query_one("#enabled", Checkbox).value

            # Prepare kwargs
            kwargs = {
                "project_id": self.project_id,
                "schedule_type": self.current_type,
                "enabled": enabled,
                "working_hours_only": working_hours,
                "cron_expression": cron_expr if self.current_type == ScheduleType.CRON else None,
                "interval_minutes": int(interval_mins_str)
                if self.current_type == ScheduleType.INTERVAL
                else None,
            }

            # If editing, preserve ID and timezone
            if self.existing_schedule:
                kwargs["id"] = self.existing_schedule.id
                kwargs["timezone"] = self.existing_schedule.timezone

            # Create schedule object
            new_schedule = Schedule(**kwargs)

            await self.scheduler.add_schedule(new_schedule)
            self.notify("Schedule saved")
            self.dismiss(new_schedule)

        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")
        except Exception as e:
            self.notify(f"Error saving: {e}", severity="error")

    @on(Button.Pressed, "#delete")
    async def on_delete(self) -> None:
        """Handle delete button."""
        if self.existing_schedule:
            await self.scheduler.remove_schedule(self.existing_schedule.id)
            self.notify("Schedule deleted")
            self.dismiss(None)
