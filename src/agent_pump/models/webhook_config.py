"""Webhook configuration models."""

from pydantic import BaseModel, ConfigDict, Field


class WebhookConfig(BaseModel):
    """Configuration for webhook triggers."""

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(default=False, description="Enable webhook triggers")
    secret_key: str | None = Field(default=None, description="Secret key for HMAC validation")
    allowed_sources: list[str] = Field(
        default_factory=lambda: ["github", "slack", "custom"],
        description="Allowed webhook sources",
    )
    auto_trigger_branches: list[str] = Field(
        default_factory=lambda: ["main", "master"],
        description="Branches that trigger workflows on push events",
    )


class WebhookTrigger(BaseModel):
    """Model representing a webhook trigger event."""

    model_config = ConfigDict(strict=True)

    source: str = Field(description="Source of the webhook (e.g., github, slack)")
    event_type: str = Field(description="Event type (e.g., push, issue_comment)")
    project_id: str | None = Field(
        default=None, description="Specific project ID, or None for routing"
    )
    phase: str | None = Field(default=None, description="Start at specific phase")
