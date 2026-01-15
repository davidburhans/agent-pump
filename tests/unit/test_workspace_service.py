"""Tests for WorkspaceService."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import ConfigUpdatedEvent
from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.services.workspace_service import WorkspaceService


class TestWorkspaceService:
    """Tests for WorkspaceService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def app_state(self):
        return MagicMock(spec=AppState)

    @pytest.fixture
    def workspace(self):
        ws = MagicMock(spec=Workspace)
        return ws

    @pytest.fixture
    def service(self, event_bus, app_state, workspace):
        svc = WorkspaceService(event_bus, app_state)
        # Inject mock workspace
        svc.set_current_workspace(workspace)
        return svc

    @pytest.mark.asyncio
    async def test_update_backend_config_global(self, service, workspace, event_bus):
        """Test updating global backend config."""
        mock_config = MagicMock()
        
        # Setup event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(ConfigUpdatedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        await service.update_backend_config(None, mock_config)
        
        # Verify persistence
        workspace.save.assert_called()
        assert workspace.default_phase_backends == mock_config
        
        # Verify event
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path is None
        assert events[0].config_type == "backend"

    @pytest.mark.asyncio
    async def test_update_backend_config_project(self, service, workspace, event_bus):
        """Test updating project backend config."""
        path = Path("/tmp/p1").resolve()
        mock_config = MagicMock()
        
        mock_project_config = MagicMock()
        workspace.get_project_config.return_value = mock_project_config
        
        # Event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(ConfigUpdatedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        await service.update_backend_config(path, mock_config)
        
        # Verify
        assert mock_project_config.phase_backends == mock_config
        workspace.save.assert_called()
        
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path == path

    @pytest.mark.asyncio
    async def test_update_global_prompts(self, service, workspace, event_bus):
        """Test updating global prompt settings."""
        mock_settings = MagicMock()
        
        events = []
        async def listener():
            async for event in event_bus.subscribe(ConfigUpdatedEvent):
                events.append(event)
                break
        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        await service.update_global_prompts(mock_settings)
        
        assert workspace.global_prompt_settings == mock_settings
        workspace.save.assert_called()
        
        await asyncio.wait_for(task, timeout=1.0)
        assert events[0].config_type == "global_prompt"
