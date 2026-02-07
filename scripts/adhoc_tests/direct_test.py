#!/usr/bin/env python3
"""Direct test execution to bypass any pytest output issues."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))


def run_tests():
    """Run tests directly without pytest."""
    import os
    import tempfile
    from pathlib import Path

    from agent_pump.utils.roadmap import RoadmapParser

    print("Running test_parse_roadmap...")
    roadmap_content = """# Agent Pump - Roadmap

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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(roadmap_content)
        temp_path = f.name

    try:
        parser = RoadmapParser(Path(temp_path))
        features = parser.parse()

        assert len(features) == 4, f"Expected 4 features, got {len(features)}"
        assert features[0].title == "Task 1", f"Expected Task 1, got {features[0].title}"
        assert features[0].status == "🟡", f"Expected 🟡, got {features[0].status}"
        assert features[0].priority == "High", f"Expected High, got {features[0].priority}"
        criteria = features[0].acceptance_criteria
        assert criteria is not None
        assert len(criteria) == 2, f"Expected 2 criteria, got {len(criteria)}"

        assert features[1].title == "Task 2", f"Expected Task 2, got {features[1].title}"
        assert features[1].status == "🔴", f"Expected 🔴, got {features[1].status}"

        assert features[3].title == "Task 0", f"Expected Task 0, got {features[3].title}"
        assert features[3].status == "🟢", f"Expected 🟢, got {features[3].status}"

        print("✓ test_parse_roadmap passed")
    finally:
        os.unlink(temp_path)

    print("\nRunning test_get_uncompleted_features...")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(roadmap_content)
        temp_path = f.name

    try:
        parser = RoadmapParser(Path(temp_path))
        parser.parse()
        uncompleted = parser.get_uncompleted_features()

        assert len(uncompleted) == 3, f"Expected 3 uncompleted, got {len(uncompleted)}"
        titles = [f.title for f in uncompleted]
        assert all(f.title in ["Task 1", "Task 2", "Task 3"] for f in uncompleted), (
            f"Unexpected titles: {titles}"
        )

        print("✓ test_get_uncompleted_features passed")
    finally:
        os.unlink(temp_path)

    print("\nRunning test_save_reordered_roadmap...")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(roadmap_content)
        temp_path = f.name

    try:
        parser = RoadmapParser(Path(temp_path))
        parser.parse()
        uncompleted = parser.get_uncompleted_features()

        # Reorder: Task 3, Task 1, Task 2
        reordered = [uncompleted[2], uncompleted[0], uncompleted[1]]

        parser.save_with_order(reordered)

        # Reload and check order
        new_parser = RoadmapParser(Path(temp_path))
        new_features = new_parser.parse()
        new_uncompleted = new_parser.get_uncompleted_features()

        assert [f.title for f in new_uncompleted] == ["Task 3", "Task 1", "Task 2"], (
            f"Expected ['Task 3', 'Task 1', 'Task 2'], got {[f.title for f in new_uncompleted]}"
        )

        # Ensure Task 0 is still there
        assert any(f.title == "Task 0" for f in new_features), "Task 0 disappeared from features"

        print("✓ test_save_reordered_roadmap passed")
    finally:
        os.unlink(temp_path)

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    run_tests()
