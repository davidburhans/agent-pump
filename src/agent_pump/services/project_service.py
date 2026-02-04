"""Project management service."""

import logging
from pathlib import Path

import yaml

from agent_pump.api.schemas import ProjectStatusDTO
from agent_pump.backends import get_backend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.config import Config
from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    ProjectAddedEvent,
    ProjectRemovedEvent,
)
from agent_pump.models.app_state import AppState
from agent_pump.models.project import Project
from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class ProjectService(BaseService):
    """Service for managing projects and their workflows."""

    def __init__(self, event_bus: EventBus, workspace: Workspace, app_state: AppState) -> None:
        """
        Initialize the project service.

        Args:
            event_bus: The event bus.
            workspace: The current workspace.
            app_state: The global app state.
        """
        super().__init__(event_bus)
        self.workspace = workspace
        self.app_state = app_state
        self.projects: dict[Path, Project] = {}
        self.workflows: dict[Path, ProjectWorkflow] = {}

    async def add_project(self, path: Path) -> Project:
        """
        Add a project to the workspace and initialize its workflow.

        Args:
            path: Absolute path to the project directory.

        Returns:
            The initialized Project object.
        """
        path = path.resolve()
        if path in self.projects:
            logger.info(f"Project already loaded: {path}")
            return self.projects[path]

        try:
            # Load project model
            project = Project.from_path(path)
            self.projects[path] = project

            # Load configuration
            config = Config.load(path)
            project.branch = config.workflow.branch
            project.backend = config.backend
            project.config = config.verification

            # Get workspace-level config overrides
            project_config = self.workspace.get_project_config(path)
            phase_backends = project_config.phase_backends if project_config else None
            prompt_customization = project_config.prompt_customization if project_config else None

            # Initialize idea queue
            idea_queue = []
            if project_config and project_config.idea_queue:
                idea_queue = [item.idea for item in project_config.idea_queue]
            elif not project_config:
                idea_queue = self.workspace.peek_ideas()

            # determine backend
            backend = GeminiBackend()
            if project_config and project_config.phase_backends.implementing.backends:
                try:
                    backend_instance = project_config.phase_backends.implementing.backends[0]
                    backend = get_backend(backend_instance.name)
                except ValueError:
                    pass

            # Determine workflow definition
            # 1. Check for project-local workflow definition (.agent-pump/workflow.yaml)
            # If not found, scaffold it!
            agent_pump_dir = path / ".agent-pump"
            if not agent_pump_dir.exists():
                logger.info(f"Scaffolding .agent-pump directory for {path}")
                agent_pump_dir.mkdir(parents=True, exist_ok=True)

            local_workflow_path = agent_pump_dir / "workflow.yaml"
            from agent_pump.orchestrator.workflow_definition import (
                DEFAULT_WORKFLOW,
                WorkflowDefinition,
            )

            if not local_workflow_path.exists():
                logger.info(f"Scaffolding default workflow.yaml for {path}")
                local_workflow_path.write_text(
                    yaml.dump(DEFAULT_WORKFLOW.model_dump(exclude_none=True), sort_keys=False),
                    encoding="utf-8",
                )

            workflow_file = local_workflow_path

            # Ensure state prompts exist
            states_dir = agent_pump_dir / "states"
            states_dir.mkdir(exist_ok=True)

            # Ensure backends directory exists
            backends_dir = agent_pump_dir / "backends"
            backends_dir.mkdir(exist_ok=True)

            # Helper to write prompt file if missing
            def ensure_prompt(name: str, content: str):
                p = states_dir / f"{name}.md"
                if not p.exists():
                    p.write_text(content, encoding="utf-8")

            # Scaffold default prompts based on the current DEFAULT_WORKFLOW logic
            # This is a bit of duplication from prompts.py, but essential for
            # "ejecting" to file-based.
            # However, if we write them, we should probably update the workflow.json
            # to use "generic" builder?
            # Or we keep using the python builder which serves as a default if the
            # file is missing/empty?
            # The current architecture (Loader) uses the file if present as BASE.
            # So if we write the files, the Python builder output becomes ignored (fallback only).
            # So we can just write the files!

            # We need to get the "default" text.
            # Ideally we'd invoke the builders to get the text, but builders require context.
            # We'll use a simplified version of the defaults here for scaffolding.

            ensure_prompt(
                "planning",
                """Create a detailed engineering plan to implement the requested feature.

Context:
- Current ROADMAP.md: {{ read_file('ROADMAP.md') }}
- Current ENGINEERING_PLAN.md: {{ read_file('ENGINEERING_PLAN.md') }}

Feature Request:
{{ read_file('TASK_NAME') }}

Requirements:
1. Format as ENGINEERING_PLAN.md with:
   - Feature description and goals
   - Detailed task list with checkboxes
   - Each task should be small and actionable
   - Include tasks for: implementation, testing, documentation
   - THE FINAL TASK MUST BE: (
      "Reflect on the work done and update BEST_PRACTICES.md with any "
      "lessons learned, and check if README.md needs updates as a result"
   )
6. Create a TASK_NAME file containing ONLY the exact title of the feature you are working on.


Be thorough but concise. The task list will guide the implementation phase.""",
            )

            ensure_prompt(
                "implementing",
                """Execute the tasks in ENGINEERING_PLAN.md.

Context:
- Current ROADMAP.md: {{ read_file('ROADMAP.md') }}
- Current ENGINEERING_PLAN.md: {{ read_file('ENGINEERING_PLAN.md') }}
- Current TASK_NAME: {{ read_file('TASK_NAME') }}

Requirements:
1. Follow the task list exactly
2. Update code, tests, documentation as needed
3. Maintain code quality and best practices
4. Keep changes focused on the current task
5. Update BEST_PRACTICES.md with any lessons learned during implementation""",
            )

            ensure_prompt(
                "verifying",
                """Verify the implementation by running verification commands and
fixing any issues.

Context:
- Current ROADMAP.md: {{ read_file('ROADMAP.md') }}
- Current ENGINEERING_PLAN.md: {{ read_file('ENGINEERING_PLAN.md') }}
- Current TASK_NAME: {{ read_file('TASK_NAME') }}

Requirements:
1. Run build, lint, and test commands as configured for this project
2. Fix any issues that arise
3. Ensure all verification commands pass
4. Update BEST_PRACTICES.md with any lessons learned during verification""",
            )

            ensure_prompt(
                "brainstorming",
                """Brainstorm the next feature to work on based on current state.

Context:
- Current ROADMAP.md: {{ read_file('ROADMAP.md') }}
- Current ENGINEERING_PLAN.md: {{ read_file('ENGINEERING_PLAN.md') }}
- Current TASK_NAME: {{ read_file('TASK_NAME') }}
- Queued Ideas:
  {{ queued_ideas | tojson(indent=2) }}

Your task:
1. Review the feature you just implemented
2. Update ROADMAP.md:
   - Remove the completed feature from the list (do not just mark it as complete, remove it
     entirely to keep the roadmap focused)
   - Ensure the "current Sprint" pointers match the new top priority
3. Documentation:
   - Check if FEATURES.md exists. If not, create it.
   - FEATURES.md should contain a list of features with:
     - Feature Name
     - Description (what it does)
     - Status (planned, in-progress, completed)
     - Link to relevant documentation
4. Update BEST_PRACTICES.md with any lessons learned during brainstorming""",
            )

            ensure_prompt(
                "committing",
                """Commit the changes with appropriate git commit messages.

Context:
- Current ROADMAP.md: {{ read_file('ROADMAP.md') }}
- Current ENGINEERING_PLAN.md: {{ read_file('ENGINEERING_PLAN.md') }}
- Current TASK_NAME: {{ read_file('TASK_NAME') }}

Requirements:
1. Create a meaningful commit message based on the changes
2. Include reference to the feature being implemented
3. Follow conventional commit format
4. Update BEST_PRACTICES.md with any lessons learned during committing""",
            )

            # Load the workflow definition (now guaranteed to exist)
            try:
                content = workflow_file.read_text(encoding="utf-8")
                workflow_def = WorkflowDefinition.model_validate(yaml.safe_load(content))
            except Exception as e:
                logger.error(f"Failed to load local workflow {workflow_file}: {e}")

            # 2. Check for workspace config override (if local not found or override desired?)
            # Usually local file > workspace config > default
            if workflow_def == DEFAULT_WORKFLOW and project_config and project_config.workflow_name:
                from agent_pump.orchestrator.workflow_definition import get_workflow

                try:
                    workflow_def = get_workflow(
                        project_config.workflow_name, self.workspace.workflow_definitions
                    )
                except KeyError:
                    logger.warning(
                        f"Workflow '{project_config.workflow_name}' not found, using default."
                    )

            # Initialize workflow
            workflow = ProjectWorkflow(
                project=project,
                backend=backend,
                event_bus=self.event_bus,
                config=config,
                project_config=project_config,
                phase_backends=phase_backends,
                prompt_customization=prompt_customization,
                idea_queue=idea_queue,
                workflow_def=workflow_def,
            )
            # Add logging adapter as a listener or handle via on_output?
            # Creating a wrapper for on_output to emit LogEntryEvent
            # But wait, LogPanel expects synchronous updates?
            # For now, let's just initialize it.
            # The TUI refactor will handle log integration properly.

            self.workflows[path] = workflow

            # Persist to workspace/app_state
            self.app_state.add_project(path)
            self.app_state.save()
            self.workspace.add_project(path)
            self.workspace.save()

            logger.info(f"Added project: {project.name}")
            await self.event_bus.publish(ProjectAddedEvent(project_path=path))

            return project

        except Exception as e:
            logger.error(f"Failed to add project {path}: {e}")
            if path in self.projects:
                del self.projects[path]
            raise

    async def remove_project(self, path: Path) -> bool:
        """
        Remove a project from the workspace.

        Args:
            path: Path to the project.

        Returns:
            True if removed, False if not found.
        """
        path = path.resolve()
        if path not in self.projects:
            return False

        # Cancel workflow if running
        workflow = self.workflows.get(path)
        if workflow and workflow.is_running():
            workflow.cancel()

        # Cleanup
        del self.projects[path]
        if path in self.workflows:
            del self.workflows[path]

        # Update persistence
        self.app_state.remove_project(path)
        self.app_state.save()
        self.workspace.remove_project(path)
        self.workspace.save()

        logger.info(f"Removed project: {path}")
        await self.event_bus.publish(ProjectRemovedEvent(project_path=path))
        return True

    def get_project(self, path: Path) -> Project | None:
        """Get project by path."""
        return self.projects.get(path.resolve())

    def list_projects(self) -> list[Project]:
        """List all managed projects."""
        return list(self.projects.values())

    def get_project_status(self, path: Path) -> ProjectStatusDTO | None:
        """Get status DTO for a project."""
        path = path.resolve()
        project = self.projects.get(path)
        if not project:
            return None

        return ProjectStatusDTO.from_internal(project)
