"""Settings modal for Agent Pump configuration."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, Switch, TabbedContent, TabPane

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import Workspace


class SettingsModal(ModalScreen[bool]):
    """A modal dialog for configuring Agent Pump settings."""

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }

    #settings-container {
        width: 80%;
        max-width: 700;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        layout: grid;
        grid-size: 1 3;
        grid-rows: 3 1fr 3;
    }

    .title {
        text-style: bold;
        text-align: center;
        width: 100%;
        background: $primary;
        color: $text;
    }

    #settings-tabs {
        height: 100%;
        overflow-y: auto;
    }

    #tab-general {
        height: auto;
    }

    #tab-model-catalog {
        height: auto;
        overflow-y: auto;
    }

    .model-list-scroll {
        height: auto;
        overflow-y: auto;
    }

    .backend-label {
        text-style: bold;
        color: $text;
        margin-top: 1;
        margin-bottom: 0;
    }

    .model-list-container {
        height: 5;
        overflow-y: auto;
        padding: 0 1;
        border: solid $primary-darken-2;
        margin-bottom: 0;
    }

    .model-row {
        height: auto;
    }

    .model-name {
        color: $text;
        width: 1fr;
    }

    .no-models-text {
        color: $text-muted;
        height: 3;
    }

    .help-text {
        color: $text-muted;
        margin-bottom: 1;
    }

    .button-row {
        align: center middle;
    }
    """

    def __init__(self, workspace: Workspace, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self._safe_id_to_backend_name: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """Compose the settings modal."""
        with Vertical(id="settings-container"):
            yield Label("Settings", classes="title")

            with TabbedContent(id="settings-tabs"):
                with TabPane("General", id="tab-general"):
                    yield Horizontal(
                        Label("Enable Desktop Notifications:"),
                        Switch(
                            value=self.workspace.notifications_enabled, id="notifications-toggle"
                        ),
                    )
                    yield Button("Test Notification", id="test-notification-btn")

                with TabPane("Model Catalog", id="tab-model-catalog"):
                    with Vertical(classes="model-list-scroll", id="model-catalog-scroll"):
                        yield from self._compose_model_catalog_tab()

            yield Horizontal(
                Button("OK", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def _sanitize_id(self, text: str) -> str:
        """Sanitize text for use as a widget ID."""
        return text.replace(".", "-").replace("_", "-")

    def _compose_model_catalog_tab(self) -> ComposeResult:
        """Compose the model catalog tab content."""
        yield Static("Configure available models for each backend.", classes="help-text")

        for backend_name in BACKEND_REGISTRY.keys():
            models = self.workspace.model_catalog.get_models(backend_name)
            yield Static(f"{backend_name.upper()}", classes="backend-label")
            safe_backend = self._sanitize_id(backend_name)
            with Vertical(classes="model-list-container", id=f"container-{safe_backend}"):
                if models:
                    for idx, model in enumerate(models):
                        with Horizontal(classes="model-row"):
                            yield Label(model, classes="model-name")
                            yield Button(
                                "×",
                                variant="error",
                                classes="remove-model-btn",
                                id=f"remove-{safe_backend}-{idx}",
                            )
                else:
                    yield Static("No models configured", classes="no-models-text")
            yield Horizontal(
                Input(placeholder=f"Add model for {backend_name}...", id=f"input-{safe_backend}"),
                Button("Add", variant="primary", id=f"add-{safe_backend}"),
            )

    def on_mount(self) -> None:
        """Called when the modal is mounted."""
        self.query_one("#ok-btn").focus()
        
        # Pre-compute the mapping of safe IDs to original backend names
        for backend_name in BACKEND_REGISTRY.keys():
            safe_backend = self._sanitize_id(backend_name)
            self._safe_id_to_backend_name[safe_backend] = backend_name

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Handle switch changes."""
        if event.switch.id == "notifications-toggle":
            self.workspace.notifications_enabled = event.value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "ok-btn":
            self.workspace.save()
            self.dismiss(True)
        elif event.button.id == "cancel-btn":
            self.dismiss(False)
        elif event.button.id == "test-notification-btn":
            self._test_notification()
        elif event.button.id and event.button.id.startswith("add-"):
            safe_backend = event.button.id[4:]
            backend_name = self._safe_id_to_backend_name.get(safe_backend, safe_backend)
            self._add_model(backend_name, safe_backend)
        elif event.button.id and event.button.id.startswith("remove-"):
            parts = event.button.id[7:].rsplit("-", 1)
            if len(parts) == 2:
                try:
                    safe_backend, idx_str = parts
                    idx = int(idx_str)
                    backend_name = self._safe_id_to_backend_name.get(safe_backend, safe_backend)
                    self._remove_model_by_idx(backend_name, safe_backend, idx)
                except ValueError:
                    pass

    def _add_model(self, backend_name: str, safe_backend: str) -> None:
        """Add a model to a backend."""
        input_widget = self.query_one(f"#input-{safe_backend}", Input)
        model = input_widget.value.strip()
        if model:
            self.workspace.model_catalog.add_model(backend_name, model)
            input_widget.value = ""
            self._refresh_model_list(backend_name, safe_backend)

    def _remove_model_by_idx(self, backend_name: str, safe_backend: str, idx: int) -> None:
        """Remove a model by index from a backend."""
        models = self.workspace.model_catalog.get_models(backend_name)
        if 0 <= idx < len(models):
            model = models[idx]
            self.workspace.model_catalog.remove_model(backend_name, model)
            self._refresh_model_list(backend_name, safe_backend)

    def _refresh_model_list(self, backend_name: str, safe_backend: str) -> None:
        """Refresh the model list display for a backend."""
        container = self.query_one(f"#container-{safe_backend}", Vertical)
        models = self.workspace.model_catalog.get_models(backend_name)
        container.remove_children()
        if models:
            for idx, model in enumerate(models):
                container.mount(
                    Horizontal(
                        Label(model, classes="model-name"),
                        Button(
                            "×",
                            variant="error",
                            classes="remove-model-btn",
                            id=f"remove-{safe_backend}-{idx}",
                        ),
                        classes="model-row",
                    )
                )
        else:
            container.mount(Static("No models configured", classes="no-models-text"))

    def _test_notification(self) -> None:
        """Send a test notification."""
        from agent_pump.utils.notifier import Notifier

        Notifier.test()
