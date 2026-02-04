"""Cost tracking models for Agent Pump.

This module provides data models for tracking API costs across backend invocations,
managing budget configurations, and generating cost reports.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetPeriod(str, Enum):
    """Budget period types for cost tracking."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BudgetAction(str, Enum):
    """Actions to take when budget is exceeded."""

    PAUSE = "pause"
    WARN = "warn"
    IGNORE = "ignore"


# Pricing rates per 1K tokens (input, output)
BACKEND_PRICING: dict[str, tuple[float, float] | dict[str, tuple[float, float]]] = {
    "gemini": {
        "default": (0.000125, 0.000375),  # Flash pricing
        "flash": (0.000125, 0.000375),
        "pro": (0.000350, 0.001050),
    },
    "claude": (0.003, 0.015),  # Claude 3.5 Sonnet
    "qwen": (0.0005, 0.001),
    "opencode": (0.0, 0.0),  # Local model, no cost
}

# Default pricing if backend not found
DEFAULT_PRICING = (0.0005, 0.001)


class CostRecord(BaseModel):
    """Record of a single backend invocation cost.

    Tracks the cost of a single AI backend invocation including token usage
    and calculated cost in USD.
    """

    model_config = ConfigDict(strict=True, arbitrary_types_allowed=True)

    timestamp: datetime = Field(default_factory=datetime.now)
    project_path: Path = Field(description="Path to the project")
    phase: str = Field(description="Workflow phase (planning, implementing, etc.)")
    backend_name: str = Field(description="Backend name (gemini, claude, etc.)")
    model: str | None = Field(default=None, description="Model name if specified")
    input_tokens: int = Field(default=0, ge=0, description="Number of input tokens")
    output_tokens: int = Field(default=0, ge=0, description="Number of output tokens")
    cost_usd: float = Field(ge=0.0, description="Cost in USD")

    @field_validator("project_path", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        """Ensure project_path is a Path object."""
        if isinstance(v, str):
            return Path(v)
        return v

    @field_validator("cost_usd", mode="before")
    @classmethod
    def round_cost(cls, v: float) -> float:
        """Round cost to 6 decimal places for consistency."""
        return round(v, 6)

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @staticmethod
    def calculate_cost(
        backend_name: str,
        model: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost based on backend, model, and token usage.

        Args:
            backend_name: Name of the backend (gemini, claude, etc.)
            model: Optional model name for model-specific pricing
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        backend_lower = backend_name.lower()
        pricing = BACKEND_PRICING.get(backend_lower, DEFAULT_PRICING)

        # Handle model-specific pricing
        if isinstance(pricing, dict):
            if model:
                model_lower = model.lower()
                # Try exact match
                if model_lower in pricing:
                    input_price, output_price = pricing[model_lower]
                else:
                    # Try partial match
                    matched = False
                    for key, prices in pricing.items():
                        if key != "default" and (key in model_lower or model_lower in key):
                            input_price, output_price = prices
                            matched = True
                            break
                    if not matched:
                        input_price, output_price = pricing.get("default", DEFAULT_PRICING)
            else:
                input_price, output_price = pricing.get("default", DEFAULT_PRICING)
        else:
            input_price, output_price = pricing

        cost = (input_tokens * input_price + output_tokens * output_price) / 1000
        return round(cost, 6)

    @classmethod
    def create(
        cls,
        project_path: Path,
        phase: str,
        backend_name: str,
        model: str | None,
        input_tokens: int,
        output_tokens: int,
    ) -> CostRecord:
        """Create a CostRecord with calculated cost.

        Args:
            project_path: Path to the project
            phase: Workflow phase
            backend_name: Backend name
            model: Optional model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            CostRecord with calculated cost
        """
        cost = cls.calculate_cost(backend_name, model, input_tokens, output_tokens)
        return cls(
            project_path=project_path,
            phase=phase,
            backend_name=backend_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
        )


class BudgetConfig(BaseModel):
    """Configuration for budget limits.

    Defines spending limits for different time periods and the action
    to take when a budget is exceeded.
    """

    model_config = ConfigDict(strict=True)

    enabled: bool = Field(default=False, description="Whether budget enforcement is enabled")
    daily_limit: float | None = Field(
        default=None, ge=0, description="Daily budget limit in USD (None = no limit)"
    )
    weekly_limit: float | None = Field(
        default=None, ge=0, description="Weekly budget limit in USD (None = no limit)"
    )
    monthly_limit: float | None = Field(
        default=None, ge=0, description="Monthly budget limit in USD (None = no limit)"
    )
    action_on_exceeded: BudgetAction = Field(
        default=BudgetAction.PAUSE,
        description="Action to take when budget is exceeded",
    )

    def is_exceeded(self, current_cost: float, period: BudgetPeriod) -> bool:
        """Check if current cost exceeds the budget for a given period.

        Args:
            current_cost: Current accumulated cost for the period
            period: Budget period to check

        Returns:
            True if budget is exceeded, False otherwise
        """
        if not self.enabled:
            return False

        limit = None
        if period == BudgetPeriod.DAILY:
            limit = self.daily_limit
        elif period == BudgetPeriod.WEEKLY:
            limit = self.weekly_limit
        elif period == BudgetPeriod.MONTHLY:
            limit = self.monthly_limit

        if limit is None:
            return False

        return current_cost > limit

    def get_limit(self, period: BudgetPeriod) -> float | None:
        """Get the budget limit for a specific period.

        Args:
            period: Budget period

        Returns:
            Budget limit in USD, or None if no limit set
        """
        if period == BudgetPeriod.DAILY:
            return self.daily_limit
        elif period == BudgetPeriod.WEEKLY:
            return self.weekly_limit
        elif period == BudgetPeriod.MONTHLY:
            return self.monthly_limit
        return None


class PeriodCosts(BaseModel):
    """Cost aggregation for a specific time period.

    Tracks total costs and token usage within a specific budget period.
    """

    model_config = ConfigDict(strict=True)

    period: BudgetPeriod = Field(description="Budget period type")
    start_date: datetime = Field(description="Start date of the period")
    total_cost: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens used")
    record_count: int = Field(default=0, ge=0, description="Number of records")

    def add_record(self, record: CostRecord) -> None:
        """Add a cost record to this period.

        Args:
            record: CostRecord to add
        """
        self.total_cost += record.cost_usd
        self.total_tokens += record.total_tokens
        self.record_count += 1


class CostSummary(BaseModel):
    """Summary of costs aggregated from multiple records.

    Provides aggregated cost data broken down by project, phase, and backend.
    """

    model_config = ConfigDict(strict=True)

    total_cost: float = Field(default=0.0, description="Total cost in USD")
    total_tokens: int = Field(default=0, description="Total tokens used")
    record_count: int = Field(default=0, description="Number of cost records")
    period_costs: list[PeriodCosts] = Field(default_factory=list, description="Costs by period")

    def __init__(self, **data: Any) -> None:
        """Initialize with empty records storage."""
        super().__init__(**data)
        self._records: list[CostRecord] = []

    @classmethod
    def from_records(cls, records: list[CostRecord]) -> CostSummary:
        """Create a CostSummary from a list of CostRecords.

        Args:
            records: List of CostRecord objects

        Returns:
            CostSummary with aggregated data
        """
        total_cost = sum(r.cost_usd for r in records)
        total_tokens = sum(r.total_tokens for r in records)

        summary = cls(
            total_cost=round(total_cost, 6),
            total_tokens=total_tokens,
            record_count=len(records),
        )
        summary._records = records
        return summary

    def get_project_breakdown(
        self, records: list[CostRecord] | None = None
    ) -> dict[str, CostSummary]:
        """Get cost breakdown by project.

        Args:
            records: Optional list of CostRecord objects.
                If not provided, uses records from summary.

        Returns:
            Dictionary mapping project path strings to CostSummary
        """
        records_to_use = records if records is not None else self._records
        by_project: dict[str, list[CostRecord]] = defaultdict(list)
        for record in records_to_use:
            by_project[str(record.project_path)].append(record)

        return {
            path: CostSummary.from_records(proj_records)
            for path, proj_records in by_project.items()
        }

    def get_phase_breakdown(
        self, records: list[CostRecord] | None = None
    ) -> dict[str, CostSummary]:
        """Get cost breakdown by workflow phase.

        Args:
            records: Optional list of CostRecord objects.
                If not provided, uses records from summary.

        Returns:
            Dictionary mapping phase names to CostSummary
        """
        records_to_use = records if records is not None else self._records
        by_phase: dict[str, list[CostRecord]] = defaultdict(list)
        for record in records_to_use:
            by_phase[record.phase].append(record)

        return {
            phase: CostSummary.from_records(phase_records)
            for phase, phase_records in by_phase.items()
        }

    def get_backend_breakdown(
        self, records: list[CostRecord] | None = None
    ) -> dict[str, CostSummary]:
        """Get cost breakdown by backend.

        Args:
            records: Optional list of CostRecord objects.
                If not provided, uses records from summary.

        Returns:
            Dictionary mapping backend names to CostSummary
        """
        records_to_use = records if records is not None else self._records
        by_backend: dict[str, list[CostRecord]] = defaultdict(list)
        for record in records_to_use:
            by_backend[record.backend_name].append(record)

        return {
            backend: CostSummary.from_records(backend_records)
            for backend, backend_records in by_backend.items()
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "record_count": self.record_count,
            "period_costs": [
                {
                    "period": pc.period.value,
                    "start_date": pc.start_date.isoformat(),
                    "total_cost": round(pc.total_cost, 6),
                    "total_tokens": pc.total_tokens,
                    "record_count": pc.record_count,
                }
                for pc in self.period_costs
            ],
        }
