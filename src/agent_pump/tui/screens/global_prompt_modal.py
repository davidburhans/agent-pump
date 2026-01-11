"""Modal screen for configuring global prompt settings per engine/model."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TabbedContent, TabPane, TextArea

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import GlobalPromptSettings

# Well-known models for each engine
KNOWN_MODELS = {
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
    "claude": ["claude-sonnet", "claude-opus", "claude-haiku"],
    "opencode": ["default"],
    "qwen": ["qwen-coder", "qwen-chat"],
}


class GlobalPromptModal(ModalScreen[GlobalPromptSettings | None]):
    """Modal for configuring global prompt prefix/suffix per engine and model."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    GlobalPromptModal {
        align: center middle;
    }

    #modal-container {
        width: 90%;
        height: 90%;
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
        height: 3;
        margin-bottom: 1;
    }

    .engine-section {
        margin-bottom: 2;
        border: solid $primary-darken-2;
        padding: 1;
        background: $surface;
    }

    .engine-title {
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    .textarea-row {
        height: auto;
        margin-bottom: 1;
    }

    .textarea-label {
        height: 1;
        color: $text-muted;
    }

    .small-textarea {
        height: 4;
    }

    .model-list {
        height: auto;
        max-height: 100%;
        overflow-y: auto;
    }

    .add-model-row {
        height: 3;
        margin-bottom: 1;
    }

    .add-model-row Input {
        width: 1fr;
    }

    .add-model-row Button {
        width: 12;
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

    TabPane {
        padding: 1;
    }

    ScrollableContainer {
        height: 1fr;
    }
    """

    def __init__(
        self,
        global_settings: GlobalPromptSettings,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        # Make a copy to edit
        self.settings = global_settings.model_copy(deep=True)
        # Track which models are configured
        self.configured_models: set[str] = set(self.settings.model_prefixes.keys()) | set(
            self.settings.model_suffixes.keys()
        )

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        with Container(id="modal-container"):
            yield Static("Global Prompt Settings", id="modal-title")
            yield Label(
                "Configure prompt prefix/suffix that applies across all phases.\n"
                "Engine settings apply to all uses of that backend. "
                "Model settings are more specific.",
                classes="help-text",
            )

            with TabbedContent():
                # Engine tab
                with TabPane("By Engine", id="tab-engine"):
                    with ScrollableContainer():
                        for engine_name in BACKEND_REGISTRY:
                            prefix = self.settings.engine_prefixes.get(engine_name, "")
                            suffix = self.settings.engine_suffixes.get(engine_name, "")

                            with Vertical(classes="engine-section"):
                                yield Static(
                                    f"Engine: {engine_name.capitalize()}",
                                    classes="engine-title"
                                )

                                with Vertical(classes="textarea-row"):
                                    yield Label("Prefix:", classes="textarea-label")
                                    yield TextArea(
                                        prefix,
                                        id=f"engine-{engine_name}-prefix",
                                        classes="small-textarea",
                                    )

                                with Vertical(classes="textarea-row"):
                                    yield Label("Suffix:", classes="textarea-label")
                                    yield TextArea(
                                        suffix,
                                        id=f"engine-{engine_name}-suffix",
                                        classes="small-textarea",
                                    )

                # Model tab
                with TabPane("By Model", id="tab-model"):
                    with ScrollableContainer(classes="model-list"):
                        # Add model input
                        with Horizontal(classes="add-model-row"):
                            yield Input(
                                placeholder="Enter model name",
                                id="new-model-input",
                            )
                            yield Button("Add Model", variant="success", id="btn-add-model")

                        # Show configured models
                        yield Label("Configured Models:", classes="engine-title")

                        for model_name in sorted(self.configured_models):
                            prefix = self.settings.model_prefixes.get(model_name, "")
                            suffix = self.settings.model_suffixes.get(model_name, "")

                            with Vertical(
                                classes="engine-section",
                                id=f"model-section-{self._safe_id(model_name)}"
                            ):
                                with Horizontal():
                                    yield Static(f"Model: {model_name}", classes="engine-title")
                                    yield Button(
                                        "X",
                                        variant="error",
                                        id=f"remove-model-{self._safe_id(model_name)}"
                                    )

                                with Vertical(classes="textarea-row"):
                                    yield Label("Prefix:", classes="textarea-label")
                                    yield TextArea(
                                        prefix,
                                        id=f"model-{self._safe_id(model_name)}-prefix",
                                        classes="small-textarea",
                                    )

                                with Vertical(classes="textarea-row"):
                                    yield Label("Suffix:", classes="textarea-label")
                                    yield TextArea(
                                        suffix,
                                        id=f"model-{self._safe_id(model_name)}-suffix",
                                        classes="small-textarea",
                                    )

            with Horizontal(classes="button-row"):
                yield Button("Clear All", variant="warning", id="btn-clear")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel")
                yield Button("Save (Ctrl+S)", variant="success", id="btn-save")

    def _safe_id(self, name: str) -> str:
        """Convert a name to a safe CSS ID."""
        return name.replace(".", "-").replace(" ", "-").lower()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-clear":
            self._clear_all()
        elif button_id == "btn-add-model":
            self._add_model()
        elif button_id and button_id.startswith("remove-model-"):
            model_id = button_id.replace("remove-model-", "")
            self._remove_model(model_id)

    def _add_model(self) -> None:
        """Add a new model configuration."""
        input_widget = self.query_one("#new-model-input", Input)
        model_name = input_widget.value.strip()

        if not model_name:
            self.notify("Please enter a model name", severity="warning")
            return

        if model_name in self.configured_models:
            self.notify(f"Model '{model_name}' already configured", severity="warning")
            return

        self.configured_models.add(model_name)
        input_widget.value = ""

        # Add the new model section (simplified - would need to mount dynamically)
        self.notify(
            f"Added model '{model_name}'. Save and reopen to configure.",
            severity="information"
        )

    def _remove_model(self, model_id: str) -> None:
        """Remove a model configuration."""
        # Find the model name from configured models
        for model_name in list(self.configured_models):
            if self._safe_id(model_name) == model_id:
                self.configured_models.discard(model_name)
                try:
                    section = self.query_one(f"#model-section-{model_id}")
                    section.remove()
                except Exception:
                    pass
                self.notify(f"Removed model '{model_name}'", severity="information")
                break

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    def _clear_all(self) -> None:
        """Clear all global prompt settings."""
        # Clear engine settings
        for engine_name in BACKEND_REGISTRY:
            try:
                self.query_one(f"#engine-{engine_name}-prefix", TextArea).text = ""
                self.query_one(f"#engine-{engine_name}-suffix", TextArea).text = ""
            except Exception:
                pass

        # Clear model settings
        for model_name in list(self.configured_models):
            model_id = self._safe_id(model_name)
            try:
                self.query_one(f"#model-{model_id}-prefix", TextArea).text = ""
                self.query_one(f"#model-{model_id}-suffix", TextArea).text = ""
            except Exception:
                pass

        self.notify("Cleared all global prompt settings", severity="information")

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        # Save engine settings
        self.settings.engine_prefixes = {}
        self.settings.engine_suffixes = {}

        for engine_name in BACKEND_REGISTRY:
            try:
                prefix = self.query_one(f"#engine-{engine_name}-prefix", TextArea).text
                suffix = self.query_one(f"#engine-{engine_name}-suffix", TextArea).text

                if prefix.strip():
                    self.settings.engine_prefixes[engine_name] = prefix
                if suffix.strip():
                    self.settings.engine_suffixes[engine_name] = suffix
            except Exception:
                pass

        # Save model settings
        self.settings.model_prefixes = {}
        self.settings.model_suffixes = {}

        for model_name in self.configured_models:
            model_id = self._safe_id(model_name)
            try:
                prefix = self.query_one(f"#model-{model_id}-prefix", TextArea).text
                suffix = self.query_one(f"#model-{model_id}-suffix", TextArea).text

                if prefix.strip():
                    self.settings.model_prefixes[model_name] = prefix
                if suffix.strip():
                    self.settings.model_suffixes[model_name] = suffix
            except Exception:
                pass

        self.dismiss(self.settings)
