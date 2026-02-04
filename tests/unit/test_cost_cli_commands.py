"""Tests for cost and budget CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from click.testing import CliRunner

from agent_pump.cli import main
from agent_pump.models.cost_tracking import BudgetAction, BudgetConfig, BudgetPeriod
from agent_pump.models.workspace import Workspace
from agent_pump.services.cost_tracking_service import CostTrackingService


@pytest.fixture
def cli_runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_workspace(tmp_path: Path):
    """Create a mock workspace."""
    workspace = Workspace(name="test_cli_workspace")
    return workspace


@pytest.fixture
def mock_cost_service(mock_workspace):
    """Create a mock cost tracking service with data."""
    service = CostTrackingService(mock_workspace)

    # Add some test data
    for i in range(5):
        service.record_invocation(
            project_path=Path(f"/test/project{i % 2}"),  # 2 projects
            phase=["planning", "implementing", "verifying"][i % 3],
            backend_name="gemini",
            input_tokens=1000 + i * 100,
            output_tokens=500 + i * 50,
            model="gemini-1.5-flash",
        )

    return service


class TestCostCLICommands:
    """Tests for cost-related CLI commands."""

    def test_cost_show_without_project(self, cli_runner, mock_cost_service):
        """Test cost show command without specifying a project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "get_workspace_costs") as mock_get_costs:
                mock_summary = MagicMock()
                mock_summary.total_cost = 0.05
                mock_summary.total_tokens = 7500
                mock_summary.record_count = 5
                mock_get_costs.return_value = mock_summary

                result = cli_runner.invoke(main, ["cost", "show"])

                assert result.exit_code == 0
                assert (
                    "Total Cost" in result.output
                    or "$0.05" in result.output
                    or "5 records" in result.output
                )

    def test_cost_show_with_project(self, cli_runner, mock_cost_service):
        """Test cost show command with specific project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "get_project_costs") as mock_get_costs:
                mock_summary = MagicMock()
                mock_summary.total_cost = 0.02
                mock_summary.total_tokens = 3000
                mock_summary.record_count = 2
                mock_get_costs.return_value = mock_summary

                result = cli_runner.invoke(main, ["cost", "show", "/test/project0"])

                assert result.exit_code == 0

    def test_cost_show_with_period_filter(self, cli_runner, mock_cost_service):
        """Test cost show command with period filter."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "get_period_costs") as mock_get_period:
                mock_period = MagicMock()
                mock_period.total_cost = 0.05
                mock_period.total_tokens = 7500
                mock_period.record_count = 5
                mock_get_period.return_value = mock_period

                result = cli_runner.invoke(main, ["cost", "show", "--period", "daily"])

                assert result.exit_code == 0

    def test_cost_export_json(self, cli_runner, mock_cost_service):
        """Test cost export command with JSON format."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "export_costs") as mock_export:
                mock_export.return_value = json.dumps(
                    {"workspace": "test", "total_records": 5, "records": []}
                )

                with cli_runner.isolated_filesystem():
                    result = cli_runner.invoke(
                        main, ["cost", "export", "--format", "json", "--output", "costs.json"]
                    )

                    assert result.exit_code == 0
                    assert "costs.json" in result.output or "exported" in result.output.lower()

    def test_cost_export_csv(self, cli_runner, mock_cost_service):
        """Test cost export command with CSV format."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "export_costs") as mock_export:
                mock_export.return_value = (
                    "timestamp,project_path,phase,cost_usd\n2024-01-01,/test,planning,0.01"
                )

                with cli_runner.isolated_filesystem():
                    result = cli_runner.invoke(
                        main, ["cost", "export", "--format", "csv", "--output", "costs.csv"]
                    )

                    assert result.exit_code == 0

    def test_cost_reset_project(self, cli_runner, mock_cost_service):
        """Test cost reset command for a specific project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "reset_costs_for_project") as mock_reset:
                result = cli_runner.invoke(main, ["cost", "reset", "/test/project0"])

                assert result.exit_code == 0

    def test_cost_reset_all(self, cli_runner, mock_cost_service):
        """Test cost reset command for all projects."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "reset_all_costs") as mock_reset:
                result = cli_runner.invoke(main, ["cost", "reset"])

                assert result.exit_code == 0

    def test_cost_breakdown_by_phase(self, cli_runner, mock_cost_service):
        """Test cost breakdown command grouped by phase."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "get_cost_breakdown_by_phase") as mock_breakdown:
                mock_breakdown.return_value = {
                    "planning": MagicMock(total_cost=0.02, record_count=2),
                    "implementing": MagicMock(total_cost=0.03, record_count=3),
                }

                result = cli_runner.invoke(main, ["cost", "breakdown", "--by", "phase"])

                assert result.exit_code == 0

    def test_cost_breakdown_by_backend(self, cli_runner, mock_cost_service):
        """Test cost breakdown command grouped by backend."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(
                CostTrackingService, "get_cost_breakdown_by_backend"
            ) as mock_breakdown:
                mock_breakdown.return_value = {
                    "gemini": MagicMock(total_cost=0.05, record_count=5),
                }

                result = cli_runner.invoke(main, ["cost", "breakdown", "--by", "backend"])

                assert result.exit_code == 0


