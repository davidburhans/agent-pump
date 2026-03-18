"""Tests for GitHubIssueSync."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.integrations.issue_sync import GitHubIssueSync
from agent_pump.models.github_config import GitHubSyncConfig
from agent_pump.models.roadmap import RoadmapItem, RoadmapStatus
from agent_pump.services.roadmap_service import RoadmapService


@pytest.fixture
def mock_config():
    return GitHubSyncConfig(
        token="test_token",
        repo="test/repo",
        sync_labels=["test_label"],
    )


@pytest.fixture
def mock_roadmap_service():
    service = MagicMock(spec=RoadmapService)
    service.get_all_items.return_value = []
    return service


@patch("agent_pump.integrations.issue_sync.Github")
def test_sync_new_issue(mock_github_cls, mock_config, mock_roadmap_service):
    # Setup mock issue
    mock_issue = MagicMock()
    mock_issue.number = 1
    mock_issue.title = "New Issue"
    mock_issue.body = "Issue Body"
    mock_issue.labels = []

    # Setup mock repo
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [mock_issue]

    mock_github_cls.return_value.get_repo.return_value = mock_repo

    # Setup sync service
    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)

    sync_service.sync()

    # Assertions
    mock_repo.get_issues.assert_called_once()
    mock_roadmap_service.add_item.assert_called_once()

    # Check arguments
    call_args = mock_roadmap_service.add_item.call_args
    assert call_args.kwargs["title"] == "New Issue"
    assert call_args.kwargs["status"] == RoadmapStatus.NOT_STARTED
    assert call_args.kwargs["metadata"] == {"github_issue": 1}


@patch("agent_pump.integrations.issue_sync.Github")
def test_sync_completed_item(mock_github_cls, mock_config, mock_roadmap_service):
    # Setup completed roadmap item
    item = RoadmapItem(
        title="Completed Feature", status=RoadmapStatus.COMPLETED, metadata={"github_issue": 123}
    )
    mock_roadmap_service.get_all_items.return_value = [item]

    # Setup mock issue (open)
    mock_issue = MagicMock()
    mock_issue.number = 123
    mock_issue.state = "open"

    # Setup mock repo
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = []  # No new issues
    mock_repo.get_issue.return_value = mock_issue

    mock_github_cls.return_value.get_repo.return_value = mock_repo

    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)

    sync_service.sync()

    # Assertions
    mock_repo.get_issue.assert_called_with(123)
    mock_issue.edit.assert_called_with(state="closed")
    mock_issue.create_comment.assert_called_once()


@patch("agent_pump.integrations.issue_sync.Github")
def test_map_priority(mock_github_cls, mock_config, mock_roadmap_service):
    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)
    # Mock labels
    label_high = MagicMock()
    label_high.name = "priority:high"

    priority = sync_service._map_priority([label_high])
    assert priority == "High"

    label_unknown = MagicMock()
    label_unknown.name = "unknown"
    priority = sync_service._map_priority([label_unknown])
    assert priority == "Medium"


def test_init_validation(mock_roadmap_service):
    with pytest.raises(ValueError, match="GitHub token is required"):
        GitHubIssueSync(GitHubSyncConfig(), mock_roadmap_service)


@patch("agent_pump.integrations.issue_sync.Github")
def test_sync_direction_github_to_roadmap(mock_github_cls, mock_config, mock_roadmap_service):
    mock_config.sync_direction = "github_to_roadmap"

    # Setup mock issue
    mock_issue = MagicMock()
    mock_issue.number = 1
    mock_issue.title = "New Issue"
    mock_issue.body = "Issue Body"
    mock_issue.labels = []

    # Setup mock repo
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [mock_issue]

    mock_github_cls.return_value.get_repo.return_value = mock_repo
    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)
    sync_service.sync()

    # Should call add_item
    mock_roadmap_service.add_item.assert_called_once()

    # Check roadmap -> github part
    # If we have completed item, it should NOT try to close issue
    mock_roadmap_service.reset_mock()
    mock_repo.reset_mock()
    mock_roadmap_service.get_all_items.return_value = [
        RoadmapItem(
            title="Completed Feature",
            status=RoadmapStatus.COMPLETED,
            metadata={"github_issue": 123},
        )
    ]

    mock_issue_completed = MagicMock()
    mock_issue_completed.number = 123
    mock_issue_completed.state = "open"
    mock_repo.get_issue.return_value = mock_issue_completed

    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)
    sync_service.sync()

    # Should NOT close issue
    mock_issue_completed.edit.assert_not_called()


@patch("agent_pump.integrations.issue_sync.Github")
def test_sync_direction_roadmap_to_github(mock_github_cls, mock_config, mock_roadmap_service):
    mock_config.sync_direction = "roadmap_to_github"

    # Setup mock issue
    mock_issue = MagicMock()
    mock_issue.number = 1
    mock_issue.title = "New Issue"
    mock_issue.body = "Issue Body"
    mock_issue.labels = []

    # Setup mock repo
    mock_repo = MagicMock()
    mock_repo.get_issues.return_value = [mock_issue]
    mock_github_cls.return_value.get_repo.return_value = mock_repo

    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)
    sync_service.sync()

    # Should NOT call add_item for new issue
    mock_roadmap_service.add_item.assert_not_called()

    # Check roadmap -> github part
    mock_roadmap_service.reset_mock()
    mock_repo.reset_mock()
    mock_roadmap_service.get_all_items.return_value = [
        RoadmapItem(
            title="Completed Feature",
            status=RoadmapStatus.COMPLETED,
            metadata={"github_issue": 123},
        )
    ]

    mock_issue_completed = MagicMock()
    mock_issue_completed.number = 123
    mock_issue_completed.state = "open"
    mock_repo.get_issue.return_value = mock_issue_completed

    sync_service = GitHubIssueSync(mock_config, mock_roadmap_service)
    sync_service.sync()

    # Should close issue
    mock_issue_completed.edit.assert_called_with(state="closed")
