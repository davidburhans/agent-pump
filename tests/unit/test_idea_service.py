"""Tests for IdeaService."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import IdeaAddedEvent, IdeasClearedEvent
from agent_pump.models.workspace import IdeaQueueItem, Workspace
from agent_pump.services.idea_service import IdeaService


class TestIdeaService:
    """Tests for IdeaService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def workspace(self):
        ws = MagicMock(spec=Workspace)
        ws.idea_queue = []
        # Mock get_project_config logic slightly more complex or just return a mock?
        # Better to return a mock object that acts as a container
        return ws

    @pytest.fixture
    def service(self, event_bus, workspace):
        return IdeaService(event_bus, workspace)

    @pytest.mark.asyncio
    async def test_add_global_idea(self, service, workspace, event_bus):
        """Test adding idea to global queue."""
        # Setup real list for workspace queue since we mock the class but attributes are tricky
        workspace.idea_queue = []
        
        # Override add_idea to append to list
        def mock_add_idea(idea, priority=0, source="user"):
            workspace.idea_queue.append(IdeaQueueItem(idea=idea, priority=priority))
        workspace.add_idea.side_effect = mock_add_idea

        # Setup event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(IdeaAddedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        await service.add_idea("Global idea")
        
        assert len(workspace.idea_queue) == 1
        assert workspace.idea_queue[0].idea == "Global idea"
        workspace.save.assert_called()
        
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path is None
        assert events[0].idea == "Global idea"

    @pytest.mark.asyncio
    async def test_add_project_idea(self, service, workspace, event_bus):
        """Test adding idea to project queue."""
        path = Path("/tmp/p1").resolve()
        
        mock_config = MagicMock()
        mock_config.idea_queue = []
        workspace.get_project_config.return_value = mock_config

        # Setup event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(IdeaAddedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        await service.add_idea("Project idea", project_path=path, priority=5)

        assert len(mock_config.idea_queue) == 1
        assert mock_config.idea_queue[0].idea == "Project idea"
        assert mock_config.idea_queue[0].priority == 5
        workspace.save.assert_called()

        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path == path

    @pytest.mark.asyncio
    async def test_clear_ideas(self, service, workspace, event_bus):
        """Test clearing ideas."""
        # Global
        workspace.idea_queue = [IdeaQueueItem(idea="i1"), IdeaQueueItem(idea="i2")]
        
        # Setup event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(IdeasClearedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        count = await service.clear_ideas()
        
        assert count == 2
        assert len(workspace.idea_queue) == 0
        workspace.save.assert_called()

        await asyncio.wait_for(task, timeout=1.0)
        assert events[0].project_path is None

    @pytest.mark.asyncio
    async def test_remove_idea(self, service, workspace):
        """Test removing single idea."""
        workspace.idea_queue = [IdeaQueueItem(idea="i1"), IdeaQueueItem(idea="i2")]
        
        result = await service.remove_idea(0)
        
        assert result is True
        assert len(workspace.idea_queue) == 1
        assert workspace.idea_queue[0].idea == "i2"
        workspace.save.assert_called()

    @pytest.mark.asyncio
    async def test_remove_idea_invalid_index(self, service, workspace):
        """Test removing with invalid index."""
        workspace.idea_queue = []
        result = await service.remove_idea(0)
        assert result is False
