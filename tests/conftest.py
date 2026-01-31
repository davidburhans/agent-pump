"""Tests configuration."""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def disable_notifications():
    """Disable desktop notifications during tests by default."""
    if "AGENT_PUMP_NO_NOTIFY" not in os.environ:
        os.environ["AGENT_PUMP_NO_NOTIFY"] = "1"


@pytest.fixture
def sample_project_path(tmp_path):
    """Create a sample project directory with ROADMAP.md and BEST_PRACTICES.md."""
    project_path = tmp_path / "test-project"
    project_path.mkdir()

    # Create ROADMAP.md
    roadmap = project_path / "ROADMAP.md"
    roadmap.write_text(
        """# Test Project Roadmap

## Current Sprint

### 🔴 First Feature
**Priority: High**

A test feature to implement.

**Acceptance Criteria:**
- It works

## Completed

*None yet*
""",
        encoding="utf-8",
    )

    # Create BEST_PRACTICES.md
    best_practices = project_path / "BEST_PRACTICES.md"
    best_practices.write_text(
        """# Best Practices

- Write clean code
- Test everything
""",
        encoding="utf-8",
    )

    return project_path


@pytest.fixture(autouse=True)
def patch_css_variables():
    """Patch TUI widgets to replace unknown CSS variables during tests."""
    # We import inside the fixture to avoid circular imports or early import issues
    from agent_pump.tui.screens.add_project_modal import AddProjectModal
    from agent_pump.tui.screens.add_roadmap_item_modal import AddRoadmapItemModal
    from agent_pump.tui.screens.backend_config_modal import BackendConfigModal
    from agent_pump.tui.screens.confirm_modal import ConfirmModal
    from agent_pump.tui.screens.global_prompt_modal import GlobalPromptModal
    from agent_pump.tui.screens.idea_input_modal import IdeaInputModal
    from agent_pump.tui.screens.log_filter_modal import LogFilterModal
    from agent_pump.tui.screens.project_config_modal import ProjectConfigModal
    from agent_pump.tui.screens.prompt_config_modal import PromptConfigModal
    from agent_pump.tui.screens.roadmap_modal import RoadmapModal

    modals = [
        AddProjectModal,
        AddRoadmapItemModal,
        BackendConfigModal,
        ConfirmModal,
        GlobalPromptModal,
        IdeaInputModal,
        LogFilterModal,
        ProjectConfigModal,
        PromptConfigModal,
        RoadmapModal,
    ]

    original_css = {}
    for modal in modals:
        if hasattr(modal, "DEFAULT_CSS"):
            original_css[modal] = modal.DEFAULT_CSS
            modal.DEFAULT_CSS = modal.DEFAULT_CSS.replace("$glass-surface", "$surface")

    yield

    for modal, css in original_css.items():
        modal.DEFAULT_CSS = css
