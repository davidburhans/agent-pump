"""Main Textual application for agent-pump."""

from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from agent_pump.config import Config
from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    ConfigUpdatedEvent,
    IdeaAddedEvent,
    IdeasClearedEvent,
    LogEntryEvent,
    ProjectAddedEvent,
    ProjectRemovedEvent,
    WorkflowStateChangedEvent,
)
from agent_pump.models.app_state import AppState
from agent_pump.models.project import Project
from agent_pump.models.workspace import (
    GlobalPromptSettings,
    PhaseBackends,
    PromptCustomization,
)
from agent_pump.services.idea_service import IdeaService
from agent_pump.services.project_service import ProjectService
from agent_pump.services.workflow_service import WorkflowService
from agent_pump.services.workspace_service import WorkspaceService
from agent_pump.tui.screens import (
    AddProjectModal,
    BackendConfigModal,
    GlobalPromptModal,
    ProjectConfigModal,
    PromptConfigModal,
    RoadmapModal,
    SettingsModal,
)
from agent_pump.tui.commands import AgentPumpCommandProvider
from agent_pump.tui.screens.confirm_modal import ConfirmModal
from agent_pump.tui.screens.log_filter_modal import LogFilterModal
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.workflow_panel import WorkflowPanel
from agent_pump.utils.config_migration import ConfigMigrator
from agent_pump.utils.roadmap import RoadmapFeature


