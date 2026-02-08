"""Notification service for sending external notifications."""

import asyncio
import logging

import httpx

from agent_pump.events.bus import EventBus
from agent_pump.events.models import WorkflowCompletedEvent, WorkflowFailedEvent
from agent_pump.models.notification_config import NotificationConfig

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notifications."""

    def __init__(self, config: NotificationConfig, event_bus: EventBus):
        self.config = config
        self.event_bus = event_bus
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start listening for events."""
        if self._task:
            return
        self._task = asyncio.create_task(self._listen())
        logger.info("NotificationService started")

    async def stop(self) -> None:
        """Stop listening."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("NotificationService stopped")

    async def _listen(self) -> None:
        """Listen for events."""
        try:
            async for event in self.event_bus.subscribe(
                (WorkflowCompletedEvent, WorkflowFailedEvent)
            ):
                if isinstance(event, WorkflowCompletedEvent):
                    await self.on_workflow_completed(event)
                elif isinstance(event, WorkflowFailedEvent):
                    await self.on_workflow_failed(event)
        except Exception as e:
            logger.error(f"Error in NotificationService listener: {e}")

    async def on_workflow_completed(self, event: WorkflowCompletedEvent) -> None:
        """Handle workflow completion event."""
        if self.config.slack.enabled and self.config.slack.webhook_url:
            message = (
                f":white_check_mark: *Workflow Completed*\n"
                f"*Project:* {event.project_name}\n"
                f"*Feature:* {event.feature_name}"
            )
            await self._send_slack_message(message)

    async def on_workflow_failed(self, event: WorkflowFailedEvent) -> None:
        """Handle workflow failure event."""
        if self.config.slack.enabled and self.config.slack.webhook_url:
            message = (
                f":x: *Workflow Failed*\n"
                f"*Project:* {event.project_name}\n"
                f"*Feature:* {event.feature_name}\n"
                f"*Error:* {event.error}"
            )
            await self._send_slack_message(message)

    async def _send_slack_message(self, message: str) -> None:
        """Send a message to Slack via webhook."""
        if not self.config.slack.webhook_url:
            return

        try:
            payload = {"text": message}
            if self.config.slack.channel:
                payload["channel"] = self.config.slack.channel

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.slack.webhook_url, json=payload, timeout=10.0
                )
                response.raise_for_status()
                logger.info("Slack notification sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
