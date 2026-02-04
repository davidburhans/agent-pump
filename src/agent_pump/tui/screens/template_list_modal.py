"""Modal for browsing and selecting project templates."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from agent_pump.models.template import ProjectTemplate
from agent_pump.models.workspace import Workspace


class TemplateListModal(ModalScreen[ProjectTemplate | None]):
    """Modal for browsing and selecting project templates.

    Displays a list of available templates (built-in and user-defined)
    with details panel showing configuration information.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
    ]

    DEFAULT_CSS = """
    TemplateListModal {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: 30;
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

    #template-list-container {
        width: 40;
        height: 100%;
    }

    #template-list {
        width: 100%;
        height: 1fr;
    }

    #template-details {
        width: 1fr;
        height: 100%;
        padding: 0 2;
    }

    #details-title {
        text-style: bold;
        margin-bottom: 1;
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

    #empty-state {
        text-align: center;
        color: $text-muted;
        height: 100%;
        content-align: center middle;
    }

    #button-row {
        margin-top: 1;
        align: right middle;
    }

    #button-row Button {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        templates: list[ProjectTemplate],
        workspace: Workspace | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the template list modal.

        Args:
            templates: List of templates to display.
            workspace: Optional workspace for context.
            name: Optional name for the modal.
            id: Optional id for the modal.
            classes: Optional classes for the modal.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.templates = templates
        self.workspace = workspace
        self._selected_template: ProjectTemplate | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="dialog"):
            yield Label("Project Templates", id="title")

            with Horizontal(id="content"):
                # Left side: Template list
                with Vertical(id="template-list-container"):
                    if self.templates:
                        table = DataTable(id="template-list")
                        table.cursor_type = "row"
                        yield table
                    else:
                        yield Static("No templates available", id="empty-state")

                # Right side: Template details
                with Vertical(id="template-details"):
                    yield Label("Select a template", id="details-title")
                    yield Static("", id="details-content")

            # Bottom: Action buttons
            with Horizontal(id="button-row"):
                yield Button(
                    "Apply to Selected Project",
                    id="btn-apply",
                    variant="success",
                    disabled=True,
                )
                yield Button(
                    "Create New Project",
                    id="btn-create",
                    variant="primary",
                    disabled=True,
                )
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        if self.templates:
            table = self.query_one("#template-list", DataTable)
            table.add_columns("Name", "Category", "Description")

            for template in self.templates:
                category_badge = self._get_category_badge(template.category)
                desc = (
                    template.description[:30] + "..."
                    if len(template.description) > 30
                    else template.description
                )
                table.add_row(
                    template.name,
                    category_badge,
                    desc or "No description",
                    key=template.name,
                )

            # Select first row by default
            if table.row_count > 0:
                # Move cursor to first row using coordinate
                from textual.coordinate import Coordinate

                table.cursor_coordinate = Coordinate(0, 0)
                self._update_selection()

    def _get_category_badge(self, category: str) -> str:
        """Get display badge for template category.

        Args:
            category: Template category (built-in, user, custom).

        Returns:
            Formatted category badge.
        """
        badges = {
            "built-in": "[ Built-in ]",
            "user": "[ User ]",
            "custom": "[ Custom ]",
        }
        return badges.get(category, f"[ {category} ]")

    def _update_selection(self) -> None:
        """Update the selected template and details view."""
        table = self.query_one("#template-list", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            # Get the template name from the row key
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if row_key:
                template_name = str(row_key.value)
                self._selected_template = next(
                    (t for t in self.templates if t.name == template_name),
                    None,
                )
                self._update_details()
                self._update_buttons()

    def _update_details(self) -> None:
        """Update the details panel with selected template info."""
        details_title = self.query_one("#details-title", Label)
        details_content = self.query_one("#details-content", Static)

        if self._selected_template:
            template = self._selected_template
            details_title.update(template.name)

            config = template.config
            content_lines = [
                f"[b]Description:[/b] {template.description or 'No description'}",
                "",
                f"[b]Category:[/b] {template.category}",
                f"[b]Backend:[/b] {config.backend}",
                f"[b]Workflow:[/b] {config.workflow_name}",
                f"[b]Max Iterations:[/b] {config.workflow_max_iterations}",
                f"[b]Timeout:[/b] {config.workflow_timeout}s",
                "",
            ]

            if template.tags:
                content_lines.append(f"[b]Tags:[/b] {', '.join(template.tags)}")

            if template.author:
                content_lines.append(f"[b]Author:[/b] {template.author}")

            content_lines.append(f"[b]Version:[/b] {template.version}")

            # Verification commands
            if config.verification:
                content_lines.append("")
                content_lines.append("[b]Verification Commands:[/b]")
                if config.verification.build_cmd:
                    content_lines.append(f"  Build: {config.verification.build_cmd}")
                if config.verification.lint_cmd:
                    content_lines.append(f"  Lint: {config.verification.lint_cmd}")
                if config.verification.test_cmd:
                    content_lines.append(f"  Test: {config.verification.test_cmd}")

            details_content.update("\n".join(content_lines))
        else:
            details_title.update("Select a template")
            details_content.update("")

    def _update_buttons(self) -> None:
        """Update button states based on selection."""
        has_selection = self._selected_template is not None

        apply_btn = self.query_one("#btn-apply", Button)
        create_btn = self.query_one("#btn-create", Button)

        apply_btn.disabled = not has_selection
        create_btn.disabled = not has_selection

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in template list."""
        self._update_selection()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight in template list."""
        self._update_selection()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.dismiss(None)
        elif button_id == "btn-apply" and self._selected_template:
            # Dismiss with selected template for applying to existing project
            self._selected_template.is_new_project = False  # type: ignore
            self.dismiss(self._selected_template)
        elif button_id == "btn-create" and self._selected_template:
            # Dismiss with selected template for creating new project
            self._selected_template.is_new_project = True  # type: ignore
            self.dismiss(self._selected_template)

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Handle select action (Enter key)."""
        if self._selected_template:
            # Default to apply mode
            self._selected_template.is_new_project = False  # type: ignore
            self.dismiss(self._selected_template)

    def get_selected_template(self) -> ProjectTemplate | None:
        """Get the currently selected template.

        Returns:
            The selected template, or None if no selection.
        """
        return self._selected_template
