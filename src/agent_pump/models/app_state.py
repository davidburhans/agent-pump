"""Application state model for global persistence."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AppState(BaseModel):
    """Global application state persisted to disk."""

    projects: list[Path] = Field(default_factory=list, description="List of managed project paths")
    current_workspace: str = Field(default="default", description="Name of the current workspace")
    log_sort_order: str = Field(default="desc", description="Log sort order: 'asc' or 'desc'")

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def get_state_path(cls) -> Path:
        """Get the path to the global state file."""
        config_dir = Path.home() / ".config" / "agent-pump"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "state.json"

    @classmethod
    def load(cls) -> "AppState":
        """Load state from disk, or return a new empty state."""
        state_path = cls.get_state_path()
        if state_path.exists():
            try:
                content = state_path.read_text(encoding="utf-8")
                return cls.model_validate_json(content)
            except Exception as e:
                logger.error(f"Failed to load app state from {state_path}: {e}")
                # Return empty state on failure to avoid crashing
                return cls()
        return cls()

    def save(self) -> None:
        """Save state to disk."""
        state_path = self.get_state_path()
        try:
            state_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save app state to {state_path}: {e}")

    def add_project(self, path: Path) -> bool:
        """
        Add a project path to the managed list.

        Returns:
            True if added, False if already exists.
        """
        path = path.resolve()
        if path not in self.projects:
            self.projects.append(path)
            return True
        return False

    def remove_project(self, path: Path) -> bool:
        """
        Remove a project path from the managed list.

        Returns:
            True if removed, False if not found.
        """
        path = path.resolve()
        if path in self.projects:
            self.projects.remove(path)
            return True
        return False
