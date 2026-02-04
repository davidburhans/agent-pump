"""Workflow management service."""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from agent_pump.api.schemas import WorkflowStateDTO
from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    WorkflowStateChangedEvent,
)
from agent_pump.models.execution_queue import QueuePriority
from agent_pump.models.project import ProjectStatus
from agent_pump.services.base import BaseService
from agent_pump.services.project_service import ProjectService

if TYPE_CHECKING:
    from agent_pump.models.checkpoint import Checkpoint
    from agent_pump.services.execution_queue_service import ExecutionQueueService

logger = logging.getLogger(__name__)


class WorkflowService(BaseService):
    """Service for controlling workflow execution."""

    def __init__(
        self,
        event_bus: EventBus,
        project_service: ProjectService,
        execution_queue_service: "ExecutionQueueService | None" = None,
    ) -> None:
        """
        Initialize the workflow service.

        Args:
            event_bus: The event bus.
            project_service: The project service to access projects and workflows.
            execution_queue_service: Optional queue service for managing execution limits.
        """
        super().__init__(event_bus)
        self.project_service = project_service
        self.execution_queue_service = execution_queue_service
        self._running_tasks: dict[Path, asyncio.Task] = {}
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for workflow state changes.

        Note: The event bus uses async iterators. Event handling is done
        by the main event loop or app, not direct callbacks.
        This method is a placeholder for future direct subscription if needed.
        """
        # Event handling is done via the event bus async iterator pattern
        # The app or main loop subscribes and routes events appropriately
        pass

    async def _on_workflow_state_changed(self, event: WorkflowStateChangedEvent) -> None:
        """Handle workflow state changes to detect completion/failure."""
        if not self.execution_queue_service:
            return

        workspace = self.project_service.workspace
        path = event.project_path

        # Check if project reached a terminal state
        if event.new_state in (ProjectStatus.COMPLETED.value, ProjectStatus.ERROR.value):
            if event.new_state == ProjectStatus.COMPLETED.value:
                await self.execution_queue_service.on_project_completed(workspace, path)
            else:
                await self.execution_queue_service.on_project_failed(workspace, path)

    async def start_project(self, path: Path, skip_queue: bool = False) -> bool:
        """
        Start the workflow for a project.

        Args:
            path: Path to the project.
            skip_queue: If True, bypass the queue and start immediately.

        Returns:
            True if started, False if already running or not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return False

        if workflow.is_running():
            return False

        # Check execution queue if available
        if self.execution_queue_service and not skip_queue:
            workspace = self.project_service.workspace
            can_start, reason = self.execution_queue_service.can_project_start(workspace, path)

            if not can_start:
                logger.info(f"Project {path} cannot start immediately: {reason}")
                # Project will be queued by the caller or remains queued
                return False

            # Mark as active in queue if it was queued
            if workspace.get_queue_position(path):
                workspace.mark_project_active(path)

        # Start workflow run loop (in background)
        max_iterations = 10
        if hasattr(workflow, "config") and workflow.config and workflow.config.workflow:
            max_iterations = workflow.config.workflow.max_iterations

        # Track the task so we can properly await it during shutdown
        task = asyncio.create_task(self._run_workflow_safe(workflow, max_iterations, path))
        self._running_tasks[path] = task

        logger.info(f"Started workflow for {path}")
        return True

    async def _run_workflow_safe(self, workflow, max_iterations: int, path: Path) -> None:
        """Run workflow and handle exceptions."""
        try:
            await workflow.run(max_iterations=max_iterations)
        except Exception as e:
            logger.error(f"Workflow failed for {workflow.project.path}: {e}")
            # Mark as failed in queue
            if self.execution_queue_service:
                workspace = self.project_service.workspace
                await self.execution_queue_service.on_project_failed(workspace, path)
        finally:
            # Clean up the task reference when done
            self._running_tasks.pop(path, None)

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

    async def rollback_to_checkpoint(self, path: Path, checkpoint_id: str) -> bool:
        """
        Rollback a project to a specific checkpoint.

        Args:
            path: Path to the project.
            checkpoint_id: ID of the checkpoint to rollback to.

        Returns:
            True if rollback successful, False if checkpoint not found or workflow not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return False

        # Get checkpoint from workflow state
        checkpoint = workflow.workflow_state.checkpoints.get_by_id(checkpoint_id)
        if not checkpoint:
            logger.warning(f"Checkpoint {checkpoint_id} not found for project {path}")
            return False

        # Perform rollback
        try:
            workflow.checkpoint_service.rollback_to_checkpoint(checkpoint)
            logger.info(f"Rolled back project {path} to checkpoint {checkpoint_id}")

            # Reset workflow to idle state after rollback
            workflow.reset_workflow()

            return True
        except Exception as e:
            logger.error(f"Failed to rollback project {path} to checkpoint {checkpoint_id}: {e}")
            raise

    async def create_manual_checkpoint(self, path: Path, description: str) -> "Checkpoint | None":
        """
        Create a manual checkpoint for a project.

        Args:
            path: Path to the project.
            description: Description for the checkpoint.

        Returns:
            The created Checkpoint object, or None if workflow not found.
        """
        path = path.resolve()
        workflow = self.project_service.workflows.get(path)
        if not workflow:
            return None

        try:
            checkpoint = workflow.checkpoint_service.create_checkpoint(
                phase="manual",
                feature=workflow.project.current_feature,
                description=description,
                auto_created=False,
            )

            # Add to workflow state
            workflow.workflow_state.add_checkpoint(checkpoint)
            workflow.workflow_state.save()

            logger.info(f"Created manual checkpoint {checkpoint.id} for project {path}")
            return checkpoint
        except Exception as e:
            logger.error(f"Failed to create manual checkpoint for project {path}: {e}")
            raise

    async def shutdown(self) -> None:
        """Gracefully shutdown all running workflows and wait for completion."""
        # Cancel all running workflows
        for path, workflow in self.project_service.workflows.items():
            if workflow.is_running():
                workflow.cancel()

        # Wait for all workflow tasks to complete (with timeout)
        if self._running_tasks:
            logger.info(f"Waiting for {len(self._running_tasks)} workflow(s) to complete...")
            tasks = list(self._running_tasks.values())
            try:
                # Wait with a 30-second timeout for graceful shutdown
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30.0)
            except TimeoutError:
                logger.warning("Shutdown timeout reached, some workflows may not have completed")
            # Cancel any remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
            self._running_tasks.clear()
            logger.info("Workflow service shutdown complete")

    # Queue management methods

    async def queue_project(
        self, path: Path, priority: QueuePriority = QueuePriority.MEDIUM
    ) -> tuple[bool, str]:
        """
        Add a project to the execution queue.

        Args:
            path: Path to the project.
            priority: Priority level for the project.

        Returns:
            Tuple of (success, message).
        """
        if not self.execution_queue_service:
            return False, "Execution queue service not available"

        workspace = self.project_service.workspace
        path = path.resolve()

        return await self.execution_queue_service.enqueue_project(workspace, path, priority)

    def get_queue_position(self, path: Path) -> int | None:
        """
        Get the position of a project in the queue.

        Args:
            path: Path to the project.

        Returns:
            Position in queue (1-indexed) or None if not in queue.
        """
        if not self.execution_queue_service:
            return None

        workspace = self.project_service.workspace
        return workspace.get_queue_position(path.resolve())

    async def reorder_queued_project(
        self, path: Path, new_priority: QueuePriority
    ) -> tuple[bool, str]:
        """
        Change the priority of a queued project.

        Args:
            path: Path to the project.
            new_priority: New priority level.

        Returns:
            Tuple of (success, message).
        """
        if not self.execution_queue_service:
            return False, "Execution queue service not available"

        workspace = self.project_service.workspace
        return await self.execution_queue_service.update_project_priority(
            workspace, path.resolve(), new_priority
        )

    async def cancel_queued_project(self, path: Path) -> tuple[bool, str]:
        """
        Cancel a project that is in the queue.

        Args:
            path: Path to the project.

        Returns:
            Tuple of (success, message).
        """
        if not self.execution_queue_service:
            return False, "Execution queue service not available"

        workspace = self.project_service.workspace
        return await self.execution_queue_service.cancel_queued_project(workspace, path.resolve())

    def get_queue_status(self) -> dict | None:
        """
        Get the current queue status.

        Returns:
            Dictionary with queue statistics and items, or None if queue service not available.
        """
        if not self.execution_queue_service:
            return None

        workspace = self.project_service.workspace
        return self.execution_queue_service.get_queue_status(workspace)

    def get_project_queue_info(self, path: Path) -> dict | None:
        """
        Get queue information for a specific project.

        Args:
            path: Path to the project.

        Returns:
            Dictionary with queue info, or None if not in queue or queue service not available.
        """
        if not self.execution_queue_service:
            return None

        workspace = self.project_service.workspace
        return self.execution_queue_service.get_project_queue_info(workspace, path.resolve())

    async def start_next_queued_project(self) -> Path | None:
        """
        Start the next project from the queue if slots are available.

        Returns:
            Path of started project, or None if no project started.
        """
        if not self.execution_queue_service:
            return None

        workspace = self.project_service.workspace
        return await self.execution_queue_service.start_next_queued_project(workspace)
