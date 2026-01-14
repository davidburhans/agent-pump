from pathlib import Path
from unittest.mock import MagicMock

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.tui.widgets.project_card import ProjectCard


def test_project_card_formatting():
    """Test that ProjectCard formats status strings correctly."""
    project = Project(
        path=Path("/tmp/test"),
        name="Test Project",
        status=ProjectStatus.PLANNING,
        current_feature="My Feature",
    )

    card = ProjectCard(project)

    # Test status formatting
    status_str = card._format_status()
    assert "Planning" in status_str
    assert "yellow" in status_str  # Color code

    # Test feature formatting
    feature_str = card._format_feature()
    assert "My Feature" in feature_str

    # Test progress formatting
    progress_str = card._format_progress()
    # 0 completed, 0 failed, 1 active = 1 total
    assert "0 completed" in progress_str
    assert "iterations" in progress_str


def test_project_card_formatting_empty():
    """Test formatting when no feature is active."""
    project = Project(path=Path("/tmp/test"), name="Test Project", status=ProjectStatus.IDLE)

    card = ProjectCard(project)

    feature_str = card._format_feature()
    assert "No active feature" in feature_str

    progress_str = card._format_progress()
    assert "No features processed yet" in progress_str


def test_timer_lifecycle():
    """Test that timer starts/stops based on project status."""
    project = Project(
        path=Path("/tmp/test"),
        name="Test",
        status=ProjectStatus.IDLE,
    )
    card = ProjectCard(project)

    # Mock methods that interact with Textual
    card.set_interval = MagicMock(return_value=MagicMock())
    # Mock query_one since refresh_content calls it
    card.query_one = MagicMock()

    # 1. Mount while IDLE (stopped) -> No timer
    card.on_mount()
    card.set_interval.assert_not_called()
    assert card._timer_handle is None

    # 2. Change to PLANNING (active) and refresh -> Timer should start
    project.status = ProjectStatus.PLANNING
    card.refresh_content()
    card.set_interval.assert_called_once()
    assert card._timer_handle is not None

    # Reset mock to test next transition
    timer_mock = card._timer_handle
    card.set_interval.reset_mock()

    # 3. Change to PAUSED (stopped) and refresh -> Timer should stop
    project.status = ProjectStatus.PAUSED
    card.refresh_content()
    timer_mock.stop.assert_called_once()
    assert card._timer_handle is None

    # 4. Change back to IMPLEMENTING (active) -> Timer should restart
    project.status = ProjectStatus.IMPLEMENTING
    card.refresh_content()
    card.set_interval.assert_called_once()
    assert card._timer_handle is not None

