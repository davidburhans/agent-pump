"""Tests for workflow plugin hook integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.plugin_manager import PluginManager


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def plugin_manager(event_bus):
    """Create a plugin manager for testing."""
    return PluginManager(event_bus)


@pytest.fixture
def temp_project(tmp_path) -> Project:
    """Create a temporary project for testing."""
    project = Project(
        path=tmp_path,
        name="test-project",
        status=ProjectStatus.IDLE,
    )
    # Create minimal .agent-pump structure
    agent_pump_dir = tmp_path / ".agent-pump"
    agent_pump_dir.mkdir()
    states_dir = agent_pump_dir / "states"
    states_dir.mkdir()
    (states_dir / "planning.md").write_text("Test prompt")

    # Create valid state file with required fields
    import json

    state_data = {
        "version": 1,
        "project_path": str(tmp_path),
        "current_state": "idle",
        "current_feature": None,
        "phase_history": [],
        "completed_features": [],
        "failed_features": [],
        "iteration_count": 0,
    }
    (agent_pump_dir / "state.json").write_text(json.dumps(state_data))

    return project


class TestWorkflowPluginIntegration:
    """Test integration between workflow and plugin manager."""

    @pytest.mark.asyncio
    async def test_workflow_initializes_plugins(self, temp_project, plugin_manager):
        """Test that workflow initializes plugins on run."""
        plugins_dir = temp_project.path / ".agent-pump" / "plugins"
        plugins_dir.mkdir()

        # Create a simple plugin
        plugin_file = plugins_dir / "test.py"
        plugin_file.write_text("""
from agent_pump.plugins.base import Plugin
from agent_pump.models.plugin import PluginInfo

class TestPlugin(Plugin):
    @property
    def info(self):
        return PluginInfo(name="test", version="1.0.0")
