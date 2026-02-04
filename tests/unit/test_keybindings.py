"""Tests for keybindings configuration."""

from textual.binding import Binding

from agent_pump.keybindings import KEYBINDINGS, Keybinding
from agent_pump.tui.app import AgentPumpApp


def test_keybinding_model():
    """Test Keybinding model instantiation."""
    kb = Keybinding(
        key="a",
        action="test_action",
        description="Test",
        scope="global",
    )
    assert kb.key == "a"
    assert kb.action == "test_action"
    assert kb.description == "Test"
    assert kb.scope == "global"
    assert kb.web_available is True
    assert kb.show_in_footer is True


def test_keybindings_manifest_structure():
    """Test that KEYBINDINGS is a list of Keybinding objects."""
    assert isinstance(KEYBINDINGS, list)
    assert len(KEYBINDINGS) > 0
    assert all(isinstance(kb, Keybinding) for kb in KEYBINDINGS)


def test_agent_pump_app_loads_bindings():
    """Test that AgentPumpApp loads global bindings from manifest."""
    # We inspect the class attribute
    app_bindings = AgentPumpApp.BINDINGS

    # Filter manifest for global bindings
    global_kbs = [kb for kb in KEYBINDINGS if kb.scope == "global"]

    # Check count matches (assuming App doesn't add extra non-manifest bindings)
    assert len(app_bindings) == len(global_kbs)

    # Check specific binding exists
    quit_kb = None
    for b in app_bindings:
        # Handle both Binding objects and tuples (though we expect objects)
        key = b.key if isinstance(b, Binding) else b[0]
        if key == "escape":
            quit_kb = b
            break

    assert quit_kb is not None
    if isinstance(quit_kb, Binding):
        assert quit_kb.action == "quit"
        assert quit_kb.show is False
    else:
        assert quit_kb[1] == "quit"


def test_unique_keys():
    """Ensure no duplicate keys in the same scope."""
    global_keys = [kb.key for kb in KEYBINDINGS if kb.scope == "global"]
    assert len(global_keys) == len(set(global_keys)), "Duplicate global keys found"

    project_keys = [kb.key for kb in KEYBINDINGS if kb.scope == "project"]
    assert len(project_keys) == len(set(project_keys)), "Duplicate project keys found"
