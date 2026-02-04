"""Metrics API endpoints."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query, Request

from agent_pump.api.schemas import (
    MetricsExportDTO,
    MetricsSummaryDTO,
    PeriodSummaryDTO,
    ProjectMetricsDTO,
)

if TYPE_CHECKING:
    from agent_pump.services.metrics_service import MetricsService

router = APIRouter(prefix="/metrics", tags=["metrics"])


def get_metrics_service(request: Request) -> "MetricsService":
    """Get metrics service from app state."""
    service = getattr(request.app.state, "metrics_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Metrics service not available")
    return service


@router.get("", response_model=MetricsSummaryDTO)
async def get_metrics(request: Request) -> MetricsSummaryDTO:
    """Get overall workspace metrics summary."""
    metrics_service = get_metrics_service(request)
    metrics = metrics_service.get_metrics()
    return MetricsSummaryDTO.from_workspace_metrics(metrics)


@router.get("/summary", response_model=dict)
async def get_metrics_summary(
    request: Request,
    period: str = Query(default="day", description="Time period: day, week, or month"),
) -> dict:
    """Get metrics summary grouped by time period.

    Args:
        period: Time grouping period (day, week, month)
    """
    metrics_service = get_metrics_service(request)
    metrics = metrics_service.get_metrics()

    # Validate period
    if period not in ["day", "week", "month"]:
        period = "day"

    summary = metrics.get_summary_by_period(period)

    # Convert to DTOs
    summary_dtos = {
        key: PeriodSummaryDTO.from_internal(key, data).model_dump() for key, data in summary.items()
    }

    return {
        "period": period,
        "summary": summary_dtos,
        "total_periods": len(summary_dtos),
    }


@router.get("/projects/{project_path:path}", response_model=ProjectMetricsDTO)
async def get_project_metrics(
    request: Request,
    project_path: Path,
) -> ProjectMetricsDTO:
    """Get metrics for a specific project.

    Args:
        project_path: Path to the project
    """
    metrics_service = get_metrics_service(request)
    project_metrics = metrics_service.get_project_metrics(project_path)

    if project_metrics is None:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for project: {project_path}",
        )

    return ProjectMetricsDTO.from_internal(project_metrics)


@router.get("/export/json", response_model=MetricsExportDTO)
async def export_metrics_json(request: Request) -> MetricsExportDTO:
    """Export all metrics as JSON."""
    metrics_service = get_metrics_service(request)
    json_data = metrics_service.export_to_json()

    timestamp = datetime.now().isoformat()
    filename = f"agent-pump-metrics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"

    return MetricsExportDTO(
        format="json",
        data=json_data,
        filename=filename,
        timestamp=timestamp,
    )


@router.get("/export/csv", response_model=MetricsExportDTO)
async def export_metrics_csv(request: Request) -> MetricsExportDTO:
    """Export metrics as CSV."""
    metrics_service = get_metrics_service(request)
    csv_data = metrics_service.export_to_csv()

    timestamp = datetime.now().isoformat()
    filename = f"agent-pump-metrics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"

    return MetricsExportDTO(
        format="csv",
        data=csv_data,
        filename=filename,
        timestamp=timestamp,
    )
