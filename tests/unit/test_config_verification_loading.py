"""Tests for loading verification configuration from .agent-pump.yml files."""

import pytest

from agent_pump.config import Config


class TestConfigVerificationLoading:
    """Tests for loading verification config from YAML files."""

    def test_load_verification_config_from_yaml(self, tmp_path):
        """Test loading verification commands from .agent-pump.yml."""
        # Create a .agent-pump.yml file with verification config
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
verification:
  build_cmd: "npm run build"
  lint_cmd: "npm run lint"
  test_cmd: "npm test"
  skip_verification: false
"""
        config_file.write_text(config_content)

        # Load the config
        config = Config.load(tmp_path)

        # Verify the verification config was loaded
        assert config.verification.build_cmd == "npm run build"
        assert config.verification.lint_cmd == "npm run lint"
        assert config.verification.test_cmd == "npm test"
        assert config.verification.skip_verification is False

    def test_load_verification_config_with_skip_enabled(self, tmp_path):
        """Test loading verification config with skip_verification enabled."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
verification:
  build_cmd: "make build"
  lint_cmd: "make lint"
  test_cmd: "make test"
  skip_verification: true
"""
        config_file.write_text(config_content)

        config = Config.load(tmp_path)

        assert config.verification.build_cmd == "make build"
        assert config.verification.lint_cmd == "make lint"
        assert config.verification.test_cmd == "make test"
        assert config.verification.skip_verification is True

    def test_load_verification_config_partial_commands(self, tmp_path):
        """Test loading verification config with only some commands specified."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
verification:
  build_cmd: "cargo build"
  test_cmd: "cargo test"
  # lint_cmd and skip_verification should use defaults
"""
        config_file.write_text(config_content)

        config = Config.load(tmp_path)

        assert config.verification.build_cmd == "cargo build"
        assert config.verification.test_cmd == "cargo test"
        assert config.verification.lint_cmd is None  # Should be None (default)
        assert config.verification.skip_verification is False  # Should be False (default)

    def test_load_verification_config_defaults(self, tmp_path):
        """Test loading config when verification section is not present."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
backend: "gemini"
workflow:
  timeout: 1200
"""
        config_file.write_text(config_content)

        config = Config.load(tmp_path)

        # Verify that verification config has defaults
        assert config.verification.build_cmd is None
        assert config.verification.lint_cmd is None
        assert config.verification.test_cmd is None
        assert config.verification.skip_verification is False

    def test_load_verification_config_empty_section(self, tmp_path):
        """Test loading config with empty verification section."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
verification: {}
"""
        config_file.write_text(config_content)

        config = Config.load(tmp_path)

        # Verify that verification config has defaults
        assert config.verification.build_cmd is None
        assert config.verification.lint_cmd is None
        assert config.verification.test_cmd is None
        assert config.verification.skip_verification is False

    def test_load_verification_config_with_other_settings(self, tmp_path):
        """Test loading verification config alongside other settings."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
backend: "claude"
workflow:
  max_iterations: 5
  timeout: 900
verification:
  build_cmd: "python -m build"
  lint_cmd: "ruff check ."
  test_cmd: "pytest tests/"
  skip_verification: false
"""
        config_file.write_text(config_content)

        config = Config.load(tmp_path)

        # Verify other settings
        assert config.backend == "claude"
        assert config.workflow.max_iterations == 5
        assert config.workflow.timeout == 900

        # Verify verification settings
        assert config.verification.build_cmd == "python -m build"
        assert config.verification.lint_cmd == "ruff check ."
        assert config.verification.test_cmd == "pytest tests/"
        assert config.verification.skip_verification is False

    def test_verification_config_validation_in_yaml(self, tmp_path):
        """Test that dangerous commands in YAML are validated during loading."""
        config_file = tmp_path / ".agent-pump.yml"
        config_content = """
verification:
  build_cmd: "echo hello && rm -rf /"
  lint_cmd: "ruff check ."
  test_cmd: "pytest"
"""
        config_file.write_text(config_content)

        # Loading should fail due to validation of dangerous command
        from pydantic_core import ValidationError

        with pytest.raises(ValidationError, match="contains potentially dangerous pattern"):
            Config.load(tmp_path)
