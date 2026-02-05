"""Cost tracking service for Agent Pump.

This service manages cost tracking across backend invocations, enforces budget limits,
and provides cost reporting functionality.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agent_pump.models.cost_tracking import (
    BudgetAction,
    BudgetConfig,
    BudgetPeriod,
    CostRecord,
    CostSummary,
    PeriodCosts,
)
from agent_pump.models.workspace import Workspace

logger = logging.getLogger(__name__)


class CostTrackingService:
    """Service for tracking API costs and managing budgets.

    Tracks costs per backend invocation, accumulates costs per project and workspace,
    enforces budget limits, and provides cost reporting.
    """

    def __init__(self, workspace: Workspace, storage_path: Path | None = None) -> None:
        """Initialize the cost tracking service.

        Args:
            workspace: The workspace to track costs for.
            storage_path: Optional custom path for storing cost data.
        """
        self.workspace = workspace
        self._storage_path = storage_path
        self._cost_records: list[CostRecord] = []
        self._budget_config = (
            workspace.budget_config if hasattr(workspace, "budget_config") else BudgetConfig()
        )
        self._load_costs()
        logger.debug(f"Initialized CostTrackingService for workspace '{workspace.name}'")

    def _get_costs_file_path(self) -> Path:
        """Get the path to the costs file for this workspace.

        Returns:
            Path to the costs JSON file.
        """
        if self._storage_path:
            costs_dir = self._storage_path
        else:
            costs_dir = Path.home() / ".config" / "agent-pump" / "costs"

        costs_dir.mkdir(parents=True, exist_ok=True)
        return costs_dir / f"{self.workspace.name}.json"

    def _load_costs(self) -> None:
        """Load cost records from disk."""
        costs_file = self._get_costs_file_path()
        if not costs_file.exists():
            logger.debug(f"No costs file found at {costs_file}")
            return

        try:
            data = json.loads(costs_file.read_text(encoding="utf-8"))

            # Load budget config if present
            if "budget_config" in data:
                config_data = data["budget_config"]
                # Handle action_on_exceeded as string
                if "action_on_exceeded" in config_data and isinstance(
                    config_data["action_on_exceeded"], str
                ):
                    config_data["action_on_exceeded"] = BudgetAction(
                        config_data["action_on_exceeded"]
                    )
                self._budget_config = BudgetConfig(**config_data)

            # Load cost records
            if "records" in data:
                for record_data in data["records"]:
                    # Parse timestamp string to datetime
                    if "timestamp" in record_data and isinstance(record_data["timestamp"], str):
                        record_data["timestamp"] = datetime.fromisoformat(record_data["timestamp"])
                self._cost_records = [CostRecord(**record_data) for record_data in data["records"]]

            logger.info(f"Loaded {len(self._cost_records)} cost records from {costs_file}")
        except Exception as e:
            logger.error(f"Failed to load costs from {costs_file}: {e}")
            self._cost_records = []

    def save_costs(self) -> None:
        """Save cost records to disk."""
        costs_file = self._get_costs_file_path()

        try:
            data = {
                "version": 1,
                "workspace": self.workspace.name,
                "last_updated": datetime.now().isoformat(),
                "budget_config": self._budget_config.model_dump(),
                "records": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "project_path": str(r.project_path),
                        "phase": r.phase,
                        "backend_name": r.backend_name,
                        "model": r.model,
                        "input_tokens": r.input_tokens,
                        "output_tokens": r.output_tokens,
                        "cost_usd": r.cost_usd,
                    }
                    for r in self._cost_records
                ],
            }

            costs_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Saved {len(self._cost_records)} cost records to {costs_file}")
        except Exception as e:
            logger.error(f"Failed to save costs to {costs_file}: {e}")

    def load_costs(self) -> None:
        """Public method to reload costs from disk."""
        self._load_costs()

    def record_invocation(
        self,
        project_path: Path,
        phase: str,
        backend_name: str,
        input_tokens: int,
        output_tokens: int,
        model: str | None = None,
    ) -> CostRecord:
        """Record a backend invocation and its cost.

        Args:
            project_path: Path to the project.
            phase: Workflow phase (planning, implementing, etc.).
            backend_name: Name of the backend used.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Optional model name.

        Returns:
            The created CostRecord.
        """
        record = CostRecord.create(
            project_path=project_path,
            phase=phase,
            backend_name=backend_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        self._cost_records.append(record)
        self.save_costs()

        logger.info(
            f"Recorded cost: {backend_name} {phase} for {project_path.name} "
            f"(${record.cost_usd:.4f}, {record.total_tokens} tokens)"
        )

        return record

    def get_project_costs(self, project_path: Path) -> CostSummary:
        """Get cost summary for a specific project.

        Args:
            project_path: Path to the project.

        Returns:
            CostSummary for the project.
        """
        project_records = [r for r in self._cost_records if r.project_path == project_path]
        return CostSummary.from_records(project_records)

    def get_workspace_costs(self) -> CostSummary:
        """Get cost summary for the entire workspace.

        Returns:
            CostSummary for all projects in the workspace.
        """
        return CostSummary.from_records(self._cost_records)

    def get_period_costs(self, period: BudgetPeriod) -> PeriodCosts:
        """Get cost summary for a specific budget period.

        Args:
            period: Budget period (daily, weekly, monthly).

        Returns:
            PeriodCosts for the specified period.
        """
        now = datetime.now()

        if period == BudgetPeriod.DAILY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.WEEKLY:
            # Start of current week (Monday)
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == BudgetPeriod.MONTHLY:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now

        period_records = [r for r in self._cost_records if r.timestamp >= start_date]

        total_cost = sum(r.cost_usd for r in period_records)
        total_tokens = sum(r.total_tokens for r in period_records)

        return PeriodCosts(
            period=period,
            start_date=start_date,
            total_cost=round(total_cost, 6),
            total_tokens=total_tokens,
            record_count=len(period_records),
        )

    def check_budget(self) -> tuple[bool, BudgetPeriod | None]:
        """Check if any budget limit has been exceeded.

        Returns:
            Tuple of (is_exceeded, period_exceeded). period_exceeded is None if not exceeded.
        """
        if not self._budget_config.enabled:
            return False, None

        for period in [BudgetPeriod.DAILY, BudgetPeriod.WEEKLY, BudgetPeriod.MONTHLY]:
            limit = self._budget_config.get_limit(period)
            if limit is None:
                continue

            period_costs = self.get_period_costs(period)
            if period_costs.total_cost > limit:
                logger.warning(
                    f"Budget exceeded: {period.value} limit ${limit:.2f}, "
                    f"spent ${period_costs.total_cost:.2f}"
                )
                return True, period

        return False, None

    def should_pause_on_budget(self) -> bool:
        """Check if execution should pause due to budget exceeded.

        Returns:
            True if budget is exceeded and action is PAUSE, False otherwise.
        """
        is_exceeded, _ = self.check_budget()
        if not is_exceeded:
            return False

        return self._budget_config.action_on_exceeded == BudgetAction.PAUSE

    def update_budget_config(self, config: BudgetConfig) -> None:
        """Update the budget configuration.

        Args:
            config: New BudgetConfig to apply.
        """
        self._budget_config = config
        self.workspace.budget_config = config
        self.save_costs()
        logger.info(f"Updated budget config for workspace '{self.workspace.name}'")

    def reset_costs_for_project(self, project_path: Path) -> None:
        """Reset cost records for a specific project.

        Args:
            project_path: Path to the project.
        """
        initial_count = len(self._cost_records)
        self._cost_records = [r for r in self._cost_records if r.project_path != project_path]
        removed_count = initial_count - len(self._cost_records)
        self.save_costs()
        logger.info(f"Reset costs for project {project_path}: removed {removed_count} records")

    def reset_all_costs(self) -> None:
        """Reset all cost records for the workspace."""
        record_count = len(self._cost_records)
        self._cost_records = []
        self.save_costs()
        logger.info(f"Reset all costs: removed {record_count} records")

    def export_costs(self, format: str = "json") -> str:
        """Export cost records to a string format.

        Args:
            format: Export format ("json" or "csv").

        Returns:
            Exported data as a string.
        """
        if format.lower() == "json":
            data = {
                "workspace": self.workspace.name,
                "export_date": datetime.now().isoformat(),
                "total_records": len(self._cost_records),
                "summary": self.get_workspace_costs().to_dict(),
                "records": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "project_path": str(r.project_path),
                        "phase": r.phase,
                        "backend_name": r.backend_name,
                        "model": r.model,
                        "input_tokens": r.input_tokens,
                        "output_tokens": r.output_tokens,
                        "total_tokens": r.total_tokens,
                        "cost_usd": r.cost_usd,
                    }
                    for r in self._cost_records
                ],
            }
            return json.dumps(data, indent=2)

        elif format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
                [
                    "timestamp",
                    "project_path",
                    "phase",
                    "backend_name",
                    "model",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "cost_usd",
                ]
            )

            # Records
            for r in self._cost_records:
                writer.writerow(
                    [
                        r.timestamp.isoformat(),
                        str(r.project_path),
                        r.phase,
                        r.backend_name,
                        r.model or "",
                        r.input_tokens,
                        r.output_tokens,
                        r.total_tokens,
                        r.cost_usd,
                    ]
                )

            return output.getvalue()

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_cost_breakdown_by_phase(self) -> dict[str, CostSummary]:
        """Get cost breakdown by workflow phase.

        Returns:
            Dictionary mapping phase names to CostSummary.
        """
        summary = CostSummary.from_records(self._cost_records)
        return summary.get_phase_breakdown(self._cost_records)

    def get_cost_breakdown_by_backend(self) -> dict[str, CostSummary]:
        """Get cost breakdown by backend.

        Returns:
            Dictionary mapping backend names to CostSummary.
        """
        summary = CostSummary.from_records(self._cost_records)
        return summary.get_backend_breakdown(self._cost_records)

    def get_budget_status(self) -> dict[str, Any]:
        """Get the current budget status.

        Returns:
            Dictionary with budget status information.
        """
        status = {
            "enabled": self._budget_config.enabled,
            "action_on_exceeded": self._budget_config.action_on_exceeded.value,
        }

        for period in [BudgetPeriod.DAILY, BudgetPeriod.WEEKLY, BudgetPeriod.MONTHLY]:
            limit = self._budget_config.get_limit(period)
            period_costs = self.get_period_costs(period)

            status[f"{period.value}_limit"] = limit
            status[f"{period.value}_spent"] = round(period_costs.total_cost, 4)
            status[f"{period.value}_remaining"] = (
                round(limit - period_costs.total_cost, 4) if limit else None
            )
            status[f"{period.value}_exceeded"] = period_costs.total_cost > limit if limit else False

        return status

    @staticmethod
    def estimate_cost(
        backend_name: str, model: str | None, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost for a backend invocation without recording it.

        Args:
            backend_name: Name of the backend.
            model: Optional model name.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        return CostRecord.calculate_cost(backend_name, model, input_tokens, output_tokens)
