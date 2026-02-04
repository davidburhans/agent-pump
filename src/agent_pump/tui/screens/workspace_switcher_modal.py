"""Modal screen for switching workspaces."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListItem, ListView, Static


class WorkspaceSwitcherModal(ModalScreen[str | None]):
    """A modal screen for switching between workspaces."""

    DEFAULT_CSS = """
    WorkspaceSwitcherModal {
        align: center middle;
    }

    #modal-container {
        width: 60%;
        min-width: 40;
        max-width: 80;
        height: auto;
        max-height: 70%;
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

    #workspace-list {
        height: auto;
        max-height: 20;
        border: solid $primary-muted;
        margin-bottom: 1;
    }

    ListItem {
        padding: 1;
    }

    ListItem:hover {
        background: $primary-muted;
    }

    ListItem.current {
        background: $success-muted;
    }

    ListItem.current Static {
        text-style: bold;
    }

    #current-indicator {
        color: $success;
        margin-left: 1;
    }

    .button-row {
        height: 3;
        align: center middle;
    }

    .button-row Button {
        margin: 0 1;
    }

    #empty-message {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }

    #help-text {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
        height: auto;
    }

    #create-section {
        height: auto;
        margin-bottom: 1;
        display: none;
    }

    #create-section.visible {
        display: block;
    }

    #create-error {
        color: $error;
        height: auto;
        margin-top: 0;
    }

    #create-input {
        margin-bottom: 1;
    }
    """

    def __init__(self, workspaces: list[str], current: str):
        """
        Initialize the workspace switcher.

        Args:
            workspaces: List of available workspace names.
            current: The name of the currently active workspace.
        """
        super().__init__()
        self.workspaces = workspaces
        self.current = current

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        yield Container(
            Static("Switch Workspace", id="modal-title"),
            Static("Select a workspace to switch to:", id="help-text"),
            ListView(id="workspace-list"),
            Vertical(
                Static("Enter new workspace name:", id="create-label"),
                Input(placeholder="workspace name...", id="create-input"),
                Static("", id="create-error"),
                Horizontal(
                    Button("Cancel", variant="error", id="btn-cancel-create"),
                    Button("Create", variant="success", id="btn-create-submit"),
                    classes="button-row",
                ),
                id="create-section",
            ),
            Horizontal(
                Button("Cancel", variant="error", id="btn-cancel"),
                Button("Create New", variant="primary", id="btn-create"),
                classes="button-row",
            ),
            id="modal-container",
        )

    def on_mount(self) -> None:
        """Populate the workspace list on mount."""
        list_view = self.query_one("#workspace-list", ListView)

        if not self.workspaces:
            # Show empty state
            list_view.mount(
                Static("No workspaces found. Create one to get started.", id="empty-message")
            )
        else:
            # Add workspace items
            for workspace_name in sorted(self.workspaces):
                is_current = workspace_name == self.current
                item = self._create_workspace_item(workspace_name, is_current)
                list_view.append(item)

    def _create_workspace_item(self, name: str, is_current: bool) -> ListItem:
        """Create a ListItem for a workspace."""
        if is_current:
            content = Horizontal(
                Static(f"● {name}", classes="workspace-name"),
                Static(" (current)", id="current-indicator"),
            )
            item = ListItem(content, id=f"workspace-{name}")
            item.add_class("current")
        else:
            content = Static(f"  {name}", classes="workspace-name")
            item = ListItem(content, id=f"workspace-{name}")

        return item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle workspace selection."""
        item = event.item
        # Extract workspace name from the item id
        if item.id and item.id.startswith("workspace-"):
            workspace_name = item.id.replace("workspace-", "")
            # Don't switch if already current
            if workspace_name == self.current:
                self.dismiss(None)
            else:
                self.dismiss(workspace_name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-create":
            self._show_create_section()
        elif event.button.id == "btn-cancel-create":
            self._hide_create_section()
        elif event.button.id == "btn-create-submit":
            self._handle_create_workspace()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "create-input":
            self._handle_create_workspace()

    def _show_create_section(self) -> None:
        """Show the create workspace input section."""
        create_section = self.query_one("#create-section")
        create_section.add_class("visible")
        self.query_one("#create-input").focus()

        # Hide the main button row while creating
        for btn_row in self.query(".button-row"):
            if btn_row.id != "create-section":
                btn_row.display = False

    def _hide_create_section(self) -> None:
        """Hide the create workspace input section."""
        create_section = self.query_one("#create-section")
        create_section.remove_class("visible")

        # Show the main button row again
        for btn_row in self.query(".button-row"):
            if btn_row.id != "create-section":
                btn_row.display = True

        # Clear error
        error_label = self.query_one("#create-error", Static)
        error_label.update("")

    def _handle_create_workspace(self) -> None:
        """Handle creating a new workspace."""
        input_widget = self.query_one("#create-input", Input)
        name = input_widget.value.strip()

        # Validate name
        if not name:
            self._show_create_error("Workspace name cannot be empty")
            return

        # Check if name already exists
        if name in self.workspaces:
            self._show_create_error(f"Workspace '{name}' already exists")
            return

        # Valid name - dismiss with the new workspace name
        # The app will handle the creation
        self.dismiss(name)

    def _show_create_error(self, message: str) -> None:
        """Show an error message in the create section."""
        error_label = self.query_one("#create-error", Static)
        error_label.update(message)
        self.query_one("#create-input").focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle highlighting for accessibility."""
        if event.item:
            # Ensure the highlighted item is visible
            event.item.scroll_visible()
