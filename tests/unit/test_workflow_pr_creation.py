import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.models.workspace import ProjectConfig
from agent_pump.models.github_integration import GitHubIntegrationConfig

@pytest.fixture
def mock_project(tmp_path):
    project = MagicMock(spec=Project)
    project.path = tmp_path
    project.name = "Test Project"
    project.current_feature = "Test Feature"
    project.status = ProjectStatus.IDLE
    # Add config if accessed directly
    project.config = MagicMock()
    return project

@pytest.fixture
def mock_workflow(mock_project):
    workflow = ProjectWorkflow(project=mock_project)
    workflow._emit_output = MagicMock()
    # Mock workflow state
    workflow.workflow_state = MagicMock()
    return workflow

@pytest.mark.asyncio
async def test_workflow_creates_pr_on_commit(mock_workflow, mock_project):
    # Enable PR creation in config
    gh_config = GitHubIntegrationConfig(create_pr_on_complete=True, token="dummy")
    project_config = ProjectConfig(path=mock_project.path, github_integration=gh_config)
    mock_workflow.project_config = project_config

    with patch("agent_pump.orchestrator.workflow.PRCreatorService") as MockPRService:
        mock_pr_instance = MockPRService.return_value
        mock_pr_instance.create_pr = AsyncMock(return_value="http://pr.url")

        # Simulate post-phase
        success = await mock_workflow._post_phase("committing", True)

        assert success is True
        MockPRService.assert_called_once()
        mock_pr_instance.create_pr.assert_called_once()
        mock_workflow._emit_output.assert_any_call("[SUCCESS] Created PR: http://pr.url\n")

@pytest.mark.asyncio
async def test_workflow_skips_pr_creation_if_disabled(mock_workflow, mock_project):
    # Disable PR creation
    gh_config = GitHubIntegrationConfig(create_pr_on_complete=False, token="dummy")
    project_config = ProjectConfig(path=mock_project.path, github_integration=gh_config)
    mock_workflow.project_config = project_config

    with patch("agent_pump.orchestrator.workflow.PRCreatorService") as MockPRService:
        success = await mock_workflow._post_phase("committing", True)

        assert success is True
        MockPRService.assert_not_called()

@pytest.mark.asyncio
async def test_workflow_skips_pr_creation_if_no_config(mock_workflow, mock_project):
    # No GitHub config
    # Need to satisfy Pydantic required fields including github_integration if it defaults to factory but we pass explicitly?
    # ProjectConfig definition: github_integration: GitHubIntegrationConfig = Field(default_factory=...)
    # So if we pass None, it might fail? No, if we don't pass it, it uses default.
    # The test says "no config".
    # If we pass path only, github_integration uses default factory which has defaults.
    # We want to test when create_pr_on_complete is False or config is missing?
    # GitHubIntegrationConfig defaults create_pr_on_complete=True.
    # So we should explicitly disable it or rely on logic check.
    # The logic checks: if self.project_config and self.project_config.github_integration ...
    # Wait, ProjectConfig ALWAYS has github_integration due to default_factory.
    # So the check `and self.project_config.github_integration` is always true unless explicitly set to None (if allowed).
    # But field type is GitHubIntegrationConfig (not Optional).
    # So we can't set it to None.
    # So we should test "if create_pr_on_complete is False" (already tested).
    # Or "if project_config is None" (workflow init handles this).

    mock_workflow.project_config = None

    with patch("agent_pump.orchestrator.workflow.PRCreatorService") as MockPRService:
        success = await mock_workflow._post_phase("committing", True)

        assert success is True
        MockPRService.assert_not_called()
