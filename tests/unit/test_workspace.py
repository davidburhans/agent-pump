"""Tests for workspace models."""

from pathlib import Path
from unittest.mock import patch

from agent_pump.models.workspace import (
    BackendFallback,
    BackendInstance,
    IdeaQueueItem,
    PhaseBackends,
    ProjectConfig,
    PromptCustomization,
    Workspace,
)


class TestBackendInstance:
    """Tests for BackendInstance model."""

    def test_default_values(self):
        """Test default instance is gemini with no args."""
        instance = BackendInstance()
        assert instance.name == "gemini"
        assert instance.args == []

    def test_with_args(self):
        """Test instance with custom args."""
        instance = BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])
        assert instance.name == "gemini"
        assert instance.args == ["--model", "gemini-2.5-flash"]


class TestBackendFallback:
    """Tests for BackendFallback model."""

    def test_default_backend(self):
        """Test default backend is gemini."""
        fallback = BackendFallback()
        assert len(fallback.backends) == 1
        assert fallback.backends[0].name == "gemini"

    def test_from_names(self):
        """Test creating from simple list of names."""
        fallback = BackendFallback.from_names(["claude", "gemini", "opencode"])
        assert len(fallback.backends) == 3
        assert fallback.backends[0].name == "claude"

    def test_custom_backends_with_args(self):
        """Test custom backend list with args."""
        fallback = BackendFallback(
            backends=[
                BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"]),
                BackendInstance(name="opencode"),
            ]
        )
        assert len(fallback.backends) == 2
        assert fallback.backends[0].args == ["--model", "gemini-2.5-flash"]


class TestPhaseBackends:
    """Tests for PhaseBackends model."""

    def test_default_phases(self):
        """Test all phases have default backends."""
        phase_backends = PhaseBackends()
        assert phase_backends.planning.backends[0].name == "gemini"
        assert phase_backends.implementing.backends[0].name == "gemini"
        assert phase_backends.verifying.backends[0].name == "gemini"
        assert phase_backends.brainstorming.backends[0].name == "gemini"
        assert phase_backends.committing.backends[0].name == "gemini"

    def test_custom_phase_backends(self):
        """Test customizing phase backends."""
        phase_backends = PhaseBackends(
            planning=BackendFallback.from_names(["claude"]),
            implementing=BackendFallback.from_names(["gemini", "opencode"]),
        )
        assert phase_backends.planning.backends[0].name == "claude"
        assert len(phase_backends.implementing.backends) == 2


class TestPromptCustomization:
    """Tests for PromptCustomization model."""

    def test_default_empty(self):
        """Test default customization has empty strings."""
        custom = PromptCustomization()
        assert custom.planning_prefix == ""
        assert custom.planning_suffix == ""

    def test_apply_to_prompt_no_customization(self):
        """Test applying empty customization returns base prompt."""
        custom = PromptCustomization()
        result = custom.apply_to_prompt("planning", "Base prompt")
        assert result == "Base prompt"

    def test_apply_to_prompt_with_prefix(self):
        """Test applying prefix."""
        custom = PromptCustomization(planning_prefix="Before:")
        result = custom.apply_to_prompt("planning", "Base prompt")
        assert "Before:" in result
        assert "Base prompt" in result

    def test_apply_to_prompt_with_suffix(self):
        """Test applying suffix."""
        custom = PromptCustomization(implementing_suffix="After this")
        result = custom.apply_to_prompt("implementing", "Base prompt")
        assert "Base prompt" in result
        assert "After this" in result

    def test_apply_to_prompt_with_both(self):
        """Test applying both prefix and suffix."""
        custom = PromptCustomization(verifying_prefix="Start:", verifying_suffix="End")
        result = custom.apply_to_prompt("verifying", "Middle")
        assert result == "Start:\n\nMiddle\n\nEnd"


class TestIdeaQueueItem:
    """Tests for IdeaQueueItem model."""

    def test_basic_idea(self):
        """Test creating a basic idea."""
        idea = IdeaQueueItem(idea="Add dark mode")
        assert idea.idea == "Add dark mode"
        assert idea.priority == 0
        assert idea.source == "user"

    def test_prioritized_idea(self):
        """Test creating a prioritized idea."""
        idea = IdeaQueueItem(idea="Critical fix", priority=10)
        assert idea.priority == 10


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_name_from_path(self):
        """Test name is inferred from path."""
        config = ProjectConfig(path=Path("c:/projects/my-app"))
        assert config.name == "my-app"

    def test_explicit_name(self):
        """Test explicit name overrides inference."""
        config = ProjectConfig(path=Path("c:/projects/my-app"), name="My Application")
        assert config.name == "My Application"

    def test_default_phase_backends(self):
        """Test default phase backends are assigned."""
        config = ProjectConfig(path=Path("."))
        assert config.phase_backends.implementing.backends[0].name == "gemini"

    def test_prompt_customization_default(self):
        """Test default prompt customization is empty."""
        config = ProjectConfig(path=Path("."))
        assert config.prompt_customization.planning_prefix == ""