class AgentPumpApp(App):
    """Main TUI application for Agent Pump."""

    TITLE = "Agent Pump"
    SUB_TITLE = "AI Coding Agent Orchestrator"

    CSS_PATH = "styles/app.tcss"

    ENABLE_COMMAND_PALETTE = True
    COMMANDS = {AgentPumpCommandProvider}

    # Base bindings always available
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "add_project", "Add"),
        Binding("d", "toggle_dark", "Dark"),
        Binding("i", "add_idea", "Idea"),
        Binding("m", "manage_roadmap", "Roadmap"),
        Binding("P", "global_prompts", "Global"),
        Binding("f", "filter_logs", "Filter"),
        Binding("o", "toggle_sort", "Order"),
        Binding("s", "open_settings", "Settings"),
        Binding("t", "toggle_timer", "Timer"),
        Binding("W", "toggle_workflow_panel", "Flow Panel"),
        Binding("u", "update_config", "Reload Conf"),
    ]

    def __init__(self, project_paths: list[Path] | None = None):
        """
        Initialize the application.

        Args:
            project_paths: Initial list of project paths to manage
        """
        super().__init__()
        self.project_paths = project_paths or []

        # Initialize services
        self.app_state = AppState.load()
        self.event_bus = EventBus()
        self.workspace_service = WorkspaceService(self.event_bus, self.app_state)
        # Using placeholder for workspace service loading; it will lazily load workspace or we can init it.
        # But ProjectService needs workspace.
        self.workspace = self.workspace_service.get_current_workspace()

        self.project_service = ProjectService(self.event_bus, self.workspace, self.app_state)
        self.workflow_service = WorkflowService(self.event_bus, self.project_service)
        self.idea_service = IdeaService(self.event_bus, self.workspace)

        self.log_panel: LogPanel | None = None
        self.workflow_panel: WorkflowPanel | None = None
        self.selected_project: Path | None = None

        # Track project-specific bindings
        self._project_bindings_active = False

    # Property delegators to maintain compatibility or ease refactor
    @property
    def projects(self) -> dict[Path, Project]:
        return self.project_service.projects

    @property
    def workflows(self) -> dict:  # Type hint omitted to avoid import cycle or simplify
        return self.project_service.workflows

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Static("Projects", classes="section-title"),
                    Container(id="project-list"),
                    Horizontal(
                        Button("+ Add", id="btn-add", variant="success"),
                        Button("▶ Start All", id="btn-start-all", variant="primary"),
                        Button("⏹ Stop All", id="btn-stop-all", variant="error"),
                        classes="button-row",
                    ),
                    id="sidebar",
                ),
                Vertical(
                    Static("Activity Log", id="activity-log-title", classes="section-title"),
                    LogPanel(id="log-panel"),
                    id="main-content",
                ),
                Vertical(
                    Static("Workflow State", classes="section-title"),
                    WorkflowPanel(id="workflow-panel"),
                    id="right-sidebar",
                ),
                id="main-layout",
            ),
            id="app-container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        self.log_panel = self.query_one("#log-panel", LogPanel)

        # Apply persisted sort order
        if self.log_panel:
            self.log_panel.set_sort_order(self.app_state.log_sort_order)

        self.workflow_panel = self.query_one("#workflow-panel", WorkflowPanel)
        self._log("Agent Pump started")
        self._log("Press 'a' to add a project, 'q' to quit")
        self._log(f"Log sort order: {self.app_state.log_sort_order.upper()}")

        # Start event loop
        self.run_worker(self._handle_events())
        # Yield to allow event loop to start and subscribe
        import asyncio

        await asyncio.sleep(0.1)

        # Load initial projects
        for path in self.project_paths:
            await self._add_project(path)

    async def _handle_events(self) -> None:
        """Handle incoming events from the bus."""
        async for event in self.event_bus.subscribe():
            if isinstance(event, ProjectAddedEvent):
                self._on_project_added(event)
            elif isinstance(event, ProjectRemovedEvent):
                self._on_project_removed(event)
            elif isinstance(event, WorkflowStateChangedEvent):
                self._on_workflow_state_change(event.project_path, event.old_state, event.new_state)
            elif isinstance(event, LogEntryEvent):
                self._log(event.message, event.project_path, event.state, event.task)
            elif isinstance(event, IdeasClearedEvent):
                self._on_ideas_processed(event.project_path)
            elif isinstance(event, IdeaAddedEvent):
                if event.project_path:
                    self._log(
                        f"Added idea to project queue: {event.idea}",
                        project_path=event.project_path,
                    )
                else:
                    self._log(f"Added idea to global queue: {event.idea}")
            elif isinstance(event, ConfigUpdatedEvent):
                self._log(
                    f"Configuration updated: {event.config_type}", project_path=event.project_path
                )

    def _log(
        self,
        message: str,
        project_path: Path | None = None,
        state: str = "unknown",
        task: str | None = None,
    ) -> None:
        """Log a message to the log panel."""
        if self.log_panel:
            self.log_panel.write(message, project_path=project_path, state=state, task=task)

    def _update_activity_log_title(self) -> None:
        """Update the Activity Log title to show the selected project."""
        try:
            title_widget = self.query_one("#activity-log-title", Static)
            if self.selected_project:
                project = self.projects.get(self.selected_project)
                if project:
                    title_widget.update(f"Activity Log - {project.name}")
                else:
                    title_widget.update("Activity Log")
            else:
                title_widget.update("Activity Log")
        except Exception:
            pass  # Widget may not be mounted yet

    def _update_project_bindings(self) -> None:
        """Update key bindings based on project selection state."""
        project_bindings = [
            ("r", "remove_project", "Remove"),
            ("s", "start_selected", "Start"),
            ("x", "stop_selected", "Stop"),
            ("S", "start_all", "All▶"),
            ("X", "stop_all", "All⏹"),
            ("k", "skip_feature", "Skip"),
            ("w", "show_workflow", "Flow"),
            ("c", "config_project", "Conf"),
            ("b", "config_backends", "Back"),
            ("p", "config_prompts", "Prmt"),
            ("R", "reset_project", "Reset"),
        ]

        if self.selected_project is not None and not self._project_bindings_active:
            # Add project-specific bindings
            for key, action, description in project_bindings:
                self.bind(key, action, description=description, show=True)
            self._project_bindings_active = True
        elif self.selected_project is None and self._project_bindings_active:
            # Remove project-specific bindings
            for key, action, description in project_bindings:
                try:
                    self.unbind(key)
                except Exception:
                    pass
            self._project_bindings_active = False

    async def _add_project(self, path: Path) -> None:
        """Add a project to the app via service."""
        try:
            await self.project_service.add_project(path)
        # UI updates handled by _on_project_added event
        except Exception as e:
            self._log(f"[ERROR] Failed to add project {path}: {e}")

    def _on_project_added(self, event: ProjectAddedEvent) -> None:
        """Handle project added event."""
        path = event.project_path
        project = self.projects.get(path)
        if not project:
            return

        workflow = self.workflows.get(path)

        # Select this project automatically
        self.selected_project = path
        if self.workflow_panel and workflow:
            self.workflow_panel.set_workflow(workflow)
        if self.log_panel:
            self.log_panel.set_filter(path)
        self._update_activity_log_title()
        self._update_project_bindings()

        # Add card to UI
        try:
            project_list = self.query_one("#project-list", Container)
            project_id = self._get_project_id(path)
            # Check if card already exists
            try:
                self.query_one(f"#{project_id}", ProjectCard)
            except Exception:
                card = ProjectCard(project, id=project_id)
                project_list.mount(card)
        except Exception as e:
            self._log(f"Error mounting project card: {e}", project_path=path)

        self._log(f"Added project: {project.name} ({path})")

        if not project.has_best_practices():
            self._log(f"  ⚠ Warning: No BEST_PRACTICES.md found in {path}")

        # Check for config migration
        self.run_worker(self._check_config_migration(project))

    async def _check_config_migration(self, project: Project) -> None:
        """Check for legacy config and offer migration."""
        migrator = ConfigMigrator(project.path)
        if migrator.needs_migration():
            result = await self.push_screen(
                ConfirmModal(
                    "Legacy Configuration Detected",
                    "Convert .agent-pump.yml to new directory structure?\n"
                    "This enables per-phase prompt customization via markdown files.",
                )
            )
            if result:
                migrator.migrate(remove_legacy=False)  # Keep backup
                self.notify("Config migrated to .agent-pump/ directory")

    async def _on_ideas_processed(self, path: Path | None) -> None:
        """Callback when ideas have been processed by the workflow."""
        if path:
            # Logic is now event driven, but we might want to log
            self._log("Project idea queue processed and cleared", project_path=path)
        """Callback when ideas have been processed by the workflow."""
        project_config = self.workspace.get_project_config(path)
        if project_config:
            # Clear ideas from project queue
            # This is already handled by IdeaService/ProjectService emitting the event.
            pass
            self._log("Project idea queue processed and cleared", project_path=path)

    def _on_workflow_state_change(self, path: Path, old_state: str, new_state: str) -> None:
        """Handle workflow state changes."""
        # Update project card
        try:
            project_id = self._get_project_id(path)
            card = self.query_one(f"#{project_id}", ProjectCard)
            card.refresh_content()
        except Exception as e:
            # Card might not exist anymore
            # Card might not exist anymore, or ID mismatch
            self._log(f"[ERROR] Failed to update card for {path}: {e}", project_path=path)

        # Update workflow panel if selected
        if self.selected_project == path:
            workflow = self.workflows.get(path)
            if workflow and self.workflow_panel:
                self.workflow_panel.set_workflow(workflow)

    async def _remove_project(self, path: Path) -> None:
        """Remove a project from the app via service."""
        await self.project_service.remove_project(path)

    def _on_project_removed(self, event: ProjectRemovedEvent) -> None:
        """Handle project removed event."""
        path = event.project_path

        # Clear workflow panel if this was selected
        if self.selected_project == path:
            self.selected_project = None
            if self.workflow_panel:
                self.workflow_panel.set_workflow(None)
            if self.log_panel:
                self.log_panel.set_filter(None)
            self._update_activity_log_title()
            self._update_project_bindings()

        # Remove from UI
        try:
            project_id = self._get_project_id(path)
            card = self.query_one(f"#{project_id}", ProjectCard)
            card.remove()
        except Exception:
            pass

        self._log(f"Removed project: {path}")

    def _get_project_id(self, path: Path) -> str:
        """Generate a safe CSS ID for a project path."""
        import re

        name = path.name or "root"
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        # Ensure it doesn't start with a number if possible, or just prefix
        return f"project-{safe_name}"

    @work(group="workflow")
    async def _run_project(self, path: Path) -> None:
        """Run the workflow for a project via service."""
        await self.workflow_service.start_project(path)

    def action_add_project(self) -> None:
        """Handle add project action."""

        def handle_project_path(path: Path | None) -> None:
            if path:
                # worker task wrapper needed for async
                self.run_worker(self._add_project(path))

        self.push_screen(AddProjectModal(), handle_project_path)

    def action_remove_project(self) -> None:
        """Handle remove project action."""
        if self.selected_project:
            self.run_worker(self._remove_project(self.selected_project))

    def action_start_selected(self) -> None:
        """Start the selected project."""
        if self.selected_project:
            self._run_project(self.selected_project)
            project = self.projects.get(self.selected_project)
            if project:
                self._log(f"Started project: {project.name}")

    def action_stop_selected(self) -> None:
        """Stop the selected project."""
        if self.selected_project:
            self.run_worker(self.workflow_service.stop_project(self.selected_project))

    def action_start_all(self) -> None:
        """Start all projects."""
        self.run_worker(self.workflow_service.start_all())

        # Log handled by service? No, usage of start_all returns count
        # But we are running worker asynchronously.
        # We can wrap it to log count.
        async def run_start_all():
            count = await self.workflow_service.start_all()
            self._log(f"Started {count} projects")

        self.run_worker(run_start_all())

    def action_stop_all(self) -> None:
        """Stop all projects."""

        async def run_stop_all():
            count = await self.workflow_service.stop_all()
            self._log(f"Stopped {count} projects")

        self.run_worker(run_stop_all())

    def action_skip_feature(self) -> None:
        """Handle skip feature action."""
        if self.selected_project:
            workflow = self.workflows.get(self.selected_project)
            if workflow and workflow.project.current_feature:
                failed_feature = workflow.project.current_feature
                workflow.project.failed_features.append(failed_feature)
                workflow.project.current_feature = None

                # If running, pause it first
                if workflow.is_running():
                    workflow.cancel()

                self._log(f"Skipped feature: {failed_feature}")

        else:
            self._log("No project selected to skip feature")

    def action_show_workflow(self) -> None:
        """Force refresh of workflow diagram."""
        if self.workflow_panel and self.selected_project:
            workflow = self.workflows.get(self.selected_project)
            self.workflow_panel.set_workflow(workflow)

    async def action_add_idea(self) -> None:
        """Add an idea to the brainstorming queue."""
        from textual.containers import Vertical
        from textual.screen import ModalScreen
        from textual.widgets import Button, Input, Label

        class IdeaInputModal(ModalScreen[str | None]):
            """Modal for entering a new idea."""

            CSS = """
            IdeaInputModal {
                align: center middle;
            }
            IdeaInputModal > Vertical {
                width: 60;
                height: auto;
                border: thick $primary;
                background: $surface;
                padding: 1 2;
            }
            """

            def compose(self) -> ComposeResult:
                yield Vertical(
                    Label("Enter your idea for the brainstormer:"),
                    Input(placeholder="e.g., Add dark mode support", id="idea-input"),
                    Horizontal(
                        Button("Add", id="btn-add-idea", variant="success"),
                        Button("Cancel", id="btn-cancel", variant="default"),
                        classes="button-row",
                    ),
                )

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "btn-add-idea":
                    input_widget = self.query_one("#idea-input", Input)
                    self.dismiss(input_widget.value)
                else:
                    self.dismiss(None)

            def on_input_submitted(self, event: Input.Submitted) -> None:
                self.dismiss(event.value)

        def handle_idea(idea: str | None) -> None:
            if idea and idea.strip():
                if self.selected_project:
                    self.run_worker(
                        self.idea_service.add_idea(idea.strip(), project_path=self.selected_project)
                    )
                else:
                    self.run_worker(self.idea_service.add_idea(idea.strip()))
            else:
                self._log("No idea added")

        self.push_screen(IdeaInputModal(), handle_idea)

    def action_manage_roadmap(self) -> None:
        """Open the roadmap management modal."""
        if not self.selected_project:
            self._log("No project selected. Select a project first.")
            return

        project = self.projects[self.selected_project]
        roadmap_path = project.path / "ROADMAP.md"

        if not roadmap_path.exists():
            self._log(f"No ROADMAP.md found in {project.name}")
            return

        def handle_result(result: list[RoadmapFeature] | None) -> None:
            if result:
                self._log(f"Roadmap reordered for {project.name}")
                # Optionally trigger a workflow update if needed
            else:
                self._log("Roadmap management cancelled")

        self.push_screen(RoadmapModal(roadmap_path), handle_result)

    def action_config_project(self) -> None:
        """Configure project settings."""
        if not self.selected_project:
            self._log("No project selected. Select a project first.")
            return

        def handle_close(result: None) -> None:
            self._log(f"Configuration closed for {self.selected_project}")
            # Refresh config dependent properties
            if self.selected_project and self.selected_project in self.projects:
                config = Config.load(self.selected_project)
                self.projects[self.selected_project].backend = config.backend

                # Update workflow with new config
                workflow = self.workflows.get(self.selected_project)
                if workflow:
                    workflow.config = config

        self.push_screen(ProjectConfigModal(self.selected_project), handle_close)

    def action_config_backends(self) -> None:
        """Configure backend settings for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first with click/arrow keys.")
            return

        project_config = self.workspace.get_project_config(self.selected_project)
        if not project_config:
            self._log("Project not found in workspace config.")
            return

        def handle_result(phase_backends: PhaseBackends | None) -> None:
            if phase_backends is not None:
                self.run_worker(
                    self.workspace_service.update_backend_config(
                        self.selected_project, phase_backends
                    )
                )
            else:
                self._log("Backend configuration cancelled")

        self.push_screen(BackendConfigModal(project_config, self.workspace), handle_result)

    def action_config_prompts(self) -> None:
        """Configure prompt customizations for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first with click/arrow keys.")
            return

        project_config = self.workspace.get_project_config(self.selected_project)
        if not project_config:
            self._log("Project not found in workspace config.")
            return

        def handle_result(prompt_customization: PromptCustomization | None) -> None:
            if prompt_customization is not None:
                self.run_worker(
                    self.workspace_service.update_prompt_config(
                        self.selected_project, prompt_customization
                    )
                )
            else:
                self._log("Prompt customization cancelled")

        self.push_screen(PromptConfigModal(project_config, self.workspace), handle_result)

    def action_global_prompts(self) -> None:
        """Configure global prompt prefix/suffix per engine and model."""

        def handle_result(settings: GlobalPromptSettings | None) -> None:
            if settings is not None:
                self.run_worker(self.workspace_service.update_global_prompts(settings))
            else:
                self._log("Global prompt settings cancelled")

        self.push_screen(GlobalPromptModal(self.workspace.global_prompt_settings), handle_result)

    async def action_update_config(self) -> None:
        """Reload configuration and check for migration."""
        if not self.selected_project:
            self._log("No project selected to update config.")
            return

        project = self.projects.get(self.selected_project)
        if not project:
            return

        # Check migration again (force check)
        await self._check_config_migration(project)

        # Reload config
        try:
             # Force reload of config from disk
             new_config = Config.load(project.path)
             # Update project object
             project.backend = new_config.backend
             if self.selected_project in self.workflows:
                 self.workflows[self.selected_project].config = new_config

             self._log(f"Configuration reloaded for {project.name}")

             # Log which config file was used
             if (project.path / ".agent-pump" / "config.yml").exists():
                 self._log("  Using: .agent-pump/config.yml")
             elif (project.path / ".agent-pump.yml").exists():
                 self._log("  Using: .agent-pump.yml (Legacy)")

        except Exception as e:
            self._log(f"[ERROR] Failed to reload config: {e}")

    def action_open_settings(self) -> None:
        """Open the settings modal."""

        def handle_result(saved: bool | None) -> None:
            if saved:
                self._log("Settings saved")
            elif saved is False:  # Explicit False, not None
                self._log("Settings cancelled")
            # If None, modal was dismissed without explicit save/cancel

        self.push_screen(SettingsModal(self.workspace), handle_result)

    def action_filter_logs(self) -> None:
        """Configure activity log filters."""
        if not self.log_panel:
            return

        current_states = self.log_panel.filter_states
        current_task = self.log_panel.filter_task

        def handle_result(result: tuple[list[str], str | None] | None) -> None:
            if result is not None:
                states, task = result
                # Let's adjust logic: If user selected states, use them. If empty, assume NO filter on state?  # noqa: E501
                # The modal returns [] if nothing selected.
                # If the user explicitly selects nothing, maybe they mean nothing.
                # But the "Clear" button is distinct.

                # Let's assume sending None means "no filter".
                final_states = states if states else None
                # Use self.selected_project as current_project_path
                current_project_path = self.selected_project

                self.log_panel.set_filter(
                    project_path=current_project_path, states=final_states, task=task
                )

                filter_desc = []
                if final_states:
                    filter_desc.append(f"states={final_states}")
                if task:
                    filter_desc.append(f"task='{task}'")

                if filter_desc:
                    self._log(f"[UI] Log filter active: {', '.join(filter_desc)}")
                else:
                    self._log("[UI] Log filters cleared")

        self.push_screen(LogFilterModal(current_states, current_task), handle_result)

    def action_toggle_sort(self) -> None:
        """Toggle log sort order."""
        if self.log_panel:
            new_order = self.log_panel.toggle_sort()
            self.app_state.log_sort_order = new_order
            self.app_state.save()
            self._log(f"[UI] Log sort order: {new_order.upper()}")

    def action_toggle_workflow_panel(self) -> None:
        """Toggle the visibility of the workflow panel."""
        try:
            right_sidebar = self.query_one("#right-sidebar")
            if right_sidebar.display:
                right_sidebar.display = False
                self._log("[UI] Workflow panel hidden")
            else:
                right_sidebar.display = True
                self._log("[UI] Workflow panel shown")
        except Exception as e:
            self._log(f"[ERROR] Failed to toggle workflow panel: {e}")

    def action_toggle_timer(self) -> None:
        """Toggle timer display between elapsed time and time remaining."""
        ProjectCard.toggle_time_mode()
        mode = "time remaining" if ProjectCard.show_time_remaining else "elapsed time"
        self._log(f"[UI] Timer mode: {mode}")
        # Refresh all project cards to show the new mode immediately
        try:
            project_list = self.query_one("#project-list", Container)
            for card in project_list.query(ProjectCard):
                card.refresh_content()
        except Exception:
            pass

    def action_reset_project(self) -> None:
        """Reset the selected project's workflow state."""
        if not self.selected_project:
            self._log("No project selected.")
            return

        workflow = self.workflows.get(self.selected_project)
        if not workflow:
            return

        def on_confirm(confirm: bool | None) -> None:
            if confirm and self.selected_project:
                self.run_worker(self.workflow_service.reset_project(self.selected_project))

        self.push_screen(
            ConfirmModal(
                "Are you sure you want to RESET the workflow state?\n"
                "This will cancel any running tasks and set the state to IDLE.",
                confirm_label="Reset",
                cancel_label="Cancel",
            ),
            on_confirm,
        )

    async def action_quit(self) -> None:
        """Quit the application, properly cleaning up subprocesses."""
        import asyncio
        import warnings

        # Stop all workflows via service (fire and forget cancellation)
        await self.workflow_service.stop_all()

        # Cancel all Textual workers (background tasks)
        self.workers.cancel_all()

        # Give asyncio time to clean up subprocess transports
        await asyncio.sleep(0.2)

        # Suppress ResourceWarning for unclosed subprocess transports on Windows
        # These warnings occur because Python's garbage collector runs after the
        # event loop is closed, but the resources are already properly cleaned up
        warnings.filterwarnings(
            "ignore", category=ResourceWarning, message=".*unclosed transport.*"
        )

        self.exit()

    @on(Button.Pressed, "#btn-add")
    def action_add_project_button(self) -> None:
        """Handle add project button."""
        self.action_add_project()

    @on(Button.Pressed, "#btn-start-all")
    def action_start_all_button(self) -> None:
        """Handle start all button."""
        self.action_start_all()

    @on(Button.Pressed, "#btn-stop-all")
    def action_stop_all_button(self) -> None:
        """Handle stop all button."""
        self.action_stop_all()

    @on(ProjectCard.Selected)
    def handle_project_card_selected(self, event: ProjectCard.Selected) -> None:
        """Handle project card selection."""
        # Update UI selection state
        project_list = self.query_one("#project-list", Container)
        for card in project_list.query(ProjectCard):
            card.remove_class("selected")

        event.card.add_class("selected")

        self.selected_project = event.project.path
        self._log(f"Selected project: {event.project.name}")

        # Update workflow panel
        workflow = self.workflows.get(event.project.path)
        if self.workflow_panel:
            self.workflow_panel.set_workflow(workflow)

        # Update log filter
        if self.log_panel:
            self.log_panel.set_filter(event.project.path)
        self._update_activity_log_title()
        self._update_project_bindings()
