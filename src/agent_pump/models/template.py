"""Template models for agent-pump."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.workspace import BackendFallback, PhaseBackends


class TemplatePrompts(BaseModel):
    """Collection of prompt files content for a template."""

    # Phase-specific prompts (full overrides)
    planning: str = Field(default="", description="Full override for planning phase")
    implementing: str = Field(default="", description="Full override for implementing phase")
    verifying: str = Field(default="", description="Full override for verifying phase")
    brainstorming: str = Field(default="", description="Full override for brainstorming phase")
    committing: str = Field(default="", description="Full override for committing phase")

    # Pre/post hooks for phases
    pre_planning: str = Field(default="", description="Prepended to planning prompt")
    post_planning: str = Field(default="", description="Appended to planning prompt")
    pre_implementing: str = Field(default="", description="Prepended to implementing prompt")
    post_implementing: str = Field(default="", description="Appended to implementing prompt")
    pre_verifying: str = Field(default="", description="Prepended to verifying prompt")
    post_verifying: str = Field(default="", description="Appended to verifying prompt")
    pre_brainstorming: str = Field(default="", description="Prepended to brainstorming prompt")
    post_brainstorming: str = Field(default="", description="Appended to brainstorming prompt")
    pre_committing: str = Field(default="", description="Prepended to committing prompt")
    post_committing: str = Field(default="", description="Appended to committing prompt")

    # Backend-specific hooks
    pre_gemini: str = Field(default="", description="Prepended when using Gemini")
    post_gemini: str = Field(default="", description="Appended when using Gemini")
    pre_claude: str = Field(default="", description="Prepended when using Claude")
    post_claude: str = Field(default="", description="Appended when using Claude")
    pre_opencode: str = Field(default="", description="Prepended when using OpenCode")
    post_opencode: str = Field(default="", description="Appended when using OpenCode")
    pre_qwen: str = Field(default="", description="Prepended when using Qwen")
    post_qwen: str = Field(default="", description="Appended when using Qwen")


class TemplateConfig(BaseModel):
    """Configuration data stored in a template."""

    # Core settings
    backend: str = Field(default="gemini", description="Default backend to use")
    workflow_max_iterations: int = Field(
        default=10, description="Maximum autonomous iterations per run"
    )
    workflow_timeout: int = Field(
        default=1800, description="Timeout in seconds for agent operations"
    )

    # Branch strategy
    branch_strategy: BranchStrategyConfig = Field(
        default_factory=BranchStrategyConfig, description="Git branch strategy configuration"
    )

    # Verification commands
    verification: VerificationConfig = Field(
        default_factory=VerificationConfig, description="Verification command configuration"
    )

    # Backend configuration
    phase_backends: PhaseBackends = Field(
        default_factory=PhaseBackends, description="Backend fallback chains for each phase"
    )
    default_chain: BackendFallback | None = Field(
        default=None, description="Default backend chain for phases that don't specify one"
    )

    # Workflow settings
    workflow_name: str = Field(default="default", description="Name of workflow definition to use")
    min_execution_time_seconds: int = Field(
        default=10,
        description="Minimum execution time for backend call to be considered successful",
    )
    default_timeout: int = Field(
        default=1800, description="Default timeout in seconds for backend execution"
    )


class ProjectTemplate(BaseModel):
    """A complete project template with all configuration."""

    name: str = Field(description="Unique template name (used as identifier)")
    description: str = Field(default="", description="Human-readable description")
    category: str = Field(
        default="custom", description="Template category (built-in, custom, user)"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Configuration
    config: TemplateConfig = Field(
        default_factory=TemplateConfig, description="Template configuration"
    )

    # Prompts
    prompts: TemplatePrompts = Field(
        default_factory=TemplatePrompts, description="Template prompt customizations"
    )

    # Optional metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    author: str = Field(default="", description="Template author")
    version: str = Field(default="1.0.0", description="Template version")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def model_dump_json(self, **kwargs: Any) -> str:
        """Override to handle Path objects in nested models."""
        # Ensure we're using the parent's implementation with proper encoding
        return super().model_dump_json(**kwargs)

    @classmethod
    def get_templates_dir(cls) -> Path:
        """Get the directory where user templates are stored."""
        templates_dir = Path.home() / ".config" / "agent-pump" / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)
        return templates_dir

    @classmethod
    def get_template_path(cls, name: str) -> Path:
        """Get the path for a template file."""
        return cls.get_templates_dir() / f"{name}.json"

    def save(self) -> None:
        """Save template to disk."""
        self.updated_at = datetime.now()
        template_path = self.get_template_path(self.name)
        template_path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def load(cls, name: str) -> "ProjectTemplate | None":
        """Load a template from disk."""
        template_path = cls.get_template_path(name)
        if not template_path.exists():
            return None
        try:
            content = template_path.read_text(encoding="utf-8")
            return cls.model_validate_json(content)
        except Exception:
            return None

    @classmethod
    def list_user_templates(cls) -> list["ProjectTemplate"]:
        """List all user-created templates."""
        templates_dir = cls.get_templates_dir()
        templates = []
        for template_path in templates_dir.glob("*.json"):
            try:
                content = template_path.read_text(encoding="utf-8")
                template = cls.model_validate_json(content)
                templates.append(template)
            except Exception:
                continue
        return templates

    @classmethod
    def delete(cls, name: str) -> bool:
        """Delete a user template."""
        template_path = cls.get_template_path(name)
        if template_path.exists():
            try:
                template_path.unlink()
                return True
            except Exception:
                return False
        return False
