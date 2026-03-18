from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import WorkflowCompletedEvent, WorkflowFailedEvent
from agent_pump.models.notification_config import NotificationConfig, SlackConfig
from agent_pump.services.notification_service import NotificationService


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def slack_config():
    return NotificationConfig(
        slack=SlackConfig(
            enabled=True,
            webhook_url="https://hooks.slack.com/services/test/test",
            channel="#test-channel",
        )
    )


@pytest.fixture
def notification_service(slack_config, event_bus):
    return NotificationService(slack_config, event_bus)


@pytest.mark.asyncio
async def test_workflow_completed_notification(notification_service, event_bus):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()

        event = WorkflowCompletedEvent(
            project_path=Path("/tmp/test"), project_name="test-project", feature_name="test-feature"
        )

        await notification_service.on_workflow_completed(event)

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://hooks.slack.com/services/test/test"
        assert kwargs["json"]["channel"] == "#test-channel"
        assert "Workflow Completed" in kwargs["json"]["text"]
        assert "test-project" in kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_workflow_failed_notification(notification_service, event_bus):
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.raise_for_status = MagicMock()

        event = WorkflowFailedEvent(
            project_path=Path("/tmp/test"),
            project_name="test-project",
            feature_name="test-feature",
            error="Something went wrong",
        )

        await notification_service.on_workflow_failed(event)

        mock_post.assert_called_once()
        kwargs = mock_post.call_args[1]
        assert "Workflow Failed" in kwargs["json"]["text"]
        assert "Something went wrong" in kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_notification_disabled(event_bus):
    config = NotificationConfig(slack=SlackConfig(enabled=False, webhook_url="http://test"))
    service = NotificationService(config, event_bus)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        event = WorkflowCompletedEvent(
            project_path=Path("/tmp/test"), project_name="test", feature_name="test"
        )
        await service.on_workflow_completed(event)
        mock_post.assert_not_called()
