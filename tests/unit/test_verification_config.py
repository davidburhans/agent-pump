"""Unit tests for verification configuration models."""


import pytest

from agent_pump.models.verification_config import (
    ProjectDetectionResult,
    VerificationConfig,
    detect_project_type,
)


class TestVerificationConfig:
    """Tests for VerificationConfig model."""

    def test_default_values(self):
        """Test that VerificationConfig has correct default values."""
        config = VerificationConfig()
        assert config.build_cmd is None
        assert config.lint_cmd is None
        assert config.test_cmd is None
        assert config.skip_verification is False

    def test_custom_values(self):
        """Test that VerificationConfig accepts custom values."""
        config = VerificationConfig(
            build_cmd="npm run build",
            lint_cmd="npm run lint",
            test_cmd="npm test",
            skip_verification=True
        )
        assert config.build_cmd == "npm run build"
        assert config.lint_cmd == "npm run lint"
        assert config.test_cmd == "npm test"
        assert config.skip_verification is True

    def test_command_validation_safe_commands(self):
        """Test that safe commands pass validation."""
        config = VerificationConfig(build_cmd="npm run build")
        assert config.build_cmd == "npm run build"

        config = VerificationConfig(lint_cmd="ruff check .")
        assert config.lint_cmd == "ruff check ."

        config = VerificationConfig(test_cmd="pytest tests/")
        assert config.test_cmd == "pytest tests/"

    def test_command_validation_dangerous_patterns(self):
        """Test that dangerous command patterns are rejected."""
        # Test || pattern
        with pytest.raises(ValueError, match="contains potentially dangerous pattern"):
            VerificationConfig(build_cmd="echo hello || echo world")

        # Test && pattern
        with pytest.raises(ValueError, match="contains potentially dangerous pattern"):
            VerificationConfig(lint_cmd="ruff check . && echo done")

        # Test ; pattern
        with pytest.raises(ValueError, match="contains potentially dangerous pattern"):
            VerificationConfig(test_cmd="echo hello; rm -rf /")

        # Test command substitution $(...)
        with pytest.raises(ValueError, match="contains potentially dangerous pattern"):
            VerificationConfig(build_cmd="echo $(whoami)")

        # Test command substitution with backticks
        with pytest.raises(ValueError, match="contains potentially dangerous pattern"):
            VerificationConfig(lint_cmd="echo `whoami`")

    def test_none_values_allowed(self):
        """Test that None values are allowed for commands."""
        config = VerificationConfig(
            build_cmd=None,
            lint_cmd=None,
            test_cmd=None
        )
        assert config.build_cmd is None
        assert config.lint_cmd is None
        assert config.test_cmd is None


class TestProjectDetectionResult:
    """Tests for ProjectDetectionResult model."""

    def test_default_values(self):
        """Test that ProjectDetectionResult has correct default values."""
        result = ProjectDetectionResult()
        assert result.project_type is None
        assert result.build_cmd is None
        assert result.lint_cmd is None
        assert result.test_cmd is None

    def test_custom_values(self):
        """Test that ProjectDetectionResult accepts custom values."""
        result = ProjectDetectionResult(
            project_type="npm",
            build_cmd="npm run build",
            lint_cmd="npm run lint",
            test_cmd="npm test"
        )
        assert result.project_type == "npm"
        assert result.build_cmd == "npm run build"
        assert result.lint_cmd == "npm run lint"
        assert result.test_cmd == "npm test"


