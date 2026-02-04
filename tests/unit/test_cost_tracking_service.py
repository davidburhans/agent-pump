"""Unit tests for CostTrackingService."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.cost_tracking import (
    BudgetAction,
    BudgetConfig,
    BudgetPeriod,
    CostRecord,
    CostSummary,
)
from agent_pump.services.cost_tracking_service import CostTrackingService


@pytest.fixture
def mock_workspace():
    """Create a mock workspace for testing."""
    workspace = MagicMock()
    workspace.name = "test-workspace"
    workspace.budget_config = BudgetConfig()
    return workspace


@pytest.fixture
def temp_storage_path(tmp_path):
    """Create a temporary storage path."""
    return tmp_path / "costs"


@pytest.fixture
def cost_service(mock_workspace, temp_storage_path):
    """Create a CostTrackingService instance for testing."""
    with patch.object(CostTrackingService, "_load_costs"):
        service = CostTrackingService(mock_workspace)
        service._storage_path = temp_storage_path
        temp_storage_path.mkdir(parents=True, exist_ok=True)
        service._cost_records = []
        return service


class TestCostTrackingServiceInitialization:
    """Tests for service initialization."""

    def test_init_creates_storage_directory_on_save(self, mock_workspace, tmp_path):
        """Test that storage directory is created when saving."""
        storage_path = tmp_path / "costs"
        with patch.object(CostTrackingService, "_load_costs"):
            service = CostTrackingService(mock_workspace)
            service._storage_path = storage_path
            service._cost_records = []
            # Directory doesn't exist yet
            assert not storage_path.exists()
            # Trigger a save
            service.save_costs()
            # Now it should exist
            assert storage_path.exists()

    def test_init_loads_existing_costs(self, mock_workspace, tmp_path):
        """Test that initialization loads existing cost data."""
        storage_path = tmp_path / "costs"
        storage_path.mkdir(parents=True, exist_ok=True)

        # Create a cost file with test data
        cost_file = storage_path / f"{mock_workspace.name}.json"
        cost_data = {
            "version": 1,
            "workspace": mock_workspace.name,
            "budget_config": {"enabled": False},
            "records": [
                {
                    "timestamp": datetime.now().isoformat(),
                    "project_path": "/test/project",
                    "phase": "planning",
                    "backend_name": "gemini",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost_usd": 0.0005,
                }
            ],
        }
        import json

        cost_file.write_text(json.dumps(cost_data))

        # Create service - it should load the costs
        service = CostTrackingService(mock_workspace)
        service._storage_path = storage_path
        service._load_costs()

        assert len(service._cost_records) == 1
        assert service._cost_records[0].cost_usd == 0.0005


class TestRecordInvocation:
    """Tests for recording backend invocations."""

    def test_record_invocation_creates_record(self, cost_service):
        """Test that record_invocation creates a CostRecord."""
        project_path = Path("/test/project")

        record = cost_service.record_invocation(
            project_path=project_path,
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
            model="gemini-2.5-flash",
        )

        assert isinstance(record, CostRecord)
        assert record.project_path == project_path
        assert record.phase == "planning"
        assert record.backend_name == "gemini"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.cost_usd > 0

    def test_record_invocation_adds_to_records_list(self, cost_service):
        """Test that record_invocation adds to the internal records list."""
        project_path = Path("/test/project")

        initial_count = len(cost_service._cost_records)
        cost_service.record_invocation(
            project_path=project_path,
            phase="implementing",
            backend_name="claude",
            input_tokens=2000,
            output_tokens=1000,
        )

        assert len(cost_service._cost_records) == initial_count + 1

    def test_record_invocation_saves_to_disk(self, cost_service, temp_storage_path):
        """Test that record_invocation persists data to disk."""
        project_path = Path("/test/project")

        cost_service.record_invocation(
            project_path=project_path,
            phase="verifying",
            backend_name="qwen",
            input_tokens=500,
            output_tokens=200,
        )

        # Check that file was created
        cost_file = temp_storage_path / f"{cost_service.workspace.name}.json"
        assert cost_file.exists()


class TestGetProjectCosts:
    """Tests for getting project cost summaries."""

    def test_get_project_costs_returns_summary(self, cost_service):
        """Test that get_project_costs returns a CostSummary."""
        project_path = Path("/test/project")

        # Add some records
        cost_service._cost_records = [
            CostRecord(
                project_path=project_path,
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=project_path,
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
        ]

        summary = cost_service.get_project_costs(project_path)

        assert isinstance(summary, CostSummary)
        assert summary.total_cost == 0.0015
        assert summary.total_tokens == 4500
        assert summary.record_count == 2

    def test_get_project_costs_filters_by_project(self, cost_service):
        """Test that get_project_costs filters by project path."""
        project1 = Path("/test/project1")
        project2 = Path("/test/project2")

        cost_service._cost_records = [
            CostRecord(
                project_path=project1,
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=project2,
                phase="planning",
                backend_name="claude",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.015,
            ),
        ]

        summary = cost_service.get_project_costs(project1)

        assert summary.total_cost == 0.0005
        assert summary.record_count == 1


class TestGetWorkspaceCosts:
    """Tests for getting workspace cost summaries."""

    def test_get_workspace_costs_returns_all_records(self, cost_service):
        """Test that get_workspace_costs returns costs for all projects."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project2"),
                phase="planning",
                backend_name="claude",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.015,
            ),
        ]

        summary = cost_service.get_workspace_costs()

        assert summary.total_cost == 0.0155
        assert summary.record_count == 2


