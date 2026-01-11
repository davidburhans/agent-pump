"""Modal screen for configuring prompt customizations per phase."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static, TabbedContent, TabPane, TextArea

from agent_pump.models.workspace import ProjectConfig, PromptCustomization


PHASES = ["planning", "implementing", "verifying", "brainstorming", "committing"]

# Default hints for each phase
PHASE_HINTS = {
    "planning": "Prefix example: 'Focus on security considerations.'\nSuffix example: 'Include rollback plan.'",
    "implementing": "Prefix example: 'Always write comprehensive tests.'\nSuffix example: 'Ensure cross-platform compatibility.'",
    "verifying": "Prefix example: 'Test edge cases thoroughly.'\nSuffix example: 'Document any known limitations.'",
    "brainstorming": "Prefix example: 'Focus on user experience.'\nSuffix example: 'Consider mobile users.'",
    "committing": "Prefix example: 'Use conventional commits.'\nSuffix example: 'Tag breaking changes.'",
}


class PromptConfigModal(ModalScreen[PromptCustomization | None]):
    """Modal for configuring prompt customizations for each workflow phase."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    PromptConfigModal {
        align: center middle;
    }

    #modal-container {
        width: 90%;
        height: 90%;
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
        height: 1fr;
        padding: 1;
    }

    .textarea-container {
        height: 1fr;
        margin-bottom: 1;
    }

    .textarea-label {
        height: 1;
        margin-bottom: 0;
        text-style: bold;
    }

    .textarea-hint {
        height: 2;
        color: $text-muted;
        text-style: italic;
    }

    .textarea-container TextArea {
        height: 1fr;
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
        # Make a copy to edit
        self.prompt_customization = project_config.prompt_customization.model_copy(deep=True)

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Container(id="modal-container"):
            yield Static(f"📝 Prompt Customization: {self.project_config.name}", id="modal-title")
            yield Label(
                "Add text before (prefix) or after (suffix) the standard prompts. Use Ctrl+S to save, Escape to cancel.",
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
                        prefix = getattr(self.prompt_customization, f"{phase}_prefix")
                        suffix = getattr(self.prompt_customization, f"{phase}_suffix")

                        with Vertical(classes="phase-config"):
                            with Vertical(classes="textarea-container"):
                                yield Label(f"Prefix (added BEFORE {phase} prompt):", classes="textarea-label")
                                yield TextArea(
                                    prefix,
                                    id=f"{phase}-prefix",
                                )

                            with Vertical(classes="textarea-container"):
                                yield Label(f"Suffix (added AFTER {phase} prompt):", classes="textarea-label")
                                yield TextArea(
                                    suffix,
                                    id=f"{phase}-suffix",
                                )

                            yield Label(PHASE_HINTS.get(phase, ""), classes="textarea-hint")

            with Horizontal(classes="button-row"):
                yield Button("Clear All", variant="warning", id="btn-clear")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel")
                yield Button("Save (Ctrl+S)", variant="success", id="btn-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-clear":
            self._clear_all()

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    def _clear_all(self) -> None:
        """Clear all prompt customizations."""
        for phase in PHASES:
            self.query_one(f"#{phase}-prefix", TextArea).text = ""
            self.query_one(f"#{phase}-suffix", TextArea).text = ""

        self.notify("Cleared all prompt customizations", severity="information")

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        for phase in PHASES:
            prefix_area = self.query_one(f"#{phase}-prefix", TextArea)
            suffix_area = self.query_one(f"#{phase}-suffix", TextArea)

            setattr(self.prompt_customization, f"{phase}_prefix", prefix_area.text)
            setattr(self.prompt_customization, f"{phase}_suffix", suffix_area.text)

        self.dismiss(self.prompt_customization)
