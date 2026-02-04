"""Tests for template list modal TUI screen."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from agent_pump.models.template import ProjectTemplate, TemplateConfig, TemplatePrompts
from agent_pump.tui.screens.template_list_modal import TemplateListModal


class TestTemplateListModalBasic:
    """Basic tests for TemplateListModal that don't require App context."""

    def test_modal_creation_empty(self):
        """Test that the modal can be created with no templates."""
        modal = TemplateListModal(templates=[], workspace=None)
        assert modal is not None
        assert modal.templates == []
        assert modal.workspace is None

    def test_modal_creation_with_templates(self):
        """Test that the modal can be created with templates."""
        templates = [
            ProjectTemplate(
                name="python-uv",
                description="Python project with uv toolchain",
                category="built-in",
                config=TemplateConfig(),
            ),
            ProjectTemplate(
                name="my-custom",
                description="My custom template",
                category="user",
                config=TemplateConfig(),
            ),
        ]
        modal = TemplateListModal(templates=templates, workspace=None)
        assert modal is not None
        assert len(modal.templates) == 2
        assert modal.templates[0].name == "python-uv"
        assert modal.templates[1].name == "my-custom"

    def test_modal_creation_with_workspace(self):
        """Test that the modal can be created with workspace."""
        mock_workspace = MagicMock()
        templates = [
            ProjectTemplate(
                name="test-template",
                description="Test template",
                config=TemplateConfig(),
            ),
        ]
        modal = TemplateListModal(templates=templates, workspace=mock_workspace)
        assert modal.workspace == mock_workspace


class TestTemplateListModalTemplateSelection:
    """Tests for template selection behavior."""

    def test_initial_selected_template(self):
        """Test that first template is selected by default."""
        templates = [
            ProjectTemplate(
                name="template1",
                description="First template",
                config=TemplateConfig(),
            ),
            ProjectTemplate(
                name="template2",
                description="Second template",
                config=TemplateConfig(),
            ),
        ]
        modal = TemplateListModal(templates=templates, workspace=None)
        # Initially no selection until mounted
        assert modal._selected_template is None

    def test_get_selected_template(self):
        """Test getting the selected template."""
        template = ProjectTemplate(
            name="test-template",
            description="Test template",
            config=TemplateConfig(),
        )
        modal = TemplateListModal(templates=[template], workspace=None)

        # Initially no selection
        assert modal.get_selected_template() is None

        # Set selection manually
        modal._selected_template = template
        assert modal.get_selected_template() == template


class TestTemplateListModalDataHandling:
    """Tests for template data handling."""

    def test_template_with_full_config(self):
        """Test modal with fully populated template."""
        config = TemplateConfig(
            backend="claude",
            workflow_max_iterations=20,
            workflow_timeout=3600,
        )
        prompts = TemplatePrompts(
            planning="Custom planning prompt",
            pre_gemini="Pre-gemini hook",
        )

        template = ProjectTemplate(
            name="full-template",
            description="Full configuration template",
            category="user",
            tags=["python", "web"],
            author="Test User",
            version="2.0.0",
            config=config,
            prompts=prompts,
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 15),
        )

        modal = TemplateListModal(templates=[template], workspace=None)

        assert len(modal.templates) == 1
        t = modal.templates[0]
        assert t.name == "full-template"
        assert t.description == "Full configuration template"
        assert t.category == "user"
        assert t.tags == ["python", "web"]
        assert t.author == "Test User"
        assert t.version == "2.0.0"
        assert t.config.backend == "claude"
        assert t.config.workflow_max_iterations == 20
        assert t.config.workflow_timeout == 3600
        assert t.prompts.planning == "Custom planning prompt"
        assert t.prompts.pre_gemini == "Pre-gemini hook"

    def test_template_categories(self):
        """Test handling of different template categories."""
        templates = [
            ProjectTemplate(
                name="builtin1",
                description="Built-in template 1",
                category="built-in",
                config=TemplateConfig(),
            ),
            ProjectTemplate(
                name="user1",
                description="User template 1",
                category="user",
                config=TemplateConfig(),
            ),
            ProjectTemplate(
                name="custom1",
                description="Custom template 1",
                category="custom",
                config=TemplateConfig(),
            ),
        ]

        modal = TemplateListModal(templates=templates, workspace=None)

        assert len(modal.templates) == 3
        categories = [t.category for t in modal.templates]
        assert "built-in" in categories
        assert "user" in categories
        assert "custom" in categories


class TestTemplateListModalDismissal:
    """Tests for modal dismissal behavior."""

    def test_dismiss_with_template(self):
        """Test dismissing modal with selected template."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateListModal(templates=[template], workspace=None)
        modal._selected_template = template

        # The modal should return the selected template when dismissed
        selected = modal.get_selected_template()
        assert selected == template
        assert selected.name == "test-template"

    def test_dismiss_cancel(self):
        """Test dismissing modal with no selection (cancel)."""
        template = ProjectTemplate(
            name="test-template",
            description="Test",
            config=TemplateConfig(),
        )
        modal = TemplateListModal(templates=[template], workspace=None)
        # Don't set _selected_template

        selected = modal.get_selected_template()
        assert selected is None


@pytest.mark.asyncio
class TestTemplateListModalAsync:
    """Async tests requiring Textual App context."""

    async def test_modal_compose(self):
        """Test that modal composes without errors."""
        from textual.app import App

        templates = [
            ProjectTemplate(
                name="test-template",
                description="Test template",
                config=TemplateConfig(),
            ),
        ]

        class TestApp(App):
            def compose(self):
                yield TemplateListModal(templates=templates, workspace=None)

        async with TestApp().run_test() as pilot:
            modal = pilot.app.query_one(TemplateListModal)
            assert modal is not None
            # Check that compose completed without errors
            assert len(modal.templates) == 1

    async def test_empty_state_display(self):
        """Test display when no templates available."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield TemplateListModal(templates=[], workspace=None)

        async with TestApp().run_test() as pilot:
            modal = pilot.app.query_one(TemplateListModal)
            assert modal is not None
            assert len(modal.templates) == 0