class TestGetPeriodCosts:
    """Tests for getting period-based costs."""

    def test_get_daily_period_costs(self, cost_service):
        """Test getting costs for the current day."""
        now = datetime.now()

        # Add a record from today
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]

        # Update timestamp to today
        cost_service._cost_records[0].timestamp = now

        period_costs = cost_service.get_period_costs(BudgetPeriod.DAILY)

        assert period_costs.period == BudgetPeriod.DAILY
        assert period_costs.total_cost == 0.0005
        assert period_costs.record_count == 1

    def test_get_weekly_period_costs(self, cost_service):
        """Test getting costs for the current week."""
        now = datetime.now()

        # Add records from this week and last week
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
        ]

        # Set both to today
        cost_service._cost_records[0].timestamp = now
        cost_service._cost_records[1].timestamp = now - timedelta(days=1)

        period_costs = cost_service.get_period_costs(BudgetPeriod.WEEKLY)

        assert period_costs.period == BudgetPeriod.WEEKLY
        assert period_costs.total_cost == 0.0015
        assert period_costs.record_count == 2

    def test_get_monthly_period_costs_filters_by_month(self, cost_service):
        """Test that monthly costs filter by current month."""
        now = datetime.now()

        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
        ]

        # One from this month, one from last month
        cost_service._cost_records[0].timestamp = now
        cost_service._cost_records[1].timestamp = now - timedelta(days=35)

        period_costs = cost_service.get_period_costs(BudgetPeriod.MONTHLY)

        assert period_costs.record_count == 1
        assert period_costs.total_cost == 0.0005


class TestCheckBudget:
    """Tests for budget checking."""

    def test_check_budget_not_exceeded(self, cost_service):
        """Test that check_budget returns False when under budget."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=10.0,
        )

        # Add a small cost
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        is_exceeded, period = cost_service.check_budget()

        assert is_exceeded is False
        assert period is None

    def test_check_budget_exceeded(self, cost_service):
        """Test that check_budget returns True when budget exceeded."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,  # Very low limit
        )

        # Add costs exceeding the limit
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=10000,
                output_tokens=5000,
                cost_usd=0.005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        is_exceeded, period = cost_service.check_budget()

        assert is_exceeded is True
        assert period == BudgetPeriod.DAILY

    def test_check_budget_disabled(self, cost_service):
        """Test that check_budget returns False when disabled."""
        cost_service._budget_config = BudgetConfig(enabled=False)

        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]

        is_exceeded, period = cost_service.check_budget()

        assert is_exceeded is False
        assert period is None


