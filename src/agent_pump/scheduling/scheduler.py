import json
import logging
import zoneinfo
from datetime import datetime
from pathlib import Path

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from agent_pump.models.schedule import Schedule, ScheduleType
from agent_pump.services.project_service import ProjectService

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Scheduler for automated workflow runs."""

    def __init__(self, project_service: ProjectService) -> None:
        """Initialize the scheduler."""
        self.scheduler = AsyncScheduler()
        self.project_service = project_service
        self.schedules: dict[str, Schedule] = {}
        self._scheduler_cm = None

    @property
    def _schedule_file(self) -> Path:
        """Path to the schedule file."""
        config_dir = Path.home() / ".config" / "agent-pump"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "schedules.json"

    async def start(self) -> None:
        """Start the scheduler and load saved schedules."""
        await self._load_schedules()

        # Start the scheduler in background context manager
        self._scheduler_cm = self.scheduler.start_in_background()
        await self._scheduler_cm.__aenter__()

        # Re-schedule loaded jobs
        for schedule in self.schedules.values():
            if schedule.enabled:
                await self._schedule_job(schedule)

    async def stop(self) -> None:
        """Stop the scheduler."""
        if self._scheduler_cm:
            await self._scheduler_cm.__aexit__(None, None, None)

    async def add_schedule(self, schedule: Schedule) -> None:
        """Add a new schedule."""
        self.schedules[schedule.id] = schedule
        if schedule.enabled:
            await self._schedule_job(schedule)
        else:
            # If disabled, ensure job is removed
            try:
                await self.scheduler.remove_schedule(schedule.id)
            except LookupError:
                pass
        await self._save_schedules()

    async def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a schedule by ID."""
        if schedule_id in self.schedules:
            # Stop the job if running
            try:
                await self.scheduler.remove_schedule(schedule_id)
            except LookupError:
                pass # Job might not exist if disabled or not started

            del self.schedules[schedule_id]
            await self._save_schedules()
            return True
        return False

    def get_schedule(self, schedule_id: str) -> Schedule | None:
        """Get a schedule by ID."""
        return self.schedules.get(schedule_id)

    def list_schedules(self) -> list[Schedule]:
        """List all schedules."""
        return list(self.schedules.values())

    async def _load_schedules(self) -> None:
        """Load schedules from disk."""
        if self._schedule_file.exists():
            try:
                content = self._schedule_file.read_text(encoding="utf-8")
                data = json.loads(content)
                for item in data:
                    try:
                        schedule = Schedule.model_validate(item)
                        self.schedules[schedule.id] = schedule
                    except Exception as e:
                        logger.error(f"Failed to validate schedule item: {e}")
            except Exception as e:
                logger.error(f"Failed to load schedules: {e}")

    async def _save_schedules(self) -> None:
        """Save schedules to disk."""
        data = [s.model_dump(mode="json") for s in self.schedules.values()]
        try:
            self._schedule_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save schedules: {e}")

    async def _schedule_job(self, schedule: Schedule) -> None:
        """Schedule the job in APScheduler."""
        trigger = self._create_trigger(schedule)

        # Remove existing if any (update)
        try:
            await self.scheduler.remove_schedule(schedule.id)
        except LookupError:
            pass

        await self.scheduler.add_schedule(
            self._run_workflow,
            trigger,
            id=schedule.id,
            kwargs={"project_id": schedule.project_id, "schedule_id": schedule.id}
        )

    def _create_trigger(self, schedule: Schedule):
        """Create an APScheduler trigger from the schedule."""
        if schedule.schedule_type == ScheduleType.CRON:
            return CronTrigger.from_crontab(
                schedule.cron_expression,
                timezone=schedule.timezone
            )
        elif schedule.schedule_type == ScheduleType.INTERVAL:
            return IntervalTrigger(minutes=schedule.interval_minutes)
        elif schedule.schedule_type == ScheduleType.ONE_TIME:
            from apscheduler.triggers.date import DateTrigger
            return DateTrigger(run_time=schedule.run_at)

        raise ValueError(f"Unknown schedule type: {schedule.schedule_type}")

    async def _run_workflow(self, project_id: str, schedule_id: str) -> None:
        """Called by scheduler when it's time to run."""
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return

        # Check working hours constraint
        if schedule.working_hours_only:
            if not self._is_working_hours(schedule):
                logger.info(f"Skipping scheduled run for {project_id}: outside working hours")
                return

        project_path = Path(project_id)
        orchestrator = self.project_service.workflows.get(project_path)

        # If workflow not loaded, try to ensure project is loaded
        if not orchestrator:
            # Try to load project
            if project_path.exists():
                logger.info(f"Loading project for scheduled run: {project_id}")
                try:
                    await self.project_service.add_project(project_path)
                    orchestrator = self.project_service.workflows.get(project_path)
                except Exception as e:
                    logger.error(f"Failed to load project {project_id} for scheduled run: {e}")
                    return
            else:
                logger.warning(f"Project path not found: {project_id}")
                return

        if orchestrator and orchestrator.is_running():
            logger.info(f"Skipping scheduled run for {project_id}: already running")
            return

        # Start workflow
        logger.info(f"Starting scheduled workflow run for {project_id}")

        # Update metadata
        schedule.last_run = datetime.now()
        schedule.run_count += 1
        await self._save_schedules()

        # Run!
        # Assuming orchestrator.start() starts the workflow.
        # It's an async method.
        # We might want to run it in background or await it?
        # APScheduler jobs are async, so awaiting it blocks this job execution, which is fine.
        await orchestrator.start()

    def _is_working_hours(self, schedule: Schedule) -> bool:
        """Check if current time is within working hours."""
        # Get current time in schedule's timezone
        try:
            tz = zoneinfo.ZoneInfo(schedule.timezone)
        except Exception:
            # Fallback to UTC if invalid timezone
            tz = zoneinfo.ZoneInfo("UTC")

        now = datetime.now(tz)

        # Check day of week (Mon=0, Sun=6)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        current_time = now.time()
        return schedule.working_hours_start <= current_time <= schedule.working_hours_end
