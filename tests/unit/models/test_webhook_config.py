"""Unit tests for WebhookConfig model."""

from agent_pump.models.webhook_config import WebhookConfig, WebhookTrigger


def test_webhook_config_defaults():
    """Test default values for WebhookConfig."""
    config = WebhookConfig()
    assert config.enabled is False
    assert config.secret_key is None
    assert "github" in config.allowed_sources
    assert "slack" in config.allowed_sources
    assert "main" in config.auto_trigger_branches


def test_webhook_config_custom_values():
    """Test custom values for WebhookConfig."""
    config = WebhookConfig(
        enabled=True,
        secret_key="mysecret",
        allowed_sources=["custom"],
        auto_trigger_branches=["develop"]
    )
    assert config.enabled is True
    assert config.secret_key == "mysecret"
    assert config.allowed_sources == ["custom"]
    assert config.auto_trigger_branches == ["develop"]


def test_webhook_trigger_model():
    """Test WebhookTrigger model."""
    trigger = WebhookTrigger(
        source="github",
        event_type="push",
        project_id="proj1",
        phase="planning"
    )
    assert trigger.source == "github"
    assert trigger.event_type == "push"
    assert trigger.project_id == "proj1"
    assert trigger.phase == "planning"
