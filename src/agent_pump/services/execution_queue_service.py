"""Execution queue service for managing parallel project execution limits."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from agent_pump.events.bus import EventBus
from agent_pump.models.execution_queue import QueuePriority, QueueStatus
from agent_pump.services.base import BaseService

if TYPE_CHECKING:
    from agent_pump.services.workflow_service import WorkflowService

logger = logging.getLogger(__name__)


class ExecutionQueueService(BaseService):
    """Service for managing the execution queue and concurrency limits.

    This service coordinates with WorkflowService to ensure that projects
    respect concurrency limits and are properly queued when limits are reached.
    """

    def __init__(
        self,
        event_bus: EventBus,
        workflow_service: "WorkflowService | None" = None,
    ) -> None:
        """Initialize the execution queue service.

        Args:
            event_bus: The event bus for publishing queue events
            workflow_service: Optional workflow service for starting projects
        """
        super().__init__(event_bus)
        self.workflow_service = workflow_service
        self._position_counter = 0

    def set_workflow_service(self, workflow_service: "WorkflowService") -> None:
        """Set the workflow service (for late initialization)."""
        self.workflow_service = workflow_service

    async def enqueue_project(
        self,
        workspace,
        path: Path,
        priority: QueuePriority = QueuePriority.MEDIUM,
    ) -> tuple[bool, str]:
        """Add a project to the execution queue.

        Args:
            workspace: The workspace containing the queue
            path: Project path to queue
            priority: Priority level for this project

        Returns:
            Tuple of (success, message). Success is True if added to queue.
            Message describes the result.
        """
        path = path.resolve()

        # Check if project is already active
        if any(item.project_path == path and item.is_active for item in workspace.execution_queue):
            return False, "Project is already running"

        # Check if project is already queued
        existing_position = workspace.get_queue_position(path)
        if existing_position:
            # Update priority instead
            item = workspace.reorder_queued_project(path, priority)
            if item:
                return True, f"Updated priority to {priority.name}, position #{existing_position}"
            return False, "Failed to update priority"

        # Add to queue
        item = workspace.queue_project(path, priority)
        position = workspace.get_queue_position(path)

        logger.info(
            f"Project {path} added to queue with {priority.name} priority at position #{position}"
        )

        # Try to start immediately if slots available
        if workspace.execution_queue_config.auto_start_queued and workspace.can_start_project():
            if self.workflow_service:
                await self._start_queued_project(workspace, path)
                return True, "Started immediately (slot available)"

        return True, f"Queued at position #{position} with {priority.name} priority"

    async def dequeue_project(self, workspace, path: Path) -> tuple[bool, str]:
        """Remove a project from the queue.

        Args:
            workspace: The workspace containing the queue
            path: Project path to dequeue

        Returns:
            Tuple of (success, message)
        """
        path = path.resolve()

        # Check if project is active
        if any(item.project_path == path and item.is_active for item in workspace.execution_queue):
            return False, "Cannot dequeue an active project (stop it first)"

        item = workspace.dequeue_project(path)
        if item:
            logger.info(f"Project {path} removed from queue")
            return True, "Removed from queue"

        return False, "Project not found in queue"

    async def cancel_queued_project(self, workspace, path: Path) -> tuple[bool, str]:
        """Cancel a queued project.

        Args:
            workspace: The workspace containing the queue
            path: Project path to cancel

        Returns:
            Tuple of (success, message)
        """
        path = path.resolve()

        item = workspace.cancel_queued_project(path)
        if item:
            logger.info(f"Project {path} cancelled")
            return True, "Project cancelled"

        return False, "Project not found in queue"

    def get_queue_status(self, workspace) -> dict:
        """Get the current queue status.

        Args:
            workspace: The workspace to check

        Returns:
            Dictionary with queue statistics and items
        """
        active = [item for item in workspace.execution_queue if item.is_active]
        queued = workspace.get_queued_projects()
        completed = [
            item for item in workspace.execution_queue if item.status == QueueStatus.COMPLETED
        ]
        failed = [item for item in workspace.execution_queue if item.status == QueueStatus.FAILED]

        return {
            "config": {
                "max_concurrent": workspace.execution_queue_config.max_concurrent,
                "auto_start": workspace.execution_queue_config.auto_start_queued,
            },
            "stats": {
                "active": len(active),
                "queued": len(queued),
                "completed": len(completed),
                "failed": len(failed),
                "available_slots": (
                    max(0, workspace.execution_queue_config.max_concurrent - len(active))
                    if workspace.execution_queue_config.has_limit
                    else None
                ),
            },
            "active_projects": [
                {
                    "path": str(item.project_path),
                    "priority": item.priority.name,
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                }
                for item in active
            ],
            "queued_projects": [
                {
                    "path": str(item.project_path),
                    "priority": item.priority.name,
                    "position": i + 1,
                    "queued_at": item.queued_at.isoformat(),
                    "wait_seconds": item.wait_time_seconds,
                }
                for i, item in enumerate(queued, 1)
            ],
        }

    async def start_next_queued_project(self, workspace) -> Path | None:
        """Start the next project from the queue if slots are available.

        Args:
            workspace: The workspace containing the queue

        Returns:
            Path of started project, or None if no project started
        """
        if not workspace.can_start_project():
            return None

        next_item = workspace.get_next_queued_project()
        if not next_item:
            return None

        path = next_item.project_path

        if await self._start_queued_project(workspace, path):
            return path
        return None

    async def _start_queued_project(self, workspace, path: Path) -> bool:
        """Start a queued project.

        Args:
            workspace: The workspace containing the queue
            path: Project path to start

        Returns:
            True if started successfully
        """
        if not self.workflow_service:
            logger.warning("Cannot start queued project: workflow service not set")
            return False

        # Mark as active in queue
        item = workspace.mark_project_active(path)
        if not item:
            logger.warning(f"Failed to mark project {path} as active")
            return False

        try:
            # Start the workflow
            success = await self.workflow_service.start_project(path)
            if not success:
                # If failed to start, mark as failed and try next
                workspace.mark_project_failed(path)
                logger.warning(f"Failed to start project {path} from queue")
                return False

            logger.info(f"Started queued project {path}")
            return True
        except Exception as e:
            logger.exception(f"Error starting queued project {path}: {e}")
            workspace.mark_project_failed(path)
            return False

    async def on_project_completed(self, workspace, path: Path) -> None:
        """Handle project completion - mark as completed and try to start next.

        Args:
            workspace: The workspace containing the queue
            path: Project path that completed
        """
        path = path.resolve()

        # Mark as completed
        workspace.mark_project_completed(path)
        logger.info(f"Project {path} marked as completed")

        # Clean up old completed items periodically (every 10 completions)
        completed_count = sum(
            1 for item in workspace.execution_queue if item.status == QueueStatus.COMPLETED
        )
        if completed_count >= 10:
            removed = workspace.cleanup_completed_queue_items(max_age_hours=1)
            if removed > 0:
                logger.info(f"Cleaned up {removed} old completed queue items")

        # Try to start next project
        if workspace.execution_queue_config.auto_start_queued:
            next_path = await self.start_next_queued_project(workspace)
            if next_path:
                logger.info(f"Auto-started next queued project: {next_path}")

    async def on_project_failed(self, workspace, path: Path) -> None:
        """Handle project failure - mark as failed and try to start next.

        Args:
            workspace: The workspace containing the queue
            path: Project path that failed
        """
        path = path.resolve()

        # Mark as failed
        workspace.mark_project_failed(path)
        logger.info(f"Project {path} marked as failed")

        # Try to start next project
        if workspace.execution_queue_config.auto_start_queued:
            next_path = await self.start_next_queued_project(workspace)
            if next_path:
                logger.info(f"Auto-started next queued project after failure: {next_path}")

    def can_project_start(self, workspace, path: Path) -> tuple[bool, str]:
        """Check if a project can be started immediately.

        Args:
            workspace: The workspace to check
            path: Project path to check

        Returns:
            Tuple of (can_start, reason). Can_start is True if project can start now.
        """
        path = path.resolve()

        # Check if already running
        if any(item.project_path == path and item.is_active for item in workspace.execution_queue):
            return False, "Project is already running"

        # Check if already queued
        if workspace.get_queue_position(path):
            return False, "Project is already in queue"

        # Check concurrency limit
        if not workspace.can_start_project():
            limit = workspace.execution_queue_config.max_concurrent
            active = workspace.get_active_projects_count()
            return False, f"Concurrency limit reached ({active}/{limit} active)"

        return True, "Can start immediately"

    async def update_project_priority(
        self,
        workspace,
        path: Path,
        new_priority: QueuePriority,
    ) -> tuple[bool, str]:
        """Update the priority of a queued project.

        Args:
            workspace: The workspace containing the queue
            path: Project path to update
            new_priority: New priority level

        Returns:
            Tuple of (success, message)
        """
        path = path.resolve()

        item = workspace.reorder_queued_project(path, new_priority)
        if item:
            new_position = workspace.get_queue_position(path)
            logger.info(
                f"Updated project {path} priority to {new_priority.name}, new position: #{new_position}"
            )
            return True, f"Priority updated to {new_priority.name}, now at position #{new_position}"

        # Check if it's active
        if any(item.project_path == path and item.is_active for item in workspace.execution_queue):
            return False, "Cannot change priority of active project"

        return False, "Project not found in queue"

    def get_project_queue_info(self, workspace, path: Path) -> dict | None:
        """Get queue information for a specific project.

        Args:
            workspace: The workspace to check
            path: Project path to look up

        Returns:
            Dictionary with queue info, or None if not in queue
        """
        path = path.resolve()

        for item in workspace.execution_queue:
            if item.project_path == path:
                position = None
                if item.is_pending:
                    position = workspace.get_queue_position(path)

                return {
                    "status": item.status.value,
                    "priority": item.priority.name,
                    "position": position,
                    "queued_at": item.queued_at.isoformat(),
                    "started_at": item.started_at.isoformat() if item.started_at else None,
                    "wait_time_seconds": item.wait_time_seconds,
                    "execution_time_seconds": item.execution_time_seconds,
                }

        return None
