"""Workspace configuration models for agent-pump."""

import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackendInstance(BaseModel):
    """A backend with its configuration."""

    name: str = Field(default="gemini", description="Backend name (gemini, claude, opencode)")
    args: list[str] = Field(
        default_factory=list,
        description="Extra command-line args (e.g., ['--model', 'gemini-2.5-flash'])",
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

    planning: BackendFallback = Field(default_factory=BackendFallback)
    implementing: BackendFallback = Field(default_factory=BackendFallback)
    verifying: BackendFallback = Field(default_factory=BackendFallback)
    brainstorming: BackendFallback = Field(default_factory=BackendFallback)
    committing: BackendFallback = Field(default_factory=BackendFallback)


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


class ProjectConfig(BaseModel):
    """Per-project configuration within a workspace."""

    path: Path = Field(description="Absolute path to the project")
    name: str = Field(default="", description="Display name for the project")
    phase_backends: PhaseBackends = Field(default_factory=PhaseBackends)
    prompt_customization: PromptCustomization = Field(default_factory=PromptCustomization)
    branch: str | None = Field(default=None, description="Optional branch to isolate work")
    min_execution_time_seconds: int = Field(
        default=10,
        description="Minimum execution time for a backend call to be considered successful",
    )

    model_config = {"arbitrary_types_allowed": True}

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
    created_at: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}

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
    def list_workspaces(cls) -> list[str]:
        """List all available workspace names."""
        workspaces_dir = cls.get_workspaces_dir()
        return [p.stem for p in workspaces_dir.glob("*.json")]

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
            config = ProjectConfig(path=path.resolve(), phase_backends=self.default_phase_backends.model_copy())

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
