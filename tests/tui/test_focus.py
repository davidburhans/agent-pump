import pytest

from agent_pump.models.workflow_snapshot import NodeSnapshot
from agent_pump.tui.screens.add_project_modal import AddProjectModal
from agent_pump.tui.widgets.workflow_panel import WorkflowNode


@pytest.mark.asyncio
async def test_add_project_modal_tab_order():
    """Test that tab key navigates through widgets in correct order."""
    app = pytest.importorskip("textual.app").App()
    modal = AddProjectModal()

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal)

        # Initial focus should be on path input
        assert modal.query_one("#path-input").has_focus

        # Tab -> Parent Button
        await pilot.press("tab")
        assert modal.query_one("#btn-parent").has_focus

        # Tab -> Directory Tree
        await pilot.press("tab")
        assert modal.query_one("#dir-tree").has_focus

        # Tab -> Cancel Button
        await pilot.press("tab")
        assert modal.query_one("#btn-cancel").has_focus

        # Tab -> Add Project Button
        await pilot.press("tab")
        assert modal.query_one("#btn-submit").has_focus

        # Tab -> Wrap back to Path Input (or whatever is first focusable)
        await pilot.press("tab")
        assert modal.query_one("#path-input").has_focus


def test_workflow_node_focusable():
    """Test that WorkflowNode is configured to receive focus."""
    snapshot = NodeSnapshot(id="planning", label="Planning", icon="P", status="pending")
    node = WorkflowNode(snapshot)
    assert node.can_focus is True
