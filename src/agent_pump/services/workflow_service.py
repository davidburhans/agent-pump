"""Workflow management service."""

import logging
from pathlib import Path

from agent_pump.api.schemas import WorkflowStateDTO
from agent_pump.events.bus import EventBus
from agent_pump.services.base import BaseService
from agent_pump.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class WorkflowService(BaseService):
    """Service for controlling workflow execution."""

    def __init__(self, event_bus: EventBus, project_service: ProjectService) -> None:
        """
        Initialize the workflow service.

        Args:
            event_bus: The event bus.
            project_service: The project service to access projects and workflows.
        """
        super().__init__(event_bus)
        self.project_service = project_service

    async def start_project(self, path: Path) -> bool:
        """
        Start the workflow for a project.

        Args:
            path: Path to the project.

        Returns:
            True if started, False if already running or not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return False

        if workflow.is_running():
            return False

        # Start workflow run loop (in background)
        # Note: In real app, we need to manage this task properly.
        # For now, we create a task and let it run.
        import asyncio

        self.project_service.projects[
            path
        ].config
        # Assuming project object has config attached
        # wait Project model doesn't store config used by workflow init.
        # Actually workflow has config.

        # We need max_iterations from config.
        # Check how app.py does it: config = Config.load(path)
        # But we already loaded config in ProjectService and passed it to ProjectWorkflow?
        # ProjectWorkflow stores self.config = config.

        # Access max_iterations from workflow config if available?
        # ProjectWorkflow doesn't expose config publicly in type hints but it's there.
        # Let's verify ProjectWorkflow definition. It initializes with config.

        max_iterations = 10
        if hasattr(workflow, "config") and workflow.config and workflow.config.workflow:
            max_iterations = workflow.config.workflow.max_iterations

        asyncio.create_task(self._run_workflow_safe(workflow, max_iterations))

        logger.info(f"Started workflow for {path}")
        return True

    async def _run_workflow_safe(self, workflow, max_iterations: int) -> None:
        """Run workflow and handle exceptions."""
        try:
            await workflow.run(max_iterations=max_iterations)
        except Exception as e:
            logger.error(f"Workflow failed for {workflow.project.path}: {e}")
            # Emit error event? Existing callbacks might handle it.

    async def stop_project(self, path: Path) -> bool:
        """
        Stop the workflow for a project.

        Args:
            path: Path to the project.

        Returns:
            True if stopped, False if not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return False

        workflow.pause_workflow()
        logger.info(f"Stopped/Paused workflow for {path}")
        return True

    async def reset_project(self, path: Path) -> bool:
        """
        Reset the workflow state for a project.

        Args:
            path: Path to the project.

        Returns:
            True if reset, False if not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return False

        workflow.reset_workflow()
        logger.info(f"Reset workflow for {path}")

        # reset_workflow triggers state change callback internally?
        # Yes, it sets state to IDLE.
        return True

    def get_workflow_status(self, path: Path) -> WorkflowStateDTO | None:
        """
        Get the current status of a workflow.

        Args:
            path: Path to the project.

        Returns:
            Workflow state DTO or None if not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return None

        return WorkflowStateDTO.from_internal(workflow)

    async def start_all(self) -> int:
        """Start all projects."""
        count = 0
        for path in self.project_service.projects:
            if await self.start_project(path):
                count += 1
        return count

    async def stop_all(self) -> int:
        """Stop all projects."""
        count = 0
        for path in self.project_service.projects:
            if await self.stop_project(path):
                count += 1
        return count
