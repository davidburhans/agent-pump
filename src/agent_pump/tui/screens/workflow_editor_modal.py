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
        self.phase = phase
        icon = phase.icon or "●"
        text = f"{icon} {phase.name}"
        if phase.description:
            text += f" - {phase.description}"
        super().__init__(Label(text), **kwargs)


class WorkflowEditorModal(ModalScreen[WorkflowDefinition | None]):
    """Modal for creating and editing custom workflow definitions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("ctrl+shift+s", "save_as", "Save As"),
        Binding("ctrl+o", "import_workflow", "Import"),
        Binding("ctrl+e", "export_workflow", "Export"),
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

    #phase-form {
        height: auto;
        border: solid $surface-lighten-2;
        padding: 1;
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
        with Container(id="editor-container"):
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
        phase_items = [
            PhaseListItem(p, id=f"phase-{i}") for i, p in enumerate(self.workflow.phases)
        ]

        return Vertical(
            Label("Workflow Phases (drag to reorder):", classes="section-label"),
            ListView(*phase_items, id="phase-list"),
            Horizontal(
                Button("Add Phase", variant="primary", id="btn-add-phase"),
                Button("Edit Phase", variant="primary", id="btn-edit-phase"),
                Button("Remove Phase", variant="error", id="btn-remove-phase"),
                classes="phase-actions",
            ),
            # Phase editing form (initially hidden)
            Vertical(
                Label("Phase Configuration:", classes="section-label"),
                Horizontal(
                    Label("Name:"),
                    Input(placeholder="phase_name", id="phase-name"),
                    classes="input-row",
                ),
                Horizontal(
                    Label("Description:"),
                    Input(placeholder="Description...", id="phase-description"),
                    classes="input-row",
                ),
                Horizontal(
                    Label("Icon:"),
                    Input(placeholder="📋", id="phase-icon"),
                    classes="input-row",
                ),
                Horizontal(
                    Label("On Success:"),
                    Select([], id="phase-on-success", allow_blank=False),
                    classes="input-row",
                ),
                Horizontal(
                    Label("On Failure:"),
                    Select([], id="phase-on-failure"),
                    classes="input-row",
                ),
                Horizontal(
                    Label("Timeout:"),
                    Input(
                        placeholder="seconds (optional)",
                        id="phase-timeout",
                        type="integer",
                    ),
                    classes="input-row",
                ),
                Horizontal(
                    Label("Max Retries:"),
                    Input(
                        placeholder="0",
                        id="phase-retries",
                        type="integer",
                    ),
                    classes="input-row",
                ),
                Horizontal(
                    Button("Save Phase", variant="success", id="btn-save-phase"),
                    Button("Cancel", variant="primary", id="btn-cancel-phase"),
                    classes="phase-actions",
                ),
                id="phase-form",
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
            # TODO: Show confirmation modal
            pass
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the workflow."""
        self._save_workflow()

    def action_save_as(self) -> None:
        """Save workflow with a new name."""
        # TODO: Prompt for new name
        pass

    def action_import_workflow(self) -> None:
        """Import workflow from file."""
        # TODO: Open file dialog
        pass

    def action_export_workflow(self) -> None:
        """Export workflow to file."""
        # TODO: Open file dialog
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

    def _edit_phase(self, phase: WorkflowPhase | None = None) -> None:
        """Open phase editor for selected or new phase."""
        # Show phase form
        form = self.query_one("#phase-form", Vertical)
        form.styles.display = "block"

        if phase:
            # Populate form with phase data
            name_input = self.query_one("#phase-name", Input)
            name_input.value = phase.name

            desc_input = self.query_one("#phase-description", Input)
            desc_input.value = phase.description

            icon_input = self.query_one("#phase-icon", Input)
            icon_input.value = phase.icon

            # Update state selectors
            self._update_state_selectors()

            success_select = self.query_one("#phase-on-success", Select)
            success_select.value = phase.on_success

            failure_select = self.query_one("#phase-on-failure", Select)
            failure_select.value = phase.on_failure if phase.on_failure else None

            timeout_input = self.query_one("#phase-timeout", Input)
            timeout_input.value = str(phase.timeout) if phase.timeout else ""

            retries_input = self.query_one("#phase-retries", Input)
            retries_input.value = str(phase.max_retries)

    def _update_state_selectors(self) -> None:
        """Update state selector options based on current workflow."""
        states = self.workflow.get_states()
        options = [(s, s) for s in states]

        success_select = self.query_one("#phase-on-success", Select)
        success_select.set_options(options)

        failure_select = self.query_one("#phase-on-failure", Select)
        failure_select.set_options([("", None)] + options)

    def _add_phase(self) -> None:
        """Add a new phase to the workflow."""
        new_phase = WorkflowPhase(
            name=f"phase_{len(self.workflow.phases) + 1}",
            on_success="completed",
            icon="●",
        )
        # Add to workflow phases list
        phases_list = list(self.workflow.phases)
        phases_list.append(new_phase)
        self.workflow.phases = phases_list
        self.unsaved_changes = True

        # Refresh phase list
        self._refresh_phase_list()
        self._edit_phase(new_phase)

    def _refresh_phase_list(self) -> None:
        """Refresh the phase list view."""
        list_view = self.query_one("#phase-list", ListView)
        list_view.clear()
        for i, phase in enumerate(self.workflow.phases):
            item = PhaseListItem(phase, id=f"phase-{i}")
            list_view.append(item)

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
        elif button_id == "btn-edit-phase":
            if self.selected_phase:
                self._edit_phase(self.selected_phase)
        elif button_id == "btn-remove-phase":
            if self.selected_phase:
                self._remove_phase(self.selected_phase)
        elif button_id == "btn-save-phase":
            self._save_current_phase()
        elif button_id == "btn-cancel-phase":
            self._cancel_phase_edit()

    def _remove_phase(self, phase: WorkflowPhase) -> None:
        """Remove a phase from the workflow."""
        phases_list = [p for p in self.workflow.phases if p != phase]
        self.workflow.phases = phases_list
        self.unsaved_changes = True
        self.selected_phase = None
        self._refresh_phase_list()

    def _save_current_phase(self) -> None:
        """Save the currently edited phase."""
        name_input = self.query_one("#phase-name", Input)
        name = name_input.value.strip()

        if not name:
            name_input.add_class("error")
            self._shake(name_input)
            return

        # Validate name is unique (unless editing same phase)
        for p in self.workflow.phases:
            if p.name == name and p != self.selected_phase:
                name_input.add_class("error")
                self.notify("Phase name must be unique", severity="error")
                return

        # Build updated phase
        desc_input = self.query_one("#phase-description", Input)
        icon_input = self.query_one("#phase-icon", Input)
        success_select = self.query_one("#phase-on-success", Select)
        failure_select = self.query_one("#phase-on-failure", Select)
        timeout_input = self.query_one("#phase-timeout", Input)
        retries_input = self.query_one("#phase-retries", Input)

        # Parse timeout
        timeout = None
        if timeout_input.value:
            try:
                timeout = int(timeout_input.value)
                if timeout <= 0:
                    timeout = None
            except ValueError:
                timeout_input.add_class("error")
                return

        # Parse retries
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

        # Build phase kwargs
        phase_kwargs: dict[str, Any] = {
            "name": name,
            "description": desc_input.value.strip(),
            "icon": icon_input.value.strip(),
            "on_success": str(success_select.value) if success_select.value else "completed",
            "timeout": timeout,
            "max_retries": max_retries,
        }

        # Only add on_failure if it's set (otherwise use default)
        if failure_target:
            phase_kwargs["on_failure"] = failure_target

        updated_phase = WorkflowPhase(**phase_kwargs)

        # Replace or add phase
        phases_list = list(self.workflow.phases)
        if self.selected_phase in phases_list:
            idx = phases_list.index(self.selected_phase)
            phases_list[idx] = updated_phase
        else:
            phases_list.append(updated_phase)

        self.workflow.phases = phases_list
        self.selected_phase = updated_phase
        self.unsaved_changes = True

        # Hide form and refresh
        form = self.query_one("#phase-form", Vertical)
        form.styles.display = "none"
        self._refresh_phase_list()
        self._refresh_transitions_tab()

    def _cancel_phase_edit(self) -> None:
        """Cancel phase editing."""
        form = self.query_one("#phase-form", Vertical)
        form.styles.display = "none"

    def _refresh_transitions_tab(self) -> None:
        """Refresh the transitions display."""
        transition_text = self.query_one("#transition-list", TextArea)
        transition_text.text = self._build_transitions_text()

    def _shake(self, widget: Widget) -> None:
        """Shake widget to indicate error."""
        offsets = [(2, 0), (-2, 0), (1, 0), (-1, 0), None]
        step_duration = 0.05

        def _step(i: int) -> None:
            if i >= len(offsets):
                return
            widget.styles.offset = offsets[i]  # type: ignore
            self.set_timer(step_duration, lambda: _step(i + 1))

        _step(0)
