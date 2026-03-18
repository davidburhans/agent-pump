"""Tests for RoadmapService."""

import pytest

from agent_pump.models.project import Project
from agent_pump.models.roadmap import RoadmapStatus
from agent_pump.services.roadmap_service import RoadmapService


@pytest.fixture
def temp_project(tmp_path):
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    return Project.from_path(project_path)


def test_load_empty_roadmap(temp_project):
    service = RoadmapService(temp_project)
    roadmap = service.load()
    assert roadmap.current_sprint == []
    assert roadmap.future_sprints == []
    assert roadmap.deferred == []


def test_load_populated_roadmap(temp_project):
    content = """# Roadmap

## Current Sprint

### 🟡 Feature A
**Priority: High**

Description A

## Future Sprints

### 🔴 Feature B
**Priority: Medium**

Description B
"""
    (temp_project.path / "ROADMAP.md").write_text(content, encoding="utf-8")
    service = RoadmapService(temp_project)
    roadmap = service.load()

    assert len(roadmap.current_sprint) == 1
    assert roadmap.current_sprint[0].title == "Feature A"
    assert roadmap.current_sprint[0].status == RoadmapStatus.IN_PROGRESS
    assert roadmap.current_sprint[0].priority == "High"

    assert len(roadmap.future_sprints) == 1
    assert roadmap.future_sprints[0].title == "Feature B"
    assert roadmap.future_sprints[0].status == RoadmapStatus.NOT_STARTED


def test_add_item(temp_project):
    service = RoadmapService(temp_project)
    service.add_item("New Feature", "Desc", "Low", RoadmapStatus.NOT_STARTED, section="future")

    roadmap = service.load()
    assert len(roadmap.future_sprints) == 1
    item = roadmap.future_sprints[0]
    assert item.title == "New Feature"
    assert item.priority == "Low"
    assert item.status == RoadmapStatus.NOT_STARTED


def test_save_roadmap(temp_project):
    service = RoadmapService(temp_project)
    service.add_item("Saved Feature", "Desc", "High", RoadmapStatus.IN_PROGRESS, section="current")

    content = (temp_project.path / "ROADMAP.md").read_text(encoding="utf-8")
    assert "## Current Sprint" in content
    assert "### 🟡 Saved Feature" in content
    assert "**Priority: High**" in content
