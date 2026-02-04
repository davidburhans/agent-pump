"""Tests for ProjectService."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    LogEntryEvent,
    ProjectAddedEvent,
    ProjectRemovedEvent,
)
from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import Workspace
from agent_pump.services.project_service import ProjectService


class TestProjectService:
    """Tests for ProjectService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def workspace(self):
        ws = MagicMock(spec=Workspace)
        ws.projects = {}
        ws.workflow_definitions = {}
        ws.get_project_config.return_value = None
        return ws

    @pytest.fixture
    def app_state(self):
        state = MagicMock(spec=AppState)
        return state

    @pytest.fixture
    def service(self, event_bus, workspace, app_state):
        return ProjectService(event_bus, workspace, app_state)

    @pytest.fixture
    def sample_project_path(self, tmp_path):
        path = tmp_path / "test_project"
        path.mkdir()

        # Create minimal project files
        (path / ".agent-pump").mkdir()
        (path / ".agent-pump" / "config.yml").write_text(
            "backend: gemini\nworkflow:\n  branch: main", encoding="utf-8"
        )

        return path

    @pytest.mark.asyncio
    async def test_add_project(self, service, sample_project_path, event_bus):
        """Test adding a project."""
        # Setup event listener
        events = []

        async def listener():
            async for event in event_bus.subscribe(ProjectAddedEvent):
                events.append(event)
                break

        task = asyncio.create_task(listener())

        # Give subscriber time to start
        await asyncio.sleep(0.01)

        # Add project
        project = await service.add_project(sample_project_path)

        # Verify project returned
        assert project is not None
        assert project.path.resolve() == sample_project_path.resolve()

        # Verify stored
        assert sample_project_path.resolve() in service.projects
        assert sample_project_path.resolve() in service.workflows

        # Verify persistence called
        service.app_state.add_project.assert_called_with(sample_project_path.resolve())
        service.app_state.save.assert_called()
        service.workspace.add_project.assert_called_with(sample_project_path.resolve())
        service.workspace.save.assert_called()

        # Verify event emitted
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path.resolve() == sample_project_path.resolve()

    @pytest.mark.asyncio
    async def test_add_existing_project(self, service, sample_project_path):
        """Test adding a project that is already loaded."""
        # Add once
        p1 = await service.add_project(sample_project_path)

        # Add again
        p2 = await service.add_project(sample_project_path)

        assert p1 is p2
        # Should not have called persistence again (or maybe it does redundantly but harmlessly?
        # Logic says: if path in self.projects: return self.projects[path])
        # So persistence should NOT be called twice.
        assert service.app_state.add_project.call_count == 1

    @pytest.mark.asyncio
    async def test_remove_project(self, service, sample_project_path, event_bus):
        """Test removing a project."""
        await service.add_project(sample_project_path)

        # Setup event listener
        events = []

        async def listener():
            async for event in event_bus.subscribe(ProjectRemovedEvent):
                events.append(event)
                break

        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        # Remove
        result = await service.remove_project(sample_project_path)

        assert result is True
        assert sample_project_path.resolve() not in service.projects
        assert sample_project_path.resolve() not in service.workflows

        # Verify persistence
        service.app_state.remove_project.assert_called_with(sample_project_path.resolve())
        service.workspace.remove_project.assert_called_with(sample_project_path.resolve())

        # Verify event
        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].project_path.resolve() == sample_project_path.resolve()

    def test_list_projects(self, service):
        """Test listing projects."""
        # Can't use async fixture here easily without loop scope issues,
        # mocking internals for simple sync test
        path1 = Path("/tmp/p1").resolve()
        path2 = Path("/tmp/p2").resolve()

        p1 = MagicMock()
        p2 = MagicMock()

        service.projects[path1] = p1
        service.projects[path2] = p2

        projects = service.list_projects()
        assert len(projects) == 2
        assert p1 in projects
        assert p2 in projects

    def test_get_project_status(self, service):
        """Test getting project status."""
        path = Path("/tmp/p1").resolve()

        mock_project = MagicMock()
        mock_project.name = "Test Project"
        mock_project.path = path
        mock_project.iteration_count = 5  # DTO reads iteration_count, not iteration
        mock_project.current_feature = "Feature A"
        mock_project.current_activity = "Coding"
        mock_project.status = MagicMock()
        mock_project.status.value = "planning"  # DTO checks .value or falls back to str
        mock_project.state_changed_at = None  # Handle timestamp check

        service.projects[path] = mock_project
        # service.workflows[path] = mock_workflow # Not needed for from_internal
        # which uses project only

        status = service.get_project_status(path)

        assert status is not None
        assert status.name == "Test Project"
        assert status.state == "planning"
        assert status.iteration == 5

    @pytest.mark.asyncio
    async def test_emit_log_event(self, service, workspace, event_bus, sample_project_path):
        """Test that log output emits LogEntryEvent."""
        path = sample_project_path

        # Add project first
        ws_config_mock = MagicMock()
        ws_config_mock.idea_queue = []
        workspace.get_project_config.return_value = ws_config_mock
        workspace.projects = {}
        workspace.add_project.return_value = True

        await service.add_project(path)

        # Trigger log emission manually (simulating workflow callback)
        # We need to access the private method or the workflow callback
        workflow = service.workflows[path]

        # Setup event listener
        events = []

        async def listener():
            async for event in event_bus.subscribe(LogEntryEvent):
                events.append(event)
                break

        task = asyncio.create_task(listener())
        await asyncio.sleep(0.01)

        # Invoke the workflow method that publishes the event
        workflow._emit_output("test log")

        await asyncio.wait_for(task, timeout=1.0)
        assert len(events) == 1
        assert events[0].message == "test log"
        assert events[0].state == "idle"
