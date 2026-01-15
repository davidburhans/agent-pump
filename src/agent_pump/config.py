"""Configuration management for agent-pump."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_pump.models.verification_config import VerificationConfig

DEFAULT_CONFIG_TEMPLATE = """# Agent Pump Host Configuration
# Generated automatically. Edit this file to customize behavior for this project.

# The AI backend to use (e.g., "gemini", "openai:gpt-4")
backend: gemini

workflow:
  # Maximum number of autonomous iterations per run
  max_iterations: 10
  # Timeout in seconds for agent operations
  timeout: 1800
  # Git branch to isolate work (optional)
  branch: null

verification:
  # Commands to verify code correctness.
  # Leave empty to skip or rely on auto-detection.

  # Command to run for building the project (e.g., "npm run build", "cargo build")
  build_cmd: null

  # Command to run for linting the project (e.g., "npm run lint", "ruff check .")
  lint_cmd: null

  # Command to run for testing the project (e.g., "npm test", "pytest")
  test_cmd: null

  # Set to true to skip verification phase entirely
  skip_verification: false
"""


class WorkflowConfig(BaseModel):
    """Workflow configuration options."""

    max_iterations: int = Field(default=10, description="Maximum workflow iterations")
    timeout: int = Field(default=1800, description="Timeout per agent invocation in seconds")
    branch: str | None = Field(default=None, description="Optional branch to isolate work")


class Config(BaseModel):
    """Agent-pump configuration."""

    backend: str = Field(default="gemini", description="AI agent backend to use")
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    verification: VerificationConfig = Field(
        default_factory=VerificationConfig, description="Verification command configuration"
    )

    @classmethod
    def load(cls, project_path: Path) -> "Config":
        """
        Load configuration from files.

        Priority:
        1. Project-level .agent-pump.yml
        2. User-level ~/.config/agent-pump/config.yml
        3. Defaults

        If project-level configuration does not exist, it is created with defaults.
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
        if not project_config.exists():
            # Create default config file if it doesn't exist
            with open(project_config, "w") as f:
                f.write(DEFAULT_CONFIG_TEMPLATE)

        if project_config.exists():
            with open(project_config) as f:
                project_data = yaml.safe_load(f) or {}
                config_data.update(project_data)

        return cls.model_validate(config_data)

    def save(self, path: Path) -> None:
        """Save configuration to a file."""
        with open(path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)
