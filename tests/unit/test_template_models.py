"""Unit tests for template models."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.models.template import (
    ProjectTemplate,
    TemplateConfig,
    TemplatePrompts,
)
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.models.workspace import BackendFallback, BackendInstance, PhaseBackends


class TestTemplatePrompts:
    """Test cases for TemplatePrompts model."""

    def test_default_construction(self):
        """Test that TemplatePrompts can be constructed with defaults."""
        prompts = TemplatePrompts()
        assert prompts.planning == ""
        assert prompts.implementing == ""
        assert prompts.pre_planning == ""
        assert prompts.post_gemini == ""

    def test_custom_values(self):
        """Test that custom values can be set."""
        prompts = TemplatePrompts(
            planning="Custom planning prompt",
            pre_gemini="Pre-gemini hook",
            post_claude="Post-claude hook",
        )
        assert prompts.planning == "Custom planning prompt"
        assert prompts.pre_gemini == "Pre-gemini hook"
        assert prompts.post_claude == "Post-claude hook"
        assert prompts.implementing == ""  # Default value

    def test_model_dump(self):
        """Test serialization of TemplatePrompts."""
        prompts = TemplatePrompts(
            planning="Test planning",
            pre_implementing="Test pre",
        )
        data = prompts.model_dump()
        assert data["planning"] == "Test planning"
        assert data["pre_implementing"] == "Test pre"
        assert data["verifying"] == ""


class TestTemplateConfig:
    """Test cases for TemplateConfig model."""

    def test_default_construction(self):
        """Test that TemplateConfig can be constructed with defaults."""
        config = TemplateConfig()
        assert config.backend == "gemini"
        assert config.workflow_max_iterations == 10
        assert config.workflow_timeout == 1800
        assert config.workflow_name == "default"
        assert config.min_execution_time_seconds == 10
        assert config.default_timeout == 1800

    def test_custom_values(self):
        """Test that custom values can be set."""
        branch_strategy = BranchStrategyConfig(enabled=True, auto_create_branch=True)
        verification = VerificationConfig(build_cmd="npm run build", test_cmd="npm test")

        config = TemplateConfig(
            backend="claude",
            workflow_max_iterations=20,
            workflow_timeout=3600,
            branch_strategy=branch_strategy,
            verification=verification,
            workflow_name="custom",
        )

        assert config.backend == "claude"
        assert config.workflow_max_iterations == 20
        assert config.workflow_timeout == 3600
        assert config.branch_strategy.enabled is True
        assert config.verification.build_cmd == "npm run build"
        assert config.workflow_name == "custom"

    def test_nested_models(self):
        """Test that nested models work correctly."""
        phase_backends = PhaseBackends(
            defaults=BackendFallback(
                backends=[BackendInstance(name="gemini", args=["--model", "flash"])]
            )
        )

        config = TemplateConfig(phase_backends=phase_backends)
        assert config.phase_backends.defaults.backends[0].name == "gemini"
        assert config.phase_backends.defaults.backends[0].args == ["--model", "flash"]


class TestProjectTemplate:
    """Test cases for ProjectTemplate model."""

    def test_default_construction(self):
        """Test that ProjectTemplate can be constructed with defaults."""
        template = ProjectTemplate(name="test-template")

        assert template.name == "test-template"
        assert template.description == ""
        assert template.category == "custom"
        assert template.version == "1.0.0"
        assert template.author == ""
        assert template.tags == []
        assert isinstance(template.config, TemplateConfig)
        assert isinstance(template.prompts, TemplatePrompts)
        assert isinstance(template.created_at, datetime)
        assert isinstance(template.updated_at, datetime)

    def test_full_construction(self):
        """Test full construction with all fields."""
        config = TemplateConfig(backend="opencode", workflow_max_iterations=5)
        prompts = TemplatePrompts(planning="Custom planning")

        template = ProjectTemplate(
            name="full-test",
            description="A test template",
            category="user",
            tags=["test", "example"],
            author="Test Author",
            version="2.0.0",
            config=config,
            prompts=prompts,
        )

        assert template.name == "full-test"
        assert template.description == "A test template"
        assert template.category == "user"
        assert template.tags == ["test", "example"]
        assert template.author == "Test Author"
        assert template.version == "2.0.0"
        assert template.config.backend == "opencode"
        assert template.prompts.planning == "Custom planning"

    def test_model_dump_json(self):
        """Test JSON serialization."""
        template = ProjectTemplate(
            name="json-test",
            description="Test for JSON",
            config=TemplateConfig(backend="qwen"),
        )

        json_str = template.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "json-test"
        assert data["description"] == "Test for JSON"
        assert data["config"]["backend"] == "qwen"
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_templates_dir(self):
        """Test that templates directory path is correct."""
        templates_dir = ProjectTemplate.get_templates_dir()
        assert isinstance(templates_dir, Path)
        assert ".config" in str(templates_dir)
        assert "agent-pump" in str(templates_dir)
        assert "templates" in str(templates_dir)

    def test_get_template_path(self):
        """Test that template file path is correct."""
        path = ProjectTemplate.get_template_path("my-template")
        assert isinstance(path, Path)
        assert path.name == "my-template.json"
        assert "templates" in str(path)


class TestProjectTemplatePersistence:
    """Test cases for template persistence (save/load/list/delete)."""

    @pytest.fixture
    def temp_templates_dir(self, tmp_path, monkeypatch):
        """Create a temporary templates directory."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Monkeypatch the get_templates_dir method
        monkeypatch.setattr(
            ProjectTemplate, "get_templates_dir", staticmethod(lambda: templates_dir)
        )

        return templates_dir

    def test_save_and_load(self, temp_templates_dir):
        """Test saving and loading a template."""
        template = ProjectTemplate(
            name="save-test",
            description="Test saving",
            config=TemplateConfig(backend="gemini"),
            prompts=TemplatePrompts(planning="Custom"),
        )

        # Save
        template.save()

        # Verify file exists
        template_path = temp_templates_dir / "save-test.json"
        assert template_path.exists()

        # Load
        loaded = ProjectTemplate.load("save-test")
        assert loaded is not None
        assert loaded.name == "save-test"
        assert loaded.description == "Test saving"
        assert loaded.config.backend == "gemini"
        assert loaded.prompts.planning == "Custom"

    def test_load_nonexistent(self, temp_templates_dir):
        """Test loading a template that doesn't exist."""
        loaded = ProjectTemplate.load("does-not-exist")
        assert loaded is None

    def test_list_user_templates(self, temp_templates_dir):
        """Test listing user templates."""
        # Create multiple templates
        for i in range(3):
            template = ProjectTemplate(name=f"template-{i}", description=f"Template {i}")
            template.save()

        # List
        templates = ProjectTemplate.list_user_templates()
        assert len(templates) == 3

        names = {t.name for t in templates}
        assert names == {"template-0", "template-1", "template-2"}

    def test_list_user_templates_empty(self, temp_templates_dir):
        """Test listing when no templates exist."""
        templates = ProjectTemplate.list_user_templates()
        assert templates == []

    def test_list_user_templates_invalid_file(self, temp_templates_dir):
        """Test listing skips invalid template files."""
        # Create a valid template
        valid = ProjectTemplate(name="valid", description="Valid template")
        valid.save()

        # Create an invalid JSON file
        invalid_file = temp_templates_dir / "invalid.json"
        invalid_file.write_text("not valid json")

        # List should return only valid template
        templates = ProjectTemplate.list_user_templates()
        assert len(templates) == 1
        assert templates[0].name == "valid"

    def test_delete_existing(self, temp_templates_dir):
        """Test deleting an existing template."""
        template = ProjectTemplate(name="to-delete", description="To be deleted")
        template.save()

        assert (temp_templates_dir / "to-delete.json").exists()

        result = ProjectTemplate.delete("to-delete")
        assert result is True
        assert not (temp_templates_dir / "to-delete.json").exists()

    def test_delete_nonexistent(self, temp_templates_dir):
        """Test deleting a template that doesn't exist."""
        result = ProjectTemplate.delete("does-not-exist")
        assert result is False

    def test_updated_at_changes_on_save(self, temp_templates_dir):
        """Test that updated_at is modified on save."""
        template = ProjectTemplate(name="update-test", description="Test updates")
        original_updated = template.updated_at

        # Wait a tiny bit to ensure time difference
        import time

        time.sleep(0.01)

        # Save
        template.save()

        # Load and check
        loaded = ProjectTemplate.load("update-test")
        assert loaded is not None
        assert loaded.updated_at > original_updated
