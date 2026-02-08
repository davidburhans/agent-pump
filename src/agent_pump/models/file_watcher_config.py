"""File watcher configuration models."""

from pydantic import BaseModel, Field


class FileWatcherConfig(BaseModel):
    """Configuration for file watcher trigger."""

    enabled: bool = Field(
        default=False,
        description="Whether to enable file watcher trigger for this project.",
    )
    patterns: list[str] = Field(
        default_factory=lambda: ["*"],
        description="List of file patterns to watch (e.g., ['*.py', '*.js']).",
    )
    ignore_patterns: list[str] = Field(
        default_factory=lambda: [
            ".git",
            "__pycache__",
            ".venv",
            "node_modules",
            ".agent-pump",
            ".pytest_cache",
            "dist",
            "build",
            "coverage",
        ],
        description="List of patterns to ignore.",
    )
    debounce_seconds: float = Field(
        default=2.0,
        description="Time to wait for changes to settle before triggering.",
    )
    action: str = Field(
        default="verification",
        description="Action to trigger on change ('verification' or 'workflow').",
    )
