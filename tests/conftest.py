"""Tests configuration."""

import pytest


@pytest.fixture
def sample_project_path(tmp_path):
    """Create a sample project directory with ROADMAP.md and BEST_PRACTICES.md."""
    project_path = tmp_path / "test-project"
    project_path.mkdir()

    # Create ROADMAP.md
    roadmap = project_path / "ROADMAP.md"
    roadmap.write_text("""# Test Project Roadmap

## Current Sprint

### 🔴 First Feature
**Priority: High**

A test feature to implement.

**Acceptance Criteria:**
- It works

## Completed

*None yet*
""", encoding="utf-8")

    # Create BEST_PRACTICES.md
    best_practices = project_path / "BEST_PRACTICES.md"
    best_practices.write_text("""# Best Practices

- Write clean code
- Test everything
""", encoding="utf-8")

    return project_path
