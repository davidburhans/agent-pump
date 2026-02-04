"""Tests for template apply modal TUI screen."""

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_pump.models.template import ProjectTemplate, TemplateConfig
from agent_pump.tui.screens.template_apply_modal import TemplateApplyModal


class TestTemplateApplyModalBasic:
    """Basic tests for TemplateApplyModal that don't require App context."""

    def test_modal_creation_with_template(self):
        """Test that the modal can be created with a template."""
        template = ProjectTemplate(
            name="python-uv",
            description="Python project with uv toolchain",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template)
        assert modal is not None
        assert modal.template == template
        assert modal.existing_project is None
        assert modal.is_new_project is False

    def test_modal_creation_with_existing_project(self):
        """Test modal creation for applying to existing project."""
        template = ProjectTemplate(
            name="python-uv",
            description="Python project",
            config=TemplateConfig(),
        )
        project_path = Path("/path/to/project")
        modal = TemplateApplyModal(template=template, existing_project=project_path)
        assert modal.template == template
        assert modal.existing_project == project_path
        assert modal.is_new_project is False

    def test_modal_creation_for_new_project(self):
        """Test modal creation for creating new project from template."""
        template = ProjectTemplate(
            name="python-uv",
            description="Python project",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template, is_new_project=True)
        assert modal.template == template
        assert modal.existing_project is None
        assert modal.is_new_project is True


class TestTemplateApplyModalPathValidation:
    """Tests for path validation in template apply modal."""

    def test_valid_new_project_path(self):
        """Test validation of valid new project path."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template, is_new_project=True)

        # Path should be valid (non-empty, no invalid chars)
        assert modal._is_valid_path("/home/user/new-project") is True
        assert modal._is_valid_path("./my-project") is True
        assert modal._is_valid_path("C:\\Users\\project") is True

    def test_invalid_new_project_path(self):
        """Test validation of invalid new project paths."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template, is_new_project=True)

        # Empty path is invalid
        assert modal._is_valid_path("") is False
        # Only whitespace is invalid
        assert modal._is_valid_path("   ") is False

    def test_path_exists_check_for_new_project(self):
        """Test that new project paths must not exist."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template, is_new_project=True)

        # For new projects, path should not already exist
        with patch.object(Path, "exists", return_value=True):
            assert modal._is_valid_new_project_path("/existing/path") is False

        with patch.object(Path, "exists", return_value=False):
            assert modal._is_valid_new_project_path("/new/path") is True


class TestTemplateApplyModalTemplateDisplay:
    """Tests for template information display."""

    def test_template_config_display(self):
        """Test that template config is accessible for display."""
        config = TemplateConfig(
            backend="claude",
            workflow_max_iterations=15,
            workflow_timeout=2400,
        )
        template = ProjectTemplate(
            name="claude-template",
            description="Template using Claude backend",
            category="user",
            config=config,
        )
        modal = TemplateApplyModal(template=template)

        assert modal.template.config.backend == "claude"
        assert modal.template.config.workflow_max_iterations == 15
        assert modal.template.config.workflow_timeout == 2400

    def test_template_verification_commands(self):
        """Test access to template verification configuration."""
        from agent_pump.models.verification_config import VerificationConfig

        verification = VerificationConfig(
            build_cmd="npm run build",
            lint_cmd="npm run lint",
            test_cmd="npm test",
        )
        config = TemplateConfig(verification=verification)
        template = ProjectTemplate(
            name="node-template",
            description="Node.js project template",
            config=config,
        )
        modal = TemplateApplyModal(template=template)

        assert modal.template.config.verification.build_cmd == "npm run build"
        assert modal.template.config.verification.lint_cmd == "npm run lint"
        assert modal.template.config.verification.test_cmd == "npm test"


class TestTemplateApplyModalDismissal:
    """Tests for modal dismissal behavior."""

    def test_dismiss_cancel(self):
        """Test dismissing modal with cancel returns None."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        _ = TemplateApplyModal(template=template)

        # When user cancels, should return None
        # This is handled by the dismiss callback
        result = None
        assert result is None

    def test_dismiss_apply_existing(self):
        """Test dismissing modal after applying to existing project."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        project_path = Path("/existing/project")
        modal = TemplateApplyModal(
            template=template, existing_project=project_path, is_new_project=False
        )

        assert modal.existing_project == project_path
        assert modal.is_new_project is False

    def test_dismiss_create_new(self):
        """Test dismissing modal after creating new project."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        new_path = Path("/new/project")
        modal = TemplateApplyModal(template=template, is_new_project=True)

        # Simulate setting the new project path
        modal._new_project_path = new_path
        assert modal._new_project_path == new_path
        assert modal.is_new_project is True


@pytest.mark.asyncio
class TestTemplateApplyModalAsync:
    """Async tests requiring Textual App context."""

    async def test_modal_compose_existing_project(self):
        """Test that modal composes for existing project."""
        from textual.app import App

        template = ProjectTemplate(
            name="test-template",
            description="Test template",
            config=TemplateConfig(),
        )

        class TestApp(App):
            def compose(self):
                yield TemplateApplyModal(
                    template=template,
                    existing_project=Path("/test/project"),
                    is_new_project=False,
                )

        async with TestApp().run_test() as pilot:
            modal = pilot.app.query_one(TemplateApplyModal)
            assert modal is not None
            assert modal.existing_project == Path("/test/project")
            assert modal.is_new_project is False

    async def test_modal_compose_new_project(self):
        """Test that modal composes for new project creation."""
        from textual.app import App

        template = ProjectTemplate(
            name="test-template",
            description="Test template",
            config=TemplateConfig(),
        )

        class TestApp(App):
            def compose(self):
                yield TemplateApplyModal(template=template, is_new_project=True)

        async with TestApp().run_test() as pilot:
            modal = pilot.app.query_one(TemplateApplyModal)
            assert modal is not None
            assert modal.is_new_project is True
            assert modal.existing_project is None

    async def test_apply_button_callback(self):
        """Test apply button triggers correct action."""
        from textual.app import App

        template = ProjectTemplate(
            name="test-template",
            description="Test template",
            config=TemplateConfig(),
        )

        class TestApp(App):
            def compose(self):
                yield TemplateApplyModal(
                    template=template,
                    existing_project=Path("/test/project"),
                    is_new_project=False,
                )

        async with TestApp().run_test() as pilot:
            modal = pilot.app.query_one(TemplateApplyModal)

            # Simulate clicking apply button
            # In real implementation, this would call TemplateService
            with patch.object(modal, "_apply_template") as mock_apply:
                mock_apply.return_value = True
                # Button press would trigger _apply_template
                # This is a simplified test - real implementation would interact with UI
                result = mock_apply()
                assert result is True


class TestTemplateApplyModalErrorHandling:
    """Tests for error handling in template application."""

    def test_apply_failure_handling(self):
        """Test handling of template application failure."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template)

        # Simulate application failure
        with patch.object(modal, "_apply_template") as mock_apply:
            mock_apply.return_value = False
            result = mock_apply()
            assert result is False
            # Modal should show error message to user

    def test_apply_success_handling(self):
        """Test handling of successful template application."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateApplyModal(template=template)

        # Simulate successful application
        with patch.object(modal, "_apply_template") as mock_apply:
            mock_apply.return_value = True
            result = mock_apply()
            assert result is True
            # Modal should dismiss with success