class TestDetectProjectType:
    """Tests for detect_project_type function."""

    def test_detect_unknown_project(self, tmp_path):
        """Test detection of unknown project type."""
        # Create a temporary directory with no project files
        result = detect_project_type(tmp_path)
        assert result.project_type is None
        assert result.build_cmd is None
        assert result.lint_cmd is None
        assert result.test_cmd is None

    def test_detect_cargo_project(self, tmp_path):
        """Test detection of Cargo project."""
        # Create Cargo.toml file
        (tmp_path / "Cargo.toml").write_text("[package]\nname = \"test\"")

        result = detect_project_type(tmp_path)
        assert result.project_type == "cargo"
        assert result.build_cmd == "cargo build"
        assert result.lint_cmd == "cargo clippy"
        assert result.test_cmd == "cargo test"

    def test_detect_npm_project(self, tmp_path):
        """Test detection of npm project."""
        # Create package.json file
        (tmp_path / "package.json").write_text('{"name": "test", "scripts": {}}')

        result = detect_project_type(tmp_path)
        assert result.project_type == "npm"
        assert result.build_cmd == "npm run build"
        assert result.lint_cmd == "npm run lint"
        assert result.test_cmd == "npm test"

    def test_detect_go_project(self, tmp_path):
        """Test detection of Go project."""
        # Create go.mod file
        (tmp_path / "go.mod").write_text("module test\n\ngo 1.19")

        result = detect_project_type(tmp_path)
        assert result.project_type == "go"
        assert result.build_cmd == "go build ./..."
        assert result.lint_cmd == "golangci-lint run"
        assert result.test_cmd == "go test ./..."

    def test_detect_python_uv_project(self, tmp_path):
        """Test detection of Python project with uv."""
        # Create pyproject.toml with uv configuration
        (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test"
version = "0.1.0"

[tool.uv]
dev-dependencies = ["pytest"]
""")

        result = detect_project_type(tmp_path)
        assert result.project_type == "uv"
        assert result.build_cmd == "uv build"
        assert result.lint_cmd == "uv run ruff check ."
        assert result.test_cmd == "uv run pytest"

    def test_detect_python_poetry_project(self, tmp_path):
        """Test detection of Poetry project."""
        # Create pyproject.toml with Poetry configuration
        (tmp_path / "pyproject.toml").write_text("""
[tool.poetry]
name = "test"
version = "0.1.0"

[tool.poetry.dependencies]
python = "^3.9"
""")

        result = detect_project_type(tmp_path)
        assert result.project_type == "poetry"
        assert result.build_cmd == "poetry build"
        assert result.lint_cmd == "poetry run ruff check ."
        assert result.test_cmd == "poetry run pytest"

    def test_detect_python_standard_project(self, tmp_path):
        """Test detection of standard Python project."""
        # Create pyproject.toml without specific tool configuration
        (tmp_path / "pyproject.toml").write_text("""
[project]
name = "test"
version = "0.1.0"
""")

        result = detect_project_type(tmp_path)
        assert result.project_type == "python"
        assert result.build_cmd == "python -m build"
        assert result.lint_cmd == "ruff check ."
        assert result.test_cmd == "pytest"

    def test_detect_make_project(self, tmp_path):
        """Test detection of Make project."""
        # Create Makefile
        (tmp_path / "Makefile").write_text("build:\n\techo 'building'")

        result = detect_project_type(tmp_path)
        assert result.project_type == "make"
        assert result.build_cmd == "make"
        assert result.lint_cmd is None
        assert result.test_cmd == "make test"

    def test_detect_maven_project(self, tmp_path):
        """Test detection of Maven project."""
        # Create pom.xml
        (tmp_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>test</artifactId>
  <version>1.0.0</version>
</project>""")

        result = detect_project_type(tmp_path)
        assert result.project_type == "maven"
        assert result.build_cmd == "mvn compile"
        assert result.lint_cmd == "mvn checkstyle:check"
        assert result.test_cmd == "mvn test"

    def test_detect_gradle_project(self, tmp_path):
        """Test detection of Gradle project."""
        # Create build.gradle
        (tmp_path / "build.gradle").write_text("// Gradle build file")

        result = detect_project_type(tmp_path)
        assert result.project_type == "gradle"
        assert result.build_cmd == "gradle build"
        assert result.lint_cmd == "gradle check"
        assert result.test_cmd == "gradle test"

    def test_detect_gradle_kotlin_project(self, tmp_path):
        """Test detection of Gradle Kotlin project."""
        # Create build.gradle.kts
        (tmp_path / "build.gradle.kts").write_text("// Gradle Kotlin build file")

        result = detect_project_type(tmp_path)
        assert result.project_type == "gradle"
        assert result.build_cmd == "gradle build"
        assert result.lint_cmd == "gradle check"
        assert result.test_cmd == "gradle test"
