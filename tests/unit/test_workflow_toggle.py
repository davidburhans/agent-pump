from unittest.mock import patch

import pytest

from agent_pump.tui.app import AgentPumpApp


@pytest.mark.asyncio
async def test_w_key_toggles_workflow_panel_globally():
    """Test that pressing 'w' (lowercase) toggles the workflow panel globally."""

    # We need to mock the services initialized in __init__
    with patch('agent_pump.tui.app.AppState'), \
         patch('agent_pump.tui.app.EventBus'), \
         patch('agent_pump.tui.app.WorkspaceService'), \
         patch('agent_pump.tui.app.ProjectService'), \
         patch('agent_pump.tui.app.WorkflowService'), \
         patch('agent_pump.tui.app.IdeaService'):

        app = AgentPumpApp()

        async with app.run_test() as pilot:
            # Initially visible
            right_sidebar = pilot.app.query_one("#right-sidebar")
            assert right_sidebar.display is True

            # No project selected - it should still work
            app.selected_project = None

            # Press 'w' (lowercase) - should toggle OFF
            await pilot.press("w")
            assert right_sidebar.display is False

            # Press 'w' again - should toggle ON
            await pilot.press("w")
            assert right_sidebar.display is True
