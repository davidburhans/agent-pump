"""Tests for cost tracking service."""

from pathlib import Path

import pytest

from agent_pump.models.cost_tracking import (
    BudgetAction,
    BudgetConfig,
    BudgetPeriod,
)
from agent_pump.models.workspace import Workspace
from agent_pump.services.cost_tracking_service import CostTrackingService


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Create a temporary workspace for testing."""
    workspace = Workspace(name="test_cost_workspace")
    # Mock the costs file path to use a temp location
    costs_file = tmp_path / "test_costs.json"
    monkeypatch.setattr(CostTrackingService, "_get_costs_file_path", lambda self: costs_file)
    return workspace


class TestCostTrackingService:
    """Tests for CostTrackingService."""

    def test_service_initialization(self, temp_workspace):
        """Test service initialization."""
        service = CostTrackingService(temp_workspace)
        assert service.workspace == temp_workspace
        assert service._cost_records == []
        assert service._budget_config is not None

    def test_record_invocation(self, temp_workspace):
        """Test recording a backend invocation."""
        service = CostTrackingService(temp_workspace)

        record = service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            model="gemini-2.5-flash",
            input_tokens=1000,
            output_tokens=500,
        )

        assert record.project_path == Path("/project1")
        assert record.phase == "planning"
        assert record.backend_name == "gemini"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.cost_usd > 0
        assert len(service._cost_records) == 1

    def test_get_project_costs(self, temp_workspace):
        """Test getting costs for a specific project."""
        service = CostTrackingService(temp_workspace)

        # Record costs for multiple projects
        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )
        service.record_invocation(
            project_path=Path("/project1"),
            phase="implementing",
            backend_name="gemini",
            input_tokens=2000,
            output_tokens=1000,
        )
        service.record_invocation(
            project_path=Path("/project2"),
            phase="planning",
            backend_name="claude",
            input_tokens=3000,
            output_tokens=1500,
        )

        project1_costs = service.get_project_costs(Path("/project1"))
        assert project1_costs.record_count == 2
        assert project1_costs.total_cost > 0

        project2_costs = service.get_project_costs(Path("/project2"))
        assert project2_costs.record_count == 1

    def test_get_workspace_costs(self, temp_workspace):
        """Test getting costs for entire workspace."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )
        service.record_invocation(
            project_path=Path("/project2"),
            phase="planning",
            backend_name="claude",
            input_tokens=3000,
            output_tokens=1500,
        )

        workspace_costs = service.get_workspace_costs()
        assert workspace_costs.record_count == 2
        assert workspace_costs.total_cost > 0

    def test_check_budget_not_exceeded(self, temp_workspace):
        """Test budget check when not exceeded."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=10.0,
        )
        service = CostTrackingService(temp_workspace)

        # Record small cost
        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        is_exceeded, period = service.check_budget()
        assert not is_exceeded
        assert period is None

    def test_check_budget_exceeded(self, temp_workspace):
        """Test budget check when exceeded."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,  # Very low limit
            action_on_exceeded=BudgetAction.PAUSE,
        )
        service = CostTrackingService(temp_workspace)

        # Record cost that exceeds budget
        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=10000,
            output_tokens=5000,
        )

        is_exceeded, period = service.check_budget()
        assert is_exceeded
        assert period == BudgetPeriod.DAILY

    def test_check_budget_disabled(self, temp_workspace):
        """Test budget check when disabled."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=False,
            daily_limit=0.001,
        )
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=10000,
            output_tokens=5000,
        )

        is_exceeded, period = service.check_budget()
        assert not is_exceeded

    def test_get_period_costs(self, temp_workspace):
        """Test getting costs for specific time periods."""
        service = CostTrackingService(temp_workspace)

        # Record costs
        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        daily_costs = service.get_period_costs(BudgetPeriod.DAILY)
        assert daily_costs.total_cost > 0
        assert daily_costs.record_count >= 1

    def test_update_budget_config(self, temp_workspace):
        """Test updating budget configuration."""
        service = CostTrackingService(temp_workspace)

        new_config = BudgetConfig(
            enabled=True,
            daily_limit=50.0,
            weekly_limit=200.0,
            action_on_exceeded=BudgetAction.WARN,
        )

        service.update_budget_config(new_config)
        assert service._budget_config.enabled is True
        assert service._budget_config.daily_limit == 50.0
        assert service._budget_config.weekly_limit == 200.0
        assert service._budget_config.action_on_exceeded == BudgetAction.WARN

    def test_reset_costs_for_project(self, temp_workspace):
        """Test resetting costs for a specific project."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )
        service.record_invocation(
            project_path=Path("/project2"),
            phase="planning",
            backend_name="gemini",
            input_tokens=2000,
            output_tokens=1000,
        )

        service.reset_costs_for_project(Path("/project1"))

        project1_costs = service.get_project_costs(Path("/project1"))
        assert project1_costs.record_count == 0
        assert project1_costs.total_cost == 0.0

        # Project2 should still have costs
        project2_costs = service.get_project_costs(Path("/project2"))
        assert project2_costs.record_count == 1

    def test_reset_all_costs(self, temp_workspace):
        """Test resetting all costs."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        service.reset_all_costs()

        workspace_costs = service.get_workspace_costs()
        assert workspace_costs.record_count == 0
        assert workspace_costs.total_cost == 0.0

    def test_export_costs_json(self, temp_workspace):
        """Test exporting costs to JSON."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        json_data = service.export_costs(format="json")
        assert "project1" in json_data or "gemini" in json_data
        assert "cost_usd" in json_data

    def test_export_costs_csv(self, temp_workspace):
        """Test exporting costs to CSV."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        csv_data = service.export_costs(format="csv")
        assert "project_path" in csv_data
        assert "cost_usd" in csv_data
        assert "gemini" in csv_data

    def test_get_cost_breakdown_by_phase(self, temp_workspace):
        """Test getting cost breakdown by phase."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )
        service.record_invocation(
            project_path=Path("/project1"),
            phase="implementing",
            backend_name="gemini",
            input_tokens=2000,
            output_tokens=1000,
        )

        breakdown = service.get_cost_breakdown_by_phase()
        assert "planning" in breakdown
        assert "implementing" in breakdown
        assert breakdown["planning"].record_count == 1
        assert breakdown["implementing"].record_count == 1

    def test_get_cost_breakdown_by_backend(self, temp_workspace):
        """Test getting cost breakdown by backend."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )
        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=2000,
            output_tokens=1000,
        )

        breakdown = service.get_cost_breakdown_by_backend()
        assert "gemini" in breakdown
        assert "claude" in breakdown

    def test_should_pause_on_budget_exceeded(self, temp_workspace):
        """Test should_pause_on_budget when exceeded with PAUSE action."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,
            action_on_exceeded=BudgetAction.PAUSE,
        )
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=10000,
            output_tokens=5000,
        )

        assert service.should_pause_on_budget() is True

    def test_should_pause_on_budget_warn(self, temp_workspace):
        """Test should_pause_on_budget when exceeded with WARN action."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,
            action_on_exceeded=BudgetAction.WARN,
        )
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=10000,
            output_tokens=5000,
        )

        # Should not pause when action is WARN
        assert service.should_pause_on_budget() is False

    def test_save_and_load_costs(self, tmp_path, temp_workspace):
        """Test saving and loading costs from disk."""
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        # Save costs
        service.save_costs()

        # Create new service and load costs
        new_service = CostTrackingService(temp_workspace)
        new_service.load_costs()

        costs = new_service.get_workspace_costs()
        assert costs.record_count == 1

    def test_get_budget_status(self, temp_workspace):
        """Test getting budget status."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=10.0,
            weekly_limit=50.0,
            monthly_limit=200.0,
        )
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
        )

        status = service.get_budget_status()
        assert status["enabled"] is True
        assert status["daily_limit"] == 10.0
        assert status["daily_spent"] > 0
        assert status["daily_remaining"] < 10.0


