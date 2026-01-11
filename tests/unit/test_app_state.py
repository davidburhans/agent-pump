"""Unit tests for AppState model."""

from pathlib import Path

from agent_pump.models.app_state import AppState


def test_app_state_persistence(tmp_path: Path, monkeypatch):
    """Test that AppState can save and load from disk."""
    # Mock config dir
    config_dir = tmp_path / ".config" / "agent-pump"

    def mock_get_state_path(*args):
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "state.json"

    monkeypatch.setattr(AppState, "get_state_path", mock_get_state_path)

    # Initial save
    state = AppState()
    state.add_project(Path("/tmp/p1"))
    state.add_project(Path("/tmp/p2"))
    state.save()

    assert (config_dir / "state.json").exists()

    # Load back
    loaded_state = AppState.load()
    assert len(loaded_state.projects) == 2
    assert Path("/tmp/p1").resolve() in loaded_state.projects
    assert Path("/tmp/p2").resolve() in loaded_state.projects


def test_add_remove_project(tmp_path: Path, monkeypatch):
    """Test adding and removing projects."""
    config_dir = tmp_path / ".config" / "agent-pump"

    def mock_get_state_path(*args):
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "state.json"

    monkeypatch.setattr(AppState, "get_state_path", mock_get_state_path)

    state = AppState()
    p1 = Path("/tmp/p1")

    # Add
    assert state.add_project(p1) is True
    assert state.add_project(p1) is False  # Duplicate
    assert len(state.projects) == 1

    # Remove
    assert state.remove_project(p1) is True
    assert state.remove_project(p1) is False  # Already removed
    assert len(state.projects) == 0
