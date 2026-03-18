"""Tests for roadmap UI components."""

import pytest

from agent_pump.tui.screens.add_roadmap_item_modal import AddRoadmapItemModal
from agent_pump.tui.screens.roadmap_modal import RoadmapModal


@pytest.fixture
def sample_roadmap(tmp_path):
    roadmap_path = tmp_path / "ROADMAP.md"
    content = """# Roadmap

## Current Sprint
### 🔴 Task 1
---
## Future Enhancements
### 🔴 Task 2
---
"""
    roadmap_path.write_text(content, encoding="utf-8")
    return roadmap_path


def test_roadmap_modal_init(sample_roadmap):
    modal = RoadmapModal(sample_roadmap)
    assert modal.roadmap_path == sample_roadmap
    assert len(modal.uncompleted_features) == 2
    assert modal.uncompleted_features[0].title == "Task 1"


def test_add_roadmap_item_modal_init():
    modal = AddRoadmapItemModal()
    assert modal is not None
