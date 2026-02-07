"""Log streaming and storage service."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator
from pathlib import Path

from agent_pump.events.bus import EventBus
from agent_pump.events.models import LogEntryEvent
from agent_pump.models.log import LogEntry
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class LogBuffer:
    """In-memory circular buffer for log entries."""

    def __init__(self, max_size: int = 1000):
        self.buffer: deque[LogEntry] = deque(maxlen=max_size)

    def add(self, entry: LogEntry) -> None:
        """Add an entry to the buffer."""
        self.buffer.append(entry)

    def get_recent(self, limit: int = 100, filter_func=None) -> list[LogEntry]:
        """Get recent entries, optionally filtered."""
        # Convert to list to slice from end
        if filter_func:
            # Filter first then slice? Or slice then filter?
            # Usually we want "last N matching items".
            # Iterating reverse is efficient.
            result = []
            count = 0
            for entry in reversed(self.buffer):
                if filter_func(entry):
                    result.append(entry)
                    count += 1
                    if count >= limit:
                        break
            return list(reversed(result))
        else:
            # Just take last N
            start = max(0, len(self.buffer) - limit)
            return list(self.buffer)[start:]

    def clear(self) -> None:
        """Clear the buffer."""
        self.buffer.clear()


class LogService(BaseService):
    """Service for managing log buffers and streaming."""

    def __init__(self, event_bus: EventBus):
        super().__init__(event_bus)
        self.buffers: dict[Path, LogBuffer] = {}
        # Listeners for streaming: dict[Path, set[asyncio.Queue]]
        self._listeners: dict[Path, set[asyncio.Queue]] = {}
        self._global_listeners: set[asyncio.Queue] = set()

        # Start listening task
        # In a real app, we should track this task to cancel it on shutdown
        # But BaseService doesn't have a start/stop lifecycle method standardized yet
        # We'll assume the caller (App) runs the listener or we hook into bus here.
        # But EventBus.subscribe is an async iterator. We need a task to consume it.
        # We can't start a task in __init__ safely without a loop reference sometimes.
        # But we can rely on Lazy initialization or explicit start.
        # For now, let's provide a `start()` method.

    async def start(self) -> None:
        """Start listening to log events."""
        asyncio.create_task(self._listen_for_logs())

    async def _listen_for_logs(self) -> None:
        """Listen to the event bus for log entries."""
        async for event in self.event_bus.subscribe():
            if isinstance(event, LogEntryEvent):
                self._handle_log_event(event)

    def _handle_log_event(self, event: LogEntryEvent) -> None:
        """Process a log event."""
        # Create LogEntry model
        # Note: We don't construct the Rich renderable here, as that is TUI-specific.
        # The TUI will inflate it from the message if needed, or we keep it None.
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")

        entry = LogEntry(
            timestamp=timestamp,
            message=event.message,
            project_path=event.project_path,
            state=event.state,
            task=event.task,
            renderable=None,
        )

        # Add to project buffer
        if event.project_path:
            self._get_buffer(event.project_path).add(entry)
            self._notify_listeners(event.project_path, entry)

        # We might also want a "global" buffer?
        # For now, we only store if project_path is known.

        # Notify global listeners
        self._notify_global_listeners(entry)

    def _get_buffer(self, project_path: Path) -> LogBuffer:
        """Get or create a buffer for a project."""
        if project_path not in self.buffers:
            self.buffers[project_path] = LogBuffer()
        return self.buffers[project_path]

    def _notify_listeners(self, project_path: Path, entry: LogEntry) -> None:
        """Push entry to relevant project listeners."""
        if project_path in self._listeners:
            for queue in self._listeners[project_path]:
                queue.put_nowait(entry)

    def _notify_global_listeners(self, entry: LogEntry) -> None:
        """Push entry to global listeners."""
        for queue in self._global_listeners:
            queue.put_nowait(entry)

    async def stream(self, project_path: Path | None = None) -> AsyncIterator[LogEntry]:
        """
        Stream logs for a project (or all if None).
        Yields past logs first, then future ones.
        """
        queue: asyncio.Queue[LogEntry] = asyncio.Queue()

        # Add history first
        if project_path:
            history = self._get_buffer(project_path).get_recent(1000)  # Max limit?
            for entry in history:
                queue.put_nowait(entry)

            # Register listener
            if project_path not in self._listeners:
                self._listeners[project_path] = set()
            self._listeners[project_path].add(queue)
        else:
            # Global stream - aggregated history? Expensive to merge.
            # Just yield nothing for history or implement merge sort if needed.
            # Let's yield nothing for global history for now to be safe.
            self._global_listeners.add(queue)

        try:
            while True:
                entry = await queue.get()
                yield entry
        finally:
            # Cleanup
            if project_path:
                self._listeners[project_path].discard(queue)
                if not self._listeners[project_path]:
                    del self._listeners[project_path]
            else:
                self._global_listeners.discard(queue)
