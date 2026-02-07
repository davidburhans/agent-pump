"""Modal screen for selecting a workflow for a project.

Displays a list of available workflows with a details panel showing
phase information and description.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow_definition import WorkflowDefinition, list_workflows


class WorkflowSelectModal(ModalScreen[str | None]):
    """Modal for browsing and selecting a workflow for a project.

    Displays a list of available workflows with a details panel
    showing phase count, description, and other workflow information.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
    ]

    DEFAULT_CSS = """
    WorkflowSelectModal {
        align: center middle;
    }

    #dialog {
        width: 85;
        height: 35;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #content {
        height: 1fr;
    }

    #workflow-list-container {
        width: 35;
        height: 100%;
    }

    #workflow-list {
        width: 100%;
        height: 1fr;
    }

    #workflow-details {
        width: 1fr;
        height: 100%;
        padding: 0 2;
        border-left: solid $primary-muted;
    }

    #details-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    #details-content {
        height: 1fr;
    }

    .detail-row {
        margin: 1 0;
    }

    .detail-label {
        text-style: bold;
        color: $text-muted;
    }

    .phase-list {
        margin-left: 2;
        color: $text;
    }

    #current-indicator {
        color: $success;
        margin-left: 1;
    }

    #empty-state {
        text-align: center;
        color: $text-muted;
        height: 100%;
        content-align: center middle;
    }

    #button-row {
        margin-top: 1;
        align: right middle;
        height: 3;
    }

    #button-row Button {
        margin-left: 1;
    }

    #confirmation-text {
        color: $warning;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        workspace: Workspace,
        current_workflow_name: str = "default",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the workflow select modal.

        Args:
            workspace: The workspace containing workflow definitions.
            current_workflow_name: The name of the currently selected workflow.
            name: Optional name for the modal.
            id: Optional id for the modal.
            classes: Optional classes for the modal.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.workspace = workspace
        self.current_workflow_name = current_workflow_name
        self._selected_workflow_name: str | None = None
        self._workflows: dict[str, WorkflowDefinition] = {}

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="dialog"):
            yield Label("Select Workflow", id="title")

            with Horizontal(id="content"):
                # Left side: Workflow list
                with Vertical(id="workflow-list-container"):
                    table = DataTable(id="workflow-list")
                    table.cursor_type = "row"
                    yield table

                # Right side: Workflow details
                with Vertical(id="workflow-details"):
                    yield Label("Select a workflow", id="details-title")
                    yield Static("", id="details-content")

            # Bottom: Action buttons
            with Horizontal(id="button-row"):
                yield Button(
                    "Select Workflow",
                    id="btn-select",
                    variant="success",
                    disabled=True,
                )
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        self._load_workflows()
        self._populate_workflow_list()

    def _load_workflows(self) -> None:
        """Load all available workflows into memory."""
        from agent_pump.orchestrator.workflow_definition import get_workflow

        workflow_names = list_workflows(self.workspace.workflow_definitions)

        for wf_name in workflow_names:
            try:
                workflow = get_workflow(wf_name, self.workspace.workflow_definitions)
                self._workflows[wf_name] = workflow
            except KeyError:
                # Skip workflows that can't be loaded
                continue

    def _populate_workflow_list(self) -> None:
        """Populate the workflow list table."""
        table = self.query_one("#workflow-list", DataTable)
        table.clear()
        table.add_columns("Name", "Phases")

        # Sort workflows: default first, then alphabetically
        sorted_names = sorted(
            self._workflows.keys(), key=lambda x: (0 if x == "default" else 1, x.lower())
        )

        for wf_name in sorted_names:
            workflow = self._workflows[wf_name]
            phase_count = len(workflow.phases)

            # Add row with workflow name as key
            table.add_row(
                wf_name,
                str(phase_count),
                key=wf_name,
            )

        # Select current workflow by default
        if self.current_workflow_name in self._workflows:
            self._select_workflow_row(self.current_workflow_name)
        elif table.row_count > 0:
            # Select first row if current not found
            from textual.coordinate import Coordinate

            table.cursor_coordinate = Coordinate(0, 0)
            self._update_selection()

    def _select_workflow_row(self, workflow_name: str) -> None:
        """Select a specific workflow row in the table."""
        table = self.query_one("#workflow-list", DataTable)

        # Find the row with this workflow name
        for row_idx in range(table.row_count):
            from textual.coordinate import Coordinate

            coord = Coordinate(row_idx, 0)
            cell_key = table.coordinate_to_cell_key(coord)
            if cell_key.row_key and str(cell_key.row_key.value) == workflow_name:
                table.cursor_coordinate = coord
                self._update_selection()
                break

    def _update_selection(self) -> None:
        """Update the selected workflow and details view."""
        table = self.query_one("#workflow-list", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            # Get the workflow name from the row key
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if row_key:
                workflow_name = str(row_key.value)
                self._selected_workflow_name = workflow_name
                self._update_details()
                self._update_buttons()

    def _update_details(self) -> None:
        """Update the details panel with selected workflow info."""
        details_title = self.query_one("#details-title", Label)
        details_content = self.query_one("#details-content", Static)

        if self._selected_workflow_name and self._selected_workflow_name in self._workflows:
            workflow = self._workflows[self._selected_workflow_name]

            # Build title with current indicator
            is_current = self._selected_workflow_name == self.current_workflow_name
            if is_current:
                details_title.update(f"{workflow.name} [Current]")
            else:
                details_title.update(workflow.name)

            # Build details content
            content_lines = []

            if workflow.description:
                content_lines.append(workflow.description)
                content_lines.append("")

            content_lines.append(f"[b]Phases:[/b] {len(workflow.phases)}")
            content_lines.append("")

            # List all phases with icons
            if workflow.phases:
                content_lines.append("[b]Workflow Phases:[/b]")
                for phase in workflow.phases:
                    icon = phase.icon or "●"
                    content_lines.append(f"  {icon} {phase.name}")
                    if phase.description:
                        content_lines.append(f"    [dim]{phase.description}[/dim]")
                content_lines.append("")

            # Show initial state
            content_lines.append(f"[b]Initial State:[/b] {workflow.initial_state}")

            # Show terminal states
            if workflow.terminal_states:
                content_lines.append(
                    f"[b]Terminal States:[/b] {', '.join(workflow.terminal_states)}"
                )

            # Add confirmation warning if different from current
            if not is_current:
                content_lines.append("")
                content_lines.append(
                    f"[yellow]Click 'Select Workflow' to change from "
                    f"'{self.current_workflow_name}' to '{self._selected_workflow_name}'[/yellow]"
                )

            details_content.update("\n".join(content_lines))
        else:
            details_title.update("Select a workflow")
            details_content.update("")

    def _update_buttons(self) -> None:
        """Update button states based on selection."""
        has_selection = self._selected_workflow_name is not None
        is_different = has_selection and self._selected_workflow_name != self.current_workflow_name

        select_btn = self.query_one("#btn-select", Button)
        # Enable button only if a different workflow is selected
        select_btn.disabled = not is_different

        if is_different:
            select_btn.label = f"Select '{self._selected_workflow_name}'"
        else:
            select_btn.label = "Select Workflow"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in workflow list."""
        self._update_selection()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight in workflow list."""
        self._update_selection()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.dismiss(None)
        elif button_id == "btn-select":
            self._handle_select()

    def _handle_select(self) -> None:
        """Handle workflow selection."""
        if (
            self._selected_workflow_name
            and self._selected_workflow_name != self.current_workflow_name
        ):
            self.dismiss(self._selected_workflow_name)
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Handle select action (Enter key)."""
        self._handle_select()

    def get_selected_workflow(self) -> str | None:
        """Get the currently selected workflow name.

        Returns:
            The selected workflow name, or None if no selection.
        """
        return self._selected_workflow_name
