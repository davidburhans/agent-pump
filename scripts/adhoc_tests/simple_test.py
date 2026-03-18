#!/usr/bin/env python3
"""Simple test to verify the current implementation."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))


def test_imports():
    """Test that core modules can be imported."""
    try:
        from agent_pump.utils.roadmap import RoadmapParser

        _ = RoadmapParser

        print("✓ RoadmapParser imported successfully")

        from agent_pump.tui.screens.roadmap_modal import RoadmapModal

        _ = RoadmapModal

        print("✓ RoadmapModal imported successfully")

        from agent_pump.models.project import Project

        _ = Project

        print("✓ Project imported successfully")

        from agent_pump.config import Config

        _ = Config

        print("✓ Config imported successfully")

        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_roadmap_functionality():
    """Test roadmap parsing functionality."""
    try:
        import tempfile
        from pathlib import Path

        from agent_pump.utils.roadmap import RoadmapParser

        # Create a temporary roadmap file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("""# Agent Pump - Roadmap

## Status Legend

- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- 🟢 **Complete** - Implemented and verified

---

## Current Sprint

### 🔴 Feature Prioritization
**Priority: High**

Allow users to prioritize which roadmap items are worked on next via the TUI.

**Acceptance Criteria:**
- List all uncompleted roadmap items in a dedicated TUI view
- Support moving items up/down the list (k/j keys or dragging)
- Persistent reordering of ROADMAP.md based on user selection
- Orchestrator respects the new order

---

### 🟡 Real-time State Visibility
**Priority: Medium**

Ability to see the current state of the machine while the machine is executing.

---

## Future Enhancements

### 🔴 Notification System
**Priority: Low**

Future notification capabilities.

""")
            temp_path = f.name

        # Test parsing
        parser = RoadmapParser(Path(temp_path))
        features = parser.parse()

        print(f"✓ Parsed {len(features)} features from roadmap")

        uncompleted = parser.get_uncompleted_features()
        print(f"✓ Found {len(uncompleted)} uncompleted features")

        # Clean up
        os.unlink(temp_path)

        return True
    except Exception as e:
        print(f"✗ Roadmap functionality test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Running simple verification tests...")

    success = True
    success &= test_imports()
    success &= test_roadmap_functionality()

    if success:
        print("\n✓ All verification tests passed!")
    else:
        print("\n✗ Some verification tests failed!")
        sys.exit(1)
