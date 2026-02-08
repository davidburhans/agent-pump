"""GitHub Issue synchronization service."""

from typing import TYPE_CHECKING, Any

from github import Github
from github.Issue import Issue

from agent_pump.models.github_config import GitHubSyncConfig
from agent_pump.models.roadmap import RoadmapItem, RoadmapStatus
from agent_pump.services.roadmap_service import RoadmapService


class GitHubIssueSync:
    """Synchronizes GitHub issues with the roadmap."""

    def __init__(self, config: GitHubSyncConfig, roadmap_service: RoadmapService) -> None:
        """Initialize the sync service.

        Args:
            config: Sync configuration.
            roadmap_service: Roadmap service instance.
        """
        self.config = config
        self.roadmap_service = roadmap_service

        if not self.config.token:
            raise ValueError("GitHub token is required for sync")

        self.github = Github(self.config.token)

        if self.config.repo:
            self.repo = self.github.get_repo(self.config.repo)
        else:
            # Repo must be provided in config
            raise ValueError("GitHub repository is required for sync")

    def sync(self) -> None:
        """
        Main sync loop:
        1. Fetch open issues from GitHub with matching labels
        2. Compare with ROADMAP.md items
        3. Create missing items in roadmap
        4. Close issues for completed roadmap items
        """
        issues = self._fetch_issues()
        roadmap_items = self.roadmap_service.get_all_items()

        # GitHub -> Roadmap
        if self.config.sync_direction in ("github_to_roadmap", "bidirectional"):
            for issue in issues:
                if not self._find_roadmap_item(issue, roadmap_items):
                    self._create_roadmap_item(issue)

        # Roadmap -> GitHub (close completed)
        if self.config.sync_direction in ("roadmap_to_github", "bidirectional"):
            if self.config.auto_close_on_complete:
                for item in roadmap_items:
                    if item.status == RoadmapStatus.COMPLETED:
                        issue = self._find_github_issue(item)
                        if issue and issue.state == "open":
                            issue.edit(state="closed")
                            issue.create_comment(
                                "✅ Closed by Agent Pump - feature completed!"
                            )

    def _fetch_issues(self) -> list[Issue]:
        """Fetch open issues matching sync labels."""
        labels = self.config.sync_labels
        # PyGithub get_issues expects labels as list of strings or Label objects
        return list(self.repo.get_issues(state="open", labels=labels))

    def _find_roadmap_item(self, issue: Issue, items: list[RoadmapItem]) -> RoadmapItem | None:
        """Find a roadmap item corresponding to a GitHub issue."""
        for item in items:
            # Check metadata first
            if item.metadata.get("github_issue") == issue.number:
                return item
            # Check title (fuzzy match?)
            if item.title.strip() == issue.title.strip():
                return item
        return None

    def _find_github_issue(self, item: RoadmapItem) -> Issue | None:
        """Find a GitHub issue corresponding to a roadmap item."""
        issue_number = item.metadata.get("github_issue")
        if issue_number:
            try:
                return self.repo.get_issue(int(issue_number))
            except Exception:
                return None
        return None

    def _create_roadmap_item(self, issue: Issue) -> None:
        """Create a new roadmap item from a GitHub issue."""
        priority = self._map_priority(issue.labels)

        self.roadmap_service.add_item(
            title=issue.title,
            description=issue.body or "",
            priority=priority,
            status=RoadmapStatus.NOT_STARTED,
            metadata={"github_issue": issue.number},
            section="future"  # Default to future sprint
        )

    def _map_priority(self, labels: list[Any]) -> str:
        """Map GitHub labels to roadmap priority."""
        label_names = [l.name for l in labels]
        for label, priority in self.config.priority_map.items():
            if label in label_names:
                return priority
        return "Medium"
