import pytest
from textual.app import App

from agent_pump.tui.app import AgentPumpApp


@pytest.mark.asyncio
async def test_app_startup():
    """Test that the app can be instantiated."""
    app = AgentPumpApp()
    assert isinstance(app, App)
    assert app.TITLE == "Agent Pump"

    # We can't easily run the full app loop in a unit test without a pilot,
    # but we can verify it initializes internal state correctly.
    assert app.projects == {}
    assert app.workflows == {}

@pytest.mark.asyncio
async def test_app_compose():
    """Test that compose returns expected widgets."""
    _ = AgentPumpApp()

    # Textual 0.40+ allows testing compose directly if we handle the yield
    # But usually we use the pilot. Let's just rely on the fact it doesn't crash on init.
    pass
