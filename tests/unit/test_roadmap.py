"""Tests for roadmap utility."""

import pytest

from agent_pump.utils.roadmap import RoadmapParser


@pytest.fixture
def sample_roadmap(tmp_path):
    roadmap_path = tmp_path / "ROADMAP.md"
    content = """# Agent Pump - Roadmap

## Status Legend
- 🔴 **Not Started**
- 🟡 **In Progress**
- 🟢 **Complete**

---

## Current Sprint

### 🟡 Task 1
**Priority: High**

Description 1

**Acceptance Criteria:**
- Criterion 1a
- Criterion 1b

---

## Future Enhancements

### 🔴 Task 2
**Priority: Medium**

Description 2

**Acceptance Criteria:**
- Criterion 2a

---

### 🔴 Task 3
**Priority: Low**

Description 3

**Acceptance Criteria:**
- Criterion 3a

---

## Completed

### 🟢 Task 0
Completed description

**Acceptance Criteria:**
- Criterion 0a
"""
    roadmap_path.write_text(content, encoding="utf-8")
    return roadmap_path

def test_parse_roadmap(sample_roadmap):
    parser = RoadmapParser(sample_roadmap)
    features = parser.parse()

    assert len(features) == 4
    assert features[0].title == "Task 1"
    assert features[0].status == "🟡"
    assert features[0].priority == "High"
    assert len(features[0].acceptance_criteria) == 2

    assert features[1].title == "Task 2"
    assert features[1].status == "🔴"

    assert features[3].title == "Task 0"
    assert features[3].status == "🟢"

def test_get_uncompleted_features(sample_roadmap):
    parser = RoadmapParser(sample_roadmap)
    parser.parse()
    uncompleted = parser.get_uncompleted_features()

    assert len(uncompleted) == 3
    assert all(f.title in ["Task 1", "Task 2", "Task 3"] for f in uncompleted)

def test_save_reordered_roadmap(sample_roadmap):
    parser = RoadmapParser(sample_roadmap)
    parser.parse()
    uncompleted = parser.get_uncompleted_features()

    # Reorder: Task 3, Task 1, Task 2
    reordered = [uncompleted[2], uncompleted[0], uncompleted[1]]

    parser.save_with_order(reordered)

    # Reload and check order
    new_parser = RoadmapParser(sample_roadmap)
    new_features = new_parser.parse()
    new_uncompleted = new_parser.get_uncompleted_features()

    assert [f.title for f in new_uncompleted] == ["Task 3", "Task 1", "Task 2"]
    # Ensure Task 0 is still there
    assert any(f.title == "Task 0" for f in new_features)
