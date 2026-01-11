"""Modal screen for configuring backend settings per phase."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent, TabPane

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import BackendFallback, BackendInstance, PhaseBackends, ProjectConfig


PHASES = ["planning", "implementing", "verifying", "brainstorming", "committing"]


class BackendConfigModal(ModalScreen[PhaseBackends | None]):
    """Modal for configuring backend settings for each workflow phase."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    BackendConfigModal {
        align: center middle;
    }

    #modal-container {
        width: 85%;
        height: 85%;
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
        color: $text;
    }

    .help-text {
        color: $text-muted;
        height: 2;
        margin-bottom: 1;
    }

    .phase-config {
        height: auto;
        padding: 1;
    }

    .section-label {
        text-style: bold;
        margin-top: 1;
    }

    .config-row {
        height: 3;
        margin-bottom: 1;
    }

    .config-row Label {
        width: 12;
    }

    .config-row Input {
        width: 1fr;
    }

    .config-row Select {
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

    TabbedContent {
        height: 1fr;
    }

    .hint {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(
        self,
        project_config: ProjectConfig,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.project_config = project_config
        # Make a copy of the phase backends to edit
        self.phase_backends = project_config.phase_backends.model_copy(deep=True)

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        available_backends = list(BACKEND_REGISTRY.keys())

        with Container(id="modal-container"):
            yield Static(f"⚙️ Backend Configuration: {self.project_config.name}", id="modal-title")
            yield Label(
                "Configure backends for each phase. Use Ctrl+S to save, Escape to cancel.",
                classes="help-text"
            )

            with TabbedContent():
                for phase in PHASES:
                    phase_icon = {
                        "planning": "📋",
                        "implementing": "🔨",
                        "verifying": "✅",
                        "brainstorming": "💡",
                        "committing": "📝",
                    }.get(phase, "")

                    with TabPane(f"{phase_icon} {phase.capitalize()}", id=f"tab-{phase}"):
                        phase_config = getattr(self.phase_backends, phase)
                        # Get backend info
                        first_backend = phase_config.backends[0] if phase_config.backends else BackendInstance()
                        fallback = phase_config.backends[1] if len(phase_config.backends) > 1 else None

                        with Vertical(classes="phase-config"):
                            yield Label("Primary Backend", classes="section-label")
                            with Horizontal(classes="config-row"):
                                yield Label("Backend:")
                                yield Select(
                                    [(b, b) for b in available_backends],
                                    value=first_backend.name,
                                    id=f"{phase}-backend",
                                )

                            with Horizontal(classes="config-row"):
                                yield Label("Args:")
                                yield Input(
                                    value=" ".join(first_backend.args),
                                    placeholder="e.g., --model gemini-2.5-flash",
                                    id=f"{phase}-args",
                                )

                            yield Label("Fallback Backend (used if primary fails/quota)", classes="section-label")
                            with Horizontal(classes="config-row"):
                                yield Label("Backend:")
                                yield Select(
                                    [("none", "(none)")] + [(b, b) for b in available_backends],
                                    value=fallback.name if fallback else "none",
                                    id=f"{phase}-fallback-backend",
                                )

                            with Horizontal(classes="config-row"):
                                yield Label("Args:")
                                yield Input(
                                    value=" ".join(fallback.args) if fallback else "",
                                    placeholder="e.g., --model gemini-2.5-flash",
                                    id=f"{phase}-fallback-args",
                                    disabled=fallback is None,
                                )

            with Horizontal(classes="button-row"):
                yield Button("Reset to Default", variant="warning", id="btn-reset")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel")
                yield Button("Save (Ctrl+S)", variant="success", id="btn-save")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Enable/disable fallback args input based on fallback selection."""
        if "-fallback-backend" in str(event.select.id):
            phase = str(event.select.id).replace("-fallback-backend", "")
            args_input = self.query_one(f"#{phase}-fallback-args", Input)
            args_input.disabled = event.value == "none"
            if event.value == "none":
                args_input.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-reset":
            self._reset_to_default()

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    def _reset_to_default(self) -> None:
        """Reset all phases to default (gemini, no args, no fallback)."""
        for phase in PHASES:
            self.query_one(f"#{phase}-backend", Select).value = "gemini"
            self.query_one(f"#{phase}-args", Input).value = ""
            self.query_one(f"#{phase}-fallback-backend", Select).value = "none"
            self.query_one(f"#{phase}-fallback-args", Input).value = ""
            self.query_one(f"#{phase}-fallback-args", Input).disabled = True

        self.notify("Reset all phases to default (Gemini)", severity="information")

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        for phase in PHASES:
            # Get primary backend
            backend_select = self.query_one(f"#{phase}-backend", Select)
            args_input = self.query_one(f"#{phase}-args", Input)

            backend_name = str(backend_select.value)
            args = args_input.value.split() if args_input.value.strip() else []

            backends = [BackendInstance(name=backend_name, args=args)]

            # Get fallback backend if set
            fallback_select = self.query_one(f"#{phase}-fallback-backend", Select)
            fallback_args_input = self.query_one(f"#{phase}-fallback-args", Input)

            fallback_name = str(fallback_select.value)
            if fallback_name != "none":
                fallback_args = fallback_args_input.value.split() if fallback_args_input.value.strip() else []
                backends.append(BackendInstance(name=fallback_name, args=fallback_args))

            # Update the phase config
            setattr(self.phase_backends, phase, BackendFallback(backends=backends))

        self.dismiss(self.phase_backends)
