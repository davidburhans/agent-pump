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
        1. Project-level .agent-pump/config.yml (New Standard)
        2. Project-level .agent-pump.yml (Legacy)
        3. User-level ~/.config/agent-pump/config.yml
        4. Defaults

        If no project-level configuration exists, the new standard (.agent-pump/config.yml) is created.
        """
        config_data: dict[str, Any] = {}

        # User-level config
        user_config = Path.home() / ".config" / "agent-pump" / "config.yml"
        if user_config.exists():
            with open(user_config) as f:
                user_data = yaml.safe_load(f) or {}
                config_data.update(user_data)

        # Check for configs
        new_config_dir = project_path / ".agent-pump"
        new_config_file = new_config_dir / "config.yml"
        legacy_config_file = project_path / ".agent-pump.yml"

        # If neither exists, create NEW structure
        if not new_config_file.exists() and not legacy_config_file.exists():
            new_config_dir.mkdir(parents=True, exist_ok=True)
            (new_config_dir / "states").mkdir(parents=True, exist_ok=True)
            (new_config_dir / "backends").mkdir(parents=True, exist_ok=True)

            with open(new_config_file, "w") as f:
                f.write(DEFAULT_CONFIG_TEMPLATE)
            
            # Create stub prompt files
            for state in [
                "planning",
                "implementing",
                "verifying",
                "brainstorming",
                "committing",
            ]:
                stub = new_config_dir / "states" / f"pre-{state}.md"
                if not stub.exists():
                    stub.write_text(
                        f"<!-- Add custom instructions to prepend to {state} phase -->\n",
                        encoding="utf-8",
                    )

        # Load project config (prefer new)
        if new_config_file.exists():
             with open(new_config_file) as f:
                project_data = yaml.safe_load(f) or {}
                config_data.update(project_data)
        elif legacy_config_file.exists():
             with open(legacy_config_file) as f:
                project_data = yaml.safe_load(f) or {}
                config_data.update(project_data)

        return cls.model_validate(config_data)

    def save(self, path: Path) -> None:
        """Save configuration to a file."""
        with open(path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)

