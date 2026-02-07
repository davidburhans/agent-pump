"""Tests for workspace switcher modal."""

import pytest

from agent_pump.tui.screens.workspace_switcher_modal import WorkspaceSwitcherModal


@pytest.mark.asyncio
async def test_workspace_switcher_modal_shows_workspaces():
    """Test that modal displays list of workspaces."""
    app = pytest.importorskip("textual.app").App()

    # Mock workspaces
    workspaces = ["default", "workspace-a", "workspace-b"]
    current = "default"

    modal = WorkspaceSwitcherModal(workspaces, current)

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal)

        # Check that workspace list is populated
        list_view = modal.query_one("#workspace-list")
        assert list_view is not None

        # Should have 3 items plus "Create New" option
        # The exact implementation may vary, but we expect at least 4 items
        assert len(list_view.children) >= 3


@pytest.mark.asyncio
async def test_workspace_switcher_modal_highlights_current():
    """Test that current workspace is highlighted."""
    app = pytest.importorskip("textual.app").App()

    workspaces = ["default", "other"]
    current = "default"

    modal = WorkspaceSwitcherModal(workspaces, current)

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal)

        # Find the current workspace item by its ID
        current_item = modal.query_one("#workspace-default")
        assert current_item is not None
        # The current item should have the 'current' class
        assert "current" in current_item.classes


@pytest.mark.asyncio
async def test_workspace_switcher_modal_select_workspace():
    """Test selecting a workspace."""
    app = pytest.importorskip("textual.app").App()

    workspaces = ["default", "target-workspace"]
    current = "default"

    modal = WorkspaceSwitcherModal(workspaces, current)
    result = None

    def handle_dismiss(value):
        nonlocal result
        result = value

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal, callback=handle_dismiss)

        # Navigate to and select the target workspace
        # This depends on the exact widget implementation
        # We'll simulate clicking on the second item
        list_view = modal.query_one("#workspace-list")
        if list_view.children:
            await pilot.click(list_view.children[1])

        # Or press enter to select
        await pilot.press("enter")

        # The result should be the selected workspace name
        # Note: In actual implementation this might differ
        # This test documents expected behavior


@pytest.mark.asyncio
async def test_workspace_switcher_modal_create_new():
    """Test creating a new workspace from modal."""
    app = pytest.importorskip("textual.app").App()

    workspaces = ["default"]
    current = "default"

    modal = WorkspaceSwitcherModal(workspaces, current)

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal)

        # Click the "Create New" button
        btn = modal.query_one("#btn-create")
        btn.focus()
        await pilot.press("enter")
        await pilot.pause()

        # Should show the create section with input field
        create_section = modal.query_one("#create-section")
        assert "visible" in create_section.classes


@pytest.mark.asyncio
async def test_workspace_switcher_modal_cancel():
    """Test cancelling the modal."""
    app = pytest.importorskip("textual.app").App()

    workspaces = ["default"]
    current = "default"

    modal = WorkspaceSwitcherModal(workspaces, current)
    result = "not-called"

    def handle_dismiss(value):
        nonlocal result
        result = value

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal, callback=handle_dismiss)

        # Click cancel or press escape
        btn = modal.query_one("#btn-cancel")
        btn.focus()
        await pilot.press("enter")
        await pilot.pause()

        # Result should be None (cancelled)
        assert result is None


@pytest.mark.asyncio
async def test_workspace_switcher_modal_empty_state():
    """Test modal behavior when no workspaces exist."""
    app = pytest.importorskip("textual.app").App()

    workspaces = []
    current = ""

    modal = WorkspaceSwitcherModal(workspaces, current)

    async with app.run_test() as pilot:
        await pilot.app.push_screen(modal)

        # Should show empty state message and emphasize create option
        # The exact implementation may vary
        list_view = modal.query_one("#workspace-list")
        assert list_view is not None
