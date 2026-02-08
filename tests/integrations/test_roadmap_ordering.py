from pathlib import Path
from agent_pump.services.roadmap_service import RoadmapService
from agent_pump.models.project import Project

def test_add_item_top(tmp_path):
    # Setup project
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / "ROADMAP.md").write_text("", encoding="utf-8")

    project = Project(path=project_path, name="Test")
    service = RoadmapService(project)

    # Add items
    service.add_item("Item 1", section="current")
    service.add_item("Item 2", section="current", position="top")

    items = service.load().current_sprint
    assert len(items) == 2
    assert items[0].title == "Item 2"
    assert items[1].title == "Item 1"

def test_add_item_bottom(tmp_path):
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / "ROADMAP.md").write_text("", encoding="utf-8")

    project = Project(path=project_path, name="Test")
    service = RoadmapService(project)

    service.add_item("Item 1", section="current")
    service.add_item("Item 2", section="current", position="bottom")

    items = service.load().current_sprint
    assert len(items) == 2
    assert items[0].title == "Item 1"
    assert items[1].title == "Item 2"
