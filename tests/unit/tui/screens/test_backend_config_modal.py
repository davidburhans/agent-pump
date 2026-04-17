import pytest
from textual.app import App, ComposeResult
from textual.widgets import Select

from agent_pump.backends import BACKEND_REGISTRY
from agent_pump.backends.base import AgentBackend
from agent_pump.models.workspace import Workspace, PhaseBackends, ProjectConfig
from agent_pump.tui.screens.backend_config_modal import BackendConfigModal


class DummyBackend(AgentBackend):
    """A dummy backend that supports model selection."""
    name = "mock_backend"
    
    @classmethod
    def supports_model_selection(cls) -> bool:
        return True
        
    @classmethod
    def get_available_models(cls) -> list[str]:
        return ["default-model"]
        
    def generate(self, *args, **kwargs):
        pass
        
    async def _check_availability(self):
        from agent_pump.backends.availability import BackendStatus
        return BackendStatus(is_available=True)
        
    def command(self, *args, **kwargs):
        pass
        
    def run(self, *args, **kwargs):
        pass


class BackendConfigApp(App):
    """A minimal app to host the BackendConfigModal."""
    def __init__(self, workspace: Workspace):
        super().__init__()
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        # Load the modal with an initial configuration.
        project_config = ProjectConfig(name="test_project", path="test/path", phase_backends=PhaseBackends())
        yield BackendConfigModal(project_config, self.workspace)


@pytest.fixture
def workspace(tmp_path):
    """Provide a fresh workspace with a pre-configured catalog."""
    ws = Workspace(name="test_ws", base_path=tmp_path)
    # Pre-populate the catalog
    ws.model_catalog.backends = {
        "mock_backend": ["catalog-model-1", "catalog-model-2"]
    }
    return ws


@pytest.mark.asyncio
async def test_backend_config_modal_loads_catalog_models(workspace):
    """Test that BackendConfigModal prioritizes the ModelCatalog over dynamic fetching."""
    
    # Temporarily register a backend
    original_registry = BACKEND_REGISTRY.copy()
    BACKEND_REGISTRY["mock_backend"] = DummyBackend
    
    try:
        app = BackendConfigApp(workspace)
        async with app.run_test() as pilot:
            # We need to find the Select widget for models in the mock_backend
            # The modal initializes default backend fields. We need to click "Add Backend" 
            # for a phase (e.g. 'defaults') and select mock_backend.
            
            import asyncio
            await asyncio.sleep(0.1)
            await pilot.pause()
            
            modal = app.screen.query_one(BackendConfigModal)
            
            # The 'defaults' tab is usually the first one open.
            # Click "Add Backend" button.
            await pilot.click("#btn-add-backend")
            
            # Find the new backend select widget (index 0)
            # The newly added backend would be at index length - 1, but we might just query the last one.
            # Let's find all Select widgets
            selects = app.screen.query(Select)
            backend_select = None
            for s in selects:
                # Based on earlier test errors, the ID is likely something like 'default-backend-0-0'
                if s.id and "backend" in s.id and ("default" in s.id or "defaults" in s.id):
                    backend_select = s
                    break
            
            assert backend_select is not None, "Could not find a backend Select widget"
            
            # Trigger the event manually if needed, or maybe it is generated with a different ID
            # Let's post the event to be safe.
            from textual.events import Click
            
            # Programmatically changing value might not trigger the event depending on Textual version.
            # Let's explicitly post the event.
            backend_select.value = "mock_backend"
            
            # Since the UI rebuilding might be asynchronous, we might need to wait for it.
            # In BackendConfigModal, changing the backend on a row doesn't re-render the row if it's a dynamic change.
            # Wait, if we click "Add Backend", it adds it to self._phase_backends_lists and calls _rebuild_backend_list.
            # When we added a backend, it defaulted to 'gemini'. Since gemini doesn't support models in the test, no model Select is created.
            # Then we change it to 'mock_backend'. But if it didn't have a model select before, it won't have one now unless it rebuilds!
            # Let's rebuild explicitly or update the phase_backend_list and rebuild!
            
            # Force the modal to rebuild the list
            phase_key = "default" if "default" in modal._phase_backends_lists else "defaults"
            modal._phase_backends_lists[phase_key][-1].name = "mock_backend"
            await modal._rebuild_backend_list(phase_key)
            
            import asyncio
            await asyncio.sleep(0.5)
            await pilot.pause()

            # Re-query selects because DOM might have changed
            selects = app.screen.query(Select)

            # Find the corresponding model select
            model_select = None
            for s in selects:
                if s.id and "model" in s.id and ("default" in s.id or "defaults" in s.id):
                    model_select = s
                    break
            
            assert model_select is not None, "Could not find a model Select widget"
            
            # Extract options (second item in each tuple is the actual value)
            options = [opt[1] for opt in model_select._options]
            
            # The options should come from the catalog, NOT from get_available_models()
            assert "catalog-model-1" in options, "Catalog model 1 not found in dropdown"
            assert "catalog-model-2" in options, "Catalog model 2 not found in dropdown"
            assert "default-model" not in options, "Dynamic models should not be loaded if catalog has entries"

    finally:
        # Restore the registry
        BACKEND_REGISTRY.clear()
        BACKEND_REGISTRY.update(original_registry)
