"""CI Watcher for handling build failures."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_pump.integrations.auto_fix import AutoFixService
from agent_pump.integrations.failure_parser import FailureParser
from agent_pump.models.project import Project
from agent_pump.services.github_service import GitHubService

if TYPE_CHECKING:
    from agent_pump.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class CIWatcher:
    """Service to watch CI runs and trigger auto-fixes."""

    def __init__(self, project_service: "ProjectService"):
        """Initialize CI Watcher.

        Args:
            project_service: Service to access projects and workflows.
        """
        self.project_service = project_service
        self.parser = FailureParser()
        self.auto_fix = AutoFixService()
        self.retry_tracker: dict[str, int] = {}  # "project_path:branch" -> retry_count

    async def handle_check_run(self, payload: dict[str, Any]) -> None:
        """Handle GitHub check_run event.

        Args:
            payload: Webhook payload.
        """
        action = payload.get("action")
        if action != "completed":
            return

        check_run = payload.get("check_run", {})
        conclusion = check_run.get("conclusion")

        # Identify project
        repo_full_name = payload.get("repository", {}).get("full_name")
        if not repo_full_name:
            return

        # Extract branch
        branch = check_run.get("check_suite", {}).get("head_branch")
        if not branch:
            # Fallback to ref if available, but usually check_run has check_suite
            return

        project = await self._find_project(repo_full_name)
        if not project:
            logger.info(f"No project found for repo {repo_full_name}, ignoring CI event.")
            return

        key = f"{project.path}:{branch}"

        # Reset on success
        if conclusion == "success":
            if key in self.retry_tracker:
                logger.info(f"CI success for {key}, resetting failure count.")
                del self.retry_tracker[key]
            return

        if conclusion != "failure":
            return

        check_run_id = check_run.get("id")
        if not check_run_id:
            return

        # Check retries
        retries = self.retry_tracker.get(key, 0)
        if retries >= 3:
            logger.info(f"Max retries reached for {key}, giving up.")
            return

        logger.info(f"Processing CI failure for {project.name}, check_run {check_run_id}")

        # Get GitHub Service
        gh_config = None
        project_config = self.project_service.workspace.get_project_config(project.path)
        if project_config:
            gh_config = project_config.github_integration

        if not gh_config:
            logger.warning(f"No GitHub integration configured for {project.name}")
            return

        github_service = GitHubService(gh_config)

        # Fetch logs
        logs = github_service.get_check_run_logs(check_run_id)

        # Parse failure
        failure_info = self.parser.parse(logs)
        failure_info.run_id = check_run_id

        # Create fix task
        self.auto_fix.create_fix_task(project, failure_info, check_run_id, retries)

        # Trigger workflow
        self.retry_tracker[key] = retries + 1

        # Ensure workflow is loaded
        workflow = self.project_service.workflows.get(project.path)
        if not workflow:
             try:
                 await self.project_service.add_project(project.path)
                 workflow = self.project_service.workflows.get(project.path)
             except Exception as e:
                 logger.error(f"Failed to load workflow for {project.name}: {e}")
                 return

        if workflow and not workflow.is_running():
            logger.info(f"Triggering auto-fix workflow for {project.name}")
            try:
                await workflow.run()
            except Exception as e:
                logger.error(f"Failed to run workflow for {project.name}: {e}")
        else:
            logger.info(f"Workflow already running for {project.name}, added task will be picked up next.")

    async def _find_project(self, repo_full_name: str) -> Project | None:
        """Find project matching the repository name."""
        workspace = self.project_service.workspace

        for path_str, proj_config in workspace.projects.items():
            if (
                proj_config.github_integration
                and proj_config.github_integration.owner
                and proj_config.github_integration.repo
            ):
                full = f"{proj_config.github_integration.owner}/{proj_config.github_integration.repo}"
                if full == repo_full_name:
                    path = Path(path_str)
                    try:
                        return await self.project_service.add_project(path)
                    except Exception as e:
                        logger.error(f"Failed to load project {path}: {e}")
                        return None
        return None
