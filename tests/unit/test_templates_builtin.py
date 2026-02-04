"""Unit tests for built-in templates."""

import pytest

from agent_pump.models.template import ProjectTemplate
from agent_pump.templates.builtin import (
    get_all_builtin_templates,
    get_builtin_template,
    get_go_template,
    get_node_npm_template,
    get_python_uv_template,
    get_rust_cargo_template,
)


class TestBuiltinTemplatesExist:
    """Test that all built-in templates exist and are valid."""

    def test_python_uv_template_exists(self):
        """Test that Python/uv template exists."""
        template = get_python_uv_template()
        assert isinstance(template, ProjectTemplate)
        assert template.name == "python-uv"

    def test_node_npm_template_exists(self):
        """Test that Node/npm template exists."""
        template = get_node_npm_template()
        assert isinstance(template, ProjectTemplate)
        assert template.name == "node-npm"

    def test_rust_cargo_template_exists(self):
        """Test that Rust/cargo template exists."""
        template = get_rust_cargo_template()
        assert isinstance(template, ProjectTemplate)
        assert template.name == "rust-cargo"

    def test_go_template_exists(self):
        """Test that Go template exists."""
        template = get_go_template()
        assert isinstance(template, ProjectTemplate)
        assert template.name == "go"


class TestPythonUvTemplate:
    """Test Python/uv template configuration."""

    @pytest.fixture
    def template(self):
        return get_python_uv_template()

    def test_basic_metadata(self, template):
        """Test template metadata."""
        assert template.name == "python-uv"
        assert "python" in template.description.lower()
        assert "uv" in template.description.lower()
        assert template.category == "built-in"
        assert template.version == "1.0.0"
        assert "python" in template.tags
        assert "uv" in template.tags
        assert template.author == "Agent Pump"

    def test_backend_configuration(self, template):
        """Test backend is set to gemini."""
        assert template.config.backend == "gemini"

    def test_workflow_settings(self, template):
        """Test workflow settings."""
        assert template.config.workflow_max_iterations == 10
        assert template.config.workflow_timeout == 1800
        assert template.config.workflow_name == "default"

    def test_branch_strategy(self, template):
        """Test branch strategy configuration."""
        assert template.config.branch_strategy.enabled is True
        assert template.config.branch_strategy.auto_create_branch is True
        assert template.config.branch_strategy.auto_merge is False
        assert template.config.branch_strategy.branch_prefix == "feature"
        assert template.config.branch_strategy.base_branch == "main"
        assert template.config.branch_strategy.require_clean_worktree is True

    def test_verification_commands(self, template):
        """Test verification commands for Python/uv."""
        assert template.config.verification.build_cmd == "uv build"
        assert template.config.verification.lint_cmd == "uv run ruff check ."
        assert template.config.verification.test_cmd == "uv run pytest tests/ -v"
        assert template.config.verification.skip_verification is False

    def test_phase_backends(self, template):
        """Test phase backend configuration."""
        assert template.config.phase_backends is not None
        assert len(template.config.phase_backends.defaults.backends) > 0
        assert template.config.phase_backends.defaults.backends[0].name == "gemini"

    def test_prompts_content(self, template):
        """Test that prompts contain relevant content."""
        # Check pre_planning mentions uv and Python
        assert "uv" in template.prompts.pre_planning.lower()
        assert "python" in template.prompts.pre_planning.lower()

        # Check pre_implementing mentions type hints and ruff
        assert "type hint" in template.prompts.pre_implementing.lower()
        assert "ruff" in template.prompts.pre_implementing.lower()


class TestNodeNpmTemplate:
    """Test Node/npm template configuration."""

    @pytest.fixture
    def template(self):
        return get_node_npm_template()

    def test_basic_metadata(self, template):
        """Test template metadata."""
        assert template.name == "node-npm"
        assert (
            "node" in template.description.lower() or "javascript" in template.description.lower()
        )
        assert template.category == "built-in"
        assert "nodejs" in template.tags or "javascript" in template.tags

    def test_verification_commands(self, template):
        """Test verification commands for Node/npm."""
        assert "npm run build" in template.config.verification.build_cmd
        assert "npm run lint" in template.config.verification.lint_cmd
        assert "npm test" in template.config.verification.test_cmd

    def test_prompts_content(self, template):
        """Test that prompts contain relevant content."""
        assert "node" in template.prompts.pre_planning.lower()
        assert "npm" in template.prompts.pre_planning.lower()
        assert "eslint" in template.prompts.pre_planning.lower()


