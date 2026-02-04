"""Unit tests for template service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.template import ProjectTemplate, TemplateConfig, TemplatePrompts
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    PhaseBackends,
    ProjectConfig,
    Workspace,
)
from agent_pump.services.template_service import TemplateService


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus."""
    return MagicMock()


@pytest.fixture
def template_service(mock_event_bus):
    """Create a template service with mock event bus."""
    return TemplateService(mock_event_bus)


@pytest.fixture
def template_service_with_workspace(mock_event_bus):
    """Create a template service with a workspace."""
    workspace = Workspace(name="test-workspace")
    return TemplateService(mock_event_bus, workspace)


class TestTemplateServiceList:
    """Test cases for listing templates."""

    def test_list_includes_builtin_templates(self, template_service):
        """Test that list_templates includes built-in templates."""
        templates = template_service.list_templates()
        names = {t.name for t in templates}

        # Check for expected built-in templates
        assert "python-uv" in names
        assert "node-npm" in names
        assert "rust-cargo" in names
        assert "go" in names

    def test_list_returns_list(self, template_service):
        """Test that list_templates returns a list."""
        templates = template_service.list_templates()
        assert isinstance(templates, list)
        assert len(templates) > 0

    def test_user_templates_override_builtin(self, template_service, tmp_path, monkeypatch):
        """Test that user templates override built-in with same name."""
        # Create a custom templates directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Monkeypatch the templates directory FIRST
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        # Create a user template that overrides python-uv
        user_template = ProjectTemplate(
            name="python-uv",
            description="Custom Python template",
            category="user",
            config=TemplateConfig(backend="claude"),
        )
        user_template.save()

        templates = template_service.list_templates()
        python_template = next(t for t in templates if t.name == "python-uv")

        assert python_template.category == "user"
        assert python_template.description == "Custom Python template"
        assert python_template.config.backend == "claude"


class TestTemplateServiceGet:
    """Test cases for getting templates."""

    def test_get_builtin_template(self, template_service, tmp_path, monkeypatch):
        """Test getting a built-in template."""
        # Use a temporary directory to avoid interference from other tests
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        template = template_service.get_template("python-uv")
        assert template is not None
        assert template.name == "python-uv"
        assert template.category == "built-in"

    def test_get_nonexistent_template(self, template_service):
        """Test getting a template that doesn't exist."""
        template = template_service.get_template("does-not-exist")
        assert template is None

    def test_get_user_template_overrides_builtin(self, template_service, tmp_path, monkeypatch):
        """Test that user template is returned instead of built-in."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Monkeypatch FIRST
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        user_template = ProjectTemplate(
            name="python-uv",
            description="User version",
            category="user",
        )
        user_template.save()

        template = template_service.get_template("python-uv")
        assert template is not None
        assert template.category == "user"
        assert template.description == "User version"


class TestTemplateServiceSaveFromProject:
    """Test cases for saving project as template."""

    def test_save_project_with_config(self, template_service_with_workspace, tmp_path, monkeypatch):
        """Test saving a project with existing configuration."""
        # Create a mock project structure
        project_path = tmp_path / "my-project"
        agent_pump_dir = project_path / ".agent-pump"
        agent_pump_dir.mkdir(parents=True)

        # Create a config file
        import yaml

        config_data = {
            "backend": "claude",
            "workflow": {"max_iterations": 20, "timeout": 3600},
            "verification": {
                "build_cmd": "npm run build",
                "lint_cmd": "npm run lint",
                "test_cmd": "npm test",
            },
        }
        config_file = agent_pump_dir / "config.yml"
        config_file.write_text(yaml.dump(config_data))

        # Create templates directory for saving
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        # Add project config to workspace
        project_config = ProjectConfig(
            path=project_path,
            branch_strategy=BranchStrategyConfig(enabled=True, auto_create_branch=True),
            phase_backends=PhaseBackends(
                defaults=BackendFallback(backends=[BackendInstance(name="claude")])
            ),
        )
        template_service_with_workspace.workspace.projects[str(project_path)] = project_config

        # Save as template
        template = template_service_with_workspace.save_project_as_template(
            project_path, "my-template", "My test template"
        )

        assert template.name == "my-template"
        assert template.description == "My test template"
        assert template.category == "user"
        assert template.config.backend == "claude"
        assert template.config.workflow_max_iterations == 20
        assert template.config.verification.build_cmd == "npm run build"
        assert template.config.branch_strategy.enabled is True

    def test_save_project_without_config(self, template_service, tmp_path, monkeypatch):
        """Test saving a project without configuration."""
        project_path = tmp_path / "bare-project"
        project_path.mkdir()

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        template = template_service.save_project_as_template(
            project_path, "bare-template", "Bare project"
        )

        assert template.name == "bare-template"
        assert template.config.backend == "gemini"  # Default
        assert template.config.workflow_max_iterations == 10  # Default

    def test_save_extracts_prompts(self, template_service, tmp_path, monkeypatch):
        """Test that prompt files are extracted when saving."""
        project_path = tmp_path / "project-with-prompts"
        agent_pump_dir = project_path / ".agent-pump"
        states_dir = agent_pump_dir / "states"
        backends_dir = agent_pump_dir / "backends"
        states_dir.mkdir(parents=True)
        backends_dir.mkdir()

        # Create some prompt files
        (states_dir / "planning.md").write_text("Custom planning prompt")
        (states_dir / "pre-planning.md").write_text("Pre-planning hook")
        (backends_dir / "pre-gemini.md").write_text("Gemini hook")

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        template = template_service.save_project_as_template(
            project_path, "prompt-template", "Template with prompts"
        )

        assert template.prompts.planning == "Custom planning prompt"
        assert template.prompts.pre_planning == "Pre-planning hook"
        assert template.prompts.pre_gemini == "Gemini hook"


class TestTemplateServiceDelete:
    """Test cases for deleting templates."""

    def test_delete_user_template(self, template_service, tmp_path, monkeypatch):
        """Test deleting a user-created template."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        # Create a user template
        template = ProjectTemplate(name="to-delete", category="user")
        template.save()

        assert (templates_dir / "to-delete.json").exists()

        result = template_service.delete_template("to-delete")
        assert result is True
        assert not (templates_dir / "to-delete.json").exists()

    def test_cannot_delete_builtin(self, template_service):
        """Test that built-in templates cannot be deleted."""
        result = template_service.delete_template("python-uv")
        assert result is False

    def test_delete_nonexistent(self, template_service):
        """Test deleting a template that doesn't exist."""
        result = template_service.delete_template("does-not-exist")
        assert result is False


