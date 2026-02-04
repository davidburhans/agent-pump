"""Modal for applying templates to projects."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from agent_pump.models.template import ProjectTemplate
from agent_pump.services.template_service import TemplateService
from agent_pump.tui.animation import shake


class TemplateApplyModal(ModalScreen[Path | None]):
    """Modal for applying a template to an existing or new project.

    Allows users to apply a selected template to an existing project
    or create a new project from the template.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    TemplateApplyModal {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #template-info {
        margin-bottom: 1;
        padding: 1;
        background: $surface-darken-1;
    }

    #project-path-section {
        margin: 1 0;
    }

    #path-label {
        margin-bottom: 1;
    }

    #project-input {
        width: 100%;
    }

    #error-label {
        color: $error;
        height: auto;
        min-height: 1;
        margin-top: 0;
        margin-bottom: 0;
        display: none;
    }

    #error-label.visible {
        display: block;
    }

    #status-label {
        margin: 1 0;
        text-align: center;
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
        template: ProjectTemplate,
        existing_project: Path | None = None,
        is_new_project: bool = False,
        template_service: TemplateService | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the template apply modal.

        Args:
            template: The template to apply.
            existing_project: Path to existing project (if applying to existing).
            is_new_project: Whether creating a new project from template.
            template_service: Optional template service for applying templates.
            name: Optional name for the modal.
            id: Optional id for the modal.
            classes: Optional classes for the modal.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.template = template
        self.existing_project = existing_project
        self.is_new_project = is_new_project
        self.template_service = template_service
        self._new_project_path: Path | None = None
        self._is_applying = False

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        with Vertical(id="dialog"):
            yield Label(
                f"Apply Template: {self.template.name}",
                id="title",
            )

            # Template info section
            with Static(id="template-info"):
                yield Label(f"Description: {self.template.description or 'No description'}")
                yield Label(f"Backend: {self.template.config.backend}")
                yield Label(f"Category: {self.template.category}")

            # Project path section
            with Vertical(id="project-path-section"):
                if self.is_new_project:
                    yield Label("Enter path for new project:", id="path-label")
                    yield Input(
                        placeholder="/path/to/new-project",
                        id="project-input",
                    )
                elif self.existing_project:
                    yield Label(
                        f"Apply to existing project: {self.existing_project}",
                        id="path-label",
                    )
                else:
                    yield Label("Enter project path:", id="path-label")
                    yield Input(
                        placeholder="/path/to/project",
                        id="project-input",
                    )

            yield Label("", id="error-label")
            yield Label("", id="status-label")

            # Action buttons
            with Horizontal(id="button-row"):
                if self.is_new_project:
                    yield Button(
                        "Create Project",
                        id="btn-apply",
                        variant="success",
                    )
                else:
                    yield Button(
                        "Apply Template",
                        id="btn-apply",
                        variant="success",
                    )
                yield Button("Cancel", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        """Called when modal is mounted."""
        if self.is_new_project:
            # Focus the input for new project
            input_widget = self.query_one("#project-input", Input)
            input_widget.focus()

    def _is_valid_path(self, path_str: str) -> bool:
        """Check if a path string is valid.

        Args:
            path_str: Path string to validate.

        Returns:
            True if path is valid, False otherwise.
        """
        if not path_str or not path_str.strip():
            return False
        return True

    def _is_valid_new_project_path(self, path_str: str) -> bool:
        """Check if path is valid for new project creation.

        Args:
            path_str: Path string to validate.

        Returns:
            True if path is valid and doesn't exist, False otherwise.
        """
        if not self._is_valid_path(path_str):
            return False

        path = Path(path_str.strip())
        if path.exists():
            return False

        return True

    def _show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message to display.
        """
        error_label = self.query_one("#error-label", Label)
        error_label.update(message)
        error_label.add_class("visible")

        # Shake animation on input
        if self.is_new_project or not self.existing_project:
            input_widget = self.query_one("#project-input", Input)
            shake(input_widget)

    def _clear_error(self) -> None:
        """Clear error message."""
        error_label = self.query_one("#error-label", Label)
        error_label.update("")
        error_label.remove_class("visible")

    def _show_status(self, message: str) -> None:
        """Show status message.

        Args:
            message: Status message to display.
        """
        status_label = self.query_one("#status-label", Label)
        status_label.update(message)

    def _clear_status(self) -> None:
        """Clear status message."""
        status_label = self.query_one("#status-label", Label)
        status_label.update("")

    def _apply_template(self) -> bool:
        """Apply the template to the project.

        Returns:
            True if application was successful, False otherwise.
        """
        if self._is_applying:
            return False

        self._is_applying = True
        self._clear_error()

        try:
            # Determine project path
            if self.is_new_project:
                input_widget = self.query_one("#project-input", Input)
                path_str = input_widget.value.strip()

                if not self._is_valid_new_project_path(path_str):
                    self._show_error(f"Invalid or existing path: {path_str}")
                    self._is_applying = False
                    return False

                project_path = Path(path_str).resolve()
                self._new_project_path = project_path

                if self.template_service:
                    self._show_status("Creating project from template...")
                    success = self.template_service.create_project_from_template(
                        self.template, project_path
                    )
                else:
                    # No service available, just dismiss with path
                    self.dismiss(project_path)
                    return True

            else:
                # Apply to existing project
                if self.existing_project:
                    project_path = self.existing_project
                else:
                    input_widget = self.query_one("#project-input", Input)
                    path_str = input_widget.value.strip()

                    if not self._is_valid_path(path_str):
                        self._show_error("Please enter a valid project path")
                        self._is_applying = False
                        return False

                    project_path = Path(path_str).resolve()

                if self.template_service:
                    self._show_status("Applying template...")
                    success = self.template_service.apply_template_to_project(
                        self.template, project_path
                    )
                else:
                    # No service available, just dismiss with path
                    self.dismiss(project_path)
                    return True

            if success:
                self.dismiss(project_path)
                return True
            else:
                self._show_error("Failed to apply template. Check logs for details.")
                self._is_applying = False
                return False

        except Exception as e:
            self._show_error(f"Error: {e}")
            self._is_applying = False
            return False

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        if event.input.id == "project-input":
            self._clear_error()
            event.input.remove_class("error")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "project-input":
            self._apply_template()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.dismiss(None)
        elif button_id == "btn-apply":
            self._apply_template()

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)