class TestCostTrackingServicePersistence:
    """Tests for cost tracking persistence."""

    def test_costs_file_path(self, tmp_path):
        """Test that costs file path is correct."""
        workspace = Workspace(name="test_workspace")
        service = CostTrackingService(workspace)

        expected_path = Path.home() / ".config" / "agent-pump" / "costs" / "test_workspace.json"
        assert service._get_costs_file_path() == expected_path

    def test_load_costs_file_not_exists(self, temp_workspace):
        """Test loading when costs file doesn't exist."""
        service = CostTrackingService(temp_workspace)

        # Should not raise an error
        service.load_costs()

        assert service._cost_records == []


class TestCostTrackingServiceEdgeCases:
    """Tests for edge cases."""

    def test_record_invocation_zero_tokens(self, temp_workspace):
        """Test recording invocation with zero tokens."""
        service = CostTrackingService(temp_workspace)

        record = service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="gemini",
            input_tokens=0,
            output_tokens=0,
        )

        assert record.cost_usd == 0.0
        assert record.total_tokens == 0

    def test_check_budget_no_limits_set(self, temp_workspace):
        """Test budget check when no limits are set."""
        temp_workspace.budget_config = BudgetConfig(enabled=True)
        service = CostTrackingService(temp_workspace)

        service.record_invocation(
            project_path=Path("/project1"),
            phase="planning",
            backend_name="claude",
            input_tokens=100000,
            output_tokens=50000,
        )

        # Should not be exceeded since no limits set
        is_exceeded, period = service.check_budget()
        assert not is_exceeded

    def test_multiple_projects_budget_check(self, temp_workspace):
        """Test budget check with multiple projects."""
        temp_workspace.budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.5,  # Lower limit to ensure budget is exceeded
        )
        service = CostTrackingService(temp_workspace)

        # Add costs from multiple projects - each costs ~0.105, so 5 = ~0.525
        for i in range(10):  # More projects to exceed budget
            service.record_invocation(
                project_path=Path(f"/project{i}"),
                phase="planning",
                backend_name="claude",
                input_tokens=10000,
                output_tokens=5000,
            )

        is_exceeded, period = service.check_budget()
        assert is_exceeded
        assert period == BudgetPeriod.DAILY
