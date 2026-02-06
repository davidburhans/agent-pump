"""Tests for PromptLoader."""


import pytest

from agent_pump.orchestrator.prompt_loader import PromptLoader


class TestPromptLoader:
    """Tests for the PromptLoader class."""

    @pytest.fixture
    def project_path(self, tmp_path):
        """Create a temporary project path."""
        path = tmp_path / "test_project"
        path.mkdir()
        (path / ".agent-pump").mkdir()
        (path / ".agent-pump" / "states").mkdir()
        (path / ".agent-pump" / "backends").mkdir()
        return path

    @pytest.fixture
    def loader(self, project_path):
        """Create a PromptLoader instance."""
        return PromptLoader(project_path)

    def test_has_directory_structure(self, loader, project_path):
        """Test directory structure detection."""
        assert loader.has_directory_structure()

        # Test false case
        empty_path = project_path.parent / "empty"
        empty_path.mkdir()
        empty_loader = PromptLoader(empty_path)
        assert not empty_loader.has_directory_structure()

    @pytest.mark.asyncio
    async def test_load_state_prompt(self, loader, project_path):
        """Test loading state prompts."""
        # Create a test prompt file
        (project_path / ".agent-pump" / "states" / "planning.md").write_text(
            "Custom Planning Prompt", encoding="utf-8"
        )
        (project_path / ".agent-pump" / "states" / "pre-planning.md").write_text(
            "Pre Planning", encoding="utf-8"
        )

        assert await loader.load_state_prompt("planning", "base") == "Custom Planning Prompt"
        assert await loader.load_state_prompt("planning", "pre") == "Pre Planning"
        assert await loader.load_state_prompt("planning", "post") is None

    @pytest.mark.asyncio
    async def test_load_backend_prompt(self, loader, project_path):
        """Test loading backend prompts."""
        (project_path / ".agent-pump" / "backends" / "pre-gemini.md").write_text(
            "Pre Gemini", encoding="utf-8"
        )

        assert await loader.load_backend_prompt("gemini", "pre") == "Pre Gemini"
        assert await loader.load_backend_prompt("gemini", "post") is None

    @pytest.mark.asyncio
    async def test_build_prompt_defaults(self, loader):
        """Test building prompt with defaults (no files)."""
        prompt = await loader.build_prompt(
            state="planning",
            backend="gemini",
            default_prompt="Default Prompt",
        )
        assert prompt == "Default Prompt"

    @pytest.mark.asyncio
    async def test_build_prompt_full_customization(self, loader, project_path):
        """Test building prompt with all customizations."""
        states_dir = project_path / ".agent-pump" / "states"
        backends_dir = project_path / ".agent-pump" / "backends"

        (states_dir / "pre-planning.md").write_text("State Pre", encoding="utf-8")
        (states_dir / "post-planning.md").write_text("State Post", encoding="utf-8")
        (backends_dir / "pre-gemini.md").write_text("Backend Pre", encoding="utf-8")
        (backends_dir / "post-gemini.md").write_text("Backend Post", encoding="utf-8")
        # Ensure base overrides default
        (states_dir / "planning.md").write_text("Custom Base {{ var }}", encoding="utf-8")

        prompt = await loader.build_prompt(
            state="planning",
            backend="gemini",
            default_prompt="Default",
            context={"var": "Value"},
        )

        expected_parts = [
            "State Pre",
            "Backend Pre",
            "Custom Base Value",
            "Backend Post",
            "State Post",
        ]
        assert prompt == "\n\n".join(expected_parts)
