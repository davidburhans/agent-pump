"""Tests for the workflow state machine."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_pump.backends.gemini import GeminiBackend
from agent_pump.models.project import Project
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.orchestrator.prompts import (
    build_brainstorming_prompt,
    build_committing_prompt,
    build_implementing_prompt,
    build_planning_prompt,
)


class TestProjectWorkflow:
    """Tests for the ProjectWorkflow state machine."""

    @pytest.fixture
    def project(self, sample_project_path):
        """Create a test project."""
        return Project.from_path(sample_project_path)

    @pytest.fixture
    def workflow(self, project):
        """Create a test workflow."""
        return ProjectWorkflow(project=project)

    def test_initial_state(self, workflow):
        """Test that workflow starts in idle state."""
        assert workflow.state == "idle"

    def test_start_transition(self, workflow):
        """Test transitioning from idle to planning."""
        workflow.start()
        assert workflow.state == "planning"

    def test_planning_to_implementing(self, workflow):
        """Test transitioning from planning to implementing."""
        workflow.start()
        workflow.plan_complete()
        assert workflow.state == "implementing"

    def test_implementing_to_brainstorming(self, workflow):
        """Test transitioning from implementing to brainstorming."""
        workflow.start()
        workflow.plan_complete()
        workflow.implement_complete()
        assert workflow.state == "brainstorming"

    def test_brainstorming_to_committing(self, workflow):
        """Test transitioning from brainstorming to committing."""
        workflow.start()
        workflow.plan_complete()
        workflow.implement_complete()
        workflow.brainstorm_complete()
        assert workflow.state == "committing"

    def test_full_cycle(self, workflow):
        """Test a full workflow cycle back to planning."""
        workflow.start()
        workflow.plan_complete()
        workflow.implement_complete()
        workflow.brainstorm_complete()
        workflow.commit_complete()
        assert workflow.state == "planning"

    def test_error_recovery(self, workflow):
        """Test error state and recovery."""
        workflow.start()
        workflow.plan_failed()
        assert workflow.state == "error"
        
        workflow.reset()
        assert workflow.state == "idle"

    def test_pause_from_any_state(self, workflow):
        """Test that pause works from any state."""
        workflow.start()
        workflow.plan_complete()
        assert workflow.state == "implementing"
        
        workflow.pause()
        assert workflow.state == "idle"

    def test_state_change_callback(self, project):
        """Test that state change callback is called."""
        callback = MagicMock()
        workflow = ProjectWorkflow(
            project=project,
            on_state_change=callback,
        )
        
        workflow.start()
        callback.assert_called_with("idle", "planning")

    def test_get_ascii_diagram(self, workflow):
        """Test ASCII diagram generation."""
        diagram = workflow.get_ascii_diagram()
        assert "WORKFLOW" in diagram
        assert "IDLE" in diagram
        assert "PLANNING" in diagram

    def test_get_diagram_source(self, workflow):
        """Test DOT diagram generation."""
        dot = workflow.get_diagram_source()
        assert "digraph" in dot
        assert "idle" in dot
        assert "planning" in dot


class TestPrompts:
    """Tests for the workflow prompts."""

    def test_planning_prompt(self):
        """Test planning prompt includes key instructions."""
        prompt = build_planning_prompt()
        assert "ROADMAP.md" in prompt
        assert "ENGINEERING_PLAN.md" in prompt
        assert "BEST_PRACTICES.md" in prompt

    def test_planning_prompt_with_branch(self):
        """Test planning prompt includes branch instructions."""
        prompt = build_planning_prompt(branch="feature/dev")
        assert "feature/dev" in prompt
        assert "git checkout" in prompt

    def test_implementing_prompt(self):
        """Test implementing prompt includes key instructions."""
        prompt = build_implementing_prompt()
        assert "ENGINEERING_PLAN.md" in prompt
        assert "BEST_PRACTICES.md" in prompt

    def test_committing_prompt_no_git_add_all(self):
        """Test committing prompt forbids git add ."""
        prompt = build_committing_prompt()
        assert "git add ." in prompt  # Mention of what NOT to do
        assert "NEVER use `git add .`" in prompt


class TestGeminiBackend:
    """Tests for the GeminiBackend."""

    def test_name(self):
        """Test backend name."""
        backend = GeminiBackend()
        assert backend.name == "Gemini CLI"

    def test_command(self):
        """Test backend command."""
        backend = GeminiBackend()
        assert backend.command == "gemini"
