"""Tests for roadmap UI components."""

import pytest
from textual.app import App

from agent_pump.tui.screens.add_project_modal import AddProjectModal
from agent_pump.tui.screens.add_roadmap_item_modal import AddRoadmapItemModal
from agent_pump.tui.screens.roadmap_modal import RoadmapModal


@pytest.fixture
def sample_roadmap(tmp_path):
    roadmap_path = tmp_path / "ROADMAP.md"
    content = """# Roadmap
## Current Sprint
### 🔴 Task 1
---
"""
    roadmap_path.write_text(content, encoding="utf-8")
    return roadmap_path


@pytest.mark.asyncio
async def test_roadmap_modal_bindings(sample_roadmap):
    """Test that 'a' in RoadmapModal opens AddRoadmapItemModal and NOT AddProjectModal."""

    class TestApp(App):
        BINDINGS = [("a", "add_project", "Add Project")]

        def action_add_project(self):
            self.push_screen(AddProjectModal())

    app = TestApp()

    async with app.run_test() as pilot:
        # Push RoadmapModal
        await app.push_screen(RoadmapModal(sample_roadmap))

        # Press 'a'
        await pilot.press("a")

        # Check top screen
        assert isinstance(app.screen, AddRoadmapItemModal)

        # Verify that AddRoadmapItemModal has a binding for 'a'
        # This ensures it captures the key even if Input doesn't
        bindings = []
        for b in app.screen.BINDINGS:
            if isinstance(b, tuple):
                bindings.append(b[0])
            else:
                bindings.append(b.key)
        assert "a" in bindings

        # Ensure AddProjectModal is NOT in the screen stack
        assert not any(isinstance(s, AddProjectModal) for s in app._screen_stack)
        assert not isinstance(app.screen, AddProjectModal)