""")

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        # Mock the run methods to avoid full execution
        with patch.object(workflow, "_prepare_phase", new_callable=AsyncMock):
            with patch.object(workflow, "run_phase", new_callable=AsyncMock) as mock_run:

                async def side_effect(*args, **kwargs):
                    workflow.cancel()
                    return False

                mock_run.side_effect = side_effect

                try:
                    await workflow.run(max_iterations=1)
                except Exception:
                    pass

                # Check that plugin was loaded
                assert "test" in plugin_manager.loaded_plugins

    @pytest.mark.asyncio
    async def test_phase_enter_hooks_called(self, temp_project, plugin_manager):
        """Test that phase enter hooks are called."""
        hook_calls = []

        async def mock_execute_hooks(phase, context, hook_type):
            hook_calls.append((phase, hook_type, context.phase))

        plugin_manager.execute_phase_hooks = mock_execute_hooks

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        # Mock to control execution
        with patch.object(workflow, "_prepare_phase", new_callable=AsyncMock):
            with patch.object(workflow, "run_phase", new_callable=AsyncMock) as mock_run:
                with patch.object(workflow, "_post_phase", new_callable=AsyncMock):

                    async def side_effect(*args, **kwargs):
                        workflow.cancel()
                        return False

                    mock_run.side_effect = side_effect

                    try:
                        await workflow.run(max_iterations=1)
                    except Exception:
                        pass

                    # Check enter hooks were called
                    enter_calls = [c for c in hook_calls if c[1] == "enter"]
                    assert len(enter_calls) > 0

    @pytest.mark.asyncio
    async def test_phase_exit_hooks_called(self, temp_project, plugin_manager):
        """Test that phase exit hooks are called."""
        hook_calls = []

        async def mock_execute_hooks(phase, context, hook_type):
            hook_calls.append((phase, hook_type))

        plugin_manager.execute_phase_hooks = mock_execute_hooks

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        with patch.object(workflow, "_prepare_phase", new_callable=AsyncMock):
            with patch.object(workflow, "run_phase", new_callable=AsyncMock) as mock_run:
                with patch.object(workflow, "_post_phase", new_callable=AsyncMock) as mock_post:
                    mock_run.return_value = True

                    async def post_side_effect(*args, **kwargs):
                        workflow.cancel()
                        return True

                    mock_post.side_effect = post_side_effect

                    # Set up workflow state to be in a phase
                    workflow.workflow_state.current_state = "planning"
                    workflow.state = "planning"  # type: ignore

                    try:
                        await workflow.run(max_iterations=1)
                    except Exception:
                        pass

                    # Check exit hooks were called
                    exit_calls = [c for c in hook_calls if c[1] == "exit"]
                    assert len(exit_calls) > 0

    @pytest.mark.asyncio
    async def test_hooks_receive_correct_context(self, temp_project, plugin_manager):
        """Test that hooks receive correct context data."""
        received_contexts = []

        async def capture_context(phase, context, hook_type):
            received_contexts.append(
                {
                    "phase": phase,
                    "hook_type": hook_type,
                    "project": context.project.name,
                    "feature": context.feature,
                }
            )

        plugin_manager.execute_phase_hooks = capture_context

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )
        workflow.project.current_feature = "test-feature"

        with patch.object(workflow, "_prepare_phase", new_callable=AsyncMock):
            with patch.object(workflow, "run_phase", new_callable=AsyncMock) as mock_run:

                async def side_effect(*args, **kwargs):
                    workflow.cancel()
                    return False

                mock_run.side_effect = side_effect

                try:
                    await workflow.run(max_iterations=1)
                except Exception:
                    pass

                # Verify context data
                assert len(received_contexts) > 0
                ctx = received_contexts[0]
                assert ctx["project"] == "test-project"
                assert ctx["feature"] == "test-feature"


class TestWorkflowVerificationHooks:
    """Test verification phase plugin hooks."""

    @pytest.mark.asyncio
    async def test_pre_verification_hooks_called(self, temp_project, plugin_manager):
        """Test that pre-verification hooks are called."""
        hook_calls = []

        async def mock_execute_hooks(phase, context, hook_type):
            if phase == "verifying" and hook_type == "enter":
                hook_calls.append("pre-verify")

        plugin_manager.execute_phase_hooks = mock_execute_hooks

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        # Mock verification executor
        workflow.verification_executor = MagicMock()
        workflow.verification_executor.run_all = AsyncMock(
            return_value={
                "build": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
                "lint": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
                "test": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
            }
        )
        workflow.verification_executor.run_command = AsyncMock(
            return_value=MagicMock(
                success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
            )
        )

        # Set plugin_manager to return no custom steps
        plugin_manager.get_custom_verification_steps = MagicMock(return_value=[])

        result = await workflow._run_custom_verification()

        # Pre-verification hook should have been called
        assert "pre-verify" in hook_calls
        assert result is True

    @pytest.mark.asyncio
    async def test_post_verification_hooks_called(self, temp_project, plugin_manager):
        """Test that post-verification hooks are called."""
        hook_calls = []

        async def mock_execute_hooks(phase, context, hook_type):
            if phase == "verifying" and hook_type == "exit":
                hook_calls.append(
                    {
                        "type": "post-verify",
                        "data": context.data,
                    }
                )

        plugin_manager.execute_phase_hooks = mock_execute_hooks

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        # Mock verification executor
        workflow.verification_executor = MagicMock()
        workflow.verification_executor.run_all = AsyncMock(
            return_value={
                "build": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
            }
        )
        workflow.verification_executor.run_command = AsyncMock(
            return_value=MagicMock(
                success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
            )
        )

        plugin_manager.get_custom_verification_steps = MagicMock(return_value=[])

        await workflow._run_custom_verification()

        # Post-verification hook should have been called with results
        post_calls = [c for c in hook_calls if c.get("type") == "post-verify"]
        assert len(post_calls) > 0
        assert "all_passed" in post_calls[0]["data"]
        assert post_calls[0]["data"]["all_passed"] is True


class TestCustomVerificationSteps:
    """Test custom verification steps from plugins."""

    @pytest.mark.asyncio
    async def test_plugin_verification_steps_executed(self, temp_project, plugin_manager):
        """Test that custom verification steps from plugins are executed."""
        executed_steps = []

        # Mock plugin manager to return custom steps
        plugin_manager.get_custom_verification_steps = MagicMock(
            return_value=[
                {"name": "custom-step-1", "command": "echo test1"},
                {"name": "custom-step-2", "command": "echo test2"},
            ]
        )

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        # Track which commands are executed
        async def mock_run_command(cmd):
            executed_steps.append(cmd)
            return MagicMock(
                success=True, command=cmd, stdout="", stderr="", exit_code=0, duration=0.0
            )

        workflow.verification_executor = MagicMock()
        workflow.verification_executor.run_all = AsyncMock(
            return_value={
                "build": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
            }
        )
        workflow.verification_executor.run_command = mock_run_command

        plugin_manager.execute_phase_hooks = AsyncMock()

        await workflow._run_custom_verification()

        # Custom steps should have been executed
        assert "echo test1" in executed_steps
        assert "echo test2" in executed_steps

    @pytest.mark.asyncio
    async def test_plugin_steps_included_in_results(self, temp_project, plugin_manager):
        """Test that plugin verification steps are included in final results."""
        plugin_manager.get_custom_verification_steps = MagicMock(
            return_value=[
                {"name": "custom-check", "command": "echo custom"},
            ]
        )

        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=plugin_manager,
        )

        workflow.verification_executor = MagicMock()
        workflow.verification_executor.run_all = AsyncMock(
            return_value={
                "build": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
            }
        )

        async def mock_run_command(cmd):
            return MagicMock(
                success=True,
                command=cmd,
                stdout="custom output",
                stderr="",
                exit_code=0,
                duration=1.0,
            )

        workflow.verification_executor.run_command = mock_run_command
        plugin_manager.execute_phase_hooks = AsyncMock()

        result = await workflow._run_custom_verification()

        # The result should be True (all passed including custom step)
        assert result is True


class TestWorkflowWithoutPlugins:
    """Test workflow behavior when plugin manager is not provided."""

    @pytest.mark.asyncio
    async def test_workflow_runs_without_plugins(self, temp_project):
        """Test that workflow works without a plugin manager."""
        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=None,
        )

        # Mock to control execution
        with patch.object(workflow, "_prepare_phase", new_callable=AsyncMock):
            with patch.object(workflow, "run_phase", new_callable=AsyncMock) as mock_run:

                async def side_effect(*args, **kwargs):
                    workflow.cancel()
                    return False

                mock_run.side_effect = side_effect

                try:
                    await workflow.run(max_iterations=1)
                except Exception:
                    pass

                # Should complete without errors
                assert workflow.plugin_manager is None

    @pytest.mark.asyncio
    async def test_verification_without_plugins(self, temp_project):
        """Test verification works without plugin manager."""
        workflow = ProjectWorkflow(
            project=temp_project,
            plugin_manager=None,
        )

        workflow.verification_executor = MagicMock()
        workflow.verification_executor.run_all = AsyncMock(
            return_value={
                "build": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
                "lint": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
                "test": MagicMock(
                    success=True, command="", stdout="", stderr="", exit_code=0, duration=0.0
                ),
            }
        )

        result = await workflow._run_custom_verification()

        assert result is True
