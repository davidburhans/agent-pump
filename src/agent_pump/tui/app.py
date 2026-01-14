"""Main Textual application for agent-pump."""

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from agent_pump.backends import get_backend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.config import Config
from agent_pump.models.app_state import AppState
from agent_pump.models.project import Project
from agent_pump.models.workspace import (
    GlobalPromptSettings,
    IdeaQueueItem,
    PhaseBackends,
    PromptCustomization,
    Workspace,
)
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.tui.screens import (
    AddProjectModal,
    BackendConfigModal,
    GlobalPromptModal,
    ProjectConfigModal,
    PromptConfigModal,
    RoadmapModal,
)
from agent_pump.tui.screens.confirm_modal import ConfirmModal
from agent_pump.tui.screens.log_filter_modal import LogFilterModal
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.workflow_panel import WorkflowPanel
from agent_pump.utils.roadmap import RoadmapFeature


class AgentPumpApp(App):
    """Main TUI application for Agent Pump."""

    TITLE = "Agent Pump"
    SUB_TITLE = "AI Coding Agent Orchestrator"

    CSS_PATH = "styles/app.tcss"

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
        Binding("t", "toggle_timer", "Timer"),
        Binding("W", "toggle_workflow_panel", "Flow Panel"),
    ]

    def __init__(self, project_paths: list[Path] | None = None):
        """
        Initialize the application.

        Args:
            project_paths: Initial list of project paths to manage
        """
        super().__init__()
        self.project_paths = project_paths or []
        self.projects: dict[Path, Project] = {}
        self.workflows: dict[Path, ProjectWorkflow] = {}
        self.log_panel: LogPanel | None = None
        self.workflow_panel: WorkflowPanel | None = None
        self.selected_project: Path | None = None
        self.app_state = AppState.load()
        # Load workspace for backend configuration
        self.workspace = Workspace.load(self.app_state.current_workspace)
        # Track project-specific bindings
        self._project_bindings_active = False

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

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.log_panel = self.query_one("#log-panel", LogPanel)

        # Apply persisted sort order
        if self.log_panel:
            self.log_panel.set_sort_order(self.app_state.log_sort_order)

        self.workflow_panel = self.query_one("#workflow-panel", WorkflowPanel)
        self._log("Agent Pump started")
        self._log("Press 'a' to add a project, 'q' to quit")
        self._log(f"Log sort order: {self.app_state.log_sort_order.upper()}")

        # Load initial projects
        for path in self.project_paths:
            self._add_project(path)

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

    def _add_project(self, path: Path) -> None:
        """Add a project to the app."""
        path = path.resolve()

        if path in self.projects:
            self._log(f"Project already added: {path}")
            return

        try:
            project = Project.from_path(path)
            self.projects[path] = project

            # Load config
            config = Config.load(path)
            project.branch = config.workflow.branch
            project.backend = config.backend

            # Get phase backends from workspace if available
            project_config = self.workspace.get_project_config(path)
            phase_backends = project_config.phase_backends if project_config else None
            prompt_customization = project_config.prompt_customization if project_config else None

            # Get queued ideas for brainstorming from project config if available
            idea_queue = []
            if project_config and project_config.idea_queue:
                idea_queue = [item.idea for item in project_config.idea_queue]
            elif not project_config:
                # Fallback to global queue if no project config (unlikely)
                idea_queue = self.workspace.peek_ideas()

            # Determine primary backend
            if project_config and project_config.phase_backends.implementing.backends:
                backend_instance = project_config.phase_backends.implementing.backends[0]
                try:
                    backend = get_backend(backend_instance.name)
                except ValueError:
                    backend = GeminiBackend()
            else:
                backend = GeminiBackend()

            workflow = ProjectWorkflow(
                project=project,
                backend=backend,
                config=config,
                project_config=project_config,
                phase_backends=phase_backends,
                prompt_customization=prompt_customization,
                idea_queue=idea_queue,
                on_output=lambda msg, s, t, p=path: self._log(msg, project_path=p, state=s, task=t),
                on_state_change=lambda old, new, p=path: self._on_workflow_state_change(
                    p, old, new
                ),
                on_ideas_processed=lambda p=path: self._on_ideas_processed(p),
            )
            self.workflows[path] = workflow

            # Select this project automatically
            self.selected_project = path
            if self.workflow_panel:
                self.workflow_panel.set_workflow(workflow)
            if self.log_panel:
                self.log_panel.set_filter(path)
            self._update_activity_log_title()
            self._update_project_bindings()

            # Add card to UI
            project_list = self.query_one("#project-list", Container)
            project_id = self._get_project_id(path)
            card = ProjectCard(project, id=project_id)
            project_list.mount(card)

            self._log(f"Added project: {project.name} ({path})")

            # Persist to global state
            if self.app_state.add_project(path):
                self.app_state.save()

            # Add to workspace and save
            self.workspace.add_project(path)
            self.workspace.save()

            if not project.has_roadmap():
                self._log(f"  ⚠ Warning: No ROADMAP.md found in {path}")
            if not project.has_best_practices():
                self._log(f"  ⚠ Warning: No BEST_PRACTICES.md found in {path}")
        except Exception as e:
            self._log(f"[ERROR] Failed to add project {path}: {e}")
            if path in self.projects:
                del self.projects[path]

    def _on_ideas_processed(self, path: Path) -> None:
        """Callback when ideas have been processed by the workflow."""
        project_config = self.workspace.get_project_config(path)
        if project_config:
            # Clear ideas from project queue
            project_config.idea_queue = []
            self.workspace.save()
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

    def _remove_project(self, path: Path) -> None:
        """Remove a project from the app."""
        if path not in self.projects:
            return

        # Cancel workflow if running
        workflow = self.workflows.get(path)
        if workflow and workflow.is_running():
            workflow.cancel()

        # Remove from state
        del self.projects[path]
        del self.workflows[path]

        # Persist removal
        if self.app_state.remove_project(path):
            self.app_state.save()

        # Remove from workspace
        if self.workspace.remove_project(path):
            self.workspace.save()

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
        """Run the workflow for a project."""
        workflow = self.workflows.get(path)
        if not workflow:
            return

        # Prevent double-execution of the same workflow
        if workflow.is_running():
            return

        config = Config.load(path)
        try:
            await workflow.run(max_iterations=config.workflow.max_iterations)
        except Exception as e:
            self._log(f"[ERROR] Workflow failed for {path.name}: {e}", project_path=path)

    def action_add_project(self) -> None:
        """Handle add project action."""

        def handle_project_path(path: Path | None) -> None:
            if path:
                self._add_project(path)

        self.push_screen(AddProjectModal(), handle_project_path)

    def action_remove_project(self) -> None:
        """Handle remove project action."""
        if self.selected_project:
            self._remove_project(self.selected_project)

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
            workflow = self.workflows.get(self.selected_project)
            if workflow and workflow.is_running():
                workflow.cancel()
                project = self.projects.get(self.selected_project)
                if project:
                    self._log(f"Stopped project: {project.name}")

    def action_start_all(self) -> None:
        """Start all projects."""
        count = 0
        for path in self.projects:
            workflow = self.workflows.get(path)
            # Only start if not already running
            if workflow and not workflow.is_running():
                self._run_project(path)
                count += 1
        self._log(f"Started {count} projects")

    def action_stop_all(self) -> None:
        """Stop all projects."""
        count = 0
        for workflow in self.workflows.values():
            if workflow.is_running():
                workflow.cancel()
                count += 1
        self._log(f"Stopped {count} projects")

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
                    project_config = self.workspace.get_project_config(self.selected_project)
                    if project_config:
                        project_config.idea_queue.append(IdeaQueueItem(idea=idea.strip()))
                        self.workspace.save()
                        self._log(f"Added idea to project queue: {idea.strip()}")
                else:
                    self.workspace.add_idea(idea.strip())
                    self.workspace.save()
                    self._log(f"Added idea to global queue: {idea.strip()}")
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
            if phase_backends is not None and project_config is not None:
                project_config.phase_backends = phase_backends
                self.workspace.save()
                self._log(f"Backend configuration saved for {project_config.name}")
                # Update the workflow if it exists
                workflow = self.workflows.get(self.selected_project)  # type: ignore
                if workflow:
                    workflow.phase_backends = phase_backends
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
            if prompt_customization is not None and project_config is not None:
                project_config.prompt_customization = prompt_customization
                self.workspace.save()
                self._log(f"Prompt customization saved for {project_config.name}")
                # Update the workflow if it exists
                workflow = self.workflows.get(self.selected_project)  # type: ignore
                if workflow:
                    workflow.prompt_customization = prompt_customization
            else:
                self._log("Prompt customization cancelled")

        self.push_screen(PromptConfigModal(project_config, self.workspace), handle_result)

    def action_global_prompts(self) -> None:
        """Configure global prompt prefix/suffix per engine and model."""

        def handle_result(settings: GlobalPromptSettings | None) -> None:
            if settings is not None:
                self.workspace.global_prompt_settings = settings
                self.workspace.save()
                self._log("Global prompt settings saved")
            else:
                self._log("Global prompt settings cancelled")

        self.push_screen(GlobalPromptModal(self.workspace.global_prompt_settings), handle_result)

    def action_filter_logs(self) -> None:
        """Configure activity log filters."""
        if not self.log_panel:
            return

        current_states = self.log_panel.filter_states
        current_task = self.log_panel.filter_task

        def handle_result(result: tuple[list[str], str | None] | None) -> None:
            if result is not None:
                states, task = result
                # Preserve project path filter from panel
                current_project_path = self.log_panel.filter_path
                # Pass explicit None for empty list if that's what we want,
                # but set_filter expects list | None.
                # Logic in LogPanel: if states is not None, it filters.
                # So if user cleared filters (empty list), we should pass None or empty list?
                # LogPanel logic: "if self.filter_states is not None: if entry.state not in self.filter_states"  # noqa: E501
                # So if we pass [], it will show NOTHING (unless state is in []).
                # Wait, if user unchecks all, they probably want to see ALL?
                # Or do they want to see nothing? Usually "Clear Filters" implies see all.
                # My Clear button returns ([], None).

                # Let's adjust logic: If user selected states, use them. If empty, assume NO filter on state?  # noqa: E501
                # The modal returns [] if nothing selected.
                # If the user explicitly selects nothing, maybe they mean nothing.
                # But the "Clear" button is distinct.

                # Let's assume sending None means "no filter".
                final_states = states if states else None

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

        def on_confirm(confirm: bool) -> None:
            if confirm and self.selected_project:
                wf = self.workflows.get(self.selected_project)
                if wf:
                    wf.reset_workflow()
                    self._log(
                        f"Reset workflow for {wf.project.name}",
                        project_path=self.selected_project,
                    )

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

        # Cancel all running workflows
        for workflow in self.workflows.values():
            if workflow.is_running():
                workflow.cancel()

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add":
            self.action_add_project()
        elif event.button.id == "btn-start-all":
            self.action_start_all()
        elif event.button.id == "btn-stop-all":
            self.action_stop_all()

    def on_project_card_selected(self, event: ProjectCard.Selected) -> None:
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
