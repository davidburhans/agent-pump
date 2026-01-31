"""Modal screen for configuring backend settings per phase."""

from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TabbedContent, TabPane

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    BackendPreset,
    PhaseBackends,
    ProjectConfig,
    Workspace,
)
from agent_pump.tui.screens.confirm_modal import ConfirmModal

PHASES = ["planning", "implementing", "verifying", "brainstorming", "committing"]


class BackendConfigModal(ModalScreen[PhaseBackends | None]):
    """Modal for configuring backend settings for each workflow phase and project defaults."""

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
        height: auto;
        max-height: 20;
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

    .inherit-checkbox {
        margin-bottom: 1;
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

        # Load standard phases
        for phase in PHASES:
            phase_config = getattr(self.phase_backends, phase)
            self._phase_backends_lists[phase] = list(phase_config.backends)

        # Load default chain (pseudo-phase "default")
        if self.project_config.default_chain:
            self._phase_backends_lists["default"] = list(self.project_config.default_chain.backends)
        else:
            # Default to Gemini if not set
            self._phase_backends_lists["default"] = [BackendInstance()]

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""
        available_backends = list(BACKEND_REGISTRY.keys())
        preset_names = list(self.workspace.backend_presets.keys())

        with Container(id="modal-container"):
            yield Static(f"⚙️ Backend Configuration: {self.project_config.name}", id="modal-title")
            yield Label(
                "Configure backend fallback chains. Backends tried in order. Ctrl+S to save, Esc to cancel.",  # noqa: E501
                classes="help-text",
            )

            with TabbedContent():
                # Default Defaults Tab
                with TabPane("🌐 Project Default", id="tab-default"):
                    yield from self._compose_phase_content(
                        "default",
                        self._phase_backends_lists["default"],
                        available_backends,
                        preset_names,
                        is_default_tab=True,
                    )

                # Phase Tabs
                for phase in PHASES:
                    phase_icon = {
                        "planning": "📋",
                        "implementing": "🔨",
                        "verifying": "✅",
                        "brainstorming": "💡",
                        "committing": "📝",
                    }.get(phase, "")

                    with TabPane(f"{phase_icon} {phase.capitalize()}", id=f"tab-{phase}"):
                        yield from self._compose_phase_content(
                            phase,
                            self._phase_backends_lists[phase],
                            available_backends,
                            preset_names,
                        )

            yield Horizontal(
                Button("+ Add Backend", id="btn-add-backend", variant="primary"),
                Button("Reset All", variant="warning", id="btn-reset"),
                Button("Apply to All Projects", variant="warning", id="btn-apply-all"),
                Button("Cancel (Esc)", variant="error", id="btn-cancel"),
                Button("Save (Ctrl+S)", variant="success", id="btn-save"),
                classes="button-row",
            )

    def _compose_phase_content(
        self,
        phase: str,
        backends: list[BackendInstance],
        available_backends: list[str],
        preset_names: list[str],
        is_default_tab: bool = False,
    ) -> ComposeResult:
        """Helper to compose content for a single phase tab."""
        with VerticalScroll(classes="phase-config", id=f"{phase}-container"):
            # "Inherit" Checkbox (only for non-default phases)
            is_inherited = False
            if not is_default_tab:
                # If list is empty, it means we are inheriting
                is_inherited = len(backends) == 0
                yield Checkbox(
                    "Use Project Default Chain",
                    value=is_inherited,
                    id=f"{phase}-inherit-checkbox",
                    classes="inherit-checkbox",
                )

            # Wrapper for content that gets disabled/hidden if inherited
            # We use a separate container ID to easily toggle visibility/disabled state

            # Copy from dropdown
            copy_options = [("(select to copy)", "")]
            if phase != "default":
                copy_options.append(("Project Default", "phase:default"))

            for p in PHASES:
                if p != phase:
                    copy_options.append((f"Phase: {p.capitalize()}", f"phase:{p}"))
            for preset_name in preset_names:
                copy_options.append((f"Preset: {preset_name}", f"preset:{preset_name}"))

            # Add projects
            current_path = str(self.project_config.path.resolve())
            for p_path_str, p_config in self.workspace.projects.items():
                if p_path_str != current_path:
                    copy_options.append((f"Project: {p_config.name}", f"project:{p_path_str}"))

            with Vertical(id=f"{phase}-content-wrapper"):
                if not is_inherited:
                    yield Horizontal(
                        Label("Copy from:"),
                        Select(
                            copy_options,
                            value="",
                            allow_blank=False,
                            id=f"{phase}-copy-from",
                        ),
                        Button("Save as Preset", id=f"{phase}-save-preset", variant="primary"),
                        classes="copy-row",
                    )

                    yield Label("Backend Chain (tried in order):", classes="section-label")

                    with VerticalScroll(classes="backend-list", id=f"{phase}-backend-list"):
                        for idx, backend in enumerate(backends):
                            yield self._create_backend_row(phase, idx, backend, available_backends)
                else:
                    yield Label("Using Project Default Chain", classes="hint")

    def _create_backend_row(
        self, phase: str, idx: int, backend: BackendInstance, available_backends: list[str]
    ) -> Horizontal:
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
                allow_blank=False,
            )
        )
        row.compose_add_child(
            Input(
                value=" ".join(backend.args),
                placeholder="args (e.g., --model gemini-2.5-flash)",
                id=f"{phase}-args-{rc}-{idx}",
            )
        )
        row.compose_add_child(
            Button(
                "✕",
                id=f"{phase}-remove-{rc}-{idx}",
                variant="error",
                tooltip="Remove backend"
            )
        )
        return row

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle copy-from selection."""
        if not event.select.id:
            return
        select_id = str(event.select.id)
        if "-copy-from" in select_id and event.value:
            phase = select_id.replace("-copy-from", "")
            self.call_later(self._apply_copy, phase, str(event.value))
            # Reset the select to placeholder
            cast(Any, event.select).value = ""

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle inherit checkbox toggle."""
        checkbox_id = str(event.checkbox.id)
        if "-inherit-checkbox" in checkbox_id:
            phase = checkbox_id.replace("-inherit-checkbox", "")
            is_inherited = event.value

            if is_inherited:
                # User wants to inherit. Clear current backends (set to empty)
                self._phase_backends_lists[phase] = []
            else:
                # User wants to customize. If empty, copy default or add one
                if not self._phase_backends_lists[phase]:
                    if self._phase_backends_lists.get("default"):
                        self._phase_backends_lists[phase] = [
                            b.model_copy() for b in self._phase_backends_lists["default"]
                        ]
                    else:
                        self._phase_backends_lists[phase] = [BackendInstance()]

            # Rebuild the UI for this phase
            self.call_later(self._rebuild_phase_ui, phase)

    async def _rebuild_phase_ui(self, phase: str) -> None:
        """Rebuild the entire content wrapper for a phase."""
        try:
            # Just remove the tab pane content and recreate it?
            # Easier to just remove children of container and recall compose logic
            container = self.query_one(f"#{phase}-container", VerticalScroll)
            await container.remove_children()

            # Re-run compose logic manually
            # Checkbox
            backends = self._phase_backends_lists[phase]
            is_inherited = phase != "default" and len(backends) == 0

            if phase != "default":
                await container.mount(
                    Checkbox(
                        "Use Project Default Chain",
                        value=is_inherited,
                        id=f"{phase}-inherit-checkbox",
                        classes="inherit-checkbox",
                    )
                )

            available_backends = list(BACKEND_REGISTRY.keys())
            preset_names = list(self.workspace.backend_presets.keys())

            # Wrapper
            wrapper = Vertical(id=f"{phase}-content-wrapper")
            await container.mount(wrapper)

            if not is_inherited:
                # Copy row
                copy_options = [("(select to copy)", "")]
                if phase != "default":
                    copy_options.append(("Project Default", "phase:default"))
                for p in PHASES:
                    if p != phase:
                        copy_options.append((f"Phase: {p.capitalize()}", f"phase:{p}"))
                for preset_name in preset_names:
                    copy_options.append((f"Preset: {preset_name}", f"preset:{preset_name}"))

                # Add projects
                current_path = str(self.project_config.path.resolve())
                for p_path_str, p_config in self.workspace.projects.items():
                    if p_path_str != current_path:
                        copy_options.append((f"Project: {p_config.name}", f"project:{p_path_str}"))

                copy_row = Horizontal(classes="copy-row")
                copy_row.compose_add_child(Label("Copy from:"))
                copy_row.compose_add_child(
                    Select(copy_options, value="", allow_blank=False, id=f"{phase}-copy-from")
                )
                copy_row.compose_add_child(
                    Button("Save as Preset", id=f"{phase}-save-preset", variant="primary")
                )
                await wrapper.mount(copy_row)

                await wrapper.mount(
                    Label("Backend Chain (tried in order):", classes="section-label")
                )

                list_container = VerticalScroll(classes="backend-list", id=f"{phase}-backend-list")
                await wrapper.mount(list_container)

                for idx, backend in enumerate(backends):
                    await list_container.mount(
                        self._create_backend_row(phase, idx, backend, available_backends)
                    )
            else:
                await wrapper.mount(Label("Using Project Default Chain", classes="hint"))

        except Exception:
            pass

    async def _apply_copy(self, target_phase: str, source: str) -> None:
        """Copy backend config from a phase or preset."""
        source_backends: list[BackendInstance] = []

        if source.startswith("phase:"):
            source_phase = source.replace("phase:", "")
            back = self._phase_backends_lists.get(source_phase)
            if back:
                source_backends = [b.model_copy() for b in back]
        elif source.startswith("preset:"):
            preset_name = source.replace("preset:", "")
            if preset_name in self.workspace.backend_presets:
                preset = self.workspace.backend_presets[preset_name]
                source_backends = [b.model_copy() for b in preset.backends.backends]
        elif source.startswith("project:"):
            project_path_str = source.replace("project:", "")
            p_config = self.workspace.projects.get(project_path_str)
            if p_config:
                if target_phase == "default":
                    if p_config.default_chain:
                        source_backends = [b.model_copy() for b in p_config.default_chain.backends]
                else:
                    phase_chain = getattr(p_config.phase_backends, target_phase, None)
                    if phase_chain and phase_chain.backends:
                        source_backends = [b.model_copy() for b in phase_chain.backends]

        if source_backends:
            self._phase_backends_lists[target_phase] = source_backends
            # If we copied to a phase, it is no longer inherited
            await self._rebuild_phase_ui(target_phase)
            self.notify(f"Copied config to {target_phase}", severity="information")

    async def _rebuild_backend_list(self, phase: str) -> None:
        """Rebuild only the backend list UI for a phase."""
        self._rebuild_counter += 1  # Increment to get unique IDs
        available_backends = list(BACKEND_REGISTRY.keys())
        try:
            container = self.query_one(f"#{phase}-backend-list", VerticalScroll)
            await container.remove_children()

            for idx, backend in enumerate(self._phase_backends_lists[phase]):
                await container.mount(
                    self._create_backend_row(phase, idx, backend, available_backends)
                )
        except Exception:
            # Container might not exist if inherited
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if not event.button.id:
            return
        button_id = str(event.button.id)

        if button_id == "btn-cancel":
            self.action_cancel()
        elif button_id == "btn-save":
            self.action_save()
        elif button_id == "btn-reset":
            self.call_later(self._reset_to_default)
        elif button_id == "btn-apply-all":
            self.action_apply_to_all()
        elif button_id == "btn-add-backend":
            # Add backend to the currently active tab
            self.call_later(self._add_backend_to_active_tab)
        elif "-remove-" in button_id:
            # ID format: {phase}-remove-{counter}-{idx}
            parts = button_id.split("-")
            idx = int(parts[-1])
            phase = parts[0]
            self.call_later(self._remove_backend, phase, idx)
        elif "-save-preset" in button_id:
            phase = button_id.replace("-save-preset", "")
            self._save_as_preset(phase)

    async def _add_backend_to_active_tab(self) -> None:
        """Determine the active tab and add a backend to it."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab_id = str(tabbed_content.active)
            # Tab IDs are like "tab-planning", "tab-default", etc.
            phase = active_tab_id.replace("tab-", "")

            # Check if this phase is inherited (empty backends)
            if phase != "default" and len(self._phase_backends_lists.get(phase, [])) == 0:
                self.notify(
                    f"Uncheck 'Use Project Default Chain' first to add backends to {phase}",
                    severity="warning",
                )
                return

            await self._add_backend(phase)
        except Exception as e:
            self.notify(f"Could not add backend: {e}", severity="error")

    async def _add_backend(self, phase: str) -> None:
        """Add a new backend to the chain."""
        self._sync_phase_from_ui(phase)  # Preserve current values
        self._phase_backends_lists[phase].append(BackendInstance())
        self.notify(
            f"Added backend #{len(self._phase_backends_lists[phase])} to {phase}",
            severity="information",
        )
        await self._rebuild_backend_list(phase)

    async def _remove_backend(self, phase: str, idx: int) -> None:
        """Remove a backend from the chain."""
        self._sync_phase_from_ui(phase)  # Preserve current values
        backends = self._phase_backends_lists[phase]
        if len(backends) > 1:
            backends.pop(idx)
            await self._rebuild_backend_list(phase)
        else:
            self.notify("Cannot remove the last backend (use reset to clear)", severity="warning")

    def _save_as_preset(self, phase: str) -> None:
        """Save current phase config as a named preset."""
        self._sync_phase_from_ui(phase)
        backends = self._phase_backends_lists[phase]

        base_name = f"{phase}-preset"
        name = base_name
        counter = 1
        while name in self.workspace.backend_presets:
            name = f"{base_name}-{counter}"
            counter += 1

        preset = BackendPreset(
            name=name,
            backends=BackendFallback(backends=[b.model_copy() for b in backends]),
        )
        self.workspace.backend_presets[name] = preset
        self.workspace.save()
        self.notify(f"Saved preset: {name}", severity="information")

    def action_apply_to_all(self) -> None:
        """Apply current configuration to all projects."""

        def on_confirm(confirm: bool | None) -> None:
            if confirm:
                self._perform_apply_to_all()

        self.app.push_screen(
            ConfirmModal(
                "Are you sure you want to apply this configuration to ALL projects?\n"
                "This will overwrite their backend settings.",
                confirm_label="Overwrite All",
            ),
            on_confirm,
        )

    def _perform_apply_to_all(self) -> None:
        """Execute the apply to all operation."""
        # Save current state to memory
        self._save_config_to_memory()

        # Apply to all projects
        current_phase_backends = self.project_config.phase_backends
        current_default_chain = self.project_config.default_chain

        count = 0
        current_path = str(self.project_config.path.resolve())
        for p_path, p_config in self.workspace.projects.items():
            if p_path == current_path:
                continue

            p_config.phase_backends = current_phase_backends.model_copy(deep=True)
            if current_default_chain:
                p_config.default_chain = current_default_chain.model_copy(deep=True)
            else:
                p_config.default_chain = None
            count += 1

        self.workspace.save()
        self.notify(f"Applied configuration to {count} other projects", severity="information")

    def _save_config_to_memory(self) -> None:
        """Save the UI state to the project config object without dismissing."""
        # Save default phase
        self._sync_phase_from_ui("default")
        default_backends = self._phase_backends_lists["default"]
        self.project_config.default_chain = BackendFallback(backends=default_backends)

        # Save other phases
        for phase in PHASES:
            self._sync_phase_from_ui(phase)
            backends = self._phase_backends_lists[phase]
            setattr(self.phase_backends, phase, BackendFallback(backends=backends))

        # Update the project config's phase_backends
        self.project_config.phase_backends = self.phase_backends

    def action_cancel(self) -> None:
        """Cancel and dismiss without saving."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config()

    async def _reset_to_default(self) -> None:
        """Reset all phases to default (inherit)."""
        self._phase_backends_lists["default"] = [BackendInstance(name="gemini")]
        for phase in PHASES:
            # Empty list means inherit
            self._phase_backends_lists[phase] = []
            await self._rebuild_phase_ui(phase)

        await self._rebuild_phase_ui("default")
        self.notify("Reset to Project Default", severity="information")

    def _sync_phase_from_ui(self, phase: str) -> None:
        """Sync backend list from UI values for a phase."""
        # Only sync if we have backends (not inherited)
        backends = self._phase_backends_lists[phase]
        if not backends:
            return

        rc = self._rebuild_counter
        for idx in range(len(backends)):
            try:
                backend_select = self.query_one(f"#{phase}-backend-{rc}-{idx}", Select)
                args_input = self.query_one(f"#{phase}-args-{rc}-{idx}", Input)
                backends[idx].name = str(backend_select.value)
                backends[idx].args = args_input.value.split() if args_input.value.strip() else []
            except Exception:
                pass  # Row may have been removed or UI mismatch

    def _save_config(self) -> None:
        """Save the configuration and dismiss."""
        self._save_config_to_memory()
        self.dismiss(self.phase_backends)
