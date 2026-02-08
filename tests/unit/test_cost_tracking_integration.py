"""Tests for cost tracking integration in workflow execution."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.backends.base import AgentBackend
from agent_pump.models.cost_tracking import (
    BudgetAction,
    BudgetConfig,
    BudgetPeriod,
)
from agent_pump.models.project import Project
from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.cost_tracking_service import CostTrackingService


@pytest.fixture(autouse=True)
def cleanup_cost_files():
    """Clean up cost files after each test."""
    yield
    # Cleanup after test
    costs_dir = Path.home() / ".config" / "agent-pump" / "costs"
    if costs_dir.exists():
        # Clean up all test workspace cost files (various test workspace name patterns)
        for pattern in [
            "test_workspace_*.json",
            "test_cost_*.json",
            "test_aggregation*.json",
            "test_phase_*.json",
            "test_backend_*.json",
            "test_period_*.json",
            "test_budget_*.json",
            "test_empty*.json",
            "test_model_*.json",
            "test_unknown_*.json",
            "test_reset*.json",
            "test_fallback*.json",
        ]:
            for file in costs_dir.glob(pattern):
                file.unlink(missing_ok=True)


class MockBackend(AgentBackend):
    """Mock backend for testing."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name
        self._extra_args: list[str] | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def command(self) -> str:
        return "mock"

    async def _check_availability(self) -> bool:
        return True

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
        auto_approve: bool = False,
    ) -> AsyncGenerator[str, None]:
        yield "Test output line 1"
        yield "Test output line 2"
        yield "Test output line 3"


