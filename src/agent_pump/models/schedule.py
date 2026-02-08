from datetime import datetime, time
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field
from tzlocal import get_localzone_name


class ScheduleType(str, Enum):
    """Type of schedule."""

    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"


class Schedule(BaseModel):
    """Schedule configuration for a project workflow."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    enabled: bool = True
    schedule_type: ScheduleType

    # For cron: "0 2 * * *" (2 AM daily)
    cron_expression: str | None = None

    # For interval: run every N minutes
    interval_minutes: int | None = None

    # For one-time: specific datetime
    run_at: datetime | None = None

    # Constraints
    timezone: str = Field(default_factory=get_localzone_name)
    working_hours_only: bool = False
    working_hours_start: time = time(9, 0)
    working_hours_end: time = time(17, 0)
    max_queue_depth: int = 3  # Don't queue more than N runs

    # Metadata
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
