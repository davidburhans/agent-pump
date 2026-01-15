"""Tests for automatic configuration creation."""

from agent_pump.config import DEFAULT_CONFIG_TEMPLATE, Config


def test_auto_create_config_on_load(tmp_path):
    """Test that .agent-pump.yml is created when loading config if it doesn't exist."""
    project_path = tmp_path / "new_project"
    project_path.mkdir()

    config_file = project_path / ".agent-pump.yml"
    assert not config_file.exists()

    # Load config should trigger creation
    config = Config.load(project_path)

    # Verify file was created
    assert config_file.exists()
    assert config_file.read_text() == DEFAULT_CONFIG_TEMPLATE

    # Verify defaults are loaded correctly
    assert config.backend == "gemini"
    assert config.workflow.max_iterations == 10
    assert config.workflow.timeout == 1800
    assert config.workflow.branch is None
    assert config.verification.build_cmd is None

def test_do_not_overwrite_existing_config(tmp_path):
    """Test that existing .agent-pump.yml is not overwritten."""
    project_path = tmp_path / "existing_project"
    project_path.mkdir()

    config_file = project_path / ".agent-pump.yml"
    custom_content = """
backend: custom_backend
workflow:
  max_iterations: 42
"""
    config_file.write_text(custom_content)

    # Load config
    config = Config.load(project_path)

    # Verify file content is unchanged
    assert config_file.read_text() == custom_content

    # Verify loaded values
    assert config.backend == "custom_backend"
    assert config.workflow.max_iterations == 42
