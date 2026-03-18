"""Tests for FileWatcherService."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import ConfigUpdatedEvent, ProjectAddedEvent, ProjectRemovedEvent
from agent_pump.models.file_watcher_config import FileWatcherConfig
from agent_pump.models.workspace import ProjectConfig, Workspace
from agent_pump.services.file_watcher_service import FileWatcherService
from agent_pump.services.project_service import ProjectService


class MockAsyncGenerator:
    def __init__(self, items=None):
        self.items = items or []

    def __aiter__(self):
        self.items_iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self.items_iter)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def event_bus():
    bus = MagicMock(spec=EventBus)
    bus.subscribe.return_value = MockAsyncGenerator([])
    return bus


@pytest.fixture
def project_service():
    service = MagicMock(spec=ProjectService)
    service.workflows = {}
    return service


@pytest.fixture
def workspace():
    ws = MagicMock(spec=Workspace)
    ws.projects = {}
    return ws


@pytest.fixture
def file_watcher_service(event_bus, project_service, workspace):
    # Mock create_task during init to avoid starting event loop task
    # We close the coroutine to avoid "coroutine never awaited" warning
    def side_effect(coro):
        coro.close()
        return MagicMock()

    with patch(
        "agent_pump.services.file_watcher_service.asyncio.create_task", side_effect=side_effect
    ) as mock_create_task:
        return FileWatcherService(event_bus, project_service, workspace)


@pytest.mark.asyncio
async def test_start_watching_enabled(file_watcher_service, workspace):
    """Test start_watching when enabled."""
    path = Path("/tmp/test-project")

    # Setup workspace config
    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(enabled=True)
    workspace.get_project_config.return_value = config

    # Mock awatch
    with patch("agent_pump.services.file_watcher_service.awatch") as mock_awatch:
        mock_awatch.return_value = MockAsyncGenerator([])

        await file_watcher_service.start_watching(path)

        assert path in file_watcher_service._watchers
        assert not file_watcher_service._watchers[path].done()

        # Cleanup
        await file_watcher_service.stop_watching(path)


@pytest.mark.asyncio
async def test_start_watching_disabled(file_watcher_service, workspace):
    """Test start_watching when disabled."""
    path = Path("/tmp/test-project")

    # Setup workspace config
    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(enabled=False)
    workspace.get_project_config.return_value = config

    await file_watcher_service.start_watching(path)

    assert path not in file_watcher_service._watchers


@pytest.mark.asyncio
async def test_on_project_added(file_watcher_service):
    """Test on_project_added event handler."""
    path = Path("/tmp/test-project")
    event = ProjectAddedEvent(project_path=path)

    with patch.object(file_watcher_service, "start_watching", new_callable=AsyncMock) as mock_start:
        await file_watcher_service.on_project_added(event)
        mock_start.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_on_project_removed(file_watcher_service):
    """Test on_project_removed event handler."""
    path = Path("/tmp/test-project")
    event = ProjectRemovedEvent(project_path=path)

    with patch.object(file_watcher_service, "stop_watching", new_callable=AsyncMock) as mock_stop:
        await file_watcher_service.on_project_removed(event)
        mock_stop.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_on_config_updated(file_watcher_service):
    """Test on_config_updated event handler."""
    path = Path("/tmp/test-project")
    event = ConfigUpdatedEvent(project_path=path, config_type="project_config")

    with (
        patch.object(file_watcher_service, "stop_watching", new_callable=AsyncMock) as mock_stop,
        patch.object(file_watcher_service, "start_watching", new_callable=AsyncMock) as mock_start,
    ):
        await file_watcher_service.on_config_updated(event)

        mock_stop.assert_awaited_once_with(path)
        mock_start.assert_awaited_once_with(path)


@pytest.mark.asyncio
async def test_watch_loop_verification(file_watcher_service, workspace, project_service):
    """Test watch loop triggers verification."""
    path = Path("/tmp/test-project")

    # Setup workspace config
    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(enabled=True, action="verification")
    workspace.get_project_config.return_value = config

    # Setup workflow
    workflow = MagicMock()
    workflow.run_verification = AsyncMock()
    project_service.workflows = {path: workflow}

    # Mock awatch to yield one change then finish
    changes = {(1, str(path / "file.py"))}

    with patch("agent_pump.services.file_watcher_service.awatch") as mock_awatch:
        mock_awatch.return_value = MockAsyncGenerator([changes])

        # Start watching
        await file_watcher_service.start_watching(path)

        # Wait for task to finish (since iterator is finite)
        task = file_watcher_service._watchers[path]
        await task

        # Verify call
        workflow.run_verification.assert_awaited_once()


@pytest.mark.asyncio
async def test_watch_loop_workflow(file_watcher_service, workspace, project_service):
    """Test watch loop triggers workflow."""
    path = Path("/tmp/test-project")

    # Setup workspace config
    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(enabled=True, action="workflow")
    workspace.get_project_config.return_value = config

    # Setup workflow
    workflow = MagicMock()
    workflow.is_running.return_value = False
    workflow.run = AsyncMock()
    project_service.workflows = {path: workflow}

    # Mock awatch
    changes = {(1, str(path / "file.py"))}

    with patch("agent_pump.services.file_watcher_service.awatch") as mock_awatch:
        mock_awatch.return_value = MockAsyncGenerator([changes])

        # Start watching
        await file_watcher_service.start_watching(path)

        # Wait for task
        task = file_watcher_service._watchers[path]
        await task

        # Wait a bit to ensure loop runs
        await asyncio.sleep(0.01)

        workflow.run.assert_called_once()


@pytest.mark.asyncio
async def test_watch_loop_workflow_already_running(
    file_watcher_service, workspace, project_service
):
    """Test watch loop does not trigger workflow if already running."""
    path = Path("/tmp/test-project")

    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(enabled=True, action="workflow")
    workspace.get_project_config.return_value = config

    workflow = MagicMock()
    workflow.is_running.return_value = True
    workflow.run = AsyncMock()
    project_service.workflows = {path: workflow}

    changes = {(1, str(path / "file.py"))}

    with patch("agent_pump.services.file_watcher_service.awatch") as mock_awatch:
        mock_awatch.return_value = MockAsyncGenerator([changes])

        await file_watcher_service.start_watching(path)
        task = file_watcher_service._watchers[path]
        await task

        workflow.run.assert_not_called()


@pytest.mark.asyncio
async def test_watch_loop_filtering(file_watcher_service, workspace, project_service):
    """Test watch loop filtering."""
    path = Path("/tmp/test-project")

    config = MagicMock(spec=ProjectConfig)
    config.file_watcher = FileWatcherConfig(
        enabled=True, action="verification", patterns=["*.py"], ignore_patterns=["ignored.py"]
    )
    workspace.get_project_config.return_value = config

    workflow = MagicMock()
    workflow.run_verification = AsyncMock()
    project_service.workflows = {path: workflow}

    # 1. Ignored file
    changes1 = {(1, str(path / "ignored.py"))}
    # 2. Non-matching file
    changes2 = {(1, str(path / "README.md"))}
    # 3. Matching file
    changes3 = {(1, str(path / "test.py"))}

    with patch("agent_pump.services.file_watcher_service.awatch") as mock_awatch:
        mock_awatch.return_value = MockAsyncGenerator([changes1, changes2, changes3])

        await file_watcher_service.start_watching(path)
        task = file_watcher_service._watchers[path]
        await task

        # run_verification should be called ONCE (for changes3)
        assert workflow.run_verification.call_count == 1