class TestBudgetCLICommands:
    """Tests for budget-related CLI commands."""

    def test_budget_show(self, cli_runner, mock_cost_service):
        """Test budget show command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "get_budget_status") as mock_status:
                mock_status.return_value = {
                    "enabled": True,
                    "action_on_exceeded": "pause",
                    "daily_limit": 1.0,
                    "daily_spent": 0.05,
                    "daily_remaining": 0.95,
                    "daily_exceeded": False,
                }

                result = cli_runner.invoke(main, ["budget", "show"])

                assert result.exit_code == 0
                assert "enabled" in result.output.lower() or "pause" in result.output.lower()

    def test_budget_set_daily(self, cli_runner, mock_cost_service):
        """Test budget set command for daily limit."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(main, ["budget", "set", "--daily", "5.00"])

                assert result.exit_code == 0
                mock_update.assert_called_once()
                call_args = mock_update.call_args[0][0]
                assert isinstance(call_args, BudgetConfig)
                assert call_args.daily_limit == 5.0

    def test_budget_set_weekly(self, cli_runner, mock_cost_service):
        """Test budget set command for weekly limit."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(main, ["budget", "set", "--weekly", "20.00"])

                assert result.exit_code == 0

    def test_budget_set_monthly(self, cli_runner, mock_cost_service):
        """Test budget set command for monthly limit."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(main, ["budget", "set", "--monthly", "100.00"])

                assert result.exit_code == 0

    def test_budget_set_with_action(self, cli_runner, mock_cost_service):
        """Test budget set command with specific action."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(
                    main, ["budget", "set", "--daily", "5.00", "--action", "warn"]
                )

                assert result.exit_code == 0
                call_args = mock_update.call_args[0][0]
                assert call_args.action_on_exceeded == BudgetAction.WARN

    def test_budget_set_multiple_limits(self, cli_runner, mock_cost_service):
        """Test budget set command with multiple limits."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(
                    main,
                    [
                        "budget",
                        "set",
                        "--daily",
                        "5.00",
                        "--weekly",
                        "25.00",
                        "--monthly",
                        "100.00",
                    ],
                )

                assert result.exit_code == 0
                call_args = mock_update.call_args[0][0]
                assert call_args.daily_limit == 5.0
                assert call_args.weekly_limit == 25.0
                assert call_args.monthly_limit == 100.0

    def test_budget_enable(self, cli_runner, mock_cost_service):
        """Test budget enable command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace
            mock_cost_service.workspace.budget_config.enabled = False

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(main, ["budget", "enable"])

                assert result.exit_code == 0

    def test_budget_disable(self, cli_runner, mock_cost_service):
        """Test budget disable command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace
            mock_cost_service.workspace.budget_config.enabled = True

            with patch.object(CostTrackingService, "update_budget_config") as mock_update:
                result = cli_runner.invoke(main, ["budget", "disable"])

                assert result.exit_code == 0

    def test_budget_no_workspace(self, cli_runner):
        """Test budget commands when no workspace exists."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = None

            result = cli_runner.invoke(main, ["budget", "show"])

            # Should handle gracefully
            assert (
                result.exit_code == 0
                or "error" in result.output.lower()
                or "no workspace" in result.output.lower()
            )


class TestCostCLIEdgeCases:
    """Tests for edge cases in cost CLI commands."""

    def test_cost_export_invalid_format(self, cli_runner, mock_cost_service):
        """Test cost export with invalid format."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            result = cli_runner.invoke(main, ["cost", "export", "--format", "xml"])

            assert (
                result.exit_code != 0
                or "error" in result.output.lower()
                or "invalid" in result.output.lower()
            )

    def test_cost_show_invalid_period(self, cli_runner, mock_cost_service):
        """Test cost show with invalid period."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            result = cli_runner.invoke(main, ["cost", "show", "--period", "yearly"])

            assert (
                result.exit_code != 0
                or "error" in result.output.lower()
                or "invalid" in result.output.lower()
            )

    def test_budget_set_invalid_amount(self, cli_runner, mock_cost_service):
        """Test budget set with invalid amount."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            result = cli_runner.invoke(main, ["budget", "set", "--daily", "-5.00"])

            assert (
                result.exit_code != 0
                or "error" in result.output.lower()
                or "invalid" in result.output.lower()
            )

    def test_budget_set_invalid_action(self, cli_runner, mock_cost_service):
        """Test budget set with invalid action."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            result = cli_runner.invoke(
                main, ["budget", "set", "--daily", "5.00", "--action", "invalid"]
            )

            assert (
                result.exit_code != 0
                or "error" in result.output.lower()
                or "invalid" in result.output.lower()
            )

    def test_cost_reset_nonexistent_project(self, cli_runner, mock_cost_service):
        """Test cost reset for non-existent project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch.object(CostTrackingService, "reset_costs_for_project") as mock_reset:
                mock_reset.return_value = None  # No records to reset

                result = cli_runner.invoke(main, ["cost", "reset", "/nonexistent/project"])

                assert result.exit_code == 0
