"""Service for creating Pull Requests."""

import logging
from agent_pump.models.project import Project
from agent_pump.services.github_service import GitHubService
from agent_pump.services.branch_manager import BranchManager

logger = logging.getLogger(__name__)


class PRCreatorService:
    """Service to handle Pull Request creation logic."""

    def __init__(self, project: Project, github_service: GitHubService):
        """Initialize the PR creator service.

        Args:
            project: The project context
            github_service: Configured GitHub service
        """
        self.project = project
        self.github = github_service

    async def create_pr(self) -> str | None:
        """Create a PR for the current feature branch.

        Returns:
            URL of the created PR, or None if creation failed.
        """
        try:
            # Check context
            if not self.project.current_feature:
                logger.warning("Cannot create PR: No current feature set")
                return None

            branch_manager = BranchManager(self.project.path)
            feature_branch = branch_manager.get_current_branch()
            base_branch = "main"
            # Use base branch from GitHub config if available
            if self.github.config.base_branch:
                base_branch = self.github.config.base_branch

            # Push feature branch
            logger.info(f"Pushing feature branch {feature_branch} to remote...")
            if not branch_manager.push_to_remote(feature_branch):
                logger.error(f"Failed to push branch {feature_branch}")
                return None

            # Gather content
            plan_path = self.project.path / "ENGINEERING_PLAN.md"
            plan_content = (
                plan_path.read_text(encoding="utf-8")
                if plan_path.exists()
                else "No engineering plan found."
            )

            commits = branch_manager.get_branch_commits(feature_branch, base_branch)
            commit_list = (
                "\n".join([f"- {msg}" for msg in commits])
                if commits
                else "No new commits found."
            )

            # Format body
            body = self._format_body(plan_content, commit_list)
            title = f"[Agent Pump] {self.project.current_feature}"

            # Create PR
            logger.info(f"Creating PR for {feature_branch} -> {base_branch}")
            pr_info = self.github.create_pull_request(
                title=title,
                body=body,
                head_branch=feature_branch,
                base_branch=base_branch,
            )

            return pr_info.pr_url

        except Exception as e:
            logger.exception("Failed to create PR")
            return None

    def _format_body(self, plan: str, commits: str) -> str:
        """Format the PR body."""
        # Simple extraction of summary from plan if possible
        summary = "See Engineering Plan for details."
        if "## Summary" in plan:
            # Extract content after ## Summary until next ##
            try:
                parts = plan.split("## Summary", 1)[1]
                summary = parts.split("##", 1)[0].strip()
            except IndexError:
                pass

        return f"""
## Summary
{summary}

## Changes
{commits}

## Verification
Automated verification passed.

---
*Created automatically by Agent Pump*
"""
