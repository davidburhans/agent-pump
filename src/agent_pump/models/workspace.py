"""Workspace configuration models for agent-pump."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .approval_gate_config import ApprovalGateConfig
from .branch_strategy import BranchStrategyConfig
from .cost_tracking import BudgetConfig
from .execution_queue import ExecutionQueueConfig, ExecutionQueueItem, QueuePriority, QueueStatus
from .github_integration import GitHubIntegrationConfig
from .verification_config import VerificationConfig

logger = logging.getLogger(__name__)


class BackendInstance(BaseModel):
    """A backend with its configuration."""

    name: str = Field(default="gemini", description="Backend name (gemini, claude, opencode)")
    args: list[str] = Field(
        default_factory=list,
        description="Extra command-line args (e.g., ['--model', 'gemini-2.5-flash'])",
    )
    timeout: int | None = Field(
        default=None, description="Timeout in seconds (None = use global default)"
    )
    concurrency_limit: int = Field(
        default=1,
        description=(
            "Max concurrent instances sharing this config "
            "(1 = serial execution). Set to 0 for unlimited."
        ),
    )


class BackendFallback(BaseModel):
    """A list of backends to try in order (fallback chain)."""

    backends: list[BackendInstance] = Field(
        default_factory=lambda: [BackendInstance()],
        description="Backends to try in order with their args.",
    )

    @classmethod
    def from_names(cls, names: list[str]) -> "BackendFallback":
        """Create from a simple list of backend names (no args)."""
        return cls(backends=[BackendInstance(name=n) for n in names])


class PhaseBackends(BaseModel):
    """Configure which backends to use for each workflow phase."""

    defaults: BackendFallback = Field(
        default_factory=BackendFallback,
        description="Default fallback chain used when phase-specific chain is empty",
    )
    planning: BackendFallback = Field(default_factory=BackendFallback)
    implementing: BackendFallback = Field(default_factory=BackendFallback)
    verifying: BackendFallback = Field(default_factory=BackendFallback)
    brainstorming: BackendFallback = Field(default_factory=BackendFallback)
    committing: BackendFallback = Field(default_factory=BackendFallback)


class BackendPreset(BaseModel):
    """A named preset for backend configuration (fallback chain)."""

    name: str = Field(description="Display name for the preset")
    backends: BackendFallback = Field(default_factory=BackendFallback)


class PromptCustomization(BaseModel):
    """Custom prompt additions per phase."""

    # Prefix is added BEFORE the standard prompt
    # Suffix is added AFTER the standard prompt
    planning_prefix: str = Field(default="", description="Added before planning prompt")
    planning_suffix: str = Field(default="", description="Added after planning prompt")
    implementing_prefix: str = Field(default="", description="Added before implementing prompt")
    implementing_suffix: str = Field(default="", description="Added after implementing prompt")
    verifying_prefix: str = Field(default="", description="Added before verifying prompt")
    verifying_suffix: str = Field(default="", description="Added after verifying prompt")
    brainstorming_prefix: str = Field(default="", description="Added before brainstorming prompt")
    brainstorming_suffix: str = Field(default="", description="Added after brainstorming prompt")
    committing_prefix: str = Field(default="", description="Added before committing prompt")
    committing_suffix: str = Field(default="", description="Added after committing prompt")

    # Base prompt overrides (empty = use default from base_prompts.py)
    planning_base: str = Field(
        default="", description="Custom base prompt for planning (empty = default)"
    )
    implementing_base: str = Field(
        default="", description="Custom base prompt for implementing (empty = default)"
    )
    verifying_base: str = Field(
        default="", description="Custom base prompt for verifying (empty = default)"
    )
    brainstorming_base: str = Field(
        default="", description="Custom base prompt for brainstorming (empty = default)"
    )
    committing_base: str = Field(
        default="", description="Custom base prompt for committing (empty = default)"
    )

    def get_base_override(self, phase: str) -> str:
        """Get the base prompt override for a phase (empty = use default)."""
        return getattr(self, f"{phase}_base", "")

    def apply_to_prompt(self, phase: str, base_prompt: str) -> str:
        """Apply prefix/suffix to a base prompt for a given phase."""
        prefix = getattr(self, f"{phase}_prefix", "")
        suffix = getattr(self, f"{phase}_suffix", "")
        parts = []
        if prefix:
            parts.append(prefix)
        parts.append(base_prompt)
        if suffix:
            parts.append(suffix)
        return "\n\n".join(parts)


class IdeaQueueItem(BaseModel):
    """An idea queued for the brainstormer to consider."""

    idea: str = Field(description="The feature idea or suggestion")
    added_at: datetime = Field(default_factory=datetime.now)
    priority: int = Field(default=0, description="Higher priority = considered first")
    source: str = Field(default="user", description="Where the idea came from")


class GlobalPromptSettings(BaseModel):
    """Global prompt settings applied across all phases.

    These settings are applied in addition to (not replacing) phase-specific
    prompt customizations. Order of application:
    1. Global engine prefix (if backend engine matches)
    2. Global model prefix (if model matches)
    3. Phase-specific prefix
    4. Base prompt (default or custom)
    5. Phase-specific suffix
    6. Global model suffix
    7. Global engine suffix
    """

    # Per-engine overrides (e.g., "gemini", "claude", "opencode")
    engine_prefixes: dict[str, str] = Field(
        default_factory=dict,
        description="Prefix text per engine name (e.g., {'gemini': 'Use JSON output.'})",
    )
    engine_suffixes: dict[str, str] = Field(
        default_factory=dict,
        description="Suffix text per engine name",
    )
    # Per-model overrides (e.g., "gemini-2.5-flash", "claude-sonnet")
    model_prefixes: dict[str, str] = Field(
        default_factory=dict,
        description="Prefix text per model name (e.g., {'gemini-2.5-flash': 'Be concise.'})",
    )
    model_suffixes: dict[str, str] = Field(
        default_factory=dict,
        description="Suffix text per model name",
    )

    def get_engine_additions(self, engine_name: str) -> tuple[str, str]:
        """Get prefix and suffix for an engine.

        Args:
            engine_name: Backend engine name (e.g., "gemini")

        Returns:
            Tuple of (prefix, suffix) for the engine.
        """
        prefix = self.engine_prefixes.get(engine_name, "")
        suffix = self.engine_suffixes.get(engine_name, "")
        return prefix, suffix

    def get_model_additions(self, model_name: str) -> tuple[str, str]:
        """Get prefix and suffix for a model.

        Args:
            model_name: Model name (e.g., "gemini-2.5-flash")

        Returns:
            Tuple of (prefix, suffix) for the model.
        """
        prefix = self.model_prefixes.get(model_name, "")
        suffix = self.model_suffixes.get(model_name, "")
        return prefix, suffix


class ProjectConfig(BaseModel):
    """Per-project configuration within a workspace."""

    path: Path = Field(description="Absolute path to the project")
    name: str = Field(default="", description="Display name for the project")
    phase_backends: PhaseBackends = Field(default_factory=PhaseBackends)
    prompt_customization: PromptCustomization = Field(default_factory=PromptCustomization)
    verification: VerificationConfig = Field(
        default_factory=VerificationConfig, description="Verification command configuration"
    )
    branch_strategy: BranchStrategyConfig = Field(
        default_factory=BranchStrategyConfig,
        description="Git branch strategy configuration for this project",
    )
    branch: str | None = Field(
        default=None, description="Optional branch to isolate work (legacy, use branch_strategy)"
    )
    min_execution_time_seconds: int = Field(
        default=10,
        description="Minimum execution time for a backend call to be considered successful",
    )
    default_timeout: int = Field(
        default=1800,
        description="Default timeout in seconds for backend execution (default 30m)",
    )
    workflow_name: str = Field(
        default="default",
        description="Name of workflow definition to use (default = built-in 5-phase)",
    )
    default_chain: BackendFallback | None = Field(
        default=None,
        description="Default backend chain for phases that don't specify one",
    )
    idea_queue: list[IdeaQueueItem] = Field(
        default_factory=list,
        description="Ideas to feed to the brainstormer for this project",
    )
    approval_gate: ApprovalGateConfig = Field(
        default_factory=ApprovalGateConfig,
        description="Approval gate configuration for this project",
    )
    github_integration: GitHubIntegrationConfig = Field(
        default_factory=GitHubIntegrationConfig,
        description=(
            "GitHub integration settings for PR creation, issue linking, and status updates"
        ),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_post_init(self, __context) -> None:
        """Set name from path if not provided."""
        if not self.name:
            self.name = self.path.name or str(self.path)


class Workspace(BaseModel):
    """A workspace configuration with projects and settings."""

    name: str = Field(default="default", description="Workspace name")
    projects: dict[str, ProjectConfig] = Field(
        default_factory=dict,
        description="Project configurations keyed by resolved path string",
    )
    idea_queue: list[IdeaQueueItem] = Field(
        default_factory=list,
        description="Ideas to feed to the brainstormer",
    )
    default_phase_backends: PhaseBackends = Field(
        default_factory=PhaseBackends,
        description="Default backend config for new projects",
    )
    global_prompt_settings: GlobalPromptSettings = Field(
        default_factory=GlobalPromptSettings,
        description="Global prompt prefix/suffix per engine and model",
    )
    backend_presets: dict[str, BackendPreset] = Field(
        default_factory=dict,
        description="Named backend presets (name -> preset)",
    )
    workflow_definitions: dict[str, dict] = Field(
        default_factory=dict,
        description="Custom workflow definitions (name -> WorkflowDefinition as dict)",
    )
    notifications_enabled: bool = Field(
        default=True, description="Enable desktop notifications for workflow events"
    )
    execution_queue: list[ExecutionQueueItem] = Field(
        default_factory=list,
        description="Queue of projects waiting to execute",
    )
    execution_queue_config: ExecutionQueueConfig = Field(
        default_factory=ExecutionQueueConfig,
        description="Execution queue configuration",
    )
    budget_config: BudgetConfig = Field(
        default_factory=BudgetConfig,
        description="Budget configuration for cost tracking",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def get_workspaces_dir(cls) -> Path:
        """Get the directory where workspaces are stored."""
        workspaces_dir = Path.home() / ".config" / "agent-pump" / "workspaces"
        workspaces_dir.mkdir(parents=True, exist_ok=True)
        return workspaces_dir

    @classmethod
    def get_workspace_path(cls, name: str) -> Path:
        """Get the path for a workspace file."""
        return cls.get_workspaces_dir() / f"{name}.json"

    @classmethod
    def load(cls, name: str = "default") -> "Workspace":
        """Load a workspace from disk, or return a new empty workspace."""
        workspace_path = cls.get_workspace_path(name)
        if workspace_path.exists():
            try:
                content = workspace_path.read_text(encoding="utf-8")
                return cls.model_validate_json(content)
            except Exception as e:
                logger.error(f"Failed to load workspace '{name}' from {workspace_path}: {e}")
                return cls(name=name)
        return cls(name=name)

    @classmethod
    async def load_async(cls, name: str = "default") -> "Workspace":
        """Load a workspace from disk asynchronously."""
        return await asyncio.to_thread(cls.load, name)

    @classmethod
    def list_workspaces(cls) -> list[str]:
        """List all available workspace names."""
        workspaces_dir = cls.get_workspaces_dir()
        return [p.stem for p in workspaces_dir.glob("*.json")]

    @classmethod
    def delete(cls, name: str) -> bool:
        """
        Delete a workspace file.

        Args:
            name: The name of the workspace to delete.

        Returns:
            True if the workspace was deleted, False if it didn't exist.
        """
        workspace_path = cls.get_workspace_path(name)
        if workspace_path.exists():
            try:
                workspace_path.unlink()
                logger.info(f"Deleted workspace '{name}' from {workspace_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete workspace '{name}' from {workspace_path}: {e}")
                return False
        return False

    def save(self) -> None:
        """Save workspace to disk."""
        self.last_modified = datetime.now()
        workspace_path = self.get_workspace_path(self.name)
        try:
            workspace_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
            logger.info(f"Saved workspace '{self.name}' to {workspace_path}")
        except Exception as e:
            logger.error(f"Failed to save workspace '{self.name}' to {workspace_path}: {e}")

    def add_project(self, path: Path, config: ProjectConfig | None = None) -> bool:
        """
        Add a project to the workspace.

        Returns:
            True if added, False if already exists.
        """
        key = str(path.resolve())
        if key in self.projects:
            return False

        if config is None:
            config = ProjectConfig(
                path=path.resolve(), phase_backends=self.default_phase_backends.model_copy()
            )

        self.projects[key] = config
        return True

    def remove_project(self, path: Path) -> bool:
        """
        Remove a project from the workspace.

        Returns:
            True if removed, False if not found.
        """
        key = str(path.resolve())
        if key in self.projects:
            del self.projects[key]
            return True
        return False

    def get_project_config(self, path: Path) -> ProjectConfig | None:
        """Get the configuration for a project."""
        key = str(path.resolve())
        return self.projects.get(key)

    def add_idea(self, idea: str, priority: int = 0, source: str = "user") -> None:
        """Add an idea to the queue."""
        item = IdeaQueueItem(idea=idea, priority=priority, source=source)
        self.idea_queue.append(item)
        # Sort by priority (highest first)
        self.idea_queue.sort(key=lambda x: x.priority, reverse=True)

    def pop_ideas(self, count: int = 5) -> list[str]:
        """
        Pop the top N ideas from the queue.

        Returns:
            List of idea strings (up to count).
        """
        ideas = [item.idea for item in self.idea_queue[:count]]
        self.idea_queue = self.idea_queue[count:]
        return ideas

    def peek_ideas(self, count: int = 5) -> list[str]:
        """
        Peek at the top N ideas without removing them.

        Returns:
            List of idea strings (up to count).
        """
        return [item.idea for item in self.idea_queue[:count]]

    # Execution Queue Management Methods

    def get_active_projects_count(self) -> int:
        """Count how many projects are currently executing."""
        return sum(1 for item in self.execution_queue if item.is_active)

    def can_start_project(self) -> bool:
        """Check if a new project can be started based on concurrency limits."""
        if not self.execution_queue_config.has_limit:
            return True
        return self.get_active_projects_count() < self.execution_queue_config.max_concurrent

    def get_queued_projects(self) -> list[ExecutionQueueItem]:
        """Get all queued (pending) projects sorted by priority and position."""
        queued = [item for item in self.execution_queue if item.is_pending]
        # Sort by priority (desc), then by position (asc) for stable ordering
        return sorted(queued, key=lambda x: (-x.priority.value, x.position))

    def get_queue_position(self, path: Path) -> int | None:
        """Get the position of a project in the queue (1-indexed).

        Returns:
            Position in queue (1 = first), or None if not queued.
        """
        queued = self.get_queued_projects()
        for i, item in enumerate(queued, 1):
            if item.project_path == path:
                return i
        return None

    def queue_project(
        self, path: Path, priority: QueuePriority = QueuePriority.MEDIUM
    ) -> ExecutionQueueItem:
        """Add a project to the execution queue.

        Args:
            path: Project path
            priority: Queue priority (default: MEDIUM)

        Returns:
            The created queue item
        """
        path = path.resolve()
        # Check if already in queue
        existing = next(
            (
                item
                for item in self.execution_queue
                if item.project_path == path and item.is_pending
            ),
            None,
        )
        if existing:
            # Update priority if already queued
            idx = self.execution_queue.index(existing)
            self.execution_queue[idx] = existing.update_priority(priority)
            return self.execution_queue[idx]

        # Create new queue item with next position
        max_position = max((item.position for item in self.execution_queue), default=0)
        item = ExecutionQueueItem(
            project_path=path,
            priority=priority,
            position=max_position + 1,
        )
        self.execution_queue.append(item)
        return item

    def dequeue_project(self, path: Path) -> ExecutionQueueItem | None:
        """Remove a project from the queue.

        Args:
            path: Project path to remove

        Returns:
            The removed item, or None if not found
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_pending:
                removed = self.execution_queue.pop(i)
                return removed
        return None

    def get_next_queued_project(self) -> ExecutionQueueItem | None:
        """Get the next project to execute from the queue.

        Returns:
            The next queue item, or None if queue is empty
        """
        queued = self.get_queued_projects()
        return queued[0] if queued else None

    def mark_project_active(self, path: Path) -> ExecutionQueueItem | None:
        """Mark a queued project as active.

        Args:
            path: Project path

        Returns:
            The updated item, or None if not found
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_pending:
                self.execution_queue[i] = item.mark_active()
                return self.execution_queue[i]
        return None

    def mark_project_completed(self, path: Path) -> ExecutionQueueItem | None:
        """Mark an active project as completed.

        Args:
            path: Project path

        Returns:
            The updated item, or None if not found
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_active:
                self.execution_queue[i] = item.mark_completed()
                return self.execution_queue[i]
        return None

    def mark_project_failed(self, path: Path) -> ExecutionQueueItem | None:
        """Mark an active project as failed.

        Args:
            path: Project path

        Returns:
            The updated item, or None if not found
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_active:
                self.execution_queue[i] = item.mark_failed()
                return self.execution_queue[i]
        return None

    def cancel_queued_project(self, path: Path) -> ExecutionQueueItem | None:
        """Cancel a queued project.

        Args:
            path: Project path

        Returns:
            The cancelled item, or None if not found
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_pending:
                self.execution_queue[i] = item.mark_cancelled()
                return self.execution_queue[i]
        return None

    def cleanup_completed_queue_items(self, max_age_hours: int = 24) -> int:
        """Remove completed/failed/cancelled items older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours (default: 24)

        Returns:
            Number of items removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        to_remove = [
            i
            for i, item in enumerate(self.execution_queue)
            if item.status in (QueueStatus.COMPLETED, QueueStatus.FAILED, QueueStatus.CANCELLED)
            and item.queued_at < cutoff
        ]
        # Remove in reverse order to maintain indices
        for i in reversed(to_remove):
            self.execution_queue.pop(i)
        return len(to_remove)

    def reorder_queued_project(
        self, path: Path, new_priority: QueuePriority
    ) -> ExecutionQueueItem | None:
        """Change the priority of a queued project.

        Args:
            path: Project path
            new_priority: New priority level

        Returns:
            The updated item, or None if not found or not queued
        """
        path = path.resolve()
        for i, item in enumerate(self.execution_queue):
            if item.project_path == path and item.is_pending:
                self.execution_queue[i] = item.update_priority(new_priority)
                return self.execution_queue[i]
        return None