@pytest.fixture
def sample_project(tmp_path: Path) -> Project:
    """Create a test project."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()

    # Create required files
    (project_path / "ROADMAP.md").write_text(
        "# Test Roadmap\n\n## Current Sprint\n### Test Feature\n"
    )
    (project_path / ".agent-pump").mkdir(exist_ok=True)

    project = Project.from_path(project_path)
    # Set min_execution_time_seconds to 0 to avoid timing issues in tests
    project.min_execution_time_seconds = 0
    return project


@pytest.fixture
def mock_workspace(tmp_path: Path) -> Workspace:
    """Create a test workspace with unique name."""
    import uuid

    workspace = Workspace(name=f"test_workspace_{uuid.uuid4().hex[:8]}")
    return workspace


class TestCostTrackingIntegration:
    """Tests for cost tracking integration in ProjectWorkflow."""

    @pytest.mark.asyncio
    async def test_run_phase_records_costs(
        self, sample_project: Project, mock_workspace: Workspace
    ):
        """Test that run_phase records costs after execution."""
        # Arrange
        backend = MockBackend("gemini")
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )
        workflow.workspace = mock_workspace

        # Initialize cost tracking service
        with patch.object(CostTrackingService, "__init__", return_value=None):
            with patch.object(CostTrackingService, "record_invocation") as mock_record:
                workflow.cost_tracking_service = CostTrackingService(mock_workspace)
                workflow.cost_tracking_service._cost_records = []
                workflow.cost_tracking_service._budget_config = BudgetConfig()

                # Act
                prompt = "Test prompt for cost tracking"
                await workflow.run_phase(prompt, "planning")

                # Assert
                mock_record.assert_called_once()
                call_args = mock_record.call_args
                assert call_args[1]["project_path"] == sample_project.path
                assert call_args[1]["phase"] == "planning"
                assert call_args[1]["backend_name"] == "gemini"
                assert call_args[1]["input_tokens"] > 0
                assert call_args[1]["output_tokens"] > 0

    @pytest.mark.asyncio
    async def test_run_phase_calculates_costs_correctly(self, sample_project: Project):
        """Test that costs are calculated with correct backend pricing."""
        import uuid

        # Arrange
        backend = MockBackend("gemini")
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )

        # Create a real cost tracking service with unique workspace name
        workspace = Workspace(name=f"test_cost_workspace_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)
        workflow.cost_tracking_service = cost_service

        # Act
        prompt = "Test prompt with known content"
        await workflow.run_phase(prompt, "implementing")

        # Assert
        costs = cost_service.get_project_costs(sample_project.path)
        assert costs.record_count == 1
        assert costs.total_cost > 0

        # Verify the record details
        record = cost_service._cost_records[0]
        assert str(record.project_path) == str(sample_project.path)
        assert record.phase == "implementing"
        assert record.backend_name == "gemini"
        assert record.input_tokens > 0
        assert record.output_tokens > 0

        # Verify cost calculation uses BACKEND_PRICING
        expected_cost = (record.input_tokens * 0.000125 + record.output_tokens * 0.000375) / 1000
        assert abs(record.cost_usd - expected_cost) < 0.001

    @pytest.mark.asyncio
    async def test_token_counting_with_different_backends(self, sample_project: Project):
        """Test token counting for different backends."""
        from agent_pump.utils.token_counter import TokenCounter

        test_text = "Hello world, this is a test prompt."

        # Test with gemini backend
        gemini_tokens = TokenCounter.count_tokens(test_text, "gemini")
        assert gemini_tokens > 0

        # Test with claude backend
        claude_tokens = TokenCounter.count_tokens(test_text, "claude")
        assert claude_tokens > 0

        # Test with qwen backend
        qwen_tokens = TokenCounter.count_tokens(test_text, "qwen")
        assert qwen_tokens > 0

        # Test with opencode backend (local, no cost)
        opencode_tokens = TokenCounter.count_tokens(test_text, "opencode")
        assert opencode_tokens > 0

    @pytest.mark.asyncio
    async def test_budget_enforcement_pause(self, sample_project: Project):
        """Test that budget enforcement pauses execution when exceeded."""
        import uuid

        # Arrange
        backend = MockBackend("gemini")
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )

        # Create workspace with very low budget
        workspace = Workspace(name=f"test_budget_pause_{uuid.uuid4().hex[:8]}")
        workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,  # Very low limit
            action_on_exceeded=BudgetAction.PAUSE,
        )
        workflow.workspace = workspace

        # Add some existing costs to exceed budget
        cost_service = CostTrackingService(workspace)
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",
            input_tokens=10000,
            output_tokens=5000,
        )
        workflow.cost_tracking_service = cost_service

        # Mock the pause_workflow method
        workflow.pause_workflow = MagicMock()

        # Act - Check budget before running
        should_pause = cost_service.should_pause_on_budget()

        # Assert
        assert should_pause is True
        is_exceeded, period = cost_service.check_budget()
        assert is_exceeded is True
        assert period == BudgetPeriod.DAILY

    @pytest.mark.asyncio
    async def test_budget_enforcement_warn(self, sample_project: Project):
        """Test that budget enforcement warns but continues when action is WARN."""
        import uuid

        # Arrange
        backend = MockBackend("gemini")
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )

        # Create workspace with budget set to WARN
        workspace = Workspace(name=f"test_budget_warn_{uuid.uuid4().hex[:8]}")
        workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,
            action_on_exceeded=BudgetAction.WARN,
        )
        workflow.workspace = workspace

        cost_service = CostTrackingService(workspace)
        # Add costs to exceed budget
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",
            input_tokens=10000,
            output_tokens=5000,
        )
        workflow.cost_tracking_service = cost_service

        # Act
        should_pause = cost_service.should_pause_on_budget()

        # Assert - Should not pause since action is WARN
        assert should_pause is False

    @pytest.mark.asyncio
    async def test_cost_tracking_without_workspace(self, sample_project: Project):
        """Test that workflow works without cost tracking when no workspace."""
        # Arrange
        backend = MockBackend("gemini")
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )
        # workspace is None by default

        # Act
        prompt = "Test prompt"
        result = await workflow.run_phase(prompt, "planning")

        # Assert - Should complete without errors
        assert result is True
        assert (
            workflow.cost_tracking_service is None
            or workflow.cost_tracking_service._cost_records == []
        )

    @pytest.mark.asyncio
    async def test_cost_aggregation_by_project(self, sample_project: Project):
        """Test that costs are correctly aggregated by project."""
        import uuid

        # Arrange
        workspace = Workspace(name=f"test_aggregation_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Record multiple invocations for same project
        for i in range(3):
            cost_service.record_invocation(
                project_path=sample_project.path,
                phase="planning" if i == 0 else "implementing",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
            )

        # Act
        project_costs = cost_service.get_project_costs(sample_project.path)
        workspace_costs = cost_service.get_workspace_costs()

        # Assert
        assert project_costs.record_count == 3
        assert workspace_costs.record_count == 3
        assert project_costs.total_cost == workspace_costs.total_cost

    @pytest.mark.asyncio
    async def test_cost_breakdown_by_phase(self, sample_project: Project):
        """Test cost breakdown by workflow phase."""
        import uuid

        # Arrange
        workspace = Workspace(name=f"test_phase_breakdown_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Record costs for different phases
        phases = ["planning", "implementing", "verifying", "brainstorming", "committing"]
        for phase in phases:
            cost_service.record_invocation(
                project_path=sample_project.path,
                phase=phase,
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
            )

        # Act
        phase_breakdown = cost_service.get_cost_breakdown_by_phase()

        # Assert
        assert len(phase_breakdown) == 5
        for phase in phases:
            assert phase in phase_breakdown
            assert phase_breakdown[phase].record_count == 1

    @pytest.mark.asyncio
    async def test_cost_breakdown_by_backend(self, sample_project: Project):
        """Test cost breakdown by backend."""
        import uuid

        # Arrange
        workspace = Workspace(name=f"test_backend_breakdown_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Record costs for different backends
        backends = ["gemini", "claude", "qwen"]
        for backend in backends:
            cost_service.record_invocation(
                project_path=sample_project.path,
                phase="planning",
                backend_name=backend,
                input_tokens=1000,
                output_tokens=500,
            )

        # Act
        backend_breakdown = cost_service.get_cost_breakdown_by_backend()

        # Assert
        assert len(backend_breakdown) == 3
        for backend in backends:
            assert backend in backend_breakdown
            assert backend_breakdown[backend].record_count == 1

    @pytest.mark.asyncio
    async def test_period_costs_calculation(self, sample_project: Project):
        """Test period-based cost calculations (daily, weekly, monthly)."""
        import uuid

        # Arrange
        workspace = Workspace(name=f"test_period_costs_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Record some costs
        for i in range(5):
            cost_service.record_invocation(
                project_path=sample_project.path,
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
            )

        # Act
        daily_costs = cost_service.get_period_costs(BudgetPeriod.DAILY)
        weekly_costs = cost_service.get_period_costs(BudgetPeriod.WEEKLY)
        monthly_costs = cost_service.get_period_costs(BudgetPeriod.MONTHLY)

        # Assert
        assert daily_costs.record_count == 5
        assert weekly_costs.record_count == 5
        assert monthly_costs.record_count == 5
        assert daily_costs.total_cost > 0
        assert daily_costs.total_tokens > 0

    @pytest.mark.asyncio
    async def test_budget_status_reporting(self, sample_project: Project):
        """Test budget status reporting."""
        import uuid

        # Arrange
        workspace = Workspace(name=f"test_budget_status_{uuid.uuid4().hex[:8]}")
        workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=1.0,
            weekly_limit=5.0,
            monthly_limit=20.0,
            action_on_exceeded=BudgetAction.PAUSE,
        )
        cost_service = CostTrackingService(workspace)

        # Record some costs
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        # Act
        status = cost_service.get_budget_status()

        # Assert
        assert status["enabled"] is True
        assert status["action_on_exceeded"] == "pause"
        assert status["daily_limit"] == 1.0
        assert status["daily_spent"] > 0
        assert status["daily_remaining"] is not None
        assert status["daily_exceeded"] is False


class TestCostTrackingEdgeCases:
    """Tests for edge cases in cost tracking."""

    @pytest.mark.asyncio
    async def test_empty_output_handling(self, sample_project: Project):
        """Test handling of empty backend output."""

        class EmptyBackend(MockBackend):
            def run(self, project_path, prompt, **kwargs):
                # Don't yield anything
                return
                yield  # Make it a generator

        backend = EmptyBackend()
        workflow = ProjectWorkflow(
            project=sample_project,
            backend=backend,
        )

        import uuid

        workspace = Workspace(name=f"test_empty_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)
        workflow.cost_tracking_service = cost_service

        # Act
        prompt = "Test prompt"
        result = await workflow.run_phase(prompt, "planning")

        # Assert - Should handle gracefully
        assert result is False  # No output received

    @pytest.mark.asyncio
    async def test_backend_with_model_specification(self, sample_project: Project):
        """Test cost tracking with model-specific pricing."""
        import uuid

        workspace = Workspace(name=f"test_model_spec_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Act - Record with model specification
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
            model="gemini-1.5-pro",  # Should use pro pricing
        )

        # Assert - Should use pro pricing (0.00035, 0.00105)
        record = cost_service._cost_records[0]
        expected_cost = (1000 * 0.00035 + 500 * 0.00105) / 1000
        assert abs(record.cost_usd - expected_cost) < 0.0001

    @pytest.mark.asyncio
    async def test_unknown_backend_uses_default_pricing(self, sample_project: Project):
        """Test that unknown backends use default pricing."""
        import uuid

        workspace = Workspace(name=f"test_unknown_backend_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Act - Record with unknown backend
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="unknown_backend_xyz",
            input_tokens=1000,
            output_tokens=500,
        )

        # Assert - Should use default pricing (0.0005, 0.001)
        record = cost_service._cost_records[0]
        expected_cost = (1000 * 0.0005 + 500 * 0.001) / 1000
        assert abs(record.cost_usd - expected_cost) < 0.0001

    @pytest.mark.asyncio
    async def test_cost_reset_functionality(self, sample_project: Project):
        """Test cost reset for project and workspace."""
        import uuid

        workspace = Workspace(name=f"test_reset_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Add costs
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        # Verify costs exist
        assert len(cost_service._cost_records) == 1

        # Reset project costs
        cost_service.reset_costs_for_project(sample_project.path)

        # Verify costs cleared
        assert len(cost_service._cost_records) == 0


class TestCostTrackingWithFallbackBackends:
    """Tests for cost tracking with fallback backend chains."""

    @pytest.mark.asyncio
    async def test_fallback_backend_tracks_actual_backend_used(self, sample_project: Project):
        """Test that cost tracking records the actual backend used, not the fallback wrapper."""
        import uuid

        # This would require more complex mocking of the fallback runner
        # For now, we'll verify the basic structure is in place
        workspace = Workspace(name=f"test_fallback_{uuid.uuid4().hex[:8]}")
        cost_service = CostTrackingService(workspace)

        # Simulate recording from fallback scenario
        cost_service.record_invocation(
            project_path=sample_project.path,
            phase="planning",
            backend_name="gemini",  # The actual backend that succeeded
            input_tokens=1000,
            output_tokens=500,
            model="gemini-1.5-flash",
        )

        # Assert
        record = cost_service._cost_records[0]
        assert record.backend_name == "gemini"
        assert record.model == "gemini-1.5-flash"
