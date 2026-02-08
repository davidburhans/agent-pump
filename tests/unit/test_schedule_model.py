from datetime import datetime, time

import pytest
from pydantic import ValidationError

from agent_pump.models.schedule import Schedule, ScheduleType


def test_schedule_creation_cron():
    """Test creating a cron schedule."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.CRON,
        cron_expression="0 2 * * *"
    )
    assert schedule.project_id == "/path/to/project"
    assert schedule.schedule_type == ScheduleType.CRON
    assert schedule.cron_expression == "0 2 * * *"
    assert schedule.enabled is True
    assert schedule.timezone is not None  # It defaults to local timezone
    assert schedule.id is not None


def test_schedule_creation_interval():
    """Test creating an interval schedule."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.INTERVAL,
        interval_minutes=60
    )
    assert schedule.schedule_type == ScheduleType.INTERVAL
    assert schedule.interval_minutes == 60


def test_schedule_creation_one_time():
    """Test creating a one-time schedule."""
    now = datetime.now()
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.ONE_TIME,
        run_at=now
    )
    assert schedule.schedule_type == ScheduleType.ONE_TIME
    assert schedule.run_at == now


def test_schedule_defaults():
    """Test default values."""
    schedule = Schedule(
        project_id="test",
        schedule_type=ScheduleType.CRON
    )
    assert schedule.working_hours_only is False
    assert schedule.working_hours_start == time(9, 0)
    assert schedule.working_hours_end == time(17, 0)
    assert schedule.max_queue_depth == 3
    assert schedule.run_count == 0


def test_schedule_validation_failure():
    """Test validation failure (missing required fields)."""
    with pytest.raises(ValidationError):
        Schedule(schedule_type=ScheduleType.CRON)  # Missing project_id
