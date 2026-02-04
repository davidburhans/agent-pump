"""Main Textual application for agent-pump."""

from pathlib import Path

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, Static

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
    WorkspaceSwitchedEvent,
)
from agent_pump.keybindings import KEYBINDINGS
from agent_pump.models.app_state import AppState
from agent_pump.models.project import Project
from agent_pump.models.template import ProjectTemplate
from agent_pump.models.workspace import (
    GlobalPromptSettings,
    PhaseBackends,
)
from agent_pump.orchestrator.workflow_definition import (
    WorkflowDefinition,
    get_workflow,
)
from agent_pump.services.idea_service import IdeaService
from agent_pump.services.log_service import LogService
from agent_pump.services.metrics_service import MetricsService
from agent_pump.services.project_service import ProjectService
from agent_pump.services.template_service import TemplateService
from agent_pump.services.workflow_service import WorkflowService
from agent_pump.services.workspace_service import WorkspaceService
from agent_pump.tui.commands import AgentPumpCommandProvider
from agent_pump.tui.screens import (
    AddProjectModal,
    BackendConfigModal,
    BootstrapModal,
    GlobalPromptModal,
    IdeaInputModal,
    MetricsModal,
    ProjectConfigModal,
    ProjectSummaryModal,
    PromptConfigModal,
    RoadmapModal,
    SettingsModal,
    TemplateApplyModal,
    TemplateListModal,
    WorkflowEditorModal,
    WorkspaceSwitcherModal,
)
from agent_pump.tui.screens.confirm_modal import ConfirmModal
from agent_pump.tui.screens.log_filter_modal import LogFilterModal
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.workflow_panel import WorkflowNodeClicked, WorkflowPanel
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
        Binding(kb.key, kb.action, kb.description, show=kb.show_in_footer)
        for kb in KEYBINDINGS
        if kb.scope == "global"
    ]

    def __init__(self, project_paths: list[Path] | None = None, dry_run: bool = False):
        """
        Initialize the application.

        Args:
            project_paths: Initial list of project paths to manage
            dry_run: Whether to run in dry-run mode (preview only, no changes)
        """
        super().__init__()
        self.project_paths = project_paths or []
        self.dry_run = dry_run

        # Initialize services
        self.app_state = AppState.load()
        self.event_bus = EventBus()
        self.workspace_service = WorkspaceService(self.event_bus, self.app_state)
        # Using placeholder for workspace service loading;
        # it will lazily load workspace or we can init it.
        # But ProjectService needs workspace.
        self.workspace = self.workspace_service.get_current_workspace()

        self.project_service = ProjectService(self.event_bus, self.workspace, self.app_state)
        self.workflow_service = WorkflowService(self.event_bus, self.project_service)
        self.idea_service = IdeaService(self.event_bus, self.workspace)
        self.log_service = LogService(self.event_bus)
        self.metrics_service = MetricsService(self.event_bus, self.workspace.name)

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
        with Container(id="app-container"):
            with Horizontal(id="main-layout"):
                with Vertical(id="sidebar"):
                    yield Static("Projects", classes="section-title")
                    yield Container(id="project-list")
                    with Horizontal(classes="button-row"):
                        yield Button(
                            "+ Add",
                            id="btn-add",
                            variant="success",
                            tooltip="Add a new project (a)",
                        )
                        yield Button(
                            "▶ Start All",
                            id="btn-start-all",
                            variant="primary",
                            tooltip="Start all projects (S)",
                        )
                        yield Button(
                            "⏹ Stop All",
                            id="btn-stop-all",
                            variant="error",
                            tooltip="Stop all projects (X)",
                        )
                        yield Label("v0.1.0", classes="dim")

                with Vertical(id="main-content"):
                    yield Static("Activity Log", id="activity-log-title", classes="section-title")
                    yield LogPanel(id="log-panel")

                with Vertical(id="right-sidebar"):
                    yield Static("Workflow State", classes="section-title")
                    yield WorkflowPanel(id="workflow-panel")

        yield Footer()
        yield Static("Quit [Esc]", id="quit-button")

    async def on_mount(self) -> None:
        """Called when app is mounted."""
        self.log_panel = self.query_one("#log-panel", LogPanel)

        # Apply persisted sort order
        if self.log_panel:
            self.log_panel.set_sort_order(self.app_state.log_sort_order)

        self.workflow_panel = self.query_one("#workflow-panel", WorkflowPanel)
        self._log("Agent Pump started")
        self._log("Press 'a' to add a project, 'escape' to quit")
        self._log(f"Log sort order: {self.app_state.log_sort_order.upper()}")

        # Start services
        await self.log_service.start()
        await self.metrics_service.start()

        # Start event loop
        _ = self.run_worker(self._handle_events())
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
                await self._on_ideas_processed(event.project_path)
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
            elif isinstance(event, WorkspaceSwitchedEvent):
                self._log(f"Workspace switched from {event.old_workspace} to {event.new_workspace}")

    def _log(
        self,
        message: str,
        project_path: Path | None = None,
        state: str = "unknown",
        task: str | None = None,
    ) -> None:
        """Log a message to the log panel."""
        if self.log_panel:
            self.log_panel.log_message(message, project_path=project_path, state=state, task=task)

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
        project_bindings = [kb for kb in KEYBINDINGS if kb.scope == "project"]

        if self.selected_project is not None and not self._project_bindings_active:
            # Add project-specific bindings
            for kb in project_bindings:
                self.bind(kb.key, kb.action, description=kb.description, show=kb.show_in_footer)
            self._project_bindings_active = True
        elif self.selected_project is None and self._project_bindings_active:
            # Remove project-specific bindings
            # Textual App does not support unbind, so we just set them to not show
            # and rely on the handlers checking for selected_project
            for kb in project_bindings:
                # Overwrite with show=False to hide from footer
                self.bind(kb.key, kb.action, description=kb.description, show=False)
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

    async def _on_ideas_processed(self, path: Path | None) -> None:
        """Callback when ideas have been processed by the workflow."""
        if path:
            # Logic is now event driven, but we might want to log
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

    def action_toggle_project_state(self) -> None:
        """Toggle the start/stop state of the selected project."""
        if not self.selected_project:
            return

        workflow = self.workflows.get(self.selected_project)
        if not workflow:
            return

        if workflow.is_running():
            self.action_stop_selected()
        else:
            self.action_start_selected()

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

    async def action_add_idea(self) -> None:
        """Add an idea to the brainstorming queue."""

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

    def action_show_summary(self) -> None:
        """Show the project summary modal."""
        if not self.selected_project:
            self._log("No project selected.")
            return

        project = self.projects.get(self.selected_project)
        if not project:
            return

        self.push_screen(ProjectSummaryModal(project))

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

    def action_config_prompts(self, initial_phase: str | None = None) -> None:
        """Configure prompt customizations for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first with click/arrow keys.")
            return

        project_config = self.workspace.get_project_config(self.selected_project)
        if not project_config:
            self._log("Project not found in workspace config.")
            return

        def handle_result(result: None) -> None:
            pass

        self.push_screen(
            PromptConfigModal(project_config, self.workspace, initial_phase=initial_phase),
            handle_result,
        )

    def action_edit_workflow(self) -> None:
        """Open the workflow editor for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first with click/arrow keys.")
            return

        project_config = self.workspace.get_project_config(self.selected_project)
        if not project_config:
            self._log("Project not found in workspace config.")
            return

        # Get the current workflow for this project
        current_workflow_name = getattr(project_config, "workflow_name", "default")
        try:
            current_workflow = get_workflow(
                current_workflow_name, self.workspace.workflow_definitions
            )
        except KeyError:
            # Fallback to default if workflow not found
            current_workflow = get_workflow("default")

        def handle_result(result: WorkflowDefinition | None) -> None:
            if result is not None:
                # Update project to use the edited workflow
                project_config.workflow_name = result.name
                self.workspace.save()
                self._log(f"Workflow updated to '{result.name}' for project {project_config.name}")
            else:
                self._log("Workflow editor closed without saving")

        self.push_screen(
            WorkflowEditorModal(self.workspace, current_workflow),
            handle_result,
        )

    @on(WorkflowNodeClicked)
    def on_workflow_node_clicked(self, event: WorkflowNodeClicked) -> None:
        """Handle workflow node clicks."""
        phase = event.node_name
        # Only open config for actual phases
        if phase in ["planning", "implementing", "verifying", "brainstorming", "committing"]:
            self.action_config_prompts(initial_phase=phase)

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

    def action_show_metrics(self) -> None:
        """Open the metrics and analytics dashboard."""
        self.push_screen(MetricsModal(self.metrics_service))

    def action_templates(self) -> None:
        """Open the template browser modal."""
        from agent_pump.services.template_service import TemplateService

        # Get all available templates
        template_service = TemplateService(self.event_bus, self.workspace)
        templates = template_service.list_templates()

        def handle_list_result(selected_template: ProjectTemplate | None) -> None:
            if selected_template is None:
                self._log("Template browser closed")
                return

            # Check if user wants to apply to existing or create new
            # We use a dynamic attribute set in the modal to determine this
            is_new_project = getattr(selected_template, "is_new_project", False)

            if is_new_project:
                # Create new project from template
                self._handle_create_from_template(selected_template, template_service)
            else:
                # Apply to existing project
                if self.selected_project:
                    self._handle_apply_template(
                        selected_template, self.selected_project, template_service
                    )
                else:
                    # No project selected, show apply modal for user to enter path
                    self._handle_apply_template(selected_template, None, template_service)

        self.push_screen(TemplateListModal(templates, self.workspace), handle_list_result)

    def _handle_apply_template(
        self,
        template: ProjectTemplate,
        existing_project: Path | None,
        template_service: TemplateService,
    ) -> None:
        """Handle applying a template to an existing or new project path.

        Args:
            template: The template to apply.
            existing_project: Path to existing project, or None to prompt for path.
            template_service: The template service for applying templates.
        """

        def handle_apply_result(project_path: Path | None) -> None:
            if project_path:
                self._log(f"Applied template '{template.name}' to {project_path}")
                # Refresh project config if it was an existing project
                if existing_project and existing_project in self.projects:
                    self._refresh_project_config(existing_project)
            else:
                self._log("Template application cancelled")

        self.push_screen(
            TemplateApplyModal(
                template=template,
                existing_project=existing_project,
                is_new_project=False,
                template_service=template_service,
            ),
            handle_apply_result,
        )

    def _handle_create_from_template(
        self, template: ProjectTemplate, template_service: TemplateService
    ) -> None:
        """Handle creating a new project from a template.

        Args:
            template: The template to use.
            template_service: The template service for creating projects.
        """

        def handle_create_result(project_path: Path | None) -> None:
            if project_path:
                self._log(f"Created new project from template '{template.name}': {project_path}")
                # Add the new project to the app
                self.run_worker(self._add_project(project_path))
            else:
                self._log("Project creation from template cancelled")

        self.push_screen(
            TemplateApplyModal(
                template=template,
                is_new_project=True,
                template_service=template_service,
            ),
            handle_create_result,
        )

    def _refresh_project_config(self, project_path: Path) -> None:
        """Refresh project configuration after template application.

        Args:
            project_path: Path to the project to refresh.
        """
        if project_path not in self.projects:
            return

        project = self.projects[project_path]
        try:
            # Reload config from disk
            from agent_pump.config import Config

            new_config = Config.load(project.path)
            project.backend = new_config.backend

            # Update workflow with new config
            workflow = self.workflows.get(project_path)
            if workflow:
                workflow.config = new_config

            self._log(f"Configuration refreshed for {project.name}")
        except Exception as e:
            self._log(f"[ERROR] Failed to refresh config: {e}")

    def action_switch_workspace(self) -> None:
        """Open the workspace switcher modal."""
        from agent_pump.models.workspace import Workspace

        workspaces = Workspace.list_workspaces()
        current = self.workspace.name if self.workspace else "default"

        def handle_result(result: str | None) -> None:
            if result is None:
                self._log("Workspace switch cancelled")
                return

            if result not in workspaces:
                # This is a new workspace name from the create flow
                self._create_and_switch_workspace(result)
            else:
                # User selected an existing workspace to switch to
                self.run_worker(self._do_workspace_switch(result))

        self.push_screen(WorkspaceSwitcherModal(workspaces, current), handle_result)

    async def _do_workspace_switch(self, workspace_name: str) -> None:
        """Perform the actual workspace switch."""
        self._log(f"Switching to workspace: {workspace_name}")

        # Stop all running workflows for safety
        await self.workflow_service.stop_all()

        # Switch workspace via service
        new_workspace = await self.workspace_service.switch_workspace(workspace_name)

        # Update local workspace reference
        self.workspace = new_workspace

        # Clear current projects from UI
        await self._clear_all_projects()

        # Reload projects from new workspace
        await self._load_workspace_projects()

        self._log(f"Switched to workspace: {workspace_name}")
        self.notify(f"Switched to workspace: {workspace_name}")

    async def _clear_all_projects(self) -> None:
        """Remove all project cards from the UI."""
        try:
            project_list = self.query_one("#project-list", Container)
            for card in list(project_list.query(ProjectCard)):
                card.remove()
        except Exception as e:
            self._log(f"[ERROR] Failed to clear project list: {e}")

        # Clear internal state
        self.selected_project = None
        if self.workflow_panel:
            self.workflow_panel.set_workflow(None)
        if self.log_panel:
            self.log_panel.set_filter(None)

    async def _load_workspace_projects(self) -> None:
        """Load all projects from the current workspace."""
        if not self.workspace:
            return

        for path_str in self.workspace.projects:
            try:
                path = Path(path_str)
                if path.exists():
                    await self._add_project(path)
            except Exception as e:
                self._log(f"[ERROR] Failed to load project {path_str}: {e}")

    def _create_and_switch_workspace(self, name: str) -> None:
        """Create a new workspace and switch to it."""
        from agent_pump.models.workspace import Workspace

        name = name.strip()
        existing = Workspace.list_workspaces()

        if name in existing:
            self._log(f"[ERROR] Workspace '{name}' already exists")
            self.notify(f"Workspace '{name}' already exists", severity="error")
            return

        # Create the workspace
        workspace = Workspace(name=name)
        workspace.save()

        self._log(f"Created workspace: {name}")
        self.notify(f"Created workspace: {name}")

        # Switch to the new workspace
        self.run_worker(self._do_workspace_switch(name))

    def action_filter_logs(self) -> None:
        """Configure activity log filters."""
        if not self.log_panel:
            return

        current_states = self.log_panel.filter_states
        current_task = self.log_panel.filter_task

        def handle_result(result: tuple[list[str], str | None] | None) -> None:
            if result is not None:
                states, task = result
                # Let's adjust logic: If user selected states, use them.
                # If empty, assume NO filter on state?
                # The modal returns [] if nothing selected.
                # If the user explicitly selects nothing, maybe they mean nothing.
                # But the "Clear" button is distinct.

                # Let's assume sending None means "no filter".
                final_states = states if states else None
                # Use self.selected_project as current_project_path
                current_project_path = self.selected_project

                if self.log_panel:
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

    def action_show_checkpoints(self) -> None:
        """Show checkpoint list and allow rollback for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first.")
            return

        workflow = self.workflows.get(self.selected_project)
        if not workflow:
            self._log("Workflow not found for selected project.")
            return

        # Get checkpoints from workflow state
        checkpoints = workflow.workflow_state.list_checkpoints()
        current_feature = workflow.project.current_feature

        def handle_result(result: tuple[str, str] | None) -> None:
            if result is None:
                self._log("Checkpoint modal closed")
                return

            action, checkpoint_id = result
            if action == "rollback":
                self.run_worker(self._do_rollback(checkpoint_id))

        from agent_pump.tui.screens.checkpoint_modal import CheckpointModal

        self.push_screen(
            CheckpointModal(checkpoints=checkpoints, current_feature=current_feature),
            handle_result,
        )

    async def _do_rollback(self, checkpoint_id: str) -> None:
        """Perform the actual rollback operation."""
        if not self.selected_project:
            return

        try:
            result = await self.workflow_service.rollback_to_checkpoint(
                self.selected_project, checkpoint_id
            )
            if result:
                self._log(f"Successfully rolled back to checkpoint {checkpoint_id}")
                self.notify(f"Rolled back to checkpoint {checkpoint_id}", severity="information")
            else:
                self._log(f"Failed to rollback: checkpoint {checkpoint_id} not found")
                self.notify("Rollback failed: checkpoint not found", severity="error")
        except Exception as e:
            self._log(f"[ERROR] Rollback failed: {e}")
            self.notify(f"Rollback failed: {e}", severity="error")

    def action_create_checkpoint(self) -> None:
        """Create a manual checkpoint for the selected project."""
        if not self.selected_project:
            self._log("No project selected. Select a project first.")
            return

        workflow = self.workflows.get(self.selected_project)
        if not workflow:
            self._log("Workflow not found for selected project.")
            return

        # Use the current feature name or a generic description
        feature = workflow.project.current_feature
        description = "Manual checkpoint" + (f" for {feature}" if feature else "")

        self.run_worker(self._do_create_checkpoint(description))

    async def _do_create_checkpoint(self, description: str) -> None:
        """Perform the actual checkpoint creation."""
        if not self.selected_project:
            return

        try:
            checkpoint = await self.workflow_service.create_manual_checkpoint(
                self.selected_project, description
            )
            if checkpoint:
                self._log(f"Created checkpoint {checkpoint.id}: {checkpoint.description}")
                self.notify(
                    f"Checkpoint created: {checkpoint.get_short_hash()}",
                    severity="information",
                )
            else:
                self._log("Failed to create checkpoint")
                self.notify("Failed to create checkpoint", severity="error")
        except Exception as e:
            self._log(f"[ERROR] Failed to create checkpoint: {e}")
            self.notify(f"Checkpoint creation failed: {e}", severity="error")

    async def action_quit(self) -> None:
        """Quit the application, properly cleaning up subprocesses."""
        import asyncio
        import warnings

        # Stop all workflows via service (fire and forget cancellation)
        await self.workflow_service.stop_all()

        # Give workflows time to acknowledge cancellation
        await asyncio.sleep(0.1)

        # Gracefully shutdown workflow service and wait for tasks
        await self.workflow_service.shutdown()

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

    def on_click(self, event: events.Click) -> None:
        """Handle click events."""
        # Check if we clicked the quit indicator
        try:
            widget, _ = self.get_widget_at(event.screen_x, event.screen_y)
            if widget and widget.id == "quit-button":
                self.run_worker(self.action_quit())
        except Exception:
            pass

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

    @on(ProjectCard.BackendConfigRequested)
    def on_project_card_backend_config_requested(
        self, event: ProjectCard.BackendConfigRequested
    ) -> None:
        """Handle backend config request from project card."""
        # Ensure project is selected
        if self.selected_project != event.project.path:
            self.handle_project_card_selected(ProjectCard.Selected(event.project, event.card))

        # Open backend config
        self.action_config_backends()

    def action_bootstrap_project(self) -> None:
        """Open the project bootstrap modal.

        Allows users to bootstrap a project with AI-generated ROADMAP.md
        and BEST_PRACTICES.md files.
        """

        def handle_bootstrap_result(result: tuple[Path, str, bool] | None) -> None:
            """Handle the result from the bootstrap modal.

            Args:
                result: Tuple of (path, backend, dry_run) or None if cancelled.
            """
            if result is None:
                self._log("Bootstrap cancelled")
                return

            path, backend_name, dry_run = result
            self.run_worker(self._bootstrap_project(path, backend_name, dry_run))

        # Use currently selected project as initial path if available
        initial_path = self.selected_project
        self.push_screen(BootstrapModal(initial_path=initial_path), handle_bootstrap_result)

    async def _bootstrap_project(self, path: Path, backend_name: str, dry_run: bool) -> None:
        """Execute the bootstrap operation.

        Args:
            path: Path to the project to bootstrap.
            backend_name: Name of the AI backend to use.
            dry_run: Whether to run in dry-run mode.
        """
        from agent_pump.backends import get_backend
        from agent_pump.services.bootstrap_service import BootstrapService

        self._log(f"Bootstrapping project: {path.name}")
        self._log(f"Using backend: {backend_name}")

        if dry_run:
            self._log("[DRY RUN] Preview mode - no files will be written")

        try:
            service = BootstrapService(self.event_bus)
            backend = get_backend(backend_name)

            result = await service.bootstrap_project(
                project_path=path,
                backend=backend,
                dry_run=dry_run,
            )

            if result.success:
                if dry_run:
                    self._log(f"[DRY RUN] Preview complete for {path.name}")
                    if result.roadmap_content:
                        preview = (
                            result.roadmap_content[:300] + "..."
                            if len(result.roadmap_content) > 300
                            else result.roadmap_content
                        )
                        self._log(f"ROADMAP.md preview:\n{preview}")
                else:
                    self._log(f"[SUCCESS] Bootstrapped {path.name}")
                    if result.files_written:
                        for f in result.files_written:
                            self._log(f"  Created: {f}")

                    # If project is already managed, refresh its config
                    if path in self.projects:
                        self._refresh_project_config(path)
            else:
                self._log(f"[ERROR] Bootstrap failed: {result.error_message}")

        except Exception as e:
            self._log(f"[ERROR] Bootstrap error: {e}")
