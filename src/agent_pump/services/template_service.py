"""Template management service for agent-pump."""

import logging
from pathlib import Path

import yaml

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.template import (
    ProjectTemplate,
    TemplateConfig,
    TemplatePrompts,
)
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.workspace import PhaseBackends, ProjectConfig, Workspace
from agent_pump.services.base import BaseService
from agent_pump.templates.builtin import get_all_builtin_templates, get_builtin_template

logger = logging.getLogger(__name__)


class TemplateService(BaseService):
    """Service for managing project templates."""

    def __init__(self, event_bus, workspace: Workspace | None = None) -> None:
        """
        Initialize the template service.

        Args:
            event_bus: The event bus.
            workspace: Optional workspace for project config access.
        """
        super().__init__(event_bus)
        self.workspace = workspace

    def list_templates(self) -> list[ProjectTemplate]:
        """
        List all available templates (built-in + user-defined).

        Returns:
            List of all templates (user templates override built-in with same name).
        """
        # Get built-in templates
        builtin_templates = {t.name: t for t in get_all_builtin_templates()}

        # Get user templates (these override built-in)
        user_templates = ProjectTemplate.list_user_templates()
        for template in user_templates:
            builtin_templates[template.name] = template

        return list(builtin_templates.values())

    def get_template(self, name: str) -> ProjectTemplate | None:
        """
        Get a template by name.

        Args:
            name: Template name.

        Returns:
            The template, or None if not found.
        """
        # Check user templates first
        user_template = ProjectTemplate.load(name)
        if user_template:
            return user_template

        # Fall back to built-in
        return get_builtin_template(name)

    def save_project_as_template(
        self, project_path: Path, name: str, description: str = ""
    ) -> ProjectTemplate:
        """
        Save a project's configuration as a template.

        Args:
            project_path: Path to the project.
            name: Template name.
            description: Template description.

        Returns:
            The created template.

        Raises:
            ValueError: If project has no configuration.
        """
        project_path = project_path.resolve()

        # Extract configuration from project
        config = self._extract_config_from_project(project_path)

        # Extract prompts from project
        prompts = self._extract_prompts_from_project(project_path)

        # Create template
        template = ProjectTemplate(
            name=name,
            description=description,
            category="user",
            config=config,
            prompts=prompts,
        )

        # Save template
        template.save()
        logger.info(f"Saved project {project_path} as template '{name}'")

        return template

    def _extract_config_from_project(self, project_path: Path) -> TemplateConfig:
        """Extract configuration from a project."""
        # Load project config from .agent-pump/config.yml if it exists
        agent_pump_dir = project_path / ".agent-pump"
        config_file = agent_pump_dir / "config.yml"

        if config_file.exists():
            try:
                content = config_file.read_text(encoding="utf-8")
                config_data = yaml.safe_load(content) or {}
            except Exception as e:
                logger.warning(f"Failed to load config.yml from {project_path}: {e}")
                config_data = {}
        else:
            config_data = {}

        # Get workspace config if available
        project_config = None
        if self.workspace:
            project_config = self.workspace.get_project_config(project_path)

        # Build template config with proper defaults
        branch_strategy = (
            project_config.branch_strategy
            if project_config and project_config.branch_strategy
            else BranchStrategyConfig()
        )

        phase_backends = (
            project_config.phase_backends
            if project_config and project_config.phase_backends
            else PhaseBackends()
        )

        return TemplateConfig(
            backend=config_data.get("backend", "gemini"),
            workflow_max_iterations=config_data.get("workflow", {}).get("max_iterations", 10),
            workflow_timeout=config_data.get("workflow", {}).get("timeout", 1800),
            branch_strategy=branch_strategy,
            verification=VerificationConfig(**config_data.get("verification", {}))
            if config_data.get("verification")
            else VerificationConfig(),
            phase_backends=phase_backends,
            default_chain=project_config.default_chain if project_config else None,
            workflow_name=project_config.workflow_name if project_config else "default",
            min_execution_time_seconds=project_config.min_execution_time_seconds
            if project_config
            else 10,
            default_timeout=project_config.default_timeout if project_config else 1800,
        )

    def _extract_prompts_from_project(self, project_path: Path) -> TemplatePrompts:
        """Extract prompt files from a project."""
        agent_pump_dir = project_path / ".agent-pump"
        states_dir = agent_pump_dir / "states"
        backends_dir = agent_pump_dir / "backends"

        prompts = TemplatePrompts()

        # Map of file names to prompt fields
        phase_files = {
            "planning.md": "planning",
            "implementing.md": "implementing",
            "verifying.md": "verifying",
            "brainstorming.md": "brainstorming",
            "committing.md": "committing",
            "pre-planning.md": "pre_planning",
            "post-planning.md": "post_planning",
            "pre-implementing.md": "pre_implementing",
            "post-implementing.md": "post_implementing",
            "pre-verifying.md": "pre_verifying",
            "post-verifying.md": "post_verifying",
            "pre-brainstorming.md": "pre_brainstorming",
            "post-brainstorming.md": "post_brainstorming",
            "pre-committing.md": "pre_committing",
            "post-committing.md": "post_committing",
        }

        backend_files = {
            "pre-gemini.md": "pre_gemini",
            "post-gemini.md": "post_gemini",
            "pre-claude.md": "pre_claude",
            "post-claude.md": "post_claude",
            "pre-opencode.md": "pre_opencode",
            "post-opencode.md": "post_opencode",
            "pre-qwen.md": "pre_qwen",
            "post-qwen.md": "post_qwen",
        }

        # Read phase prompt files
        if states_dir.exists():
            for filename, field_name in phase_files.items():
                file_path = states_dir / filename
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        setattr(prompts, field_name, content)
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")

        # Read backend prompt files
        if backends_dir.exists():
            for filename, field_name in backend_files.items():
                file_path = backends_dir / filename
                if file_path.exists():
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        setattr(prompts, field_name, content)
                    except Exception as e:
                        logger.warning(f"Failed to read {file_path}: {e}")

        return prompts

    def delete_template(self, name: str) -> bool:
        """
        Delete a user-created template.

        Args:
            name: Template name.

        Returns:
            True if deleted, False if not found or is built-in.
        """
        # Don't allow deleting built-in templates
        if get_builtin_template(name) is not None:
            logger.warning(f"Cannot delete built-in template '{name}'")
            return False

        return ProjectTemplate.delete(name)

    def apply_template_to_project(self, template: ProjectTemplate, project_path: Path) -> bool:
        """
        Apply a template to an existing or new project.

        Args:
            template: The template to apply.
            project_path: Path to the project.

        Returns:
            True if applied successfully.
        """
        project_path = project_path.resolve()

        try:
            # Create .agent-pump directory structure
            agent_pump_dir = project_path / ".agent-pump"
            agent_pump_dir.mkdir(parents=True, exist_ok=True)

            states_dir = agent_pump_dir / "states"
            states_dir.mkdir(exist_ok=True)

            backends_dir = agent_pump_dir / "backends"
            backends_dir.mkdir(exist_ok=True)

            # Write config.yml
            self._write_config_file(template, agent_pump_dir)

            # Write prompt files
            self._write_prompt_files(template, states_dir, backends_dir)

            # Update workspace if available
            if self.workspace:
                self._update_workspace_config(template, project_path)

            logger.info(f"Applied template '{template.name}' to {project_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply template to {project_path}: {e}")
            return False

    def _write_config_file(self, template: ProjectTemplate, agent_pump_dir: Path) -> None:
        """Write the config.yml file."""
        config_data = {
            "backend": template.config.backend,
            "workflow": {
                "max_iterations": template.config.workflow_max_iterations,
                "timeout": template.config.workflow_timeout,
            },
        }

        # Add verification config if present
        verification_dict = template.config.verification.model_dump()
        if any(verification_dict.values()):  # Only add if not all empty/false
            config_data["verification"] = verification_dict

        # Add branch strategy if enabled
        if template.config.branch_strategy and template.config.branch_strategy.enabled:
            config_data["branch_strategy"] = template.config.branch_strategy.model_dump()

        config_file = agent_pump_dir / "config.yml"
        config_file.write_text(
            yaml.dump(config_data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _write_prompt_files(
        self, template: ProjectTemplate, states_dir: Path, backends_dir: Path
    ) -> None:
        """Write prompt files to the project."""
        prompts = template.prompts

        # Phase files mapping
        phase_files = {
            "planning.md": prompts.planning,
            "implementing.md": prompts.implementing,
            "verifying.md": prompts.verifying,
            "brainstorming.md": prompts.brainstorming,
            "committing.md": prompts.committing,
            "pre-planning.md": prompts.pre_planning,
            "post-planning.md": prompts.post_planning,
            "pre-implementing.md": prompts.pre_implementing,
            "post-implementing.md": prompts.post_implementing,
            "pre-verifying.md": prompts.pre_verifying,
            "post-verifying.md": prompts.post_verifying,
            "pre-brainstorming.md": prompts.pre_brainstorming,
            "post-brainstorming.md": prompts.post_brainstorming,
            "pre-committing.md": prompts.pre_committing,
            "post-committing.md": prompts.post_committing,
        }

        # Write phase files if they have content
        for filename, content in phase_files.items():
            if content:
                file_path = states_dir / filename
                file_path.write_text(content, encoding="utf-8")

        # Backend files mapping
        backend_files = {
            "pre-gemini.md": prompts.pre_gemini,
            "post-gemini.md": prompts.post_gemini,
            "pre-claude.md": prompts.pre_claude,
            "post-claude.md": prompts.post_claude,
            "pre-opencode.md": prompts.pre_opencode,
            "post-opencode.md": prompts.post_opencode,
            "pre-qwen.md": prompts.pre_qwen,
            "post-qwen.md": prompts.post_qwen,
        }

        # Write backend files if they have content
        for filename, content in backend_files.items():
            if content:
                file_path = backends_dir / filename
                file_path.write_text(content, encoding="utf-8")

    def _update_workspace_config(self, template: ProjectTemplate, project_path: Path) -> None:
        """Update workspace with template backend configuration."""
        if not self.workspace:
            return

        # Get or create project config
        project_config = self.workspace.get_project_config(project_path)
        if not project_config:
            project_config = ProjectConfig(path=project_path)
            self.workspace.projects[str(project_path)] = project_config

        # Update backend configuration
        if template.config.phase_backends:
            project_config.phase_backends = template.config.phase_backends

        if template.config.default_chain:
            project_config.default_chain = template.config.default_chain

        # Update other settings
        project_config.workflow_name = template.config.workflow_name
        project_config.min_execution_time_seconds = template.config.min_execution_time_seconds
        project_config.default_timeout = template.config.default_timeout

        # Save workspace
        self.workspace.save()

    def create_project_from_template(self, template: ProjectTemplate, project_path: Path) -> bool:
        """
        Create a new project directory and apply template.

        Args:
            template: The template to apply.
            project_path: Path where the new project should be created.

        Returns:
            True if created and template applied successfully.
        """
        project_path = project_path.resolve()

        if project_path.exists():
            logger.error(f"Project path already exists: {project_path}")
            return False

        try:
            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)

            # Apply template
            return self.apply_template_to_project(template, project_path)

        except Exception as e:
            logger.error(f"Failed to create project from template: {e}")
            return False
