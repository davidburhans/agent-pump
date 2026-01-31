
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_pump.events.bus import EventBus
from agent_pump.events.models import WorkspaceSwitchedEvent
from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.services.workspace_service import WorkspaceService

class TestWorkspaceAsync:
    """Tests for async workspace operations."""

    @pytest.mark.asyncio
    async def test_load_async(self, tmp_path):
        """Test loading workspace asynchronously."""
        workspace_name = "async_test_ws"
        workspace_file = tmp_path / f"{workspace_name}.json"

        # Create a workspace file
        workspace_file.write_text('{"name": "async_test_ws", "projects": {}}', encoding="utf-8")

        with patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path):
            ws = await Workspace.load_async(workspace_name)
            assert ws.name == workspace_name
            assert ws.projects == {}

    @pytest.mark.asyncio
    async def test_load_async_non_existent(self, tmp_path):
        """Test loading a non-existent workspace returns a new one."""
        with patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path):
            ws = await Workspace.load_async("non_existent")
            assert ws.name == "non_existent"

    @pytest.mark.asyncio
    async def test_get_current_workspace_async(self):
        """Test get_current_workspace_async loads properly."""
        event_bus = EventBus()
        app_state = MagicMock(spec=AppState)
        app_state.current_workspace = "default"

        service = WorkspaceService(event_bus, app_state)

        # Mock load_async to avoid actual I/O
        mock_ws = Workspace(name="default")
        with patch.object(Workspace, "load_async", return_value=mock_ws) as mock_load:
            ws = await service.get_current_workspace_async()
            assert ws == mock_ws
            mock_load.assert_awaited_once_with("default")

            # Second call should return cached
            mock_load.reset_mock()
            ws2 = await service.get_current_workspace_async()
            assert ws2 == mock_ws
            mock_load.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_workspace(self):
        """Test switching workspace updates state and loads new workspace."""
        event_bus = EventBus()
        app_state = MagicMock(spec=AppState)
        app_state.current_workspace = "old_ws"

        service = WorkspaceService(event_bus, app_state)

        new_ws_name = "new_ws"
        mock_new_ws = Workspace(name=new_ws_name)

        # Setup event listener
        events = []
        async def listener():
            async for event in event_bus.subscribe(WorkspaceSwitchedEvent):
                events.append(event)
                break

        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        with patch.object(Workspace, "load_async", return_value=mock_new_ws) as mock_load:
            result = await service.switch_workspace(new_ws_name)

            # Verify result
            assert result == mock_new_ws

            # Verify state update
            assert app_state.current_workspace == new_ws_name
            app_state.save.assert_called_once()

            # Verify load called
            mock_load.assert_awaited_once_with(new_ws_name)

            # Verify service internal state
            assert service._workspace == mock_new_ws

        # Verify event
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].old_workspace == "old_ws"
        assert events[0].new_workspace == new_ws_name
