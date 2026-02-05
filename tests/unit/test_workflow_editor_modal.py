"""Tests for workflow editor modal TUI screen."""

import pytest
from textual.app import App
from textual.widgets import Select

from agent_pump.models.workspace import Workspace
from agent_pump.tui.screens.workflow_editor_modal import WorkflowEditorModal


class WorkflowEditorTestApp(App):
    """Test app for WorkflowEditorModal."""
    def __init__(self, workspace=None, workflow=None):
        super().__init__()
        self.modal = WorkflowEditorModal(workspace=workspace, workflow=workflow)

    def on_mount(self):
        self.push_screen(self.modal)


class TestWorkflowEditorModal:
    """Tests for WorkflowEditorModal screen."""

    @pytest.mark.asyncio
    async def test_modal_composition_no_crash(self, tmp_path):
        """Test that the modal can be composed without crashing (fix for EmptySelectError)."""
        # Create a mock workspace in tmp_path
        workspace = Workspace(path=tmp_path)

        app = WorkflowEditorTestApp(workspace=workspace)
        async with app.run_test():
            modal = app.modal
            # If we reach here, it didn't crash during compose
            assert modal.query_one("#phase-on-success", Select)
            assert modal.query_one("#phase-on-failure", Select)

            # Verify options are empty initially (as they are populated later or
            # allowed to be blank)
            success_select = modal.query_one("#phase-on-success", Select)
            assert success_select._allow_blank is True
