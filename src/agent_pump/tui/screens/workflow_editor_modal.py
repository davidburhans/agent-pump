"""Modal screen for editing custom workflow definitions."""

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow_definition import WorkflowDefinition, WorkflowPhase
from agent_pump.services.workflow_editor_service import (
    WorkflowEditorService,
    WorkflowValidationError,
)


class PhaseListItem(ListItem):
    """A list item representing a workflow phase."""

    def __init__(self, phase: WorkflowPhase, **kwargs):
        super().__init__(**kwargs)
        self.phase = phase

    def compose(self) -> ComposeResult:
        icon = self.phase.icon or "●"
        text = f"{icon} {self.phase.name}"
        if self.phase.description:
            text += f" - {self.phase.description}"

        yield Label(text)

        # Row action buttons
        with Horizontal(classes="row-buttons"):
            yield Button("↑", classes="btn-row-up", variant="default", tooltip="Move Up (Ctrl+Up)")
            yield Button(
                "↓", classes="btn-row-down", variant="default", tooltip="Move Down (Ctrl+Down)"
            )
            yield Button("✏️", classes="btn-row-edit", variant="default", tooltip="Edit (Enter)")
            yield Button("🗑️", classes="btn-row-remove", variant="default", tooltip="Remove (Del)")


class PhaseEditorModal(ModalScreen[WorkflowPhase | None]):
    """Modal for creating and editing a single workflow phase."""

    DEFAULT_CSS = """
    PhaseEditorModal {
        align: center middle;
    }

    #phase-editor-container {
        width: 80%;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
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
        phase: WorkflowPhase | None = None,
        existing_names: list[str] | None = None,
        available_states: list[str] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.phase = phase
        self.existing_names = existing_names or []
        self.available_states = available_states or []
        self.is_new = phase is None

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        title = "Edit Phase" if not self.is_new else "Add Phase"

        # Determine initial values
        initial_name = self.phase.name if self.phase else ""
        initial_desc = self.phase.description if self.phase else ""
        initial_icon = self.phase.icon if self.phase else ""
        initial_success = self.phase.on_success if self.phase else "completed"
        initial_failure = self.phase.on_failure if self.phase and self.phase.on_failure else None
        initial_timeout = str(self.phase.timeout) if self.phase and self.phase.timeout else ""
        initial_retries = str(self.phase.max_retries) if self.phase else "0"

        # Build options for selects
        state_options = [(s, s) for s in self.available_states]
        failure_options = [("", None)] + state_options

        with Container(id="phase-editor-container"):
            yield Label(title, classes="section-label")

            yield Horizontal(
                Label("Name:"),
                Input(initial_name, placeholder="phase_name", id="phase-name"),
                classes="input-row",
            )
            yield Horizontal(
                Label("Description:"),
                Input(initial_desc, placeholder="Description...", id="phase-description"),
                classes="input-row",
            )
            yield Horizontal(
                Label("Icon:"),
                Input(initial_icon, placeholder="📋", id="phase-icon"),
                classes="input-row",
            )
            yield Horizontal(
                Label("On Success:"),
                Select(state_options, value=initial_success, id="phase-on-success"),
                classes="input-row",
            )
            yield Horizontal(
                Label("On Failure:"),
                Select(failure_options, value=initial_failure, id="phase-on-failure"),
                classes="input-row",
            )
            yield Horizontal(
                Label("Timeout:"),
                Input(
                    initial_timeout,
                    placeholder="seconds (optional)",
                    id="phase-timeout",
                    type="integer",
                ),
                classes="input-row",
            )
            yield Horizontal(
                Label("Max Retries:"),
                Input(initial_retries, placeholder="0", id="phase-retries", type="integer"),
                classes="input-row",
            )

            yield Horizontal(
                Button("Save", variant="success", id="btn-save-phase"),
                Button("Cancel", variant="error", id="btn-cancel-phase"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save-phase":
            self._save_phase()
        elif event.button.id == "btn-cancel-phase":
            self.dismiss(None)

    def _save_phase(self) -> None:
        name_input = self.query_one("#phase-name", Input)
        name = name_input.value.strip()

        if not name:
            name_input.add_class("error")
            return

        # Check uniqueness
        if name in self.existing_names:
            # If we are editing, we can reuse our own name
            if not self.phase or self.phase.name != name:
                name_input.add_class("error")
                self.notify("Phase name must be unique", severity="error")
                return

        desc_input = self.query_one("#phase-description", Input)
        icon_input = self.query_one("#phase-icon", Input)
        success_select = self.query_one("#phase-on-success", Select)
        failure_select = self.query_one("#phase-on-failure", Select)
        timeout_input = self.query_one("#phase-timeout", Input)
        retries_input = self.query_one("#phase-retries", Input)

        # Parse numeric fields
        timeout = None
        if timeout_input.value:
            try:
                timeout = int(timeout_input.value)
                if timeout <= 0:
                    timeout = None
            except ValueError:
                timeout_input.add_class("error")
                return

        max_retries = 0
        if retries_input.value:
            try:
                max_retries = int(retries_input.value)
                if max_retries < 0:
                    max_retries = 0
            except ValueError:
                retries_input.add_class("error")
                return

        failure_value = failure_select.value
        failure_target = None
        if isinstance(failure_value, str) and failure_value:
            failure_target = failure_value

        phase_kwargs: dict[str, Any] = {
            "name": name,
            "description": desc_input.value.strip(),
            "icon": icon_input.value.strip(),
            "on_success": str(success_select.value) if success_select.value else "completed",
            "timeout": timeout,
            "max_retries": max_retries,
        }

        if failure_target:
            phase_kwargs["on_failure"] = failure_target

        self.dismiss(WorkflowPhase(**phase_kwargs))


class WorkflowEditorModal(ModalScreen[WorkflowDefinition | None]):
    """Modal for creating and editing custom workflow definitions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+shift+s", "save_as", "Save As"),
        Binding("ctrl+o", "import_workflow", "Import"),
        Binding("ctrl+e", "export_workflow", "Export"),
        # Phase list shortcuts
        Binding("ctrl+up", "move_phase_up", "Move Up", show=False),
        Binding("ctrl+down", "move_phase_down", "Move Down", show=False),
        Binding("delete", "remove_phase", "Remove", show=False),
        Binding("enter", "edit_phase", "Edit", show=False),
        Binding("e", "edit_phase", "Edit", show=False),
    ]

    DEFAULT_CSS = """
    WorkflowEditorModal {
        align: center middle;
    }

    #editor-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #editor-title {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        text-style: bold;
        background: $primary;
    }

    .tab-content {
        height: 1fr;
        padding: 1;
    }

    TabbedContent {
        height: 1fr;
    }

    ContentSwitcher {
        height: 1fr;
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

    #phase-list {
        height: 1fr;
        border: solid $surface-lighten-2;
        margin: 1 0;
    }

    .phase-actions {
        height: auto;
        margin-top: 1;
    }

    .error-message {
        color: $error;
        text-style: bold;
        margin: 1 0;
    }

    ListView:focus {
        border: solid $primary;
    }

    /* Phase List Row Styling */
    PhaseListItem {
        layout: horizontal;
        height: auto;
        padding: 0 1;  /* Reduced vertical padding */
        align-vertical: middle;
    }

    PhaseListItem Label {
        width: 1fr;
        content-align: left middle;
    }

    .row-buttons {
        width: auto;
        height: auto;
        align-horizontal: right;
    }

    .row-buttons Button {
        height: 1;
        width: 5;
        min-width: 5;
        margin: 0;
        padding: 0;
        border: none;
        background: transparent;
        color: $text;
        content-align: center middle;
    }

    .row-buttons Button:hover, .row-buttons Button:focus {
        background: $boost;
        color: $accent;
        border: none;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(
        self,
        workspace: Workspace | None = None,
        workflow: WorkflowDefinition | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.workspace = workspace or Workspace.load()
        self.service = WorkflowEditorService(self.workspace)

        # Either edit existing or create new
        if workflow:
            # Create a mutable copy since WorkflowDefinition is frozen
            self.workflow = workflow.model_copy(deep=True)
            self.is_new = False
        else:
            self.workflow = self.service.create_from_template("default")
            # Create a mutable copy and set name
            self.workflow = self.workflow.model_copy(deep=True)
            self.workflow.name = self.service.generate_unique_name("custom")
            self.is_new = True

        self.selected_phase: WorkflowPhase | None = None
        self.unsaved_changes = False

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Vertical(id="editor-container"):
            yield Static(f"⚙️ Workflow Editor: {self.workflow.name}", id="editor-title")

            with TabbedContent():
                with TabPane("General", id="tab-general"):
                    yield self._compose_general_tab()

                with TabPane("Phases", id="tab-phases"):
                    yield self._compose_phases_tab()

                with TabPane("Transitions", id="tab-transitions"):
                    yield self._compose_transitions_tab()

            # Button row
            yield Horizontal(
                Button("Cancel (Esc)", variant="error", id="btn-cancel"),
                Button("Import (Ctrl+O)", variant="primary", id="btn-import"),
                Button("Export (Ctrl+E)", variant="primary", id="btn-export"),
                Button("Save (Ctrl+S)", variant="success", id="btn-save"),
                classes="button-row",
            )

    def _compose_general_tab(self) -> Widget:
        """Compose the General tab content."""
        return Vertical(
            Label("Basic Information:", classes="section-label"),
            Horizontal(
                Label("Name:"),
                Input(
                    self.workflow.name,
                    placeholder="workflow_name",
                    id="workflow-name",
                ),
                classes="input-row",
            ),
            Horizontal(
                Label("Description:"),
                Input(
                    self.workflow.description,
                    placeholder="Describe this workflow...",
                    id="workflow-description",
                ),
                classes="input-row",
            ),
            Horizontal(
                Label("Initial State:"),
                Select(
                    [("idle", "idle")],
                    value=self.workflow.initial_state,
                    id="initial-state",
                    allow_blank=False,
                ),
                classes="input-row",
            ),
            Static("", id="general-error", classes="error-message"),
            classes="tab-content",
        )

    def _compose_phases_tab(self) -> Widget:
        """Compose the Phases tab content."""
        # Build phase list items
        phase_items = [PhaseListItem(p) for p in self.workflow.phases]

        return Vertical(
            Label("Workflow Phases:", classes="section-label"),
            ListView(*phase_items, id="phase-list"),
            # Global 'Add' button
            Horizontal(
                Button("Add Phase", variant="primary", id="btn-add-phase"),
                classes="dialog-buttons",  # Reuse right-aligned styling
            ),
            Label(
                "Info: Workflow starts in 'idle', then auto-transitions to the first phase.",
                classes="dim",
            ),
            Label(
                "Flow: 'On Success' triggers next phase. "
                "Terminal states ('completed'/error) reset to idle.",
                classes="dim",
            ),
            classes="tab-content",
        )

    def _compose_transitions_tab(self) -> Widget:
        """Compose the Transitions tab content."""
        # Build transition list
        transitions_text = self._build_transitions_text()

        return Vertical(
            Label("Workflow Transitions:", classes="section-label"),
            TextArea(transitions_text, read_only=True, id="transition-list"),
            Label(
                "Transitions are automatically generated from phase configurations.", classes="dim"
            ),
            classes="tab-content",
        )

    def _build_transitions_text(self) -> str:
        """Build text representation of transitions."""
        lines = []
        transitions = self.workflow.get_transitions()
        for t in transitions:
            source = t.get("source", "?")
            dest = t.get("dest", "?")
            trigger = t.get("trigger", "?")
            lines.append(f"{source} --[{trigger}]--> {dest}")
        return "\n".join(lines)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Mark unsaved changes when input changes."""
        event.input.remove_class("error")
        self.unsaved_changes = True

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle phase selection."""
        if isinstance(event.item, PhaseListItem):
            self.selected_phase = event.item.phase

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        if self.unsaved_changes:
            # For v1.0, directly dismiss without confirmation
            # Future: Add confirmation modal for unsaved changes
            pass
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the workflow."""
        self._save_workflow()

    def action_save_as(self) -> None:
        """Save workflow with a new name."""
        # For v1.0, not implemented
        # Future: Prompt user for new name and save
        pass

    def action_import_workflow(self) -> None:
        """Import workflow from file."""
        # For v1.0, not implemented
        # Future: Open file dialog and import workflow JSON/YAML
        pass

    def action_export_workflow(self) -> None:
        """Export workflow to file."""
        # For v1.0, not implemented
        # Future: Open file dialog and export workflow to JSON/YAML
        pass

    def _save_workflow(self) -> None:
        """Save the current workflow."""
        # Update workflow from form fields
        name_input = self.query_one("#workflow-name", Input)
        self.workflow.name = name_input.value.strip()

        desc_input = self.query_one("#workflow-description", Input)
        self.workflow.description = desc_input.value.strip()

        # Validate
        errors = self.service.validate_workflow(self.workflow)
        if errors:
            error_widget = self.query_one("#general-error", Static)
            error_widget.update("\n".join(f"• {e}" for e in errors))
            return

        try:
            self.service.save_workflow(self.workflow)
            self.unsaved_changes = False
            self.notify(
                f"Workflow '{self.workflow.name}' saved successfully", severity="information"
            )
            self.dismiss(self.workflow)
        except WorkflowValidationError as e:
            error_widget = self.query_one("#general-error", Static)
            error_widget.update("\n".join(f"• {err}" for err in e.errors))
        except Exception as e:
            self.notify(f"Error saving workflow: {e}", severity="error")

    # Removed _update_state_selectors as it is now handled in PhaseEditorModal

    def _add_phase(self) -> None:
        """Add a new phase to the workflow."""
        existing_names = [p.name for p in self.workflow.phases]
        states = self.workflow.get_states()

        def _on_phase_created(phase: WorkflowPhase | None) -> None:
            if phase:
                phases_list = list(self.workflow.phases)
                phases_list.append(phase)
                self.workflow.phases = phases_list
                self.unsaved_changes = True
                self._refresh_phase_list()
                self._refresh_transitions_tab()

        self.app.push_screen(
            PhaseEditorModal(existing_names=existing_names, available_states=states),
            _on_phase_created,
        )

    def _edit_phase(self, phase: WorkflowPhase) -> None:
        """Open phase editor for selected phase."""
        existing_names = [p.name for p in self.workflow.phases]
        states = self.workflow.get_states()

        def _on_phase_edited(updated_phase: WorkflowPhase | None) -> None:
            if updated_phase:
                phases_list = list(self.workflow.phases)
                # Find and replace
                for i, p in enumerate(phases_list):
                    if p.name == phase.name:  # Use original name to find, or index
                        phases_list[i] = updated_phase
                        break
                    # Fallback check if name changed but object identity matches
                    # (unlikely in this flow)
                    if p == phase:
                        phases_list[i] = updated_phase
                        break

                self.workflow.phases = phases_list
                self.unsaved_changes = True
                self.selected_phase = updated_phase
                self._refresh_phase_list()
                self._refresh_transitions_tab()

        self.app.push_screen(
            PhaseEditorModal(phase=phase, existing_names=existing_names, available_states=states),
            _on_phase_edited,
        )

    def _refresh_phase_list(self) -> None:
        """Refresh the phase list view."""
        list_view = self.query_one("#phase-list", ListView)
        # Store index to restore selection if possible
        old_index = list_view.index

        list_view.clear()
        for phase in self.workflow.phases:
            item = PhaseListItem(phase)
            list_view.append(item)

        # Restore selection if valid
        if old_index is not None and 0 <= old_index < len(self.workflow.phases):
            list_view.index = old_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self._save_workflow()
        elif button_id == "btn-import":
            self.action_import_workflow()
        elif button_id == "btn-export":
            self.action_export_workflow()
        elif button_id == "btn-add-phase":
            self._add_phase()

        # Handle row buttons
        elif (
            event.button.has_class("btn-row-up")
            or event.button.has_class("btn-row-down")
            or event.button.has_class("btn-row-edit")
            or event.button.has_class("btn-row-remove")
        ):
            # Find the parent PhaseListItem
            item = None
            node = event.button
            while node:
                if isinstance(node, PhaseListItem):
                    item = node
                    break
                node = node.parent

            if item:
                # Select this item first to ensure actions work on the right item
                list_view = self.query_one("#phase-list", ListView)
                list_view.index = list_view.children.index(item)

                # Force update selected_phase immediately, as on_highlighted might be async
                self.selected_phase = item.phase

                if event.button.has_class("btn-row-edit"):
                    self.action_edit_phase()
                elif event.button.has_class("btn-row-remove"):
                    self.action_remove_phase()
                elif event.button.has_class("btn-row-up"):
                    self.action_move_phase_up()
                elif event.button.has_class("btn-row-down"):
                    self.action_move_phase_down()

    def action_move_phase_up(self) -> None:
        """Move the selected phase up."""
        if not self.selected_phase:
            return
        self._move_phase_up()

    def action_move_phase_down(self) -> None:
        """Move the selected phase down."""
        if not self.selected_phase:
            return
        self._move_phase_down()

    def action_edit_phase(self) -> None:
        """Edit the selected phase."""
        if not self.selected_phase:
            return
        self._edit_phase(self.selected_phase)

    def action_remove_phase(self) -> None:
        """Remove the selected phase."""
        if not self.selected_phase:
            return
        self._remove_phase(self.selected_phase)

    def _move_phase_up(self) -> None:
        """Move the selected phase up in the list."""
        if not self.selected_phase:
            return

        phases = list(self.workflow.phases)
        if self.selected_phase not in phases:
            return

        idx = phases.index(self.selected_phase)
        if idx > 0:
            phases[idx], phases[idx - 1] = phases[idx - 1], phases[idx]
            self.workflow.phases = phases
            self.unsaved_changes = True
            self._refresh_phase_list()
            # Restore selection
            self.query_one("#phase-list", ListView).index = idx - 1

    def _move_phase_down(self) -> None:
        """Move the selected phase down in the list."""
        if not self.selected_phase:
            return

        phases = list(self.workflow.phases)
        if self.selected_phase not in phases:
            return

        idx = phases.index(self.selected_phase)
        if idx < len(phases) - 1:
            phases[idx], phases[idx + 1] = phases[idx + 1], phases[idx]
            self.workflow.phases = phases
            self.unsaved_changes = True
            self._refresh_phase_list()
            # Restore selection
            self.query_one("#phase-list", ListView).index = idx + 1

    def _remove_phase(self, phase: WorkflowPhase) -> None:
        """Remove a phase from the workflow."""
        phases_list = [p for p in self.workflow.phases if p != phase]
        self.workflow.phases = phases_list
        self.unsaved_changes = True
        self.selected_phase = None
        self._refresh_phase_list()
        self._refresh_transitions_tab()

    def _refresh_transitions_tab(self) -> None:
        """Refresh the transitions tab content."""
        try:
            text_area = self.query_one("#transition-list", TextArea)
            transitions_text = self._build_transitions_text()
            text_area.load_text(transitions_text)
        except Exception:
            # Widget might not be mounted yet or not found
            pass