class TestRustCargoTemplate:
    """Test Rust/cargo template configuration."""

    @pytest.fixture
    def template(self):
        return get_rust_cargo_template()

    def test_basic_metadata(self, template):
        """Test template metadata."""
        assert template.name == "rust-cargo"
        assert "rust" in template.description.lower()
        assert template.category == "built-in"
        assert "rust" in template.tags
        assert "cargo" in template.tags

    def test_verification_commands(self, template):
        """Test verification commands for Rust/cargo."""
        assert "cargo build" in template.config.verification.build_cmd
        assert "cargo clippy" in template.config.verification.lint_cmd
        assert "cargo test" in template.config.verification.test_cmd

    def test_prompts_content(self, template):
        """Test that prompts contain relevant content."""
        assert "rust" in template.prompts.pre_planning.lower()
        assert "cargo" in template.prompts.pre_planning.lower()
        assert "clippy" in template.prompts.pre_verifying.lower()
        assert (
            "result" in template.prompts.pre_implementing.lower()
            or "type" in template.prompts.pre_implementing.lower()
        )


class TestGoTemplate:
    """Test Go template configuration."""

    @pytest.fixture
    def template(self):
        return get_go_template()

    def test_basic_metadata(self, template):
        """Test template metadata."""
        assert template.name == "go"
        assert "go" in template.description.lower() or "golang" in template.description.lower()
        assert template.category == "built-in"
        assert "go" in template.tags or "golang" in template.tags

    def test_verification_commands(self, template):
        """Test verification commands for Go."""
        assert "go build" in template.config.verification.build_cmd
        assert "golangci-lint" in template.config.verification.lint_cmd
        assert "go test" in template.config.verification.test_cmd

    def test_prompts_content(self, template):
        """Test that prompts contain relevant content."""
        assert "go" in template.prompts.pre_planning.lower()
        assert (
            "gofmt" in template.prompts.pre_planning.lower()
            or "format" in template.prompts.pre_planning.lower()
        )


class TestGetAllBuiltinTemplates:
    """Test getting all built-in templates."""

    def test_returns_list(self):
        """Test that function returns a list."""
        templates = get_all_builtin_templates()
        assert isinstance(templates, list)
        assert len(templates) == 4  # python-uv, node-npm, rust-cargo, go

    def test_all_expected_templates_present(self):
        """Test that all expected templates are present."""
        templates = get_all_builtin_templates()
        names = {t.name for t in templates}

        assert "python-uv" in names
        assert "node-npm" in names
        assert "rust-cargo" in names
        assert "go" in names

    def test_all_are_builtin_category(self):
        """Test that all templates are marked as built-in."""
        templates = get_all_builtin_templates()
        for template in templates:
            assert template.category == "built-in"

    def test_all_have_required_fields(self):
        """Test that all templates have required fields."""
        templates = get_all_builtin_templates()
        for template in templates:
            assert template.name
            assert template.description
            assert template.config is not None
            assert template.config.verification is not None


class TestGetBuiltinTemplate:
    """Test getting specific built-in template by name."""

    def test_get_python_uv(self):
        """Test getting python-uv template."""
        template = get_builtin_template("python-uv")
        assert template is not None
        assert template.name == "python-uv"

    def test_get_node_npm(self):
        """Test getting node-npm template."""
        template = get_builtin_template("node-npm")
        assert template is not None
        assert template.name == "node-npm"

    def test_get_rust_cargo(self):
        """Test getting rust-cargo template."""
        template = get_builtin_template("rust-cargo")
        assert template is not None
        assert template.name == "rust-cargo"

    def test_get_go(self):
        """Test getting go template."""
        template = get_builtin_template("go")
        assert template is not None
        assert template.name == "go"

    def test_get_nonexistent_returns_none(self):
        """Test that non-existent template returns None."""
        template = get_builtin_template("does-not-exist")
        assert template is None

    def test_get_case_sensitive(self):
        """Test that template names are case-sensitive."""
        template = get_builtin_template("Python-UV")  # Wrong case
        assert template is None
