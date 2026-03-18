"""File watcher service for triggering workflows on changes."""

import asyncio
import fnmatch
import logging
from pathlib import Path

from watchfiles import DefaultFilter, awatch

from agent_pump.events.bus import EventBus
from agent_pump.events.models import ConfigUpdatedEvent, ProjectAddedEvent, ProjectRemovedEvent
from agent_pump.models.file_watcher_config import FileWatcherConfig
from agent_pump.models.workspace import Workspace
from agent_pump.services.base import BaseService
from agent_pump.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class FileWatcherService(BaseService):
    """Service for watching file changes and triggering workflow actions."""

    def __init__(
        self, event_bus: EventBus, project_service: ProjectService, workspace: Workspace
    ) -> None:
        """
        Initialize the file watcher service.

        Args:
            event_bus: The event bus.
            project_service: Service to access project workflows.
            workspace: The workspace configuration.
        """
        super().__init__(event_bus)
        self.project_service = project_service
        self.workspace = workspace
        self._watchers: dict[Path, asyncio.Task] = {}

        # Start event listener loop
        self._event_task = asyncio.create_task(self._listen_to_events())

    async def _listen_to_events(self) -> None:
        """Listen to relevant events."""
        event_types = (ProjectAddedEvent, ProjectRemovedEvent, ConfigUpdatedEvent)
        # subscribe returns an async generator, so we iterate over it
        async for event in self.event_bus.subscribe(event_types):
            try:
                if isinstance(event, ProjectAddedEvent):
                    await self.on_project_added(event)
                elif isinstance(event, ProjectRemovedEvent):
                    await self.on_project_removed(event)
                elif isinstance(event, ConfigUpdatedEvent):
                    await self.on_config_updated(event)
            except Exception as e:
                logger.error(f"Error handling event {event}: {e}")

    async def on_project_added(self, event: ProjectAddedEvent) -> None:
        """Handle project added event."""
        await self.start_watching(event.project_path)

    async def on_project_removed(self, event: ProjectRemovedEvent) -> None:
        """Handle project removed event."""
        await self.stop_watching(event.project_path)

    async def on_config_updated(self, event: ConfigUpdatedEvent) -> None:
        """Handle configuration updated event."""
        # If project_path is None, it might be workspace config update.
        # But file_watcher is per project.
        # We'll check if it's relevant.
        if event.project_path:
            # Restart watcher for this project to pick up new config
            await self.stop_watching(event.project_path)
            await self.start_watching(event.project_path)

    async def start_watching(self, path: Path) -> None:
        """
        Start watching a project directory.

        Args:
            path: Path to the project directory.
        """
        path = path.resolve()

        # Stop existing watcher if any
        if path in self._watchers:
            await self.stop_watching(path)

        project_config = self.workspace.get_project_config(path)
        if not project_config:
            return

        config: FileWatcherConfig = project_config.file_watcher
        if not config.enabled:
            return

        logger.info(f"Starting file watcher for {path} (debounce={config.debounce_seconds}s)")

        # Create watcher task
        task = asyncio.create_task(self._watch_loop(path, config))
        self._watchers[path] = task

    async def stop_watching(self, path: Path) -> None:
        """
        Stop watching a project directory.

        Args:
            path: Path to the project directory.
        """
        path = path.resolve()
        if path in self._watchers:
            logger.info(f"Stopping file watcher for {path}")
            task = self._watchers.pop(path)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _watch_loop(self, path: Path, config: FileWatcherConfig) -> None:
        """
        Loop to watch for file changes.

        Args:
            path: Project path.
            config: Watcher configuration.
        """
        try:
            debounce_ms = int(config.debounce_seconds * 1000)

            # Prepare ignore list for DefaultFilter
            # We assume user provides directory names to ignore, but we also filter manually
            # to support glob patterns.
            # DefaultFilter is good for ignoring common junk directories efficiently.
            # We filter config.ignore_patterns for simple directory names (no globs/slashes)
            ignore_dirs = [p for p in config.ignore_patterns if "/" not in p and "*" not in p]

            watch_filter = DefaultFilter(ignore_dirs=ignore_dirs)

            async for changes in awatch(path, debounce=debounce_ms, watch_filter=watch_filter):
                # Filter changes based on patterns and ignore_patterns
                relevant_changes = []
                for change_type, file_path in changes:
                    file_path_obj = Path(file_path)
                    try:
                        rel_path = file_path_obj.relative_to(path)
                    except ValueError:
                        # Should not happen if watchfiles works correctly, but safe fallback
                        rel_path = file_path_obj

                    rel_path_str = str(rel_path)
                    name = file_path_obj.name

                    # Check ignore patterns first
                    ignored = False
                    for pattern in config.ignore_patterns:
                        # Check against name (e.g. *.pyc) or relative path (e.g. build/*)
                        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path_str, pattern):
                            ignored = True
                            break
                    if ignored:
                        continue

                    # Check match patterns
                    matched = False
                    for pattern in config.patterns:
                        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path_str, pattern):
                            matched = True
                            break

                    if matched:
                        relevant_changes.append(file_path)

                if not relevant_changes:
                    continue

                logger.info(f"File changes detected in {path}: {relevant_changes}")

                # Get workflow
                workflow = self.project_service.workflows.get(path)
                if not workflow:
                    logger.warning(f"Workflow not found for {path}, skipping trigger")
                    continue

                if config.action == "verification":
                    logger.info(f"Triggering verification for {path}")
                    # Run verification (async)
                    await workflow.run_verification()

                elif config.action == "workflow":
                    if not workflow.is_running():
                        logger.info(f"Starting workflow for {path}")
                        asyncio.create_task(workflow.run())
                    else:
                        logger.debug(f"Workflow already running for {path}, ignoring change.")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error in file watcher loop for {path}: {e}")
