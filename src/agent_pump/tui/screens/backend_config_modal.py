"""Modal screen for configuring backend settings per phase."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent, TabPane

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    BackendPreset,
    PhaseBackends,
    ProjectConfig,
    Workspace,
)


PHASES = ["planning", "implementing", "verifying", "brainstorming", "committing"]


class BackendConfigModal(ModalScreen[PhaseBackends | None]):
    """Modal for configuring backend settings for each workflow phase."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    BackendConfigModal {
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
        height: 2;
        margin-bottom: 1;
    }

    .phase-config {
        height: 1fr;
        padding: 1;
    }

    .section-label {
        text-style: bold;
        margin-top: 1;
    }

    .copy-row {
        height: 3;
        margin-bottom: 1;
    }

    .copy-row Label {
        width: 12;
    }

    .copy-row Select {
        width: 1fr;
    }

    .copy-row Button {
        width: auto;
        margin-left: 1;
    }

    .backend-list {
        height: 1fr;
        min-height: 10;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }

    .backend-row {
        height: 3;
        margin-bottom: 1;
    }

    .backend-row Label {
        width: 3;
    }

    .backend-row Select {
        width: 20;
    }

    .backend-row Input {
        width: 1fr;
    }

    .backend-row Button {
        width: 4;
        margin-left: 1;
    }

    .add-row {
        height: 3;
        margin-top: 1;
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

    .hint {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(
        self,
        project_config: ProjectConfig,
        workspace: Workspace,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.project_config = project_config
        self.workspace = workspace
        # Make a copy of the phase backends to edit
        self.phase_backends = project_config.phase_backends.model_copy(deep=True)
        # Track backends per phase as lists for dynamic editing
        self._phase_backends_lists: dict[str, list[BackendInstance]] = {}
        # Counter to ensure unique IDs across rebuilds
        self._rebuild_counter = 0
        for phase in PHASES:
            phase_config = getattr(self.phase_backends, phase)
            self._phase_backends_lists[phase] = list(phase_config.backends)

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        available_backends = list(BACKEND_REGISTRY.keys())
        preset_names = list(self.workspace.backend_presets.keys())

        with Container(id="modal-container"):
            yield Static(f"⚙️ Backend Configuration: {self.project_config.name}", id="modal-title")
            yield Label(
                "Configure backend fallback chains. Backends tried in order. Ctrl+S to save, Esc to cancel.",
                classes="help-text"
            )

            with TabbedContent():
                for phase in PHASES:
                    phase_icon = {
                        "planning": "📋",
                        "implementing": "🔨",
                        "verifying": "✅",
                        "brainstorming": "💡",
                        "committing": "📝",
                    }.get(phase, "")

                    with TabPane(f"{phase_icon} {phase.capitalize()}", id=f"tab-{phase}"):
                        backends = self._phase_backends_lists[phase]

                        with VerticalScroll(classes="phase-config"):
                            # Copy from dropdown
                            copy_options = [("(select to copy)", "")]
                            for p in PHASES:
                                if p != phase:
                                    copy_options.append((f"Phase: {p.capitalize()}", f"phase:{p}"))
                            for preset_name in preset_names:
                                copy_options.append((f"Preset: {preset_name}", f"preset:{preset_name}"))

                            with Horizontal(classes="copy-row"):
                                yield Label("Copy from:")
                                yield Select(
                                    copy_options,
                                    value="",
                                    allow_blank=False,
                                    id=f"{phase}-copy-from",
                                )
                                yield Button("Save as Preset", id=f"{phase}-save-preset", variant="primary")

                            yield Label(f"Backend Chain (tried in order):", classes="section-label")

                            with VerticalScroll(classes="backend-list", id=f"{phase}-backend-list"):
                                for idx, backend in enumerate(backends):
                                    yield self._create_backend_row(phase, idx, backend, available_backends)

                            with Horizontal(classes="add-row"):
                                yield Button("+ Add Backend", id=f"{phase}-add-backend", variant="success")

            with Horizontal(classes="button-row"):
                yield Button("Reset to Default", variant="warning", id="btn-reset")
                yield Button("Cancel (Esc)", variant="error", id="btn-cancel")
                yield Button("Save (Ctrl+S)", variant="success", id="btn-save")

    def _create_backend_row(
        self, phase: str, idx: int, backend: BackendInstance, available_backends: list[str]
    ) -> Container:
        """Create a row for a single backend in the chain."""
        # Use rebuild counter in IDs to avoid duplicate ID errors during async removal
        rc = self._rebuild_counter
        row = Horizontal(classes="backend-row", id=f"{phase}-row-{rc}-{idx}")
        row.compose_add_child(Label(f"{idx + 1}."))
        row.compose_add_child(
            Select(
                [(b, b) for b in available_backends],
                value=backend.name,
                id=f"{phase}-backend-{rc}-{idx}",
            )
        )
        row.compose_add_child(
            Input(
                value=" ".join(backend.args),
                placeholder="args (e.g., --model gemini-2.5-flash)",
                id=f"{phase}-args-{rc}-{idx}",
            )
        )
        row.compose_add_child(Button("✕", id=f"{phase}-remove-{rc}-{idx}", variant="error"))
        return row

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle copy-from selection."""
        select_id = str(event.select.id)
        if "-copy-from" in select_id and event.value:
            phase = select_id.replace("-copy-from", "")
            self.call_later(self._apply_copy, phase, str(event.value))
            # Reset the select to placeholder
            event.select.value = ""

    async def _apply_copy(self, target_phase: str, source: str) -> None:
        """Copy backend config from a phase or preset."""
        source_backends: list[BackendInstance] = []

        if source.startswith("phase:"):
            source_phase = source.replace("phase:", "")
            source_backends = [b.model_copy() for b in self._phase_backends_lists[source_phase]]
        elif source.startswith("preset:"):
            preset_name = source.replace("preset:", "")
            if preset_name in self.workspace.backend_presets:
                preset = self.workspace.backend_presets[preset_name]
                source_backends = [b.model_copy() for b in preset.backends.backends]

        if source_backends:
            self._phase_backends_lists[target_phase] = source_backends
            await self._rebuild_backend_list(target_phase)
            self.notify(f"Copied config to {target_phase}", severity="information")

    async def _rebuild_backend_list(self, phase: str) -> None:
        """Rebuild the backend list UI for a phase."""
        self._rebuild_counter += 1  # Increment to get unique IDs
        available_backends = list(BACKEND_REGISTRY.keys())
        container = self.query_one(f"#{phase}-backend-list", VerticalScroll)
        await container.remove_children()

        for idx, backend in enumerate(self._phase_backends_lists[phase]):
            await container.mount(self._create_backend_row(phase, idx, backend, available_backends))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = str(event.button.id)

        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-reset":
            self.call_later(self._reset_to_default)
        elif "-add-backend" in button_id:
            phase = button_id.replace("-add-backend", "")
            self.call_later(self._add_backend, phase)
        elif "-remove-" in button_id:
            # ID format: {phase}-remove-{counter}-{idx}
            # Extract index from the end
            parts = button_id.split("-")
            idx = int(parts[-1])
            phase = parts[0]
            self.call_later(self._remove_backend, phase, idx)
        elif "-save-preset" in button_id:
            phase = button_id.replace("-save-preset", "")
            self._save_as_preset(phase)

    async def _add_backend(self, phase: str) -> None:
        """Add a new backend to the chain."""
        self._sync_phase_from_ui(phase)  # Preserve current values
        self._phase_backends_lists[phase].append(BackendInstance())
        self.notify(f"Added backend #{len(self._phase_backends_lists[phase])} to {phase}", severity="information")
        await self._rebuild_backend_list(phase)

    async def _remove_backend(self, phase: str, idx: int) -> None:
        """Remove a backend from the chain."""
        self._sync_phase_from_ui(phase)  # Preserve current values
        backends = self._phase_backends_lists[phase]
        if len(backends) > 1:
            backends.pop(idx)
            await self._rebuild_backend_list(phase)
        else:
            self.notify("Cannot remove the last backend", severity="warning")

    def _save_as_preset(self, phase: str) -> None:
        """Save current phase config as a named preset."""
        # Sync current UI values
        self._sync_phase_from_ui(phase)
        backends = self._phase_backends_lists[phase]

        # Generate a unique preset name
        base_name = f"{phase}-preset"
        name = base_name
        counter = 1
        while name in self.workspace.backend_presets:
            name = f"{base_name}-{counter}"
            counter += 1

        # Create and save preset
        preset = BackendPreset(
            name=name,
            backends=BackendFallback(backends=[b.model_copy() for b in backends]),
        )
        self.workspace.backend_presets[name] = preset
        self.workspace.save()
        self.notify(f"Saved preset: {name}", severity="information")

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    async def _reset_to_default(self) -> None:
        """Reset all phases to default (gemini, no args, no fallback)."""
        for phase in PHASES:
            self._phase_backends_lists[phase] = [BackendInstance()]
            await self._rebuild_backend_list(phase)

        self.notify("Reset all phases to default (Gemini)", severity="information")

    def _sync_phase_from_ui(self, phase: str) -> None:
        """Sync backend list from UI values for a phase."""
        backends = self._phase_backends_lists[phase]
        rc = self._rebuild_counter
        for idx in range(len(backends)):
            try:
                backend_select = self.query_one(f"#{phase}-backend-{rc}-{idx}", Select)
                args_input = self.query_one(f"#{phase}-args-{rc}-{idx}", Input)
                backends[idx].name = str(backend_select.value)
                backends[idx].args = args_input.value.split() if args_input.value.strip() else []
            except Exception:
                pass  # Row may have been removed

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        for phase in PHASES:
            self._sync_phase_from_ui(phase)
            backends = self._phase_backends_lists[phase]
            setattr(self.phase_backends, phase, BackendFallback(backends=backends))

        self.dismiss(self.phase_backends)
