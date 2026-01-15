from unittest.mock import MagicMock

import pytest

from agent_pump.models.workspace import (
    BackendInstance,
    ProjectConfig,
    Workspace,
)
from agent_pump.tui.screens.backend_config_modal import BackendConfigModal
from agent_pump.tui.screens.prompt_config_modal import PromptConfigModal


class MockApp:
    def push_screen(self, screen, callback=None):
        pass

@pytest.fixture
def workspace_with_projects(tmp_path):
    ws = Workspace(name="test_ws")

    # Project A (Source)
    proj_a = ProjectConfig(path=tmp_path / "project_a", name="Project A")
    # Configure A
    proj_a.phase_backends.planning.backends = [
        BackendInstance(name="gemini", args=["--model", "gemini-pro"])
    ]
    proj_a.prompt_customization.planning_prefix = "PLAN_PREFIX_A"

    # Project B (Target)
    proj_b = ProjectConfig(path=tmp_path / "project_b", name="Project B")
    # Configure B (Default/Empty)

    # Project C (Other)
    proj_c = ProjectConfig(path=tmp_path / "project_c", name="Project C")

    ws.add_project(proj_a.path, proj_a)
    ws.add_project(proj_b.path, proj_b)
    ws.add_project(proj_c.path, proj_c)

    return ws, proj_a, proj_b, proj_c

@pytest.mark.asyncio
async def test_backend_copy_from_project(workspace_with_projects):
    ws, proj_a, proj_b, proj_c = workspace_with_projects

    # Open modal for Project B
    modal = BackendConfigModal(proj_b, ws)
    modal.notify = MagicMock()

    # Initial state: B has default planning
    assert len(modal._phase_backends_lists["planning"]) == 1
    assert modal._phase_backends_lists["planning"][0].name == "gemini"
    assert not modal._phase_backends_lists["planning"][0].args

    # Copy from Project A
    # The source string format is "project:{path}"
    source_str = f"project:{proj_a.path}"
    await modal._apply_copy("planning", source_str)

    # Verify B's modal state
    backends = modal._phase_backends_lists["planning"]
    assert len(backends) == 1
    assert backends[0].name == "gemini"
    assert backends[0].args == ["--model", "gemini-pro"]

@pytest.mark.asyncio
async def test_backend_apply_to_all(workspace_with_projects):
    ws, proj_a, proj_b, proj_c = workspace_with_projects

    # Open modal for Project A
    modal = BackendConfigModal(proj_a, ws)
    # Mock notify
    modal.notify = MagicMock()

    # Apply A's config to all (B and C)
    modal._perform_apply_to_all()

    # Verify B and C are updated
    assert len(proj_b.phase_backends.planning.backends) == 1
    assert proj_b.phase_backends.planning.backends[0].args == ["--model", "gemini-pro"]

    assert len(proj_c.phase_backends.planning.backends) == 1
    assert proj_c.phase_backends.planning.backends[0].args == ["--model", "gemini-pro"]

@pytest.mark.asyncio
async def test_prompt_copy_from_project(workspace_with_projects):
    ws, proj_a, proj_b, proj_c = workspace_with_projects

    # Open modal for Project B
    modal = PromptConfigModal(proj_b, ws)
    # Mock query_one to return mocks for TextAreas
    mock_widgets = {}
    def query_one_side_effect(selector, type=None):
        if selector not in mock_widgets:
            mock = MagicMock()
            mock.text = "" # Default text
            mock_widgets[selector] = mock
        return mock_widgets[selector]

    modal.query_one = MagicMock(side_effect=query_one_side_effect)
    modal.notify = MagicMock()

    # Copy from Project A
    source_str = f"project:{proj_a.path}"
    await modal._apply_copy("planning", source_str)

    # Verify UI update (mocked widgets)
    assert mock_widgets["#planning-prefix"].text == "PLAN_PREFIX_A"

@pytest.mark.asyncio
async def test_prompt_apply_to_all(workspace_with_projects):
    ws, proj_a, proj_b, proj_c = workspace_with_projects

    # Open modal for Project A
    modal = PromptConfigModal(proj_a, ws)
    modal.notify = MagicMock()

    # Mock UI state (TextArea values) because _save_config_to_memory reads from UI
    mock_widgets = {}
    def query_one_side_effect(selector, type=None):
        if selector not in mock_widgets:
            mock = MagicMock()
            # If it's a prefix/suffix/base, return what's in proj_a
            if "prefix" in selector:
                mock.text = "PLAN_PREFIX_A" if "planning" in selector else ""
            elif "suffix" in selector:
                mock.text = ""
            elif "base" in selector:
                mock.text = ""
            elif "checkbox" in selector:
                mock.value = False
            mock_widgets[selector] = mock
        return mock_widgets[selector]

    modal.query_one = MagicMock(side_effect=query_one_side_effect)

    # Apply A's config to all
    modal._perform_apply_to_all()

    # Verify B and C are updated
    assert proj_b.prompt_customization.planning_prefix == "PLAN_PREFIX_A"
    assert proj_c.prompt_customization.planning_prefix == "PLAN_PREFIX_A"