class TestTemplateServiceApply:
    """Test cases for applying templates to projects."""

    def test_apply_creates_directories(self, template_service, tmp_path):
        """Test that applying template creates .agent-pump directories."""
        project_path = tmp_path / "new-project"
        project_path.mkdir()

        template = ProjectTemplate(
            name="test",
            config=TemplateConfig(backend="gemini"),
        )

        result = template_service.apply_template_to_project(template, project_path)
        assert result is True

        assert (project_path / ".agent-pump").exists()
        assert (project_path / ".agent-pump" / "states").exists()
        assert (project_path / ".agent-pump" / "backends").exists()

    def test_apply_writes_config(self, template_service, tmp_path):
        """Test that config.yml is written correctly."""
        import yaml

        project_path = tmp_path / "project-with-config"
        project_path.mkdir()

        template = ProjectTemplate(
            name="test",
            config=TemplateConfig(
                backend="claude",
                workflow_max_iterations=15,
                verification=VerificationConfig(build_cmd="make", test_cmd="make test"),
                branch_strategy=BranchStrategyConfig(enabled=True, base_branch="develop"),
            ),
        )

        result = template_service.apply_template_to_project(template, project_path)
        assert result is True

        config_file = project_path / ".agent-pump" / "config.yml"
        assert config_file.exists()

        config_data = yaml.safe_load(config_file.read_text())
        assert config_data["backend"] == "claude"
        assert config_data["workflow"]["max_iterations"] == 15
        assert config_data["verification"]["build_cmd"] == "make"
        assert config_data["branch_strategy"]["base_branch"] == "develop"

    def test_apply_writes_prompts(self, template_service, tmp_path):
        """Test that prompt files are written correctly."""
        project_path = tmp_path / "project-with-prompts"
        project_path.mkdir()

        template = ProjectTemplate(
            name="test",
            prompts=TemplatePrompts(
                planning="Planning override",
                pre_implementing="Pre hook",
                pre_gemini="Gemini hook",
            ),
        )

        result = template_service.apply_template_to_project(template, project_path)
        assert result is True

        states_dir = project_path / ".agent-pump" / "states"
        backends_dir = project_path / ".agent-pump" / "backends"

        assert (states_dir / "planning.md").read_text() == "Planning override"
        assert (states_dir / "pre-implementing.md").read_text() == "Pre hook"
        assert (backends_dir / "pre-gemini.md").read_text() == "Gemini hook"

    def test_apply_skips_empty_prompts(self, template_service, tmp_path):
        """Test that empty prompts are not written to files."""
        project_path = tmp_path / "project-minimal"
        project_path.mkdir()

        template = ProjectTemplate(
            name="test",
            prompts=TemplatePrompts(
                planning="Has content",
                implementing="",  # Empty
            ),
        )

        result = template_service.apply_template_to_project(template, project_path)
        assert result is True

        states_dir = project_path / ".agent-pump" / "states"
        assert (states_dir / "planning.md").exists()
        assert not (states_dir / "implementing.md").exists()

    def test_apply_with_workspace_updates_config(self, template_service_with_workspace, tmp_path):
        """Test that workspace is updated when applying template."""
        project_path = tmp_path / "project-with-workspace"
        project_path.mkdir()

        phase_backends = PhaseBackends(
            defaults=BackendFallback(backends=[BackendInstance(name="claude", args=["--version"])])
        )

        template = ProjectTemplate(
            name="test",
            config=TemplateConfig(
                backend="claude",
                phase_backends=phase_backends,
                workflow_name="custom-workflow",
                min_execution_time_seconds=20,
            ),
        )

        result = template_service_with_workspace.apply_template_to_project(template, project_path)
        assert result is True

        # Check workspace was updated
        project_config = template_service_with_workspace.workspace.get_project_config(project_path)
        assert project_config is not None
        # Backend is stored in phase_backends, not directly
        assert project_config.phase_backends.defaults.backends[0].name == "claude"
        assert project_config.workflow_name == "custom-workflow"
        assert project_config.min_execution_time_seconds == 20


