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
from agent_pump.models.workspace import PhaseBackends, PromptCustomization, Workspace
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.tui.screens import AddProjectModal, BackendConfigModal, PromptConfigModal
from agent_pump.tui.widgets.log_panel import LogPanel
from agent_pump.tui.widgets.project_card import ProjectCard
from agent_pump.tui.widgets.workflow_panel import WorkflowPanel


class AgentPumpApp(App):
    """Main TUI application for Agent Pump."""

    TITLE = "Agent Pump"
    SUB_TITLE = "AI Coding Agent Orchestrator"

    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("a", "add_project", "Add Project"),
        Binding("r", "remove_project", "Remove Project"),
        Binding("s", "start_selected", "Start"),
        Binding("x", "stop_selected", "Stop"),
        Binding("S", "start_all", "Start All"),
        Binding("X", "stop_all", "Stop All"),
        Binding("k", "skip_feature", "Skip Feature"),
        Binding("d", "toggle_dark", "Toggle Dark"),
        Binding("w", "show_workflow", "Show Workflow"),
        Binding("i", "add_idea", "Add Idea"),
        Binding("b", "config_backends", "Backends"),
        Binding("p", "config_prompts", "Prompts"),
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
                    Static("Activity Log", classes="section-title"),
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
        self.workflow_panel = self.query_one("#workflow-panel", WorkflowPanel)
        self._log("Agent Pump started")
        self._log("Press 'a' to add a project, 'q' to quit")

        # Load initial projects
        for path in self.project_paths:
            self._add_project(path)

    def _log(self, message: str, project_path: Path | None = None) -> None:
        """Log a message to the log panel."""
        if self.log_panel:
            self.log_panel.write(message, project_path=project_path)

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

            # Get queued ideas for brainstorming
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
                phase_backends=phase_backends,
                prompt_customization=prompt_customization,
                idea_queue=idea_queue,
                on_output=lambda msg, p=path: self._log(msg, project_path=p),
                on_state_change=lambda old, new, p=path: self._on_workflow_state_change(p, old, new),
            )
            self.workflows[path] = workflow

            # Select this project automatically
            self.selected_project = path
            if self.workflow_panel:
                self.workflow_panel.set_workflow(workflow)
            if self.log_panel:
                self.log_panel.set_filter(path)

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

    def _on_workflow_state_change(self, path: Path, old_state: str, new_state: str) -> None:
        """Handle workflow state changes."""
        # Update project card
        try:
            project_id = self._get_project_id(path)
            card = self.query_one(f"#{project_id}", ProjectCard)
            card.refresh_content()
        except Exception:
            # Card might not exist anymore
            pass

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
        from textual.widgets import Input
        from textual.screen import ModalScreen
        from textual.containers import Vertical
        from textual.widgets import Button, Label

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
                self.workspace.add_idea(idea.strip())
                self.workspace.save()
                self._log(f"Added idea to queue: {idea.strip()}")
                self._log(f"Total ideas in queue: {len(self.workspace.idea_queue)}")
            else:
                self._log("No idea added")

        self.push_screen(IdeaInputModal(), handle_idea)

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

        self.push_screen(BackendConfigModal(project_config), handle_result)

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

        self.push_screen(PromptConfigModal(project_config), handle_result)

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
