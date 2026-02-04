"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from agent_pump import __version__
from agent_pump.utils.memory_profiler import memory_profiler
from agent_pump.utils.subprocess_manager import subprocess_manager

router = APIRouter(prefix="/health", tags=["health"])


class ResourceUsage(BaseModel):
    """Resource usage statistics."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    memory_rss_mb: float = Field(description="Resident memory size in MB")
    memory_vms_mb: float = Field(description="Virtual memory size in MB")
    memory_percent: float = Field(description="Memory usage percentage")
    cpu_percent: float | None = Field(
        default=None, description="CPU usage percentage (if available)"
    )


class SubprocessStats(BaseModel):
    """Subprocess statistics."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    active_count: int = Field(description="Number of currently active subprocesses")
    total_spawned: int = Field(description="Total subprocesses spawned")
    total_completed: int = Field(description="Total subprocesses completed")
    total_timeout: int = Field(description="Total subprocesses timed out")
    total_cancelled: int = Field(description="Total subprocesses cancelled")


class HealthResponse(BaseModel):
    """Health check response with resource usage."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    status: str = Field(default="ok", description="Service status")
    timestamp: str = Field(description="Current server timestamp in ISO format")
    version: str = Field(description="Agent Pump version")
    uptime_seconds: float | None = Field(default=None, description="Server uptime in seconds")
    resources: ResourceUsage | None = Field(default=None, description="Resource usage statistics")
    subprocesses: SubprocessStats | None = Field(default=None, description="Subprocess statistics")
    event_queue_depth: int | None = Field(default=None, description="Number of events in queue")


@router.get("", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint.

    Returns comprehensive health status including resource usage, subprocess
    statistics, and event queue depth for monitoring and debugging.
    This endpoint is always accessible (bypasses auth) for monitoring.
    """
    now = datetime.now()
    startup_time = getattr(request.app.state, "startup_time", None)

    uptime = None
    if startup_time:
        uptime = (now - startup_time).total_seconds()

    # Get resource usage
    resources: ResourceUsage | None = None
    if memory_profiler.is_enabled:
        snapshot = memory_profiler.take_snapshot()
        if snapshot:
            resources = ResourceUsage(
                memory_rss_mb=snapshot.rss_mb,
                memory_vms_mb=snapshot.vms_mb,
                memory_percent=snapshot.percent,
                cpu_percent=None,  # Could add CPU tracking in the future
            )

    # Get subprocess stats
    metrics = subprocess_manager.get_metrics()
    subprocess_stats = SubprocessStats(
        active_count=len(metrics.active_processes),
        total_spawned=metrics.total_spawned,
        total_completed=metrics.total_completed,
        total_timeout=metrics.total_timeout,
        total_cancelled=metrics.total_cancelled,
    )

    # Get event queue depth
    queue_depth: int | None = None
    try:
        app_event_bus = getattr(request.app.state, "event_bus", None)
        if app_event_bus and hasattr(app_event_bus, "_subscribers"):
            queue_depth = len(app_event_bus._subscribers)
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        timestamp=now.isoformat(),
        version=__version__,
        uptime_seconds=uptime,
        resources=resources,
        subprocesses=subprocess_stats,
        event_queue_depth=queue_depth,
    )
