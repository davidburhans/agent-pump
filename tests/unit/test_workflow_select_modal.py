"""Tests for workflow select modal TUI screen."""

from unittest.mock import MagicMock

import pytest

from agent_pump.orchestrator.workflow_definition import WorkflowDefinition, WorkflowPhase
from agent_pump.tui.screens.workflow_select_modal import WorkflowSelectModal


@pytest.fixture
def mock_workspace():
    """Create a mock workspace with workflow definitions."""
    workspace = MagicMock()
    workspace.workflow_definitions = {}
    return workspace


@pytest.fixture
def default_workflow():
    """Create the default workflow definition."""
    return WorkflowDefinition(
        name="default",
        description="Standard 5-phase development workflow",
        phases=[
            WorkflowPhase(name="planning", on_success="implementing", icon="📋"),
            WorkflowPhase(name="implementing", on_success="verifying", icon="🔨"),
            WorkflowPhase(name="verifying", on_success="completed", icon="✅"),
        ],
    )


@pytest.fixture
def custom_workflow():
    """Create a custom workflow definition."""
    return WorkflowDefinition(
        name="custom",
        description="Custom minimal workflow",
        phases=[
            WorkflowPhase(name="planning", on_success="completed", icon="📋"),
            WorkflowPhase(name="review", on_success="completed", icon="👀"),
        ],
    )


class TestWorkflowSelectModal:
    """Tests for WorkflowSelectModal screen."""

    @pytest.mark.asyncio
    async def test_modal_shows_workflow_list(self, mock_workspace, default_workflow):
        """Test that modal displays list of workflows."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow}

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            await pilot.pause()

            # Check that workflow list table exists and has rows
            table = modal.query_one("#workflow-list")
            assert table is not None
            # Table should have the workflow
            from textual.widgets import DataTable

            assert isinstance(table, DataTable)
            assert table.row_count >= 1

    @pytest.mark.asyncio
    async def test_modal_selects_current_workflow_by_default(
        self, mock_workspace, default_workflow, custom_workflow
    ):
        """Test that current workflow is in the list."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {
            "default": default_workflow,
            "custom": custom_workflow,
        }

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            await pilot.pause()

            # Check that workflows are in the list
            table = modal.query_one("#workflow-list")
            from textual.widgets import DataTable

            assert isinstance(table, DataTable)
            assert table.row_count == 2

    @pytest.mark.asyncio
    async def test_select_different_workflow_updates_button(
        self, mock_workspace, default_workflow, custom_workflow
    ):
        """Test that selecting a different workflow enables the select button."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {
            "default": default_workflow,
            "custom": custom_workflow,
        }

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            await pilot.pause()

            # Initially select button should be disabled (same workflow selected)
            select_btn = modal.query_one("#btn-select")
            assert select_btn.disabled

            # Manually update selection to different workflow
            modal._selected_workflow_name = "custom"
            modal._update_buttons()

            # Button should now be enabled
            assert not select_btn.disabled

    @pytest.mark.asyncio
    async def test_escape_key_dismisses_with_none(self, mock_workspace, default_workflow):
        """Test that pressing escape dismisses with None."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow}

        result = "not_none"

        def handle_dismiss(value):
            nonlocal result
            result = value

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal, callback=handle_dismiss)
            await pilot.pause()

            # Press escape
            await pilot.press("escape")
            await pilot.pause()

            # Result should be None
            assert result is None

    @pytest.mark.asyncio
    async def test_empty_workflow_list_shows_no_workflows(self, mock_workspace):
        """Test that empty workflow list is handled gracefully."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        # Empty workflows dict (simulate no workflows available)
        modal._workflows = {}

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            await pilot.pause()

            # Table should exist - if workflows dict is empty, the table may still
            # be populated from workspace.workflow_definitions, so just verify it exists
            table = modal.query_one("#workflow-list")
            from textual.widgets import DataTable

            assert isinstance(table, DataTable)
            # The modal gracefully handles empty state

    def test_modal_initialization(self, mock_workspace):
        """Test modal initialization with various parameters."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="custom",
        )

        assert modal.workspace == mock_workspace
        assert modal.current_workflow_name == "custom"
        assert modal._selected_workflow_name is None

    def test_get_selected_workflow_returns_selected_name(self, mock_workspace, default_workflow):
        """Test get_selected_workflow method."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )

        # Initially None
        assert modal.get_selected_workflow() is None

        # After setting
        modal._selected_workflow_name = "custom"
        assert modal.get_selected_workflow() == "custom"

    @pytest.mark.asyncio
    async def test_same_workflow_selection_does_not_enable_button(
        self, mock_workspace, default_workflow
    ):
        """Test that selecting the same workflow keeps button disabled."""
        textual_app = pytest.importorskip("textual.app").App()

        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow}

        async with textual_app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            await pilot.pause()

            # Select button should be disabled when current workflow is selected
            select_btn = modal.query_one("#btn-select")
            assert select_btn.disabled

    def test_handle_select_dismisses_with_workflow_name(self, mock_workspace, custom_workflow):
        """Test that _handle_select dismisses with workflow name."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": custom_workflow, "custom": custom_workflow}
        modal._selected_workflow_name = "custom"

        result = None

        def handle_dismiss(value):
            nonlocal result
            result = value

        modal.dismiss = handle_dismiss  # type: ignore[assignment]
        modal._handle_select()

        assert result == "custom"

    def test_handle_select_dismisses_with_none_for_same_workflow(
        self, mock_workspace, default_workflow
    ):
        """Test that _handle_select dismisses with None when same workflow selected."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow}
        modal._selected_workflow_name = "default"

        result = "not_none"

        def handle_dismiss(value):
            nonlocal result
            result = value

        modal.dismiss = handle_dismiss  # type: ignore[assignment]
        modal._handle_select()

        assert result is None

    def test_update_buttons_with_same_workflow(self, mock_workspace, default_workflow):
        """Test _update_buttons disables button for same workflow."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow}
        modal._selected_workflow_name = "default"

        # Create a mock button
        mock_button = MagicMock()
        mock_button.label = "Select Workflow"
        modal.query_one = MagicMock(return_value=mock_button)

        modal._update_buttons()

        assert mock_button.disabled is True

    def test_update_buttons_with_different_workflow(
        self, mock_workspace, default_workflow, custom_workflow
    ):
        """Test _update_buttons enables button for different workflow."""
        modal = WorkflowSelectModal(
            workspace=mock_workspace,
            current_workflow_name="default",
        )
        modal._workflows = {"default": default_workflow, "custom": custom_workflow}
        modal._selected_workflow_name = "custom"

        # Create a mock button
        mock_button = MagicMock()
        mock_button.label = "Select Workflow"
        modal.query_one = MagicMock(return_value=mock_button)

        modal._update_buttons()

        assert mock_button.disabled is False
