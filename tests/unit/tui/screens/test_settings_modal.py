import pytest
from textual.app import App, ComposeResult

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.backends.base import AgentBackend
from agent_pump.models.workspace import Workspace
from agent_pump.tui.screens.settings_modal import SettingsModal


class DummyBackend(AgentBackend):
    """A dummy backend for testing."""
    name = "mock_backend"

    def generate(self, *args, **kwargs):
        pass


class SettingsApp(App):
    """A minimal app to host the SettingsModal."""
    def __init__(self, workspace: Workspace):
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        yield SettingsModal(self.workspace)


@pytest.fixture
def workspace(tmp_path):
    """Provide a fresh workspace with default models."""
    ws = Workspace(name="test_ws", base_path=tmp_path)
    # Clear the catalog for testing
    ws.model_catalog.backends = {}
    return ws


@pytest.mark.asyncio
async def test_settings_modal_add_model_sanitization(workspace):
    """Test that adding a model maps the sanitized widget ID back to the real backend name."""

    # Temporarily register a backend with an underscore
    original_registry = BACKEND_REGISTRY.copy()
    BACKEND_REGISTRY["mock_backend"] = DummyBackend

    try:
        app = SettingsApp(workspace)
        async with app.run_test() as pilot:
            # Switch to the Model Catalog tab
            await pilot.click("#tab-model-catalog")

            # The input ID should be sanitized: 'mock-backend'
            input_id = "#input-mock-backend"

            # Find the input and enter a model name
            input_widget = app.screen.query_one(input_id)
            input_widget.value = "my-new-model"

            # Click the Add button
            button = app.screen.query_one("#add-mock-backend")
            button.press()

            import asyncio
            await asyncio.sleep(0.1)
            await pilot.pause()

            # Get the modal instance
            modal = app.screen.query_one(SettingsModal)

            # The model should be registered under the ORIGINAL backend name
            models = workspace.model_catalog.get_models("mock_backend")
            assert "my-new-model" in models, f"Model not found in 'mock_backend'. Current catalog: {workspace.model_catalog.backends}"
            # Ensure it WAS NOT registered under the sanitized name
            assert "mock-backend" not in workspace.model_catalog.backends
    finally:
        # Restore the registry
        BACKEND_REGISTRY.clear()
        BACKEND_REGISTRY.update(original_registry)
