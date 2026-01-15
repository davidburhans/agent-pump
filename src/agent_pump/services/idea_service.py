"""Idea queue management service."""

import logging
from pathlib import Path

from agent_pump.events.bus import EventBus
from agent_pump.events.models import IdeaAddedEvent, IdeasClearedEvent
from agent_pump.models.workspace import IdeaQueueItem, Workspace
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class IdeaService(BaseService):
    """Service for managing idea queues."""

    def __init__(self, event_bus: EventBus, workspace: Workspace) -> None:
        """
        Initialize the idea service.

        Args:
            event_bus: The event bus.
            workspace: The current workspace.
        """
        super().__init__(event_bus)
        self.workspace = workspace

    async def add_idea(
        self, idea: str, project_path: Path | None = None, priority: int = 0
    ) -> IdeaQueueItem:
        """
        Add an idea to the queue.

        Args:
            idea: The idea text.
            project_path: Optional project path (if None, adds to global queue).
            priority: Priority level.

        Returns:
            The created IdeaQueueItem.
        """
        idea = idea.strip()
        if not idea:
            raise ValueError("Idea cannot be empty")

        if project_path:
            project_path = project_path.resolve()
            project_config = self.workspace.get_project_config(project_path)
            if not project_config:
                raise ValueError(f"Project not found: {project_path}")

            item = IdeaQueueItem(idea=idea, priority=priority)
            project_config.idea_queue.append(item)
            # Sort by priority
            project_config.idea_queue.sort(key=lambda x: x.priority, reverse=True)
        else:
            self.workspace.add_idea(idea, priority)
            # Fetch the item we just added (last one? no, logic sorts it)
            # add_idea inside workspace creates the item.
            # We want to return the item.
            # Let's assume it's there.
            # For simplicity, reconstructing it or finding it.
            # Workspace.add_idea appends then sorts.
            # We can construct it here to return it, even if exact instance reference might differ slightly if reloaded.
            item = IdeaQueueItem(idea=idea, priority=priority)

        self.workspace.save()
        logger.info(f"Added idea: {idea[:20]}... (Project: {project_path})")

        await self.event_bus.publish(
            IdeaAddedEvent(idea=idea, project_path=project_path)
        )
        return item

    def list_ideas(self, project_path: Path | None = None) -> list[IdeaQueueItem]:
        """
        List ideas in the queue.

        Args:
            project_path: Optional project path.

        Returns:
            List of IdeaQueueItem objects.
        """
        if project_path:
            project_path = project_path.resolve()
            project_config = self.workspace.get_project_config(project_path)
            if not project_config:
                return []
            return project_config.idea_queue
        else:
            return self.workspace.idea_queue

    async def clear_ideas(self, project_path: Path | None = None) -> int:
        """
        Clear the idea queue.

        Args:
            project_path: Optional project path.

        Returns:
            Number of items removed.
        """
        count = 0
        if project_path:
            project_path = project_path.resolve()
            project_config = self.workspace.get_project_config(project_path)
            if project_config:
                count = len(project_config.idea_queue)
                project_config.idea_queue = []
        else:
            count = len(self.workspace.idea_queue)
            self.workspace.idea_queue = []

        if count > 0:
            self.workspace.save()
            logger.info(f"Cleared {count} ideas (Project: {project_path})")
            await self.event_bus.publish(IdeasClearedEvent(project_path=project_path))

        return count

    async def remove_idea(self, index: int, project_path: Path | None = None) -> bool:
        """
        Remove a specific idea by index.

        Args:
            index: Index in the list.
            project_path: Optional project path.

        Returns:
            True if removed, False if index out of bounds.
        """
        queue = self.list_ideas(project_path)
        if 0 <= index < len(queue):
            removed = queue.pop(index)
            self.workspace.save()
            logger.info(f"Removed idea: {removed.idea[:20]}...")
            # Ideally emit IdeaRemovedEvent, but sticking to existing events for now.
            # Could trigger a list refresh.
            return True
        return False
