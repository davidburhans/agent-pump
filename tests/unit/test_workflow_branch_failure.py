
import asyncio
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.workspace import ProjectConfig
from agent_pump.orchestrator.workflow import ProjectWorkflow


class TestBranchCreationFailure(unittest.TestCase):
    def setUp(self):
        # Use real path to satisfy Pydantic
        self.project_path = Path(".")

        self.project = Project(
            name="Test",
            path=self.project_path,
            status=ProjectStatus.IDLE,
            current_feature="New Feature"
        )
        self.config = ProjectConfig(
            path=self.project_path,
            branch_strategy=BranchStrategyConfig(
                enabled=True,
                auto_create_branch=True,
                base_branch="main"
            )
        )

    @patch("agent_pump.orchestrator.workflow.BranchManager")
    def test_workflow_pauses_on_branch_failure(self, mock_bm_cls):
        mock_manager = MagicMock()
        mock_bm_cls.return_value = mock_manager

        # Configure get_current_branch to return 'main' so we attempt creation
        mock_manager.get_current_branch.return_value = "main"

        # Simulate exception during branch creation
        mock_manager.create_feature_branch.side_effect = Exception("Git error: conflict")

        workflow = ProjectWorkflow(
            project=self.project,
            project_config=self.config
        )

        # Mock dependencies
        workflow._read_file_content = AsyncMock(return_value="New Feature")
        workflow._emit_output = MagicMock()

        # IMPORTANT: Set running=True so pause_workflow() works
        workflow._running = True

        async def run_test():
            # This calls _create_feature_branch internally
            # It should return False and call pause_workflow
            return await workflow._prepare_planning_phase({})

        result = asyncio.run(run_test())

        # Verify attempt was made
        mock_manager.create_feature_branch.assert_called_once()

        # Verify return value is False (failure signal)
        self.assertFalse(result, "Expected _prepare_planning_phase to return False on failure")

        # Verify workflow was cancelled/paused
        self.assertTrue(workflow._cancelled, "Workflow should be cancelled")

        # Verify error message emitted
        workflow._emit_output.assert_called()
        found_error = False
        for call in workflow._emit_output.call_args_list:
            args, _ = call
            # Should have "Branch creation failed" (from _prepare_planning_phase)
            # OR "Failed to create feature branch" (from _create_feature_branch)
            if "Branch creation failed" in str(args[0]):
                found_error = True
                break
        self.assertTrue(found_error, "Error message 'Branch creation failed' not emitted")

if __name__ == "__main__":
    unittest.main()
