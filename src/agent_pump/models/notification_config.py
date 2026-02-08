"""Notification configuration models."""

from pydantic import BaseModel, ConfigDict, Field


class SlackConfig(BaseModel):
    """Configuration for Slack notifications."""

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(default=False, description="Enable Slack notifications")
    webhook_url: str | None = Field(default=None, description="Slack Webhook URL")
    channel: str | None = Field(default=None, description="Optional channel override")


class NotificationConfig(BaseModel):
    """Configuration for notifications."""

    model_config = ConfigDict(strict=True)

    slack: SlackConfig = Field(default_factory=SlackConfig, description="Slack configuration")
