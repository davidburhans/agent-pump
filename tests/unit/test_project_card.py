from pathlib import Path

from agent_pump.models.project import Project, ProjectStatus
from agent_pump.tui.widgets.project_card import ProjectCard


def test_project_card_formatting():
    """Test that ProjectCard formats status strings correctly."""
    project = Project(
        path=Path("/tmp/test"),
        name="Test Project",
        status=ProjectStatus.PLANNING,
        current_feature="My Feature"
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
    project = Project(
        path=Path("/tmp/test"),
        name="Test Project",
        status=ProjectStatus.IDLE
    )
    
    card = ProjectCard(project)
    
    feature_str = card._format_feature()
    assert "No active feature" in feature_str
    
    progress_str = card._format_progress()
    assert "No features processed yet" in progress_str
