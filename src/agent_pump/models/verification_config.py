"""Verification configuration models for agent-pump."""

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class VerificationConfig(BaseModel):
    """Configuration for verification commands (build, lint, test)."""

    build_cmd: str | None = Field(
        default=None,
        description="Command to run for building the project (e.g., 'npm run build', 'cargo build')",  # noqa: E501
    )
    lint_cmd: str | None = Field(
        default=None,
        description="Command to run for linting the project (e.g., 'npm run lint', 'ruff check .')",
    )
    test_cmd: str | None = Field(
        default=None,
        description="Command to run for testing the project (e.g., 'npm test', 'pytest')",
    )
    coverage_cmd: str | None = Field(
        default=None,
        description="Command to run for measuring code coverage (e.g., 'pytest --cov')",
    )
    coverage_threshold: float = Field(
        default=0.0,
        description="Minimum coverage percentage required to pass verification",
    )
    skip_verification: bool = Field(
        default=False, description="Whether to skip the verification phase entirely"
    )
    sandbox_image: str | None = Field(
        default=None,
        description="Docker image to use for sandboxed verification commands (e.g. 'node:18-slim', 'python:3.11-slim')",
    )

    @field_validator("build_cmd", "lint_cmd", "test_cmd", "coverage_cmd")
    @classmethod
    def validate_command_format(cls, v: str | None) -> str | None:
        """Validate command format to prevent dangerous patterns."""
        if v is None:
            return v

        # Check for dangerous patterns that could be security risks
        dangerous_patterns = [
            r"\|\|",  # Command chaining
            r"&&",  # Command chaining
            r";",  # Command separator
            r"\$\(.*\)",  # Command substitution
            r"`\w+`",  # Backtick command substitution
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, v):
                raise ValueError(f"Command contains potentially dangerous pattern: {v}")

        return v


class ProjectDetectionResult(BaseModel):
    """Result of project type detection."""

    project_type: str | None = Field(
        default=None, description="Detected project type (e.g., 'npm', 'cargo', 'go', 'uv')"
    )
    build_cmd: str | None = Field(
        default=None, description="Suggested build command based on project type"
    )
    lint_cmd: str | None = Field(
        default=None, description="Suggested lint command based on project type"
    )
    test_cmd: str | None = Field(
        default=None, description="Suggested test command based on project type"
    )
    coverage_cmd: str | None = Field(
        default=None, description="Suggested coverage command based on project type"
    )
    sandbox_image: str | None = Field(
        default=None, description="Suggested docker image for sandboxed execution"
    )


def detect_project_type(project_path: Path) -> ProjectDetectionResult:
    """
    Detect project type and suggest appropriate commands based on files in the project directory.

    Args:
        project_path: Path to the project directory

    Returns:
        ProjectDetectionResult with suggested commands
    """
    # Look for common project files to determine project type
    files = {f.name.lower() for f in project_path.iterdir() if f.is_file()}

    # Check for different project types in order of specificity
    # Note: all comparisons are lowercase to handle case variations across systems
    if "cargo.toml" in files:
        return ProjectDetectionResult(
            project_type="cargo",
            build_cmd="cargo build",
            lint_cmd="cargo clippy",
            test_cmd="cargo test",
            coverage_cmd="cargo tarpaulin",
            sandbox_image="rust:slim",
        )
    elif "go.mod" in files:
        return ProjectDetectionResult(
            project_type="go",
            build_cmd="go build ./...",
            lint_cmd="golangci-lint run",
            test_cmd="go test ./...",
            coverage_cmd="go test -cover ./...",
            sandbox_image="golang:alpine",
        )
    elif "package.json" in files:
        # NPM coverage command detection is tricky, usually 'npm run coverage' or 'npm test -- --coverage'
        # We'll suggest 'npm run coverage' assuming user might have it, or 'npm test -- --coverage' for jest/vitest defaults
        return ProjectDetectionResult(
            project_type="npm",
            build_cmd="npm run build",
            lint_cmd="npm run lint",
            test_cmd="npm test",
            coverage_cmd="npm run coverage",
            sandbox_image="node:18-slim",
        )
    elif "pyproject.toml" in files:
        # Check for specific Python tools in pyproject.toml
        pyproject_path = project_path / "pyproject.toml"
        try:
            content = pyproject_path.read_text()

            # Check for uv project
            if "[tool.uv]" in content or "uv" in content:
                return ProjectDetectionResult(
                    project_type="uv",
                    build_cmd="uv build",
                    lint_cmd="uv run ruff check .",
                    test_cmd="uv run pytest",
                    coverage_cmd="uv run pytest --cov",
                    sandbox_image="python:3.11-slim",
                )
            # Check for poetry project
            elif "[tool.poetry]" in content:
                return ProjectDetectionResult(
                    project_type="poetry",
                    build_cmd="poetry build",
                    lint_cmd="poetry run ruff check .",
                    test_cmd="poetry run pytest",
                    coverage_cmd="poetry run pytest --cov",
                    sandbox_image="python:3.11-slim",
                )
            # Default to pip/standard Python project
            else:
                return ProjectDetectionResult(
                    project_type="python",
                    build_cmd="python -m build",
                    lint_cmd="ruff check .",
                    test_cmd="pytest",
                    coverage_cmd="pytest --cov",
                    sandbox_image="python:3.11-slim",
                )
        except Exception:
            # If we can't read pyproject.toml, assume standard Python
            return ProjectDetectionResult(
                project_type="python",
                build_cmd="python -m build",
                lint_cmd="ruff check .",
                test_cmd="pytest",
                coverage_cmd="pytest --cov",
                sandbox_image="python:3.11-slim",
            )
    elif "Makefile" in files or "makefile" in files:
        return ProjectDetectionResult(
            project_type="make",
            build_cmd="make",
            lint_cmd=None,
            test_cmd="make test",
            coverage_cmd="make coverage",
            # Makefiles are generic, can't guess image easily, assume python/base or let user set
            sandbox_image=None,
        )
    elif "pom.xml" in files:
        return ProjectDetectionResult(
            project_type="maven",
            build_cmd="mvn compile",
            lint_cmd="mvn checkstyle:check",
            test_cmd="mvn test",
            coverage_cmd="mvn jacoco:report",
            sandbox_image="maven:3-eclipse-temurin-17",
        )
    elif "build.gradle" in files or "build.gradle.kts" in files:
        return ProjectDetectionResult(
            project_type="gradle",
            build_cmd="gradle build",
            lint_cmd="gradle check",
            test_cmd="gradle test",
            coverage_cmd="gradle jacocoTestReport",
            sandbox_image="gradle:jdk17",
        )
    else:
        # No specific project type detected, return empty suggestions
        return ProjectDetectionResult(
            project_type=None,
            build_cmd=None,
            lint_cmd=None,
            test_cmd=None,
            coverage_cmd=None,
            sandbox_image=None,
        )
