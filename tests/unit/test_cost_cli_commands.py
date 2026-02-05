"""Tests for cost tracking CLI commands."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_pump.cli import main
from agent_pump.services.cost_tracking_service import CostTrackingService


@pytest.fixture
def cli_runner():
    """Create a CliRunner for testing."""
    # Patch configure_logging to prevent it from messing with global logging/stdout
    with patch("agent_pump.utils.logging_config.configure_logging"):
        yield CliRunner()


@pytest.fixture
def mock_cost_service():
    """Create a mock CostTrackingService."""
    from agent_pump.models.cost_tracking import BudgetConfig

    workspace = MagicMock()
    workspace.name = "test_cli_workspace"
    workspace.budget_config = BudgetConfig()

    # Use a real instance but mock internal methods to avoid file I/O
    with patch("agent_pump.services.cost_tracking_service.CostTrackingService._load_costs"):
        with patch("agent_pump.services.cost_tracking_service.CostTrackingService.save_costs"):
            service = CostTrackingService(workspace)
            # Pre-populate some records for testing
            service.record_invocation(
                project_path=Path("/test/project0"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                model="gemini-2.5-flash",
            )
            return service


class TestCostCLICommands:
    """Tests for cost-related CLI commands."""

    def test_cost_show_workspace(self, cli_runner, mock_cost_service):
        """Test cost show command for workspace."""
        # Mock Workspace.load to return our workspace
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            # Patch CostTrackingService in the cli module via sys.modules or just patch
            # where it's used. Since the command imports it inside the function, we
            # need to patch it there.
            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                # Mock get_workspace_costs on our instance
                with patch.object(mock_cost_service, "get_workspace_costs") as mock_get:
                    mock_get.return_value = SimpleNamespace(
                        total_cost=0.01, total_tokens=10000, record_count=5
                    )

                    result = cli_runner.invoke(main, ["cost", "show"])

                    assert result.exit_code == 0
                    assert "Workspace Costs" in result.output
                    assert mock_cost_service.workspace.name in result.output

    def test_cost_show_project(self, cli_runner, mock_cost_service):
        """Test cost show command for a specific project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "get_project_costs") as mock_get:
                    mock_get.return_value = SimpleNamespace(
                        total_cost=0.005, total_tokens=5000, record_count=3
                    )

                    result = cli_runner.invoke(main, ["cost", "show", "/test/project0"])

                    assert result.exit_code == 0
                    assert "Costs for project" in result.output
                    # Normalize path check for cross-platform
                    assert str(Path("/test/project0")) in result.output

    def test_cost_show_period(self, cli_runner, mock_cost_service):
        """Test cost show command for a specific period."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "get_period_costs") as mock_get:
                    mock_get.return_value = SimpleNamespace(
                        total_cost=0.002, total_tokens=2000, record_count=2
                    )

                    result = cli_runner.invoke(main, ["cost", "show", "--period", "daily"])

                    assert result.exit_code == 0
                    assert "Costs for daily period" in result.output

    def test_cost_export(self, cli_runner, mock_cost_service):
        """Test cost export command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                # Mock export_costs to return string
                with patch.object(mock_cost_service, "export_costs", return_value="{}"):
                    # Use a temp file for output
                    with cli_runner.isolated_filesystem():
                        result = cli_runner.invoke(
                            main, ["cost", "export", "--output", "costs.json"]
                        )

                        assert result.exit_code == 0
                        assert "exported to" in result.output
                        assert Path("costs.json").exists()

    def test_cost_reset_project(self, cli_runner, mock_cost_service):
        """Test cost reset command for a specific project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                # Mock reset method
                with patch.object(mock_cost_service, "reset_costs_for_project") as mock_reset:
                    # Provide 'y' input for confirmation
                    result = cli_runner.invoke(main, ["cost", "reset", "/test/project0"], input="y")

                    assert result.exit_code == 0
                    assert "Reset costs for project" in result.output
                    mock_reset.assert_called_once()

    def test_cost_reset_all(self, cli_runner, mock_cost_service):
        """Test cost reset command for all projects."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "reset_all_costs") as mock_reset:
                    # Provide 'y' input for confirmation
                    result = cli_runner.invoke(main, ["cost", "reset"], input="y")

                    assert result.exit_code == 0
                    assert "Reset all costs" in result.output
                    mock_reset.assert_called_once()

    def test_cost_breakdown_by_phase(self, cli_runner, mock_cost_service):
        """Test cost breakdown command grouped by phase."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(
                    mock_cost_service, "get_cost_breakdown_by_phase"
                ) as mock_breakdown:
                    # Use SimpleNamespace instead of MagicMock for data objects
                    mock_breakdown.return_value = {
                        "planning": SimpleNamespace(
                            total_cost=0.02, total_tokens=1000, record_count=2
                        ),
                        "implementing": SimpleNamespace(
                            total_cost=0.03, total_tokens=2000, record_count=3
                        ),
                    }

                    result = cli_runner.invoke(main, ["cost", "breakdown", "--by", "phase"])

                    assert result.exit_code == 0
                    assert "Cost Breakdown by Phase" in result.output
                    assert "planning" in result.output
                    assert "implementing" in result.output

    def test_cost_breakdown_by_backend(self, cli_runner, mock_cost_service):
        """Test cost breakdown command grouped by backend."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(
                    mock_cost_service, "get_cost_breakdown_by_backend"
                ) as mock_breakdown:
                    mock_breakdown.return_value = {
                        "gemini": SimpleNamespace(
                            total_cost=0.05, total_tokens=3000, record_count=5
                        ),
                    }

                    result = cli_runner.invoke(main, ["cost", "breakdown", "--by", "backend"])

                    assert result.exit_code == 0
                    assert "Cost Breakdown by Backend" in result.output
                    assert "gemini" in result.output