class TestShouldPauseOnBudget:
    """Tests for the should_pause_on_budget method."""

    def test_should_pause_when_budget_exceeded_and_action_pause(self, cost_service):
        """Test should_pause_on_budget returns True when budget exceeded and action is PAUSE."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,
            action_on_exceeded=BudgetAction.PAUSE,
        )

        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=10000,
                output_tokens=5000,
                cost_usd=0.005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        assert cost_service.should_pause_on_budget() is True

    def test_should_not_pause_when_action_warn(self, cost_service):
        """Test should_pause_on_budget returns False when action is WARN."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=0.001,
            action_on_exceeded=BudgetAction.WARN,
        )

        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=10000,
                output_tokens=5000,
                cost_usd=0.005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        assert cost_service.should_pause_on_budget() is False

    def test_should_not_pause_when_budget_not_exceeded(self, cost_service):
        """Test should_pause_on_budget returns False when budget not exceeded."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=10.0,
            action_on_exceeded=BudgetAction.PAUSE,
        )

        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        assert cost_service.should_pause_on_budget() is False


class TestBudgetConfig:
    """Tests for budget configuration management."""

    def test_update_budget_config(self, cost_service):
        """Test updating budget configuration."""
        new_config = BudgetConfig(
            enabled=True,
            daily_limit=5.0,
            weekly_limit=25.0,
        )

        cost_service.update_budget_config(new_config)

        assert cost_service._budget_config.enabled is True
        assert cost_service._budget_config.daily_limit == 5.0
        assert cost_service._budget_config.weekly_limit == 25.0

    def test_get_budget_status(self, cost_service):
        """Test getting budget status."""
        cost_service._budget_config = BudgetConfig(
            enabled=True,
            daily_limit=10.0,
            weekly_limit=50.0,
            monthly_limit=200.0,
        )

        # Add some costs
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]
        cost_service._cost_records[0].timestamp = datetime.now()

        status = cost_service.get_budget_status()

        assert status["enabled"] is True
        assert status["daily_limit"] == 10.0
        assert status["daily_spent"] == 0.0005
        assert status["daily_remaining"] == 9.9995
        assert status["daily_exceeded"] is False


class TestResetCosts:
    """Tests for resetting cost records."""

    def test_reset_costs_for_project(self, cost_service):
        """Test resetting costs for a specific project."""
        project1 = Path("/test/project1")
        project2 = Path("/test/project2")

        cost_service._cost_records = [
            CostRecord(
                project_path=project1,
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=project2,
                phase="planning",
                backend_name="claude",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.015,
            ),
        ]

        cost_service.reset_costs_for_project(project1)

        assert len(cost_service._cost_records) == 1
        assert cost_service._cost_records[0].project_path == project2

    def test_reset_all_costs(self, cost_service):
        """Test resetting all cost records."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project2"),
                phase="planning",
                backend_name="claude",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.015,
            ),
        ]

        cost_service.reset_all_costs()

        assert len(cost_service._cost_records) == 0


class TestExportCosts:
    """Tests for exporting cost data."""

    def test_export_costs_json(self, cost_service):
        """Test exporting costs in JSON format."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]

        export = cost_service.export_costs(format="json")
        data = __import__("json").loads(export)

        assert data["workspace"] == cost_service.workspace.name
        assert data["total_records"] == 1
        assert len(data["records"]) == 1
        assert data["records"][0]["cost_usd"] == 0.0005

    def test_export_costs_csv(self, cost_service):
        """Test exporting costs in CSV format."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
        ]

        export = cost_service.export_costs(format="csv")
        lines = export.strip().split("\n")

        assert len(lines) == 2  # Header + 1 record
        assert "timestamp" in lines[0]
        assert "cost_usd" in lines[0]

    def test_export_costs_invalid_format(self, cost_service):
        """Test that invalid export format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            cost_service.export_costs(format="xml")


class TestCostBreakdown:
    """Tests for cost breakdown methods."""

    def test_get_cost_breakdown_by_phase(self, cost_service):
        """Test getting cost breakdown by phase."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
        ]

        breakdown = cost_service.get_cost_breakdown_by_phase()

        assert "planning" in breakdown
        assert "implementing" in breakdown
        assert breakdown["planning"].total_cost == 0.0005
        assert breakdown["implementing"].total_cost == 0.001

    def test_get_cost_breakdown_by_backend(self, cost_service):
        """Test getting cost breakdown by backend."""
        cost_service._cost_records = [
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/test/project"),
                phase="planning",
                backend_name="claude",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.015,
            ),
        ]

        breakdown = cost_service.get_cost_breakdown_by_backend()

        assert "gemini" in breakdown
        assert "claude" in breakdown
        assert breakdown["gemini"].total_cost == 0.0005
        assert breakdown["claude"].total_cost == 0.015


class TestEstimateCost:
    """Tests for the estimate_cost static method."""

    def test_estimate_cost_gemini(self):
        """Test estimating cost for Gemini."""
        cost = CostTrackingService.estimate_cost("gemini", "gemini-2.5-flash", 1000, 500)

        assert cost > 0
        # Should be approximately (1000 * 0.000125 + 500 * 0.000375) / 1000
        assert cost == pytest.approx(0.000313, rel=1e-6)

    def test_estimate_cost_claude(self):
        """Test estimating cost for Claude."""
        cost = CostTrackingService.estimate_cost("claude", "claude-3.5-sonnet", 1000, 500)

        assert cost > 0
        # Should be approximately (1000 * 0.003 + 500 * 0.015) / 1000
        assert cost == pytest.approx(0.0105, rel=1e-6)

    def test_estimate_cost_opencode(self):
        """Test estimating cost for OpenCode (should be free)."""
        cost = CostTrackingService.estimate_cost("opencode", None, 1000, 500)

        assert cost == 0.0
