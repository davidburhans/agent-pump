"""Tests for GitHubSyncConfig."""

from agent_pump.models.github_config import GitHubSyncConfig


def test_defaults():
    config = GitHubSyncConfig()
    assert config.enabled is False
    assert config.repo is None
    assert config.token is None
    assert "agent-pump" in config.sync_labels
    assert "wontfix" in config.ignore_labels
    assert config.priority_map["priority:high"] == "High"
    assert config.auto_close_on_complete is True
    assert config.sync_direction == "bidirectional"
    assert config.sync_interval_minutes == 30

def test_custom_values():
    config = GitHubSyncConfig(
        enabled=True,
        repo="my/repo",
        token="my_token",
        sync_labels=["bug"],
        ignore_labels=["ignore"],
        priority_map={"urgent": "High"},
        auto_close_on_complete=False,
        sync_direction="github_to_roadmap",
        sync_interval_minutes=60,
    )

    assert config.enabled is True
    assert config.repo == "my/repo"
    assert config.token == "my_token"
    assert config.sync_labels == ["bug"]
    assert config.ignore_labels == ["ignore"]
    assert config.priority_map == {"urgent": "High"}
    assert config.auto_close_on_complete is False
    assert config.sync_direction == "github_to_roadmap"
    assert config.sync_interval_minutes == 60
