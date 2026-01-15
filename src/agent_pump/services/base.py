"""Base service class."""

import logging

from agent_pump.events.bus import EventBus

logger = logging.getLogger(__name__)


class BaseService:
    """Base class for all services."""

    def __init__(self, event_bus: EventBus) -> None:
        """
        Initialize the service.

        Args:
            event_bus: The event bus for publishing events.
        """
        self.event_bus = event_bus
        logger.debug(f"Initialized {self.__class__.__name__}")
