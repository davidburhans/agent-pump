import json
from datetime import UTC, time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.models.schedule import Schedule, ScheduleType
from agent_pump.scheduling.scheduler import WorkflowScheduler
from agent_pump.services.project_service import ProjectService


@pytest.fixture
def mock_project_service():
    service = MagicMock(spec=ProjectService)
    service.workflows = {}
    return service


@pytest.fixture
def temp_schedule_file(tmp_path):
    return tmp_path / "schedules.json"


@pytest.fixture
def scheduler(mock_project_service, temp_schedule_file):
    with patch("agent_pump.scheduling.scheduler.AsyncScheduler") as MockScheduler:
        # Mock instance
        mock_instance = AsyncMock()
        MockScheduler.return_value = mock_instance

        # AsyncScheduler 4.0 usage mock
        # Mock context manager methods on the scheduler instance itself
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)

        # start_in_background is async method returning None
        mock_instance.start_in_background = AsyncMock(return_value=None)

        # Create scheduler
        scheduler = WorkflowScheduler(mock_project_service)
        scheduler.scheduler = mock_instance # Ensure we use the mock

        # Patch _schedule_file property
        with patch.object(WorkflowScheduler, "_schedule_file", new=temp_schedule_file):
            yield scheduler


@pytest.mark.asyncio
async def test_add_schedule(scheduler):
    """Test adding a schedule."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.INTERVAL,
        interval_minutes=60
    )

    # Mock _create_trigger to avoid complexity
    with patch.object(scheduler, "_create_trigger", return_value=MagicMock()):
        await scheduler.add_schedule(schedule)

    # Verify added to dict
    assert schedule.id in scheduler.schedules

    # Verify saved to disk (check file content)
    assert scheduler._schedule_file.exists()
    content = scheduler._schedule_file.read_text()
    data = json.loads(content)
    assert len(data) == 1
    assert data[0]["id"] == schedule.id


@pytest.mark.asyncio
async def test_remove_schedule(scheduler):
    """Test removing a schedule."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.INTERVAL,
        interval_minutes=60
    )
    scheduler.schedules[schedule.id] = schedule
    # Create file
    data = [schedule.model_dump(mode="json")]
    scheduler._schedule_file.write_text(json.dumps(data))

    # Mock scheduler.remove_schedule
    scheduler.scheduler.remove_schedule = AsyncMock()

    await scheduler.remove_schedule(schedule.id)

    assert schedule.id not in scheduler.schedules

    # Verify file updated
    content = scheduler._schedule_file.read_text()
    data = json.loads(content)
    assert len(data) == 0


@pytest.mark.asyncio
async def test_load_schedules(scheduler):
    """Test loading schedules from disk."""
    schedule = Schedule(
        project_id="p1",
        schedule_type=ScheduleType.CRON,
        cron_expression="* * * * *"
    )
    data = [schedule.model_dump(mode="json")]
    scheduler._schedule_file.write_text(json.dumps(data))

    # Clear memory
    scheduler.schedules = {}

    await scheduler._load_schedules()

    assert len(scheduler.schedules) == 1
    assert scheduler.schedules[schedule.id].id == schedule.id


@pytest.mark.asyncio
async def test_start(scheduler):
    """Test starting the scheduler."""
    schedule = Schedule(
        project_id="p1",
        schedule_type=ScheduleType.CRON,
        cron_expression="* * * * *"
    )
    data = [schedule.model_dump(mode="json")]
    scheduler._schedule_file.write_text(json.dumps(data))

    # Mock _schedule_job
    scheduler._schedule_job = AsyncMock()

    await scheduler.start()

    # Verify loaded
    assert len(scheduler.schedules) == 1

    # Verify start called
    scheduler.scheduler.start_in_background.assert_called_once()

    # Verify jobs rescheduled
    scheduler._schedule_job.assert_called_once()


@pytest.mark.asyncio
async def test_run_workflow(scheduler):
    """Test running a workflow."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.CRON,
        cron_expression="* * * * *"
    )
    scheduler.schedules[schedule.id] = schedule

    # Mock project service
    mock_workflow = MagicMock()
    mock_workflow.is_running.return_value = False
    mock_workflow.start = AsyncMock()

    scheduler.project_service.workflows = {Path("/path/to/project"): mock_workflow}

    # Mock save
    scheduler._save_schedules = AsyncMock()

    await scheduler._run_workflow("/path/to/project", schedule.id)

    # Verify ran
    mock_workflow.start.assert_called_once()
    assert schedule.run_count == 1
    assert schedule.last_run is not None


@pytest.mark.asyncio
async def test_run_workflow_working_hours(scheduler):
    """Test working hours constraint."""
    schedule = Schedule(
        project_id="/path/to/project",
        schedule_type=ScheduleType.CRON,
        cron_expression="* * * * *",
        working_hours_only=True,
        working_hours_start=time(9, 0),
        working_hours_end=time(17, 0),
        timezone="UTC"
    )
    scheduler.schedules[schedule.id] = schedule

    mock_workflow = MagicMock()
    mock_workflow.is_running.return_value = False
    mock_workflow.start = AsyncMock()
    scheduler.project_service.workflows = {Path("/path/to/project"): mock_workflow}

    # Mock datetime.now
    # We mock agent_pump.scheduling.scheduler.datetime because it's imported there

    from datetime import datetime

    # Case 1: Weekend (Saturday)
    # 2023-10-21 is Saturday
    dt_weekend = datetime(2023, 10, 21, 10, 0, tzinfo=UTC)

    with patch("agent_pump.scheduling.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt_weekend
        # side_effect for other calls if any? No, only now() used.
        # But wait, datetime.time() or datetime.combine() might be used? No.

        await scheduler._run_workflow("/path/to/project", schedule.id)
        mock_workflow.start.assert_not_called()

    # Case 2: Weekday but early (Monday 8 AM)
    # 2023-10-23 is Monday
    dt_early = datetime(2023, 10, 23, 8, 0, tzinfo=UTC)

    with patch("agent_pump.scheduling.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt_early
        await scheduler._run_workflow("/path/to/project", schedule.id)
        mock_workflow.start.assert_not_called()

    # Case 3: Weekday working hours (Monday 10 AM)
    dt_working = datetime(2023, 10, 23, 10, 0, tzinfo=UTC)

    with patch("agent_pump.scheduling.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = dt_working
        await scheduler._run_workflow("/path/to/project", schedule.id)
        mock_workflow.start.assert_called_once()
