"""Tests for the workflow state machine."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.backends.gemini import GeminiBackend
from agent_pump.models.project import Project
from agent_pump.orchestrator.workflow import ProjectWorkflow


class TestProjectWorkflow:
    """Tests for the ProjectWorkflow state machine."""

    @pytest.fixture
    def project(self, sample_project_path):
        """Create a test project."""
        return Project.from_path(sample_project_path)

    @pytest.fixture
    def workflow(self, project):
        """Create a test workflow."""
        return ProjectWorkflow(project=project)

    def test_initial_state(self, workflow):
        """Test that workflow starts in idle state."""
        assert workflow.state == "idle"

    def test_start_transition(self, workflow):
        """Test transitioning from idle to planning."""
        workflow.start()
        assert workflow.state == "planning"

    def test_planning_to_implementing(self, workflow):
        """Test transitioning from planning to implementing."""
        workflow.start()
        workflow.planning_complete()
        assert workflow.state == "implementing"

    def test_implementing_to_verifying(self, workflow):
        """Test transitioning from implementing to verifying."""
        workflow.start()
        workflow.planning_complete()
        workflow.implementing_complete()
        assert workflow.state == "verifying"

    def test_verifying_to_brainstorming(self, workflow):
        """Test transitioning from verifying to brainstorming."""
        workflow.start()
        workflow.planning_complete()
        workflow.implementing_complete()
        workflow.verifying_complete()
        assert workflow.state == "brainstorming"

    def test_brainstorming_to_committing(self, workflow):
        """Test transitioning from brainstorming to committing."""
        workflow.start()
        workflow.planning_complete()
        workflow.implementing_complete()
        workflow.verifying_complete()
        workflow.brainstorming_complete()
        assert workflow.state == "committing"

    def test_full_cycle(self, workflow):
        """Test a full workflow cycle back to planning."""
        workflow.start()
        workflow.planning_complete()
        workflow.implementing_complete()
        workflow.verifying_complete()
        workflow.brainstorming_complete()
        workflow.committing_complete()
        assert workflow.state == "planning"

    def test_error_recovery(self, workflow):
        """Test error state and recovery."""
        workflow.start()
        workflow.planning_failed()
        assert workflow.state == "error"

        workflow.reset()
        assert workflow.state == "idle"

    @pytest.mark.asyncio
    async def test_cancel_preserves_state(self, workflow):
        """Test that cancel stops execution but preserves state."""
        workflow.start()
        workflow.planning_complete()
        assert workflow.state == "implementing"

        # We can't easily test the "stopping" of the loop here without running it,
        # but we can verify that cancel() doesn't reset the state
        workflow.cancel()
        assert workflow.state == "implementing"

    def test_pause_workflow(self, workflow):
        """Test that pause_workflow sets status to PAUSED but preserves state."""
        from agent_pump.models.project import ProjectStatus

        workflow.start()
        workflow.planning_complete()
        assert workflow.state == "implementing"
        assert workflow.project.status == ProjectStatus.IMPLEMENTING

        workflow.pause_workflow()
        assert workflow.state == "implementing"
        assert workflow.project.status == ProjectStatus.PAUSED

    def test_state_persistence_pauses_on_load(self, project):
        """Test that active state is saved and loaded as PAUSED."""
        from agent_pump.models.project import ProjectStatus

        # Create first workflow and advance state
        workflow = ProjectWorkflow(project=project)
        workflow.start()
        workflow.planning_complete()
        assert workflow.state == "implementing"
        assert workflow.project.status == ProjectStatus.IMPLEMENTING

        # Create second workflow instance for same project
        workflow2 = ProjectWorkflow(project=project)
        # Should auto-load the state
        assert workflow2.state == "implementing"
        # BUT project status should be PAUSED for UI/timer purposes
        assert workflow2.project.status == ProjectStatus.PAUSED
        assert workflow2.workflow_state.current_state == "implementing"

    def test_state_persistence(self, project):
        """Test that state is saved and loaded correctly."""
        # Create first workflow and advance state
        workflow = ProjectWorkflow(project=project)
        workflow.start()
        workflow.planning_complete()
        assert workflow.state == "implementing"

        # Create second workflow instance for same project
        workflow2 = ProjectWorkflow(project=project)
        # Should auto-load the state
        assert workflow2.state == "implementing"
        assert workflow2.workflow_state.current_state == "implementing"

    def test_custom_workflow_definition(self, project):
        """Test using a custom workflow definition."""
        from agent_pump.orchestrator.workflow_definition import WorkflowDefinition, WorkflowPhase

        custom_def = WorkflowDefinition(
            name="custom",
            initial_state="init",
            phases=[
                WorkflowPhase(name="phase1", on_success="phase2"),
                WorkflowPhase(name="phase2", on_success="completed"),
            ],
        )

        workflow = ProjectWorkflow(project=project, workflow_def=custom_def)

        # Verify initial state matches custom def
        # Ensure we force reset state for this test since project path is shared per fixture
        workflow.workflow_state.current_state = "init"
        workflow.machine.set_state("init")

        assert workflow.state == "init"
        assert "phase1" in workflow.machine.states
        assert "phase2" in workflow.machine.states

        # Test transition
        workflow.start()
        assert workflow.state == "phase1"

        # Trigger dynamic transition method
        workflow.phase1_complete()  # type: ignore
        assert workflow.state == "phase2"

    def test_state_change_callback(self, project):
        """Test that state change callback is called."""
        callback = MagicMock()
        workflow = ProjectWorkflow(
            project=project,
            on_state_change=callback,
        )

        workflow.start()
        callback.assert_called_with("idle", "planning")

    @pytest.mark.asyncio
    async def test_run_loop_execution(self, workflow):
        """Test that run loop executes phases including verifying."""
        # Ensure prompt files exist for all phases
        states_dir = workflow.project.path / ".agent-pump" / "states"
        states_dir.mkdir(parents=True, exist_ok=True)
        for phase in ["planning", "implementing", "verifying", "brainstorming", "committing"]:
            (states_dir / f"{phase}.md").write_text(f"Prompt for {phase}", encoding="utf-8")

        # Mock run_phase to return True (success)
        workflow.run_phase = AsyncMock(return_value=True)

        # Set up a side effect to stop the loop after one full cycle
        # We can't easily stop the loop from inside run_phase without cancelling
        # So we'll let it run a bit and then cancel

        task = asyncio.create_task(workflow.run(max_iterations=1))

        # Give it enough time to run through one cycle (all phases mocked)
        await asyncio.sleep(0.1)

        workflow.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Verify calls
        calls = workflow.run_phase.call_args_list
        phase_names = [c.args[1] for c in calls]

        assert "planning" in phase_names
        assert "implementing" in phase_names
        assert "verifying" in phase_names
        assert "brainstorming" in phase_names
        assert "committing" in phase_names

    @pytest.mark.asyncio
    async def test_auto_pick_roadmap_item(self, tmp_path):
        """Test that planning phase auto-picks the first roadmap item if TASK_NAME is missing."""
        import textwrap
        from unittest.mock import patch

        project_dir = tmp_path / "test_project_auto_pick"
        project_dir.mkdir()

        # Create a ROADMAP.md
        roadmap_path = project_dir / "ROADMAP.md"
        roadmap_path.write_text(
            textwrap.dedent("""\
            # Roadmap

            ## Future Enhancements

            ### 🔴 Next Task
            Description

            **Acceptance Criteria:**
            - Done
        """),
            encoding="utf-8",
        )

        project = Project.from_path(project_dir)
        workflow = ProjectWorkflow(project=project)
        workflow.state = "planning"

        # Mock run_phase to avoid calling real backend
        workflow.run_phase = AsyncMock(return_value=True)
        # Mock build_prompt to verify arguments
        with patch(
            "agent_pump.orchestrator.prompt_loader.PromptLoader.build_prompt",
            return_value="Mocked Prompt",
        ) as mock_build:
            # Run one iteration of the loop
            # We'll cancel it immediately after one cycle
            task = asyncio.create_task(workflow.run(max_iterations=1))
            await asyncio.sleep(0.1)
            workflow.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Verify it picked "Next Task"
            assert workflow.project.current_feature == "Next Task"
            assert (project_dir / "TASK_NAME").read_text() == "Next Task"

            # Verify build_prompt was called.
            # Unlike the old test, we don't necessarily pass the feature request as a direct arg
            # to build_prompt, but rather it's in the context or read from file.
            # But let's check if it was called at all.
            mock_build.assert_called()


class TestGeminiBackend:
    """Tests for the GeminiBackend."""

    def test_name(self):
        """Test backend name."""
        backend = GeminiBackend()
        assert backend.name == "Gemini CLI"

    def test_command(self, backend=None):
        """Test backend command."""
        backend = GeminiBackend()
        assert backend.command == "gemini"


class TestMinimumExecutionTime:
    """Tests for minimum execution time enforcement."""

    @pytest.fixture
    def project(self, tmp_path):
        """Create a test project."""
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        return Project.from_path(project_dir)

    @pytest.mark.asyncio
    async def test_run_phase_fails_if_too_fast(self, project):
        """Test that run_phase fails if backend returns too quickly."""
        project.min_execution_time_seconds = 1.0
        workflow = ProjectWorkflow(project=project)

        # Mock backend that returns immediately
        mock_backend = MagicMock()
        mock_backend.run = MagicMock()

        async def fast_output(*args, **kwargs):
            yield "Some output"

        mock_backend.run.return_value = fast_output()
        workflow.backend = mock_backend

        success = await workflow.run_phase("prompt", "test_phase")
        assert not success

    @pytest.mark.asyncio
    async def test_run_phase_succeeds_if_min_time_is_zero(self, project):
        """Test that run_phase succeeds if min_execution_time_seconds is 0."""
        project.min_execution_time_seconds = 0
        workflow = ProjectWorkflow(project=project)

        # Mock backend that returns immediately
        mock_backend = MagicMock()
        mock_backend.run = MagicMock()

        async def fast_output(*args, **kwargs):
            yield "Some output"

        mock_backend.run.return_value = fast_output()
        workflow.backend = mock_backend

        success = await workflow.run_phase("prompt", "test_phase")
        assert success
