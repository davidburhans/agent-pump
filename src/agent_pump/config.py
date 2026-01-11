"""Configuration management for agent-pump."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    """Workflow configuration options."""

    max_iterations: int = Field(default=10, description="Maximum workflow iterations")
    timeout: int = Field(default=600, description="Timeout per agent invocation in seconds")
    branch: str | None = Field(default=None, description="Optional branch to isolate work")


class Config(BaseModel):
    """Agent-pump configuration."""

    backend: str = Field(default="gemini", description="AI agent backend to use")
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)

    @classmethod
    def load(cls, project_path: Path) -> "Config":
        """
        Load configuration from files.

        Priority:
        1. Project-level .agent-pump.yml
        2. User-level ~/.config/agent-pump/config.yml
        3. Defaults
        """
        config_data: dict[str, Any] = {}

        # User-level config
        user_config = Path.home() / ".config" / "agent-pump" / "config.yml"
        if user_config.exists():
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
                config_data.update(user_data)

        # Project-level config (overrides user)
        project_config = project_path / ".agent-pump.yml"
        if project_config.exists():
            with open(project_config) as f:
                project_data = yaml.safe_load(f) or {}
                config_data.update(project_data)

        return cls.model_validate(config_data)

    def save(self, path: Path) -> None:
        """Save configuration to a file."""
        with open(path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)
