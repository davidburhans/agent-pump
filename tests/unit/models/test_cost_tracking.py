"""Tests for cost tracking models."""

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_pump.models.cost_tracking import (
    BudgetAction,
    BudgetConfig,
    BudgetPeriod,
    CostRecord,
    CostSummary,
    PeriodCosts,
)


class TestCostRecord:
    """Tests for CostRecord model."""

    def test_cost_record_creation(self):
        """Test creating a valid CostRecord."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="planning",
            backend_name="gemini",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.0005,
        )
        assert record.project_path == Path("/path/to/project")
        assert record.phase == "planning"
        assert record.backend_name == "gemini"
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.total_tokens == 1500
        assert record.cost_usd == 0.0005
        assert record.timestamp is not None

    def test_cost_record_with_model(self):
        """Test CostRecord with model specified."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="implementing",
            backend_name="claude",
            model="claude-3.5-sonnet",
            input_tokens=2000,
            output_tokens=1000,
            cost_usd=0.021,
        )
        assert record.model == "claude-3.5-sonnet"

    def test_cost_record_defaults(self):
        """Test CostRecord with default values."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="planning",
            backend_name="gemini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0001,
        )
        assert record.model is None
        assert isinstance(record.timestamp, datetime)

    def test_cost_record_total_tokens_computed(self):
        """Test that total_tokens is computed correctly."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="planning",
            backend_name="gemini",
            input_tokens=3000,
            output_tokens=2000,
            cost_usd=0.001,
        )
        assert record.total_tokens == 5000

    def test_cost_record_zero_tokens(self):
        """Test CostRecord with zero tokens."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="planning",
            backend_name="gemini",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
        assert record.total_tokens == 0

    def test_cost_record_negative_cost_raises_error(self):
        """Test that negative cost raises validation error."""
        with pytest.raises(ValidationError):
            CostRecord(
                project_path=Path("/path/to/project"),
                phase="planning",
                backend_name="gemini",
                input_tokens=100,
                output_tokens=50,
                cost_usd=-0.001,
            )

    def test_cost_record_string_path(self):
        """Test CostRecord with string path."""
        record = CostRecord(
            project_path=Path("/path/to/project"),
            phase="planning",
            backend_name="gemini",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.0001,
        )
        assert record.project_path == Path("/path/to/project")


class TestBudgetConfig:
    """Tests for BudgetConfig model."""

    def test_budget_config_defaults(self):
        """Test BudgetConfig with default values."""
        config = BudgetConfig()
        assert config.enabled is False
        assert config.daily_limit is None
        assert config.weekly_limit is None
        assert config.monthly_limit is None
        assert config.action_on_exceeded == BudgetAction.PAUSE

    def test_budget_config_with_limits(self):
        """Test BudgetConfig with specific limits."""
        config = BudgetConfig(
            enabled=True,
            daily_limit=5.0,
            weekly_limit=25.0,
            monthly_limit=100.0,
            action_on_exceeded=BudgetAction.WARN,
        )
        assert config.enabled is True
        assert config.daily_limit == 5.0
        assert config.weekly_limit == 25.0
        assert config.monthly_limit == 100.0
        assert config.action_on_exceeded == BudgetAction.WARN

    def test_budget_config_only_daily(self):
        """Test BudgetConfig with only daily limit."""
        config = BudgetConfig(enabled=True, daily_limit=10.0)
        assert config.enabled is True
        assert config.daily_limit == 10.0
        assert config.weekly_limit is None
        assert config.monthly_limit is None

    def test_budget_config_validation_negative_limit(self):
        """Test that negative limit raises validation error."""
        with pytest.raises(ValidationError):
            BudgetConfig(enabled=True, daily_limit=-5.0)

    def test_budget_config_validation_zero_limit(self):
        """Test that zero limit is allowed (meaning no limit)."""
        # Zero or None means no limit
        config = BudgetConfig(enabled=True, daily_limit=0.0)
        assert config.daily_limit == 0.0


class TestBudgetPeriod:
    """Tests for BudgetPeriod enum."""

    def test_budget_period_values(self):
        """Test BudgetPeriod enum values."""
        assert BudgetPeriod.DAILY.value == "daily"
        assert BudgetPeriod.WEEKLY.value == "weekly"
        assert BudgetPeriod.MONTHLY.value == "monthly"


class TestBudgetAction:
    """Tests for BudgetAction enum."""

    def test_budget_action_values(self):
        """Test BudgetAction enum values."""
        assert BudgetAction.PAUSE.value == "pause"
        assert BudgetAction.WARN.value == "warn"
        assert BudgetAction.IGNORE.value == "ignore"


class TestPeriodCosts:
    """Tests for PeriodCosts model."""

    def test_period_costs_creation(self):
        """Test creating PeriodCosts."""
        costs = PeriodCosts(
            period=BudgetPeriod.DAILY,
            start_date=datetime(2026, 2, 1, 0, 0, 0),
            total_cost=5.5,
            total_tokens=15000,
            record_count=3,
        )
        assert costs.period == BudgetPeriod.DAILY
        assert costs.total_cost == 5.5
        assert costs.total_tokens == 15000
        assert costs.record_count == 3

    def test_period_costs_defaults(self):
        """Test PeriodCosts with defaults."""
        costs = PeriodCosts(
            period=BudgetPeriod.WEEKLY,
            start_date=datetime(2026, 1, 26, 0, 0, 0),
        )
        assert costs.total_cost == 0.0
        assert costs.total_tokens == 0
        assert costs.record_count == 0


class TestCostSummary:
    """Tests for CostSummary model."""

    def test_cost_summary_empty(self):
        """Test CostSummary with no records."""
        summary = CostSummary()
        assert summary.total_cost == 0.0
        assert summary.total_tokens == 0
        assert summary.record_count == 0
        assert summary.period_costs == []

    def test_cost_summary_with_records(self):
        """Test CostSummary aggregation from records."""
        records = [
            CostRecord(
                project_path=Path("/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/project1"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
            CostRecord(
                project_path=Path("/project2"),
                phase="planning",
                backend_name="claude",
                input_tokens=3000,
                output_tokens=1500,
                cost_usd=0.015,
            ),
        ]
        summary = CostSummary.from_records(records)
        assert summary.total_cost == 0.0165
        assert summary.total_tokens == 9000
        assert summary.record_count == 3

    def test_cost_summary_project_breakdown(self):
        """Test CostSummary project breakdown."""
        records = [
            CostRecord(
                project_path=Path("/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/project1"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
            CostRecord(
                project_path=Path("/project2"),
                phase="planning",
                backend_name="claude",
                input_tokens=3000,
                output_tokens=1500,
                cost_usd=0.015,
            ),
        ]
        summary = CostSummary.from_records(records)
        breakdown = summary.get_project_breakdown(records)
        assert len(breakdown) == 2
        assert breakdown[str(Path("/project1"))].total_cost == 0.0015
        assert breakdown[str(Path("/project2"))].total_cost == 0.015

    def test_cost_summary_phase_breakdown(self):
        """Test CostSummary phase breakdown."""
        records = [
            CostRecord(
                project_path=Path("/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/project1"),
                phase="implementing",
                backend_name="gemini",
                input_tokens=2000,
                output_tokens=1000,
                cost_usd=0.001,
            ),
        ]
        summary = CostSummary.from_records(records)
        breakdown = summary.get_phase_breakdown(records)
        assert len(breakdown) == 2
        assert breakdown["planning"].total_cost == 0.0005
        assert breakdown["implementing"].total_cost == 0.001

    def test_cost_summary_backend_breakdown(self):
        """Test CostSummary backend breakdown."""
        records = [
            CostRecord(
                project_path=Path("/project1"),
                phase="planning",
                backend_name="gemini",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=0.0005,
            ),
            CostRecord(
                project_path=Path("/project1"),
                phase="planning",
                backend_name="claude",
                input_tokens=3000,
                output_tokens=1500,
                cost_usd=0.015,
            ),
        ]
        summary = CostSummary.from_records(records)
        breakdown = summary.get_backend_breakdown(records)
        assert len(breakdown) == 2
        assert breakdown["gemini"].total_cost == 0.0005
        assert breakdown["claude"].total_cost == 0.015


class TestCostRecordPricing:
    """Tests for cost calculation from tokens."""

    def test_calculate_cost_gemini_flash(self):
        """Test cost calculation for Gemini Flash."""
        cost = CostRecord.calculate_cost("gemini", "gemini-2.5-flash", 1000, 500)
        # (1000 * 0.000125 + 500 * 0.000375) / 1000 = 0.0003125, rounded to 6 decimals = 0.000313
        assert cost == pytest.approx(0.000313, rel=1e-6)

    def test_calculate_cost_gemini_pro(self):
        """Test cost calculation for Gemini Pro."""
        cost = CostRecord.calculate_cost("gemini", "gemini-pro", 1000, 500)
        # (1000 * 0.00035 + 500 * 0.00105) / 1000 = 0.000875
        assert cost == pytest.approx(0.000875, rel=1e-6)

    def test_calculate_cost_claude(self):
        """Test cost calculation for Claude."""
        cost = CostRecord.calculate_cost("claude", "claude-3.5-sonnet", 1000, 500)
        # (1000 * 0.003 + 500 * 0.015) / 1000 = 0.0105
        assert cost == pytest.approx(0.0105, rel=1e-6)

    def test_calculate_cost_qwen(self):
        """Test cost calculation for Qwen."""
        cost = CostRecord.calculate_cost("qwen", None, 1000, 500)
        # (1000 * 0.0005 + 500 * 0.001) / 1000 = 0.001
        assert cost == pytest.approx(0.001, rel=1e-6)

    def test_calculate_cost_opencode(self):
        """Test cost calculation for OpenCode (free)."""
        cost = CostRecord.calculate_cost("opencode", None, 1000, 500)
        assert cost == 0.0

    def test_calculate_cost_unknown_backend(self):
        """Test cost calculation for unknown backend."""
        cost = CostRecord.calculate_cost("unknown", None, 1000, 500)
        # Should use default pricing
        assert cost > 0


class TestBudgetConfigMethods:
    """Tests for BudgetConfig helper methods."""

    def test_is_exceeded_no_limits(self):
        """Test is_exceeded with no limits set."""
        config = BudgetConfig(enabled=True)
        assert not config.is_exceeded(100.0, BudgetPeriod.DAILY)
        assert not config.is_exceeded(100.0, BudgetPeriod.WEEKLY)
        assert not config.is_exceeded(100.0, BudgetPeriod.MONTHLY)

    def test_is_exceeded_daily(self):
        """Test is_exceeded with daily limit."""
        config = BudgetConfig(enabled=True, daily_limit=10.0)
        assert not config.is_exceeded(5.0, BudgetPeriod.DAILY)
        assert config.is_exceeded(15.0, BudgetPeriod.DAILY)
        assert not config.is_exceeded(100.0, BudgetPeriod.WEEKLY)  # No weekly limit

    def test_is_exceeded_disabled(self):
        """Test is_exceeded when budget is disabled."""
        config = BudgetConfig(enabled=False, daily_limit=10.0)
        assert not config.is_exceeded(100.0, BudgetPeriod.DAILY)

    def test_is_exceeded_exact_match(self):
        """Test is_exceeded at exact limit."""
        config = BudgetConfig(enabled=True, daily_limit=10.0)
        assert not config.is_exceeded(10.0, BudgetPeriod.DAILY)  # At limit, not exceeded
        assert config.is_exceeded(10.01, BudgetPeriod.DAILY)
