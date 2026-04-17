#!/usr/bin/env python3
"""Comprehensive test to verify the roadmap feature implementation."""

import os
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))


def test_roadmap_parsing():
    """Test roadmap parsing functionality."""
    print("Testing roadmap parsing functionality...")

    from agent_pump.utils.roadmap import RoadmapParser

    # Create a temporary roadmap file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
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

### 🟡 Real-time State Visibility
**Priority: Medium**

Ability to see the current state of the machine while the machine is executing.

---

## Future Enhancements

### 🔴 Notification System
**Priority: Low**

Future notification capabilities.

""")
        temp_path = Path(f.name)

    # Test parsing
    parser = RoadmapParser(temp_path)
    features = parser.parse()

    print(f"✓ Parsed {len(features)} features from roadmap")
    assert len(features) == 3, f"Expected 3 features, got {len(features)}"

    uncompleted = parser.get_uncompleted_features()
    print(f"✓ Found {len(uncompleted)} uncompleted features")
    assert len(uncompleted) == 3, f"Expected 3 uncompleted features, got {len(uncompleted)}"

    # Check that Feature Prioritization is in the uncompleted list
    # despite being described as high priority
    titles = [f.title for f in uncompleted]
    assert "Feature Prioritization" in titles
    assert "Real-time State Visibility" in titles
    assert "Notification System" in titles

    # Test reordering
    reordered = [
        uncompleted[2],
        uncompleted[0],
        uncompleted[1],
    ]  # Notification, Feature Prioritization, Real-time
    parser.save_with_order(reordered)

    # Verify the reordering worked by parsing again
    new_parser = RoadmapParser(temp_path)
    _ = new_parser.parse()
    new_uncompleted = new_parser.get_uncompleted_features()

    new_titles = [f.title for f in new_uncompleted]
    expected_order = [
        "Notification System",
        "Feature Prioritization",
        "Real-time State Visibility",
    ]
    assert new_titles[:3] == expected_order, f"Expected {expected_order}, got {new_titles[:3]}"

    print("✓ Reordering functionality works correctly")

    # Clean up
    os.unlink(temp_path)


def test_tui_integration():
    """Test that TUI components exist and can be imported."""
    print("Testing TUI integration...")

    from agent_pump.tui.screens.roadmap_modal import RoadmapItem

    print("✓ RoadmapModal and RoadmapItem can be imported")

    from agent_pump.utils.roadmap import RoadmapFeature

    print("✓ RoadmapFeature can be imported")

    # Test creating a basic RoadmapItem
    feature = RoadmapFeature(
        title="Test Feature", status="🔴", priority="High", description="Test description"
    )
    _ = RoadmapItem(feature)
    print("✓ RoadmapItem can be instantiated")


def test_app_integration():
    """Test that the app integrates the roadmap functionality."""
    print("Testing app integration...")

    from agent_pump.tui.app import AgentPumpApp

    print("✓ AgentPumpApp can be imported")

    # Check that the app has the roadmap action
    app_class = AgentPumpApp
    # Check if the action exists by looking for the method
    assert hasattr(app_class, "action_manage_roadmap"), "action_manage_roadmap method not found"
    print("✓ action_manage_roadmap method exists")

    # Check that the 'm' binding exists
    bindings = getattr(app_class, "BINDINGS", [])
    m_binding = None
    for binding in bindings:
        if hasattr(binding, "key") and binding.key == "m":
            m_binding = binding
        elif isinstance(binding, (tuple, list)) and binding[0] == "m":
            m_binding = binding
            break

    assert m_binding is not None, "'m' binding not found in app bindings"
    print("✓ 'm' key binding exists for roadmap management")


def main():
    print("Running comprehensive verification tests for roadmap feature...\n")

    try:
        test_roadmap_parsing()
        print()
        test_tui_integration()
        print()
        test_app_integration()

        print()
        print("✅ ALL VERIFICATION TESTS PASSED!")
        print("The Feature Prioritization functionality is working correctly.")
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        print("❌ SOME VERIFICATION TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
