"""Project management service."""

import logging
from pathlib import Path

from agent_pump.backends import get_backend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.config import Config
from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    ProjectAddedEvent,
    ProjectRemovedEvent,
    WorkflowStateChangedEvent,
)
from agent_pump.models.app_state import AppState
from agent_pump.models.project import Project
from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.base import BaseService
from agent_pump.api.schemas import ProjectStatusDTO

logger = logging.getLogger(__name__)


class ProjectService(BaseService):
    """Service for managing projects and their workflows."""

    def __init__(self, event_bus: EventBus, workspace: Workspace, app_state: AppState) -> None:
        """
        Initialize the project service.

        Args:
            event_bus: The event bus.
            workspace: The current workspace.
            app_state: The global app state.
        """
        super().__init__(event_bus)
        self.workspace = workspace
        self.app_state = app_state
        self.projects: dict[Path, Project] = {}
        self.workflows: dict[Path, ProjectWorkflow] = {}

    async def add_project(self, path: Path) -> Project:
        """
        Add a project to the workspace and initialize its workflow.

        Args:
            path: Absolute path to the project directory.

        Returns:
            The initialized Project object.
        """
        path = path.resolve()
        if path in self.projects:
            logger.info(f"Project already loaded: {path}")
            return self.projects[path]

        try:
            # Load project model
            project = Project.from_path(path)
            self.projects[path] = project

            # Load configuration
            config = Config.load(path)
            project.branch = config.workflow.branch
            project.backend = config.backend

            # Get workspace-level config overrides
            project_config = self.workspace.get_project_config(path)
            phase_backends = project_config.phase_backends if project_config else None
            prompt_customization = (
                project_config.prompt_customization if project_config else None
            )

            # Initialize idea queue
            idea_queue = []
            if project_config and project_config.idea_queue:
                idea_queue = [item.idea for item in project_config.idea_queue]
            elif not project_config:
                idea_queue = self.workspace.peek_ideas()

            # determine backend
            backend = GeminiBackend()
            if (
                project_config
                and project_config.phase_backends.implementing.backends
            ):
                try:
                    backend_instance = project_config.phase_backends.implementing.backends[0]
                    backend = get_backend(backend_instance.name)
                except ValueError:
                    pass

            # Initialize workflow
            workflow = ProjectWorkflow(
                project=project,
                backend=backend,
                event_bus=self.event_bus,
                config=config,
                project_config=project_config,
                phase_backends=phase_backends,
                prompt_customization=prompt_customization,
                idea_queue=idea_queue,
            )
            # Add logging adapter as a listener or handle via on_output?
            # Creating a wrapper for on_output to emit LogEntryEvent
            # But wait, LogPanel expects synchronous updates?
            # For now, let's just initialize it. The TUI refactor will handle log integration properly.

            self.workflows[path] = workflow

            # Persist to workspace/app_state
            self.app_state.add_project(path)
            self.app_state.save()
            self.workspace.add_project(path)
            self.workspace.save()

            logger.info(f"Added project: {project.name}")
            await self.event_bus.publish(ProjectAddedEvent(project_path=path))

            return project

        except Exception as e:
            logger.error(f"Failed to add project {path}: {e}")
            if path in self.projects:
                del self.projects[path]
            raise

    async def remove_project(self, path: Path) -> bool:
        """
        Remove a project from the workspace.

        Args:
            path: Path to the project.

        Returns:
            True if removed, False if not found.
        """
        path = path.resolve()
        if path not in self.projects:
            return False

        # Cancel workflow if running
        workflow = self.workflows.get(path)
        if workflow and workflow.is_running():
            workflow.cancel()

        # Cleanup
        del self.projects[path]
        if path in self.workflows:
            del self.workflows[path]

        # Update persistence
        self.app_state.remove_project(path)
        self.app_state.save()
        self.workspace.remove_project(path)
        self.workspace.save()

        logger.info(f"Removed project: {path}")
        await self.event_bus.publish(ProjectRemovedEvent(project_path=path))
        return True

    def get_project(self, path: Path) -> Project | None:
        """Get project by path."""
        return self.projects.get(path.resolve())

    def list_projects(self) -> list[Project]:
        """List all managed projects."""
        return list(self.projects.values())

    def get_project_status(self, path: Path) -> ProjectStatusDTO | None:
        """Get status DTO for a project."""
        path = path.resolve()
        project = self.projects.get(path)
        if not project:
            return None

        return ProjectStatusDTO.from_internal(project)