class TestWorkspace:
    """Tests for Workspace model."""

    def test_default_name(self):
        """Test default workspace name."""
        workspace = Workspace()
        assert workspace.name == "default"
        assert workspace.projects == {}
        assert workspace.idea_queue == []

    def test_add_project(self, tmp_path):
        """Test adding a project to workspace."""
        workspace = Workspace()
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        result = workspace.add_project(project_path)
        assert result is True
        assert str(project_path.resolve()) in workspace.projects

        # Adding again should return False
        result = workspace.add_project(project_path)
        assert result is False

    def test_remove_project(self, tmp_path):
        """Test removing a project from workspace."""
        workspace = Workspace()
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        workspace.add_project(project_path)
        result = workspace.remove_project(project_path)
        assert result is True
        assert str(project_path.resolve()) not in workspace.projects

        # Removing again should return False
        result = workspace.remove_project(project_path)
        assert result is False

    def test_get_project_config(self, tmp_path):
        """Test getting project config."""
        workspace = Workspace()
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Before adding
        assert workspace.get_project_config(project_path) is None

        # After adding
        workspace.add_project(project_path)
        config = workspace.get_project_config(project_path)
        assert config is not None
        assert config.path == project_path.resolve()

    def test_add_idea(self):
        """Test adding ideas to queue."""
        workspace = Workspace()
        workspace.add_idea("First idea")
        workspace.add_idea("High priority idea", priority=10)
        workspace.add_idea("Second idea")

        assert len(workspace.idea_queue) == 3
        # Should be sorted by priority (highest first)
        assert workspace.idea_queue[0].idea == "High priority idea"

    def test_peek_ideas(self):
        """Test peeking at ideas without removing."""
        workspace = Workspace()
        workspace.add_idea("Idea 1")
        workspace.add_idea("Idea 2")
        workspace.add_idea("Idea 3")

        ideas = workspace.peek_ideas(2)
        assert len(ideas) == 2
        assert len(workspace.idea_queue) == 3  # Not removed

    def test_pop_ideas(self):
        """Test popping ideas (removes them)."""
        workspace = Workspace()
        workspace.add_idea("Idea 1")
        workspace.add_idea("Idea 2")
        workspace.add_idea("Idea 3")

        ideas = workspace.pop_ideas(2)
        assert len(ideas) == 2
        assert len(workspace.idea_queue) == 1  # Removed

    def test_save_and_load(self, tmp_path):
        """Test saving and loading workspace."""
        # Create a workspace with data
        workspace = Workspace(name="test-workspace")
        workspace.add_idea("Test idea")

        # Mock both directory and validation logic
        def mock_get_workspace_path(name):
            return tmp_path / f"{name}.json"

        with (
            patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path),
            patch.object(Workspace, "get_workspace_path", side_effect=mock_get_workspace_path),
        ):
            workspace.save()

            # Load and verify
            loaded = Workspace.load("test-workspace")
            assert loaded.name == "test-workspace"
            assert len(loaded.idea_queue) == 1
            assert loaded.idea_queue[0].idea == "Test idea"

    def test_list_workspaces(self, tmp_path):
        """Test listing available workspaces."""
        # Create some workspace files
        (tmp_path / "default.json").write_text("{}")
        (tmp_path / "project-a.json").write_text("{}")
        (tmp_path / "project-b.json").write_text("{}")

        with patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path):
            workspaces = Workspace.list_workspaces()
            assert "default" in workspaces
            assert "project-a" in workspaces
            assert "project-b" in workspaces

    def test_delete_workspace(self, tmp_path):
        """Test deleting a workspace."""
        # Create a workspace file
        workspace_file = tmp_path / "test-workspace.json"
        workspace_file.write_text('{"name": "test-workspace"}')

        def mock_get_workspace_path(name):
            return tmp_path / f"{name}.json"

        with (
            patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path),
            patch.object(Workspace, "get_workspace_path", side_effect=mock_get_workspace_path),
        ):
            # Delete should succeed
            result = Workspace.delete("test-workspace")
            assert result is True
            assert not workspace_file.exists()

            # Deleting again should return False
            result = Workspace.delete("test-workspace")
            assert result is False

    def test_delete_nonexistent_workspace(self, tmp_path):
        """Test deleting a workspace that doesn't exist."""

        def mock_get_workspace_path(name):
            return tmp_path / f"{name}.json"

        with (
            patch.object(Workspace, "get_workspaces_dir", return_value=tmp_path),
            patch.object(Workspace, "get_workspace_path", side_effect=mock_get_workspace_path),
        ):
            result = Workspace.delete("nonexistent")
            assert result is False
