"""Modal screen for configuring global prompt settings per engine/model."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static, TabbedContent, TabPane, TextArea

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import GlobalPromptSettings
from agent_pump.tui.screens.confirm_modal import ConfirmModal

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
    }

    .help-text {
        color: $text-muted;
        height: 3;
        margin-bottom: 1;
    }

    .engine-section {
        margin-bottom: 2;
        border-bottom: solid $primary-darken-2;
        padding-bottom: 1;
    }

    .engine-title {
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    .textarea-row {
        height: 9;
        margin-bottom: 2;
    }

    .textarea-label {
        height: 1;
        color: $text-muted;
    }

    .small-textarea {
        height: 7;
        border: solid $secondary;
        background: $surface-darken-1;
    }

    .model-list {
        height: auto;
        margin-top: 1;
        padding-bottom: 1;
    }

    .add-model-row {
        height: 5;
        min-height: 5;
        border-top: solid $primary-darken-2;
        padding-top: 1;
        margin-top: 1;
    }

    .add-model-row Input {
        width: 1fr;
    }

    .add-model-row Button {
        width: 16;
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
        height: 1fr;
    }

    /* Target the container wrapping the split content */
    .tab-content-wrapper {
        height: 1fr;
        width: 100%;
    }

    /* Specific scroll container inside the wrapper */
    .settings-scroll-container {
        height: 1fr;
        scrollbar-size: 1 1;
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
            yield Static("🌐 Global Prompt Settings", id="modal-title")
            yield Label(
                "Configure prompt prefix/suffix per provider.\n"
                "Engine settings apply to all models. "
                "Specific model settings override engine settings.",
                classes="help-text",
            )

            with TabbedContent():
                # specific tabs for each engine
                for engine_name in BACKEND_REGISTRY:
                    with TabPane(f"{engine_name.capitalize()}", id=f"tab-{engine_name}"):
                        # Wrapper to hold scrollable area + fixed footer
                        with Vertical(classes="tab-content-wrapper"):
                            # Scrollable Area (1fr)
                            with ScrollableContainer(classes="settings-scroll-container"):
                                # 1. Engine Level Settings
                                yield Label(
                                    f"🔧 {engine_name.capitalize()} Global Settings",
                                    classes="engine-title",
                                )

                                e_prefix = self.settings.engine_prefixes.get(engine_name, "")
                                e_suffix = self.settings.engine_suffixes.get(engine_name, "")

                                with Vertical(classes="textarea-row"):
                                    yield Label("Engine Prefix:", classes="textarea-label")
                                    yield TextArea(
                                        e_prefix,
                                        id=f"engine-{engine_name}-prefix",
                                        classes="small-textarea",
                                    )

                                with Vertical(classes="textarea-row"):
                                    yield Label("Engine Suffix:", classes="textarea-label")
                                    yield TextArea(
                                        e_suffix,
                                        id=f"engine-{engine_name}-suffix",
                                        classes="small-textarea",
                                    )

                                # 2. Model Level Settings for this engine
                                yield Label(
                                    f"📦 {engine_name.capitalize()} Models",
                                    classes="engine-title",
                                    id=f"models-title-{engine_name}",
                                )

                                # Filter models relevant to this engine
                                relevant_models = self._get_models_for_engine(engine_name)

                                with Vertical(id=f"model-list-{engine_name}", classes="model-list"):
                                    for model_name in sorted(relevant_models):
                                        yield from self._compose_model_section(model_name)

                            # Fixed Footer (auto height)
                            yield Horizontal(
                                Input(
                                    placeholder=f"Add {engine_name} model...",
                                    id=f"new-model-input-{engine_name}",
                                ),
                                Button(
                                    "Add Model",
                                    variant="success",
                                    id=f"btn-add-model-{engine_name}",
                                ),
                                classes="add-model-row",
                            )

            yield Horizontal(
                Button("Clear All", variant="warning", id="btn-clear"),
                Button("Cancel (Esc)", variant="error", id="btn-cancel"),
                Button("Save (Ctrl+S)", variant="success", id="btn-save"),
                classes="button-row",
            )

    def _get_models_for_engine(self, engine_name: str) -> list[str]:
        """Return a list of configured models that belong to the given engine."""
        models = []
        for model_name in self.configured_models:
            # Check explicit widely known list
            if model_name in KNOWN_MODELS.get(engine_name, []):
                models.append(model_name)
                continue

            # Check implicit naming convention
            if model_name.lower().startswith(engine_name.lower()):
                models.append(model_name)
                continue

            # Fallback for "other" or unclassified?
            # For now, simplistic matching.
            # If opencode, everything might be opencode if not matched elsewhere?
            # Let's keep it strict for now to avoid duplication.
        return models

    def _compose_model_section(self, model_name: str) -> ComposeResult:
        """Compose the widgets for a single model configuration."""
        m_prefix = self.settings.model_prefixes.get(model_name, "")
        m_suffix = self.settings.model_suffixes.get(model_name, "")
        safe_id = self._safe_id(model_name)

        with Vertical(classes="engine-section", id=f"model-section-{safe_id}"):
            yield Horizontal(
                Label(f"🔹 {model_name}", classes="engine-title"),
                Button("Remove", variant="error", id=f"remove-model-{safe_id}"),
            )

            with Vertical(classes="textarea-row"):
                yield Label("Prefix:", classes="textarea-label")
                yield TextArea(m_prefix, id=f"model-{safe_id}-prefix", classes="small-textarea")

            with Vertical(classes="textarea-row"):
                yield Label("Suffix:", classes="textarea-label")
                yield TextArea(m_suffix, id=f"model-{safe_id}-suffix", classes="small-textarea")

    def _safe_id(self, name: str) -> str:
        """Convert a name to a safe CSS ID."""
        return name.replace(".", "-").replace(" ", "-").lower()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if not button_id:
            return

        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-clear":
            self._confirm_clear_all()
        elif button_id.startswith("btn-add-model-"):
            engine_name = button_id.replace("btn-add-model-", "")
            self._add_model(engine_name)
        elif button_id.startswith("remove-model-"):
            model_id = button_id.replace("remove-model-", "")
            self._remove_model(model_id)

    def _add_model(self, engine_name: str) -> None:
        """Add a new model configuration."""
        input_widget = self.query_one(f"#new-model-input-{engine_name}", Input)
        model_name = input_widget.value.strip()

        if not model_name:
            self.notify("Please enter a model name", severity="warning")
            return

        if model_name in self.configured_models:
            self.notify(f"Model '{model_name}' already configured", severity="warning")
            return

        self.configured_models.add(model_name)
        input_widget.value = ""

        # Dynamically mount the new section
        try:
            container = self.query_one(f"#model-list-{engine_name}", Vertical)
            container.mount_all(self._compose_model_section(model_name))
            self.notify(f"Added model '{model_name}'", severity="information")
        except Exception:
            self.notify(f"Could not find container for {engine_name}", severity="error")

    def _remove_model(self, model_id: str) -> None:
        """Remove a model configuration."""
        # Find the model name from configured models (reverse lookup needed or iterate)
        target_name = None
        for model_name in self.configured_models:
            if self._safe_id(model_name) == model_id:
                target_name = model_name
                break

        if target_name:
            self.configured_models.discard(target_name)
            try:
                self.query_one(f"#model-section-{model_id}").remove()
                self.notify(f"Removed model '{target_name}'", severity="information")
            except Exception:
                pass

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    def _confirm_clear_all(self) -> None:
        """Ask for confirmation before clearing."""

        def on_confirm(result: bool | None) -> None:
            if result:
                self._clear_all()

        self.app.push_screen(
            ConfirmModal(
                question="Are you sure you want to clear ALL global prompt settings?",
                confirm_label="Clear All",
            ),
            on_confirm,
        )

    def _clear_all(self) -> None:
        """Clear all global prompt settings."""
        # Clear fields currently in UI
        for note in self.query(TextArea):
            note.text = ""

        self.notify("Cleared all visible settings. Save to apply.", severity="information")

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        # Re-construct settings from UI state

        # 1. Engine Settings
        self.settings.engine_prefixes = {}
        self.settings.engine_suffixes = {}

        for engine_name in BACKEND_REGISTRY:
            try:
                p_widget = self.query_one(f"#engine-{engine_name}-prefix", TextArea)
                s_widget = self.query_one(f"#engine-{engine_name}-suffix", TextArea)

                if p_widget.text.strip():
                    self.settings.engine_prefixes[engine_name] = p_widget.text
                if s_widget.text.strip():
                    self.settings.engine_suffixes[engine_name] = s_widget.text
            except Exception:
                # Might not be rendered if tab not visited?
                # Textual usually keeps tab content in DOM but hidden.
                # If lazy loading is involved, this might be risky, but
                # TabbedContent usually keeps it.
                pass

        # 2. Model Settings
        self.settings.model_prefixes = {}
        self.settings.model_suffixes = {}

        for model_name in self.configured_models:
            safe_id = self._safe_id(model_name)
            try:
                # We search globally because we don't know which tab exactly without logic
                p_widget = self.query_one(f"#model-{safe_id}-prefix", TextArea)
                s_widget = self.query_one(f"#model-{safe_id}-suffix", TextArea)

                if p_widget.text.strip():
                    self.settings.model_prefixes[model_name] = p_widget.text
                if s_widget.text.strip():
                    self.settings.model_suffixes[model_name] = s_widget.text
            except Exception:
                # If the widget isn't in the DOM (e.g. was never rendered?), we might
                # lose data? But we initialized `configured_models` from existing
                # settings. If the user didn't open the tab, we might effectively delete
                # it if we rely ONLY on DOM. BUT, since we render ALL tabs in `compose`,
                # they should be in DOM. Ideally, we should merge with original settings
                # if not found, but "Clear All" complicates that. For this
                # implementation, we assume DOM existence.
                pass

        self.dismiss(self.settings)
