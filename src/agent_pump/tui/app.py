"""Main Textual application for agent-pump."""

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from agent_pump.backends.gemini import GeminiBackend
from agent_pump.config import Config
from agent_pump.models.project import Project
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.tui.screens import AddProjectModal
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
        Binding("p", "toggle_pause", "Pause/Resume"),
        Binding("s", "skip_feature", "Skip Feature"),
        Binding("d", "toggle_dark", "Toggle Dark"),
        Binding("w", "show_workflow", "Show Workflow"),
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
                        Button("▶ Start All", id="btn-start", variant="primary"),
                        Button("⏸ Pause All", id="btn-pause", variant="warning"),
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

    def _log(self, message: str) -> None:
        """Log a message to the log panel."""
        if self.log_panel:
            self.log_panel.write(message)

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

            # Create workflow
            workflow = ProjectWorkflow(
                project=project,
                backend=GeminiBackend(),
                on_output=self._log,
                on_state_change=self._on_workflow_state_change,
            )
            self.workflows[path] = workflow
            
            # Select this project automatically
            self.selected_project = path
            if self.workflow_panel:
                self.workflow_panel.set_workflow(workflow)

            # Add card to UI
            project_list = self.query_one("#project-list", Container)
            project_id = self._get_project_id(path)
            card = ProjectCard(project, id=project_id)
            project_list.mount(card)

            self._log(f"Added project: {project.name} ({path})")

            if not project.has_roadmap():
                self._log(f"  ⚠ Warning: No ROADMAP.md found in {path}")
            if not project.has_best_practices():
                self._log(f"  ⚠ Warning: No BEST_PRACTICES.md found in {path}")
        except Exception as e:
            self._log(f"[ERROR] Failed to add project {path}: {e}")
            if path in self.projects:
                del self.projects[path]

    def _on_workflow_state_change(self, old_state: str, new_state: str) -> None:
        """Handle workflow state changes."""
        # Find which project changed (simplified for now as we don't pass project in callback)
        #Ideally callback should include project reference
        # For now just refresh global log
        pass
        
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
        
        # Clear workflow panel if this was selected
        if self.selected_project == path:
            self.selected_project = None
            if self.workflow_panel:
                self.workflow_panel.set_workflow(None)

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

    @work(exclusive=True, group="workflow")
    async def _run_project(self, path: Path) -> None:
        """Run the workflow for a project."""
        workflow = self.workflows.get(path)
        if not workflow:
            return

        config = Config.load(path)
        await workflow.run(max_iterations=config.workflow.max_iterations)

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

    def action_toggle_pause(self) -> None:
        """Handle pause/resume action."""
        for workflow in self.workflows.values():
            if workflow.is_running():
                workflow.cancel()
                self._log("Paused all workflows")
                return

        # Resume first idle project
        for path, workflow in self.workflows.items():
            if workflow.state == "idle":  # type: ignore
                self._run_project(path)
                project = self.projects.get(path)
                project_name = project.name if project else str(path)
                self._log(f"Resumed workflow for: {project_name}")
                return

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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-add":
            self.action_add_project()
        elif event.button.id == "btn-start":
            for path in self.projects:
                self._run_project(path)
            self._log("Started all workflows")
        elif event.button.id == "btn-pause":
            for workflow in self.workflows.values():
                workflow.cancel()
            self._log("Paused all workflows")

    def on_project_card_selected(self, event: ProjectCard.Selected) -> None:
        """Handle project card selection."""
        self.selected_project = event.project.path
        self._log(f"Selected project: {event.project.name}")
        
        # Update workflow panel
        workflow = self.workflows.get(event.project.path)
        if self.workflow_panel:
            self.workflow_panel.set_workflow(workflow)
