"""Modal screen for configuring prompt customizations per phase."""

from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from agent_pump.models.workspace import ProjectConfig, PromptCustomization, Workspace
from agent_pump.orchestrator.base_prompts import get_base_prompt_manager
from agent_pump.tui.screens.confirm_modal import ConfirmModal

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

    .copy-row {
        height: 3;
        margin-bottom: 1;
        align: center middle;
    }

    .copy-row Label {
        width: 12;
    }

    .copy-row Select {
        width: 1fr;
    }

    TabbedContent {
        height: 1fr;
    }
    """

    def __init__(
        self,
        project_config: ProjectConfig,
        workspace: Workspace,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.project_config = project_config
        self.workspace = workspace
        # Make a copy to edit
        self.prompt_customization = project_config.prompt_customization.model_copy(deep=True)
        self.prompt_manager = get_base_prompt_manager()

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Container(id="modal-container"):
            yield Static(f"📝 Prompt Customization: {self.project_config.name}", id="modal-title")
            yield Label(
                "Edit prefix/suffix "
                "(Ctrl+S save, Ctrl+B toggle base, Ctrl+R reset phase, Esc cancel)",
                classes="help-text",
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
                            # Copy from row
                            copy_options = [("(select to copy)", "")]

                            # Phases
                            for p in PHASES:
                                if p != phase:
                                    copy_options.append((f"Phase: {p.capitalize()}", f"phase:{p}"))

                            # Projects
                            current_path = str(self.project_config.path.resolve())
                            for p_path_str, p_config in self.workspace.projects.items():
                                if p_path_str != current_path:
                                    copy_options.append(
                                        (f"Project: {p_config.name}", f"project:{p_path_str}")
                                    )

                            yield Horizontal(
                                Label("Copy from:"),
                                Select(
                                    copy_options,
                                    value="",
                                    allow_blank=False,
                                    id=f"{phase}-copy-from",
                                ),
                                classes="copy-row",
                            )

                            # Prefix
                            with Vertical(classes="textarea-container"):
                                yield Label(
                                    f"Prefix (added BEFORE {phase} prompt):",
                                    classes="textarea-label",
                                )
                                yield TextArea(prefix, id=f"{phase}-prefix")

                            # Suffix
                            with Vertical(classes="textarea-container"):
                                yield Label(
                                    f"Suffix (added AFTER {phase} prompt):",
                                    classes="textarea-label",
                                )
                                yield TextArea(suffix, id=f"{phase}-suffix")

                            yield Label(PHASE_HINTS.get(phase, ""), classes="textarea-hint")

                            # Base prompt section (collapsible)
                            with Vertical(classes="base-prompt-section"):
                                with Collapsible(
                                    title="Base Prompt (click to expand)",
                                    collapsed=True,
                                    id=f"{phase}-base-collapsible",
                                ):
                                    yield Horizontal(
                                        Checkbox(
                                            "Override base prompt",
                                            value=has_override,
                                            id=f"{phase}-override-checkbox",
                                        ),
                                        Button(
                                            "Reset to Default",
                                            variant="warning",
                                            id=f"{phase}-reset-base",
                                        ),
                                        classes="override-row",
                                    )
                                yield TextArea(
                                    base_override if has_override else default_base,
                                    id=f"{phase}-base",
                                    read_only=not has_override,
                                )

            yield Horizontal(
                Button("Clear All", variant="warning", id="btn-clear"),
                Button("Apply to All Projects", variant="warning", id="btn-apply-all"),
                Button("Cancel (Esc)", variant="error", id="btn-cancel"),
                Button("Save (Ctrl+S)", variant="success", id="btn-save"),
                classes="button-row",
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle copy-from selection."""
        if not event.select.id:
            return
        select_id = str(event.select.id)
        if "-copy-from" in select_id and event.value:
            phase = select_id.replace("-copy-from", "")
            self.call_later(self._apply_copy, phase, str(event.value))
            # Reset the select to placeholder
            cast(Any, event.select).value = ""

    async def _apply_copy(self, target_phase: str, source: str) -> None:
        """Copy prompt config from a phase or project."""
        src_prefix = ""
        src_suffix = ""
        src_base = ""

        if source.startswith("phase:"):
            src_phase = source.replace("phase:", "")
            src_prefix = getattr(self.prompt_customization, f"{src_phase}_prefix")
            src_suffix = getattr(self.prompt_customization, f"{src_phase}_suffix")
            src_base = self.prompt_customization.get_base_override(src_phase)

        elif source.startswith("project:"):
            project_path_str = source.replace("project:", "")
            p_config = self.workspace.projects.get(project_path_str)
            if p_config:
                src_prefix = getattr(p_config.prompt_customization, f"{target_phase}_prefix")
                src_suffix = getattr(p_config.prompt_customization, f"{target_phase}_suffix")
                src_base = p_config.prompt_customization.get_base_override(target_phase)

        # Update UI
        self.query_one(f"#{target_phase}-prefix", TextArea).text = src_prefix
        self.query_one(f"#{target_phase}-suffix", TextArea).text = src_suffix

        # Update base prompt if overriding
        base_area = self.query_one(f"#{target_phase}-base", TextArea)
        checkbox = self.query_one(f"#{target_phase}-override-checkbox", Checkbox)

        if src_base:
            base_area.text = src_base
            checkbox.value = True
            base_area.read_only = False
        else:
            # If copying logic that has NO override, should we reset?
            # Yes, copy exact state.
            checkbox.value = False
            self._reset_base_prompt(target_phase)

        self.notify(f"Copied config to {target_phase}", severity="information")

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
        elif button_id == "btn-apply-all":
            self.action_apply_to_all()
        elif button_id and button_id.endswith("-reset-base"):
            phase = button_id.replace("-reset-base", "")
            self._reset_base_prompt(phase)

    def action_apply_to_all(self) -> None:
        """Apply current configuration to all projects."""

        def on_confirm(confirm: bool | None) -> None:
            if confirm:
                self._perform_apply_to_all()

        self.app.push_screen(
            ConfirmModal(
                "Are you sure you want to apply this configuration to ALL projects?\n"
                "This will overwrite their prompt settings.",
                confirm_label="Overwrite All",
            ),
            on_confirm,
        )

    def _perform_apply_to_all(self) -> None:
        """Execute the apply to all operation."""
        # Save current state to memory
        self._save_config_to_memory()

        # Apply to all projects
        current_prompts = self.project_config.prompt_customization

        count = 0
        current_path = str(self.project_config.path.resolve())
        for p_path, p_config in self.workspace.projects.items():
            if p_path == current_path:
                continue

            p_config.prompt_customization = current_prompts.model_copy(deep=True)
            count += 1

        self.workspace.save()
        self.notify(f"Applied configuration to {count} other projects", severity="information")

    def _save_config_to_memory(self) -> None:
        """Save the UI state to the project config object without dismissing."""
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

        self.project_config.prompt_customization = self.prompt_customization

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
        self._save_config_to_memory()
        self.dismiss(self.prompt_customization)
