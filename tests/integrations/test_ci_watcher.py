from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.integrations.ci_watcher import CIWatcher
from agent_pump.models.project import Project


@pytest.mark.asyncio
async def test_handle_check_run_success():
    # Mocks
    project_service = MagicMock()
    workspace = MagicMock()
    project_service.workspace = workspace

    # Setup workspace project config
    proj_config = MagicMock()
    proj_config.github_integration.owner = "owner"
    proj_config.github_integration.repo = "repo"

    # Key is path string
    workspace.projects = {"/tmp/project": proj_config}

    # Mock add_project to return Project object
    mock_project = Project(path=Path("/tmp/project"), name="Test Project")
    project_service.add_project = AsyncMock(return_value=mock_project)

    # Mock workflow
    workflow = MagicMock()
    workflow.is_running.return_value = False
    workflow.run = AsyncMock()
    project_service.workflows.get.return_value = workflow

    # Mock workspace.get_project_config for CIWatcher
    workspace.get_project_config.return_value = proj_config

    # Patch AutoFixService
    with patch("agent_pump.integrations.ci_watcher.AutoFixService") as MockAutoFix:
        mock_auto_fix = MockAutoFix.return_value

        watcher = CIWatcher(project_service)
        # Ensure watcher uses the mock (it should if instantiated inside patch)
        # But wait, AutoFixService() call inside __init__ uses the patched class.

        # Patch GitHubService
        with patch("agent_pump.integrations.ci_watcher.GitHubService") as MockGitHubService:
            mock_gh = MockGitHubService.return_value
            mock_gh.get_check_run_logs.return_value = "ERROR: something broke\nFAILED tests/test_foo.py::test_bar"

            payload = {
                "action": "completed",
                "check_run": {
                    "id": 123,
                    "conclusion": "failure",
                    "check_suite": {"head_branch": "feature/foo"}
                },
                "repository": {"full_name": "owner/repo"}
            }

            await watcher.handle_check_run(payload)

            # Verifications
            project_service.add_project.assert_called()
            mock_gh.get_check_run_logs.assert_called_with(123)
            mock_auto_fix.create_fix_task.assert_called()
            workflow.run.assert_called_once()

            # Check retry tracker
            key = f"{mock_project.path}:feature/foo"
            assert watcher.retry_tracker[key] == 1

@pytest.mark.asyncio
async def test_handle_check_run_ignored_actions():
    project_service = MagicMock()
    watcher = CIWatcher(project_service)

    # Not completed
    await watcher.handle_check_run({"action": "started"})

    # Not failure (but now success might trigger logic, so be careful)
    # Success without branch/repo might return early.
    await watcher.handle_check_run({"action": "completed", "check_run": {"conclusion": "neutral"}})


@pytest.mark.asyncio
async def test_handle_check_run_max_retries():
    project_service = MagicMock()
    workspace = MagicMock()
    project_service.workspace = workspace

    proj_config = MagicMock()
    proj_config.github_integration.owner = "owner"
    proj_config.github_integration.repo = "repo"
    workspace.projects = {"/tmp/project": proj_config}

    mock_project = Project(path=Path("/tmp/project"), name="Test Project")
    project_service.add_project = AsyncMock(return_value=mock_project)

    watcher = CIWatcher(project_service)
    key = f"{mock_project.path}:feature/foo"
    watcher.retry_tracker[key] = 3

    payload = {
        "action": "completed",
        "check_run": {
            "id": 123,
            "conclusion": "failure",
            "check_suite": {"head_branch": "feature/foo"}
        },
        "repository": {"full_name": "owner/repo"}
    }

    # Setup workflow mock to ensure it's NOT called
    workflow = MagicMock()
    workflow.run = AsyncMock()
    project_service.workflows.get.return_value = workflow

    await watcher.handle_check_run(payload)

    project_service.add_project.assert_called()
    workflow.run.assert_not_called()

@pytest.mark.asyncio
async def test_handle_check_run_reset_on_success():
    project_service = MagicMock()
    workspace = MagicMock()
    project_service.workspace = workspace

    proj_config = MagicMock()
    proj_config.github_integration.owner = "owner"
    proj_config.github_integration.repo = "repo"
    workspace.projects = {"/tmp/project": proj_config}

    mock_project = Project(path=Path("/tmp/project"), name="Test Project")
    project_service.add_project = AsyncMock(return_value=mock_project)

    watcher = CIWatcher(project_service)
    key = f"{mock_project.path}:feature/foo"
    watcher.retry_tracker[key] = 2

    payload = {
        "action": "completed",
        "check_run": {
            "id": 123,
            "conclusion": "success",
            "check_suite": {"head_branch": "feature/foo"}
        },
        "repository": {"full_name": "owner/repo"}
    }

    await watcher.handle_check_run(payload)

    assert key not in watcher.retry_tracker