class TestBudgetCLICommands:
    """Tests for budget-related CLI commands."""

    def test_budget_show(self, cli_runner, mock_cost_service):
        """Test budget show command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "get_budget_status") as mock_status:
                    mock_status.return_value = {
                        "enabled": True,
                        "action_on_exceeded": "warn",
                        "daily_limit": 10.0,
                        "daily_spent": 5.0,
                        "daily_remaining": 5.0,
                        "daily_exceeded": False,
                    }

                    result = cli_runner.invoke(main, ["budget", "show"])

                    assert result.exit_code == 0
                    assert "Budget Status" in result.output
                    assert "Daily" in result.output
                    assert "$10.00" in result.output

    def test_budget_set(self, cli_runner, mock_cost_service):
        """Test budget set command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "update_budget_config") as mock_update:
                    result = cli_runner.invoke(main, ["budget", "set", "--daily", "10.0"])

                    assert result.exit_code == 0
                    assert "Budget configuration updated" in result.output
                    mock_update.assert_called_once()

    def test_budget_enable(self, cli_runner, mock_cost_service):
        """Test budget enable command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace
            mock_cost_service.workspace.budget_config.enabled = False

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "update_budget_config") as mock_update:
                    result = cli_runner.invoke(main, ["budget", "enable"])

                    assert result.exit_code == 0
                    assert "Budget enforcement enabled" in result.output
                    mock_update.assert_called_once()

    def test_budget_disable(self, cli_runner, mock_cost_service):
        """Test budget disable command."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace
            mock_cost_service.workspace.budget_config.enabled = True

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                with patch.object(mock_cost_service, "update_budget_config") as mock_update:
                    result = cli_runner.invoke(main, ["budget", "disable"])

                    assert result.exit_code == 0
                    assert "Budget enforcement disabled" in result.output
                    mock_update.assert_called_once()

    def test_budget_no_workspace(self, cli_runner):
        """Test budget commands when no workspace exists."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = None

            result = cli_runner.invoke(main, ["budget", "show"])

            # Should handle gracefully
            assert result.exit_code != 0
            assert "not found" in result.output


class TestCostCLIEdgeCases:
    """Tests for edge cases in CLI commands."""

    def test_cost_reset_nonexistent_project(self, cli_runner, mock_cost_service):
        """Test cost reset for non-existent project."""
        with patch("agent_pump.models.workspace.Workspace.load") as mock_load:
            mock_load.return_value = mock_cost_service.workspace

            with patch(
                "agent_pump.services.cost_tracking_service.CostTrackingService"
            ) as mock_service_cls:
                mock_service_cls.return_value = mock_cost_service

                # Mock reset to just do nothing
                with patch.object(mock_cost_service, "reset_costs_for_project") as mock_reset:
                    # Provide 'y' input for confirmation
                    result = cli_runner.invoke(
                        main, ["cost", "reset", "/nonexistent/project"], input="y"
                    )

                    assert result.exit_code == 0
                    mock_reset.assert_called_once()
