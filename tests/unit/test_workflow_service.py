"""Tests for WorkflowService."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.services.project_service import ProjectService
from agent_pump.services.workflow_service import WorkflowService


class TestWorkflowService:
    """Tests for WorkflowService."""

    @pytest.fixture
    def event_bus(self):
        return EventBus()

    @pytest.fixture
    def project_service(self):
        service = MagicMock(spec=ProjectService)
        service.workflows = {}
        service.projects = {}
        return service

    @pytest.fixture
    def service(self, event_bus, project_service):
        return WorkflowService(event_bus, project_service)

    @pytest.mark.asyncio
    async def test_start_project(self, service):
        """Test starting a project."""
        path = Path("/tmp/p1").resolve()

        mock_workflow = MagicMock()
        mock_workflow.is_running.return_value = False
        mock_workflow.run = AsyncMock()
        mock_workflow.config.workflow.max_iterations = 5

        service.project_service.workflows[path] = mock_workflow
        service.project_service.projects[path] = MagicMock()

        result = await service.start_project(path)

        assert result is True
        # Allow time for background task to start
        await asyncio.sleep(0.01)
        mock_workflow.run.assert_called_with(max_iterations=5)

    @pytest.mark.asyncio
    async def test_start_running_project(self, service):
        """Test starting a project that is already running."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        mock_workflow.is_running.return_value = True
        service.project_service.workflows[path] = mock_workflow

        result = await service.start_project(path)
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_project(self, service):
        """Test stopping a project."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        service.project_service.workflows[path] = mock_workflow

        result = await service.stop_project(path)

        assert result is True
        mock_workflow.pause_workflow.assert_called()

    @pytest.mark.asyncio
    async def test_reset_project(self, service):
        """Test resetting a project."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        service.project_service.workflows[path] = mock_workflow

        result = await service.reset_project(path)

        assert result is True
        mock_workflow.reset_workflow.assert_called()

    def test_get_workflow_status(self, service):
        """Test getting status."""
        path = Path("/tmp/p1").resolve()
        mock_workflow = MagicMock()
        mock_workflow.state = "implementing"
        mock_workflow.project.iteration_count = 2
        mock_workflow.machine.get_triggers.return_value = ["complete"]

        service.project_service.workflows[path] = mock_workflow

        status = service.get_workflow_status(path)

        assert status is not None
        assert status.current_state == "implementing"
        assert status.iteration == 2
        assert "complete" in status.available_transitions
