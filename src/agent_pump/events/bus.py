"""Async Event Bus implementation."""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TypeVar

from .models import Event

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Event)


class EventBus:
    """Async event bus with multiple subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: The event to publish.
        """
        # Copy list to iterate safely in case subscribers modify list
        subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.error(f"Failed to deliver event {event} to subscriber: {e}")

    async def subscribe(
        self, event_types: type[T] | tuple[type[T], ...] | None = None
    ) -> AsyncIterator[T]:
        """
        Subscribe to events.

        Args:
            event_types: Optional type(s) of events to filter for.
                         If None, receives all events.

        Yields:
            Events matching the filter.
        """
        queue: asyncio.Queue[Event] = asyncio.Queue()
        self._subscribers.append(queue)

        try:
            while True:
                event = await queue.get()
                if event_types is None or isinstance(event, event_types):
                    # We know it matches T because of the check
                    yield event  # type: ignore
        except asyncio.CancelledError:
            # Clean up when the consumer task is cancelled
            pass
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
