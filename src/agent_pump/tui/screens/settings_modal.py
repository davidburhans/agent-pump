"""Settings modal for Agent Pump configuration."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Switch

from agent_pump.models.workspace import Workspace


class SettingsModal(ModalScreen[bool]):
    """A modal dialog for configuring Agent Pump settings."""

    def __init__(self, workspace: Workspace, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        """Compose the settings modal."""
        with Vertical(id="settings-container"):
            yield Label("Settings", classes="title")

            # Notifications toggle
            yield Horizontal(
                Label("Enable Desktop Notifications:"),
                Switch(value=self.workspace.notifications_enabled, id="notifications-toggle"),
            )

            # Test notification button
            yield Button("Test Notification", id="test-notification-btn")

            # OK and Cancel buttons
            yield Horizontal(
                Button("OK", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
            )

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Set focus to OK button by default
        self.query_one("#ok-btn").focus()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        if event.switch.id == "notifications-toggle":
            self.workspace.notifications_enabled = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "ok-btn":
            # Save the workspace configuration
            self.workspace.save()
            self.dismiss(True)  # Return True to indicate settings were saved
        elif event.button.id == "cancel-btn":
            self.dismiss(False)  # Return False to indicate cancellation
        elif event.button.id == "test-notification-btn":
            self._test_notification()

    def _test_notification(self) -> None:
        """Send a test notification."""
        from agent_pump.utils.notifier import Notifier

        Notifier.test()
