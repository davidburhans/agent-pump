"""Modal screen for configuring verification commands."""

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Switch, TextArea

from agent_pump.models.verification_config import VerificationConfig


class VerificationConfigModal(ModalScreen[VerificationConfig]):
    """Modal screen for configuring verification commands."""

    BINDINGS = [
        ("escape", "dismiss(None)", "Dismiss"),
        ("ctrl+s", "save_and_dismiss", "Save and Close"),
    ]

    def __init__(self, config: VerificationConfig | None = None, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.original_config = config or VerificationConfig()
        self.config = VerificationConfig(
            build_cmd=self.original_config.build_cmd,
            lint_cmd=self.original_config.lint_cmd,
            test_cmd=self.original_config.test_cmd,
            skip_verification=self.original_config.skip_verification,
        )

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Vertical(id="verification-config-container"):
            yield Label("[b]Verification Configuration[/b]", id="verification-config-title")

            with VerticalScroll(id="verification-config-scroll"):
                # Skip verification toggle
                yield Horizontal(
                    Label("Skip Verification:", classes="setting-label"),
                    Switch(value=self.config.skip_verification, id="skip-verification-switch"),
                    classes="setting-row"
                )

                # Build command
                with Vertical(classes="command-section"):
                    yield Label("[b]Build Command:[/b]", classes="command-label")
                    yield TextArea(
                        text=self.config.build_cmd or "",
                        id="build-command-input",
                        placeholder="e.g., npm run build, cargo build, python -m build",
                    )

                # Lint command
                with Vertical(classes="command-section"):
                    yield Label("[b]Lint Command:[/b]", classes="command-label")
                    yield TextArea(
                        text=self.config.lint_cmd or "",
                        id="lint-command-input",
                        placeholder="e.g., npm run lint, ruff check ., cargo clippy",
                    )

                # Test command
                with Vertical(classes="command-section"):
                    yield Label("[b]Test Command:[/b]", classes="command-label")
                    yield TextArea(
                        text=self.config.test_cmd or "",
                        id="test-command-input",
                        placeholder="e.g., npm test, pytest, cargo test",
                    )

            yield Horizontal(
                Button("Cancel", variant="default", id="cancel-button"),
                Button("Save", variant="primary", id="save-button"),
                id="button-row"
            )

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        # Set focus to the first input field
        self.query_one("#build-command-input", TextArea).focus()

        # Set up event handlers
        self.query_one("#skip-verification-switch", Switch).can_focus = True

    @on(Button.Pressed, "#cancel-button")
    def on_cancel_pressed(self) -> None:
        """Handle cancel button press."""
        self.dismiss(None)

    @on(Button.Pressed, "#save-button")
    def on_save_pressed(self) -> None:
        """Handle save button press."""
        self.action_save_and_dismiss()

    def action_save_and_dismiss(self) -> None:
        """Save the configuration and dismiss the modal."""
        # Update the config with values from the form
        build_input = self.query_one("#build-command-input", TextArea)
        lint_input = self.query_one("#lint-command-input", TextArea)
        test_input = self.query_one("#test-command-input", TextArea)
        skip_switch = self.query_one("#skip-verification-switch", Switch)

        self.config.build_cmd = build_input.text.strip() or None
        self.config.lint_cmd = lint_input.text.strip() or None
        self.config.test_cmd = test_input.text.strip() or None
        self.config.skip_verification = skip_switch.value

        # Validate the commands to ensure they don't contain dangerous patterns
        try:
            # This will raise ValueError if validation fails
            VerificationConfig(
                build_cmd=self.config.build_cmd,
                lint_cmd=self.config.lint_cmd,
                test_cmd=self.config.test_cmd,
                skip_verification=self.config.skip_verification,
            )
        except ValueError as e:
            # Show error message to user
            self.notify(f"Invalid command format: {e}", severity="error")
            return

        self.dismiss(self.config)

    def on_key(self, event) -> None:
        """Handle key events."""
        # Handle Ctrl+S for saving
        if event.key == "ctrl+s":
            self.action_save_and_dismiss()
            event.stop()
