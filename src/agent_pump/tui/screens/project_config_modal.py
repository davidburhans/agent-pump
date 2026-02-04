"""Modal screen for configuring project settings."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TabbedContent, TabPane

from agent_pump.config import Config


class ProjectConfigModal(ModalScreen[None]):
    """Modal for configuring project settings."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    ProjectConfigModal {
        align: center middle;
    }

    #modal-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #modal-title {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        text-style: bold;
        background: $primary;
    }

    .section-label {
        text-style: bold;
        margin-top: 1;
        margin-bottom: 1;
    }

    .input-row {
        height: auto;
        margin-bottom: 1;
    }

    .input-row Label {
        width: 20;
    }

    .input-row Input, .input-row Select {
        width: 1fr;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .button-row Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        project_path: Path,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.project_path = project_path
        self.config = Config.load(project_path)
        self.config_path = project_path / ".agent-pump" / "config.yml"

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Container(id="modal-container"):
            yield Static(f"⚙️ Project Configuration: {self.project_path.name}", id="modal-title")

            with TabbedContent():
                with TabPane("General", id="tab-general"):
                    yield Label("AI Backend:", classes="section-label")
                    yield Select(
                        [
                            ("Gemini (Google)", "gemini"),
                            ("GPT-4 (OpenAI)", "openai:gpt-4"),
                            ("GPT-4o (OpenAI)", "openai:gpt-4o"),
                            ("Claude 3 Opus (Anthropic)", "anthropic:claude-3-opus"),
                            (
                                "Claude 3.5 Sonnet (Anthropic)",
                                "anthropic:claude-3-5-sonnet-20240620",
                            ),
                        ],
                        value=self.config.backend,
                        id="input-backend",
                        allow_blank=False,
                    )

                    yield Label("Workflow Settings:", classes="section-label")

                    yield Horizontal(
                        Label("Max Iterations:"),
                        Input(
                            str(self.config.workflow.max_iterations),
                            placeholder="10",
                            id="input-max-iterations",
                            type="integer",
                        ),
                        classes="input-row",
                    )

                    yield Horizontal(
                        Label("Timeout (seconds):"),
                        Input(
                            str(self.config.workflow.timeout),
                            placeholder="1800",
                            id="input-timeout",
                            type="integer",
                        ),
                        classes="input-row",
                    )

                    yield Horizontal(
                        Label("Git Branch:"),
                        Input(
                            self.config.workflow.branch or "",
                            placeholder="(optional branch name)",
                            id="input-branch",
                        ),
                        classes="input-row",
                    )

                with TabPane("Verification", id="tab-verification"):
                    yield Checkbox(
                        "Skip Verification Phase",
                        value=self.config.verification.skip_verification,
                        id="input-skip-verification",
                    )

                    yield Label("Commands (leave empty to auto-detect):", classes="section-label")

                    yield Horizontal(
                        Label("Build Command:"),
                        Input(
                            self.config.verification.build_cmd or "",
                            placeholder="e.g., npm run build",
                            id="input-build-cmd",
                        ),
                        classes="input-row",
                    )

                    yield Horizontal(
                        Label("Lint Command:"),
                        Input(
                            self.config.verification.lint_cmd or "",
                            placeholder="e.g., npm run lint",
                            id="input-lint-cmd",
                        ),
                        classes="input-row",
                    )

                    yield Horizontal(
                        Label("Test Command:"),
                        Input(
                            self.config.verification.test_cmd or "",
                            placeholder="e.g., npm test",
                            id="input-test-cmd",
                        ),
                        classes="input-row",
                    )

            # Button row (outside tabs)
            yield Horizontal(
                Button("Cancel (Esc)", variant="error", id="btn-cancel"),
                Button("Save (Ctrl+S)", variant="success", id="btn-save"),
                classes="button-row",
            )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear error state when user types."""
        event.input.remove_class("error")

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def _shake(self, widget: Widget) -> None:
        """Shake the widget to indicate an error."""
        # Manual shake animation sequence
        offsets = [(2, 0), (-2, 0), (1, 0), (-1, 0), None]
        step_duration = 0.05

        def _step(i: int) -> None:
            if i >= len(offsets):
                return
            widget.styles.offset = offsets[i]  # type: ignore
            self.set_timer(step_duration, lambda: _step(i + 1))

        _step(0)

    async def action_save(self) -> None:
        """Save the configuration and dismiss."""
        try:
            # Workflow Validation
            max_iter_input = self.query_one("#input-max-iterations", Input)
            max_iter_val = max_iter_input.value
            if max_iter_val:
                try:
                    val = int(max_iter_val)
                    if val <= 0:
                        raise ValueError("Must be positive")
                    self.config.workflow.max_iterations = val
                except ValueError:
                    self.notify("Max iterations must be a positive integer", severity="error")
                    self.query_one(TabbedContent).active = "tab-general"
                    max_iter_input.focus()
                    max_iter_input.add_class("error")
                    self._shake(max_iter_input)
                    return

            timeout_input = self.query_one("#input-timeout", Input)
            timeout_val = timeout_input.value
            if timeout_val:
                try:
                    val = int(timeout_val)
                    if val <= 0:
                        raise ValueError("Must be positive")
                    self.config.workflow.timeout = val
                except ValueError:
                    self.notify("Timeout must be a positive integer", severity="error")
                    self.query_one(TabbedContent).active = "tab-general"
                    timeout_input.focus()
                    timeout_input.add_class("error")
                    self._shake(timeout_input)
                    return

            # Update other config (safe fields)
            backend = self.query_one("#input-backend", Select).value
            if backend:
                self.config.backend = str(backend)

            branch = self.query_one("#input-branch", Input).value
            self.config.workflow.branch = str(branch) if branch.strip() else None

            # Verification
            self.config.verification.skip_verification = self.query_one(
                "#input-skip-verification", Checkbox
            ).value

            build_cmd = self.query_one("#input-build-cmd", Input).value
            self.config.verification.build_cmd = str(build_cmd) if build_cmd.strip() else None

            lint_cmd = self.query_one("#input-lint-cmd", Input).value
            self.config.verification.lint_cmd = str(lint_cmd) if lint_cmd.strip() else None

            test_cmd = self.query_one("#input-test-cmd", Input).value
            self.config.verification.test_cmd = str(test_cmd) if test_cmd.strip() else None

            # Save to file
            self.config.save(self.config_path)

            self.notify("Configuration saved successfully", severity="information")
            self.dismiss(None)

        except Exception as e:
            self.notify(f"Error saving configuration: {e}", severity="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-save":
            await self.action_save()
