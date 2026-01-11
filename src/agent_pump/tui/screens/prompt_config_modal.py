"""Modal screen for configuring prompt customizations per phase."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Collapsible, Label, Static, TabbedContent, TabPane, TextArea

from agent_pump.models.workspace import ProjectConfig, PromptCustomization
from agent_pump.orchestrator.base_prompts import get_base_prompt_manager


PHASES = ["planning", "implementing", "verifying", "brainstorming", "committing"]

# Default hints for each phase
PHASE_HINTS = {
    "planning": "Prefix example: 'Focus on security considerations.'",
    "implementing": "Prefix example: 'Always write comprehensive tests.'",
    "verifying": "Prefix example: 'Test edge cases thoroughly.'",
    "brainstorming": "Prefix example: 'Focus on user experience.'",
    "committing": "Prefix example: 'Use conventional commits.'",
}


class PromptConfigModal(ModalScreen[PromptCustomization | None]):
    """Modal for configuring prompt customizations for each workflow phase."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+b", "toggle_base", "Toggle Base", priority=True),
        Binding("ctrl+r", "reset_phase", "Reset Phase", priority=True),
    ]

    DEFAULT_CSS = """
    PromptConfigModal {
        align: center middle;
    }

    #modal-container {
        width: 95%;
        height: 95%;
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
        overflow-y: auto;
    }

    .textarea-container {
        height: auto;
        min-height: 6;
        margin-bottom: 1;
    }

    .textarea-label {
        height: 1;
        margin-bottom: 0;
        text-style: bold;
    }

    .textarea-hint {
        height: 1;
        color: $text-muted;
        text-style: italic;
    }

    .textarea-container TextArea {
        height: 5;
    }

    .base-prompt-section {
        margin-top: 1;
    }

    .base-prompt-section Collapsible {
        background: $surface-darken-1;
    }

    .base-prompt-section TextArea {
        height: 10;
    }

    .base-prompt-section .override-row {
        height: 2;
        margin-bottom: 1;
    }

    .override-row Checkbox {
        margin-right: 2;
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
        self.prompt_manager = get_base_prompt_manager()

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Container(id="modal-container"):
            yield Static(f"📝 Prompt Customization: {self.project_config.name}", id="modal-title")
            yield Label(
                "Edit prefix/suffix (Ctrl+S save, Ctrl+B toggle base, Ctrl+R reset phase, Esc cancel)",
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
                        base_override = self.prompt_customization.get_base_override(phase)
                        default_base = self.prompt_manager.get_default(phase)
                        has_override = bool(base_override.strip())

                        with Vertical(classes="phase-config"):
                            # Prefix
                            with Vertical(classes="textarea-container"):
                                yield Label(f"Prefix (added BEFORE {phase} prompt):", classes="textarea-label")
                                yield TextArea(prefix, id=f"{phase}-prefix")

                            # Suffix
                            with Vertical(classes="textarea-container"):
                                yield Label(f"Suffix (added AFTER {phase} prompt):", classes="textarea-label")
                                yield TextArea(suffix, id=f"{phase}-suffix")

                            yield Label(PHASE_HINTS.get(phase, ""), classes="textarea-hint")

                            # Base prompt section (collapsible)
                            with Vertical(classes="base-prompt-section"):
                                with Collapsible(title="Base Prompt (click to expand)", collapsed=True, id=f"{phase}-base-collapsible"):
                                    with Horizontal(classes="override-row"):
                                        yield Checkbox(
                                            "Override base prompt",
                                            value=has_override,
                                            id=f"{phase}-override-checkbox",
                                        )
                                        yield Button("Reset to Default", variant="warning", id=f"{phase}-reset-base")
                                    yield TextArea(
                                        base_override if has_override else default_base,
                                        id=f"{phase}-base",
                                        read_only=not has_override,
                                    )

            with Horizontal(classes="button-row"):
                yield Button("Clear All", variant="warning", id="btn-clear")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel")
                yield Button("Save (Ctrl+S)", variant="success", id="btn-save")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes for base prompt override."""
        checkbox_id = event.checkbox.id
        if checkbox_id and checkbox_id.endswith("-override-checkbox"):
            phase = checkbox_id.replace("-override-checkbox", "")
            base_area = self.query_one(f"#{phase}-base", TextArea)
            
            if event.value:
                # User wants to override - make editable
                base_area.read_only = False
                self.notify(f"Base prompt for {phase} is now editable", severity="information")
            else:
                # User doesn't want override - reset to default and lock
                default_base = self.prompt_manager.get_default(phase)
                base_area.text = default_base
                base_area.read_only = True
                self.notify(f"Base prompt for {phase} reset to default", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-clear":
            self._clear_all()
        elif button_id and button_id.endswith("-reset-base"):
            phase = button_id.replace("-reset-base", "")
            self._reset_base_prompt(phase)

    def _reset_base_prompt(self, phase: str) -> None:
        """Reset base prompt for a phase to default."""
        default_base = self.prompt_manager.get_default(phase)
        base_area = self.query_one(f"#{phase}-base", TextArea)
        checkbox = self.query_one(f"#{phase}-override-checkbox", Checkbox)
        
        base_area.text = default_base
        base_area.read_only = True
        checkbox.value = False
        self.notify(f"Reset {phase} base prompt to default", severity="information")

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    def action_toggle_base(self) -> None:
        """Toggle the base prompt collapsible for the active tab."""
        # Get the current tab
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active
        if active_tab:
            phase = active_tab.replace("tab-", "")
            try:
                collapsible = self.query_one(f"#{phase}-base-collapsible", Collapsible)
                collapsible.collapsed = not collapsible.collapsed
            except Exception:
                pass

    def action_reset_phase(self) -> None:
        """Reset the current phase to defaults."""
        tabbed = self.query_one(TabbedContent)
        active_tab = tabbed.active
        if active_tab:
            phase = active_tab.replace("tab-", "")
            self.query_one(f"#{phase}-prefix", TextArea).text = ""
            self.query_one(f"#{phase}-suffix", TextArea).text = ""
            self._reset_base_prompt(phase)
            self.notify(f"Reset all {phase} customizations", severity="information")

    def _clear_all(self) -> None:
        """Clear all prompt customizations."""
        for phase in PHASES:
            self.query_one(f"#{phase}-prefix", TextArea).text = ""
            self.query_one(f"#{phase}-suffix", TextArea).text = ""
            self._reset_base_prompt(phase)

        self.notify("Cleared all prompt customizations", severity="information")

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        for phase in PHASES:
            prefix_area = self.query_one(f"#{phase}-prefix", TextArea)
            suffix_area = self.query_one(f"#{phase}-suffix", TextArea)
            override_checkbox = self.query_one(f"#{phase}-override-checkbox", Checkbox)
            base_area = self.query_one(f"#{phase}-base", TextArea)

            setattr(self.prompt_customization, f"{phase}_prefix", prefix_area.text)
            setattr(self.prompt_customization, f"{phase}_suffix", suffix_area.text)
            
            # Only save base override if checkbox is checked
            if override_checkbox.value:
                setattr(self.prompt_customization, f"{phase}_base", base_area.text)
            else:
                setattr(self.prompt_customization, f"{phase}_base", "")

        self.dismiss(self.prompt_customization)