class TestTemplateServiceCreateProject:
    """Test cases for creating new projects from templates."""

    def test_create_new_project(self, template_service, tmp_path):
        """Test creating a new project from template."""
        project_path = tmp_path / "brand-new-project"
        # Don't create the directory - it shouldn't exist

        template = ProjectTemplate(
            name="test",
            config=TemplateConfig(backend="gemini"),
        )

        result = template_service.create_project_from_template(template, project_path)
        assert result is True

        assert project_path.exists()
        assert (project_path / ".agent-pump" / "config.yml").exists()

    def test_create_fails_if_exists(self, template_service, tmp_path):
        """Test that creation fails if project already exists."""
        project_path = tmp_path / "existing-project"
        project_path.mkdir()  # Create it first

        template = ProjectTemplate(name="test")

        result = template_service.create_project_from_template(template, project_path)
        assert result is False


class TestTemplateServiceExtractConfig:
    """Test cases for extracting configuration from projects."""

    def test_extract_from_yaml_config(self, template_service, tmp_path):
        """Test extracting config from existing YAML file."""
        import yaml

        project_path = tmp_path / "project"
        agent_pump_dir = project_path / ".agent-pump"
        agent_pump_dir.mkdir(parents=True)

        config_data = {
            "backend": "qwen",
            "workflow": {"max_iterations": 25, "timeout": 2400},
            "verification": {"build_cmd": "cargo build", "test_cmd": "cargo test"},
        }
        (agent_pump_dir / "config.yml").write_text(yaml.dump(config_data))

        config = template_service._extract_config_from_project(project_path)

        assert config.backend == "qwen"
        assert config.workflow_max_iterations == 25
        assert config.workflow_timeout == 2400
        assert config.verification.build_cmd == "cargo build"

    def test_extract_defaults_when_no_config(self, template_service, tmp_path):
        """Test that defaults are used when no config exists."""
        project_path = tmp_path / "bare-project"
        project_path.mkdir()

        config = template_service._extract_config_from_project(project_path)

        assert config.backend == "gemini"
        assert config.workflow_max_iterations == 10
        assert config.workflow_timeout == 1800
        assert isinstance(config.branch_strategy, BranchStrategyConfig)
        assert isinstance(config.verification, VerificationConfig)


class TestTemplateServiceExtractPrompts:
    """Test cases for extracting prompts from projects."""

    def test_extract_all_prompt_types(self, template_service, tmp_path):
        """Test extracting all types of prompt files."""
        project_path = tmp_path / "project"
        states_dir = project_path / ".agent-pump" / "states"
        backends_dir = project_path / ".agent-pump" / "backends"
        states_dir.mkdir(parents=True)
        backends_dir.mkdir()

        # Create various prompt files
        (states_dir / "planning.md").write_text("planning")
        (states_dir / "implementing.md").write_text("implementing")
        (states_dir / "pre-planning.md").write_text("pre-planning")
        (states_dir / "post-planning.md").write_text("post-planning")
        (backends_dir / "pre-gemini.md").write_text("pre-gemini")
        (backends_dir / "post-claude.md").write_text("post-claude")

        prompts = template_service._extract_prompts_from_project(project_path)

        assert prompts.planning == "planning"
        assert prompts.implementing == "implementing"
        assert prompts.pre_planning == "pre-planning"
        assert prompts.post_planning == "post-planning"
        assert prompts.pre_gemini == "pre-gemini"
        assert prompts.post_claude == "post-claude"

    def test_extract_missing_directories(self, template_service, tmp_path):
        """Test extraction when directories don't exist."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        prompts = template_service._extract_prompts_from_project(project_path)

        assert isinstance(prompts, TemplatePrompts)
        assert prompts.planning == ""
        assert prompts.pre_gemini == ""
