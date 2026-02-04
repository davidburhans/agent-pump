"""Modal screen for bootstrapping a project with AI-generated documentation."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DirectoryTree, Input, Label, Select, Static

from agent_pump.services.bootstrap_service import BootstrapService
from agent_pump.tui.animation import shake


class BootstrapModal(ModalScreen[tuple[Path, str, bool] | None]):
    """A modal screen for bootstrapping projects with AI-generated documentation.

    Allows users to select a project directory, choose an AI backend,
    and optionally run in dry-run mode to preview what would be generated.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    BootstrapModal {
        align: center middle;
    }

    #modal-container {
        width: 70%;
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

    #content-area {
        height: 1fr;
    }

    #left-panel {
        width: 50%;
        height: 100%;
    }

    #right-panel {
        width: 50%;
        height: 100%;
        padding-left: 1;
    }

    #path-section {
        height: auto;
        margin-bottom: 1;
    }

    #path-input {
        width: 1fr;
    }

    #dir-tree {
        height: 1fr;
        border: solid $primary-muted;
        margin-bottom: 1;
    }

    #options-section {
        height: auto;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
    }

    #backend-select {
        width: 100%;
        margin-bottom: 1;
    }

    #dry-run-checkbox {
        margin-top: 1;
    }

    #preview-section {
        height: 1fr;
        border: solid $primary-muted;
        padding: 1;
        background: $surface-darken-1;
    }

    #preview-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #preview-content {
        height: 1fr;
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
        text-style: bold;
    }

    #button-row {
        height: auto;
        margin-top: 1;
        align: center middle;
    }

    #button-row Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        initial_path: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the bootstrap modal.

        Args:
            initial_path: Optional initial path to display.
            name: Optional name for the modal.
            id: Optional id for the modal.
            classes: Optional classes for the modal.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._selected_path = initial_path
        self._analysis_result: dict | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Vertical(id="modal-container"):
            yield Static("Bootstrap Project", id="modal-title")

            with Horizontal(id="content-area"):
                # Left panel: Directory selection
                with Vertical(id="left-panel"):
                    yield Label("Select project directory:")
                    with Horizontal(id="path-section"):
                        yield Input(
                            placeholder="Path to project...",
                            id="path-input",
                            value=str(self._selected_path) if self._selected_path else "",
                        )
                    yield Label("", id="error-label")
                    yield DirectoryTree(
                        str(self._selected_path.parent) if self._selected_path else "./",
                        id="dir-tree",
                    )

                # Right panel: Options and preview
                with Vertical(id="right-panel"):
                    with Vertical(id="options-section"):
                        yield Label("AI Backend:")
                        yield Select(
                            [
                                ("Gemini", "gemini"),
                                ("Claude", "claude"),
                                ("Qwen", "qwen"),
                                ("OpenCode", "opencode"),
                            ],
                            value="gemini",
                            id="backend-select",
                        )
                        yield Checkbox(
                            "Dry run (preview only, don't write files)",
                            id="dry-run-checkbox",
                        )

                    with Vertical(id="preview-section"):
                        yield Static("Project Analysis", id="preview-title")
                        yield Static(
                            "Select a directory to see project analysis...",
                            id="preview-content",
                        )

            yield Label("", id="status-label")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="error", id="btn-cancel")
                yield Button("Preview", variant="primary", id="btn-preview")
                yield Button("Bootstrap", variant="success", id="btn-bootstrap")

    def on_mount(self) -> None:
        """Focus the input field on mount."""
        self.query_one("#path-input", Input).focus()

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Update the input field and analyze when a directory is selected."""
        path_str = str(event.path)
        self.query_one("#path-input", Input).value = path_str
        self._selected_path = Path(path_str)
        self._analyze_project()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Clear errors when input changes."""
        if event.input.id == "path-input":
            event.input.remove_class("error")
            self._clear_error()
            path_str = event.input.value.strip()
            if path_str:
                self._selected_path = Path(path_str)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "path-input":
            self._analyze_project()

    def _analyze_project(self) -> None:
        """Analyze the selected project and update preview."""
        if not self._selected_path:
            return

        try:
            # Create a temporary service to analyze project
            service = BootstrapService(None)  # type: ignore[arg-type]
            analysis = service.analyze_project_structure(self._selected_path)

            # Update preview
            preview_text = self._format_analysis(analysis)
            preview_widget = self.query_one("#preview-content", Static)
            preview_widget.update(preview_text)

            self._clear_error()
        except Exception as e:
            self._show_error(f"Cannot analyze: {e}")

    def _format_analysis(self, analysis) -> str:
        """Format project analysis for display.

        Args:
            analysis: ProjectAnalysis object.

        Returns:
            Formatted string for display.
        """
        lines = [
            f"Type: {analysis.project_type}",
            f"Language: {analysis.language}",
        ]
        if analysis.framework:
            lines.append(f"Framework: {analysis.framework}")
        lines.extend(
            [
                f"",
                f"Key files: {len(analysis.key_files)}",
                f"Has tests: {'Yes' if analysis.has_tests else 'No'}",
                f"Has docs: {'Yes' if analysis.has_docs else 'No'}",
                f"Has CI/CD: {'Yes' if analysis.has_ci else 'No'}",
            ]
        )
        if analysis.key_files:
            lines.append(f"\nDetected files:")
            for f in analysis.key_files[:5]:  # Show max 5
                lines.append(f"  - {f}")
            if len(analysis.key_files) > 5:
                lines.append(f"  ... and {len(analysis.key_files) - 5} more")

        return "\n".join(lines)

    def _get_backend(self) -> str:
        """Get the selected backend value.

        Returns:
            Backend string identifier.
        """
        select = self.query_one("#backend-select", Select)
        value = select.value
        if isinstance(value, str):
            return value
        return "gemini"  # Default fallback

    def _is_dry_run(self) -> bool:
        """Check if dry-run mode is enabled.

        Returns:
            True if dry-run is checked.
        """
        checkbox = self.query_one("#dry-run-checkbox", Checkbox)
        return checkbox.value

    def _validate_and_bootstrap(self, preview_only: bool = False) -> bool:
        """Validate inputs and perform bootstrap.

        Args:
            preview_only: If True, only analyze and show preview.

        Returns:
            True if successful, False otherwise.
        """
        path_input = self.query_one("#path-input", Input)
        path_str = path_input.value.strip()

        if not path_str:
            self._show_error("Please enter or select a project path")
            return False

        path = Path(path_str).resolve()

        if not path.exists():
            self._show_error(f"Path does not exist: {path}")
            return False

        if not path.is_dir():
            self._show_error(f"Path is not a directory: {path}")
            return False

        self._clear_error()

        if preview_only:
            self._show_status("Analyzing project...")
            self._analyze_project()
            self._clear_status()
            return True

        backend = self._get_backend()
        dry_run = self._is_dry_run()

        # Dismiss with the selected options
        self.dismiss((path, backend, dry_run))
        return True

    def _show_error(self, message: str) -> None:
        """Show error message.

        Args:
            message: Error message to display.
        """
        error_label = self.query_one("#error-label", Label)
        error_label.update(message)
        error_label.add_class("visible")

        input_widget = self.query_one("#path-input", Input)
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn-cancel":
            self.dismiss(None)
        elif button_id == "btn-preview":
            self._validate_and_bootstrap(preview_only=True)
        elif button_id == "btn-bootstrap":
            self._validate_and_bootstrap(preview_only=False)

    def action_cancel(self) -> None:
        """Handle cancel action."""
        self.dismiss(None)
