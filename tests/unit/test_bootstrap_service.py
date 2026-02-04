"""Unit tests for the bootstrap service."""

import json
from unittest.mock import MagicMock

import pytest

from agent_pump.backends.base import AgentBackend
from agent_pump.services.bootstrap_service import (
    BootstrapResult,
    BootstrapService,
    ProjectAnalysis,
)


class MockBackend(AgentBackend):
    """Mock backend for testing."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self._available = True

    @property
    def name(self) -> str:
        return "MockBackend"

    @property
    def command(self) -> str:
        return "mock"

    async def _check_availability(self) -> bool:
        return self._available

    async def run(self, project_path, prompt, timeout=600, verbose=False, extra_args=None):
        """Yield mock response based on prompt content."""
        if "roadmap" in prompt.lower():
            response = self.responses.get("roadmap", "# Default Roadmap")
        elif "best practice" in prompt.lower():
            response = self.responses.get("best_practices", "# Default Best Practices")
        else:
            response = "# Default Response"

        for line in response.split("\n"):
            yield line + "\n"


@pytest.fixture
def event_bus():
    """Mock event bus fixture."""
    return MagicMock()


@pytest.fixture
def service(event_bus):
    """Bootstrap service fixture."""
    return BootstrapService(event_bus)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


class TestProjectAnalysis:
    """Tests for project structure analysis."""

    def test_detect_python_project(self, service, temp_project):
        """Test detection of Python project with pyproject.toml."""
        (temp_project / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (temp_project / "README.md").write_text("# Test Project\n")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "python"
        assert analysis.language == "python"
        assert "pyproject.toml" in analysis.key_files
        assert "README.md" in analysis.key_files
        assert analysis.has_docs is True

    def test_detect_python_with_poetry(self, service, temp_project):
        """Test detection of Poetry-based Python project."""
        (temp_project / "pyproject.toml").write_text("[tool.poetry]\n")
        (temp_project / "poetry.lock").write_text("")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "python"
        assert analysis.framework == "poetry"

    def test_detect_python_with_uv(self, service, temp_project):
        """Test detection of uv-based Python project."""
        (temp_project / "pyproject.toml").write_text("[project]\n")
        (temp_project / "uv.lock").write_text("")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.framework == "uv"

    def test_detect_nodejs_project(self, service, temp_project):
        """Test detection of Node.js project."""
        package_json = {
            "name": "test-project",
            "dependencies": {"react": "^18.0.0"},
        }
        (temp_project / "package.json").write_text(json.dumps(package_json))

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "nodejs"
        assert analysis.language == "javascript"
        assert analysis.framework == "react"
        assert "package.json" in analysis.key_files

    def test_detect_nodejs_with_vue(self, service, temp_project):
        """Test detection of Vue.js project."""
        package_json = {
            "name": "test-project",
            "dependencies": {"vue": "^3.0.0"},
        }
        (temp_project / "package.json").write_text(json.dumps(package_json))

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.framework == "vue"

    def test_detect_rust_project(self, service, temp_project):
        """Test detection of Rust project."""
        (temp_project / "Cargo.toml").write_text("[package]\nname = 'test'\n")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "rust"
        assert analysis.language == "rust"

    def test_detect_go_project(self, service, temp_project):
        """Test detection of Go project."""
        (temp_project / "go.mod").write_text("module test\n")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "go"
        assert analysis.language == "go"

    def test_detect_java_maven(self, service, temp_project):
        """Test detection of Java Maven project."""
        (temp_project / "pom.xml").write_text("<project></project>")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "java"
        assert analysis.framework == "maven"

    def test_detect_java_gradle(self, service, temp_project):
        """Test detection of Java Gradle project."""
        (temp_project / "build.gradle").write_text("plugins {}")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.project_type == "java"
        assert analysis.framework == "gradle"

    def test_detect_tests_directory(self, service, temp_project):
        """Test detection of test directories."""
        (temp_project / "tests").mkdir()

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.has_tests is True

    def test_detect_pytest_ini(self, service, temp_project):
        """Test detection of pytest configuration."""
        (temp_project / "pytest.ini").write_text("[pytest]\n")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.has_tests is True

    def test_detect_ci_github(self, service, temp_project):
        """Test detection of GitHub Actions."""
        (temp_project / ".github").mkdir()

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.has_ci is True

    def test_detect_ci_gitlab(self, service, temp_project):
        """Test detection of GitLab CI."""
        (temp_project / ".gitlab-ci.yml").write_text("stages: []\n")

        analysis = service.analyze_project_structure(temp_project)

        assert analysis.has_ci is True

    def test_directory_structure_listing(self, service, temp_project):
        """Test that directory structure is captured."""
        (temp_project / "src").mkdir()
        (temp_project / "tests").mkdir()
        (temp_project / "README.md").write_text("# Test")

        analysis = service.analyze_project_structure(temp_project)

        assert "src/" in analysis.directory_structure
        assert "tests/" in analysis.directory_structure
        assert "README.md" in analysis.directory_structure


class TestPromptGeneration:
    """Tests for prompt generation."""

    def test_roadmap_prompt_contains_project_info(self, service):
        """Test roadmap prompt includes project information."""
        analysis = ProjectAnalysis(
            project_type="python",
            language="python",
            framework="poetry",
            key_files=["pyproject.toml"],
            directory_structure=["src/", "tests/"],
            has_tests=True,
            has_docs=True,
            has_ci=False,
        )

        prompt = service._generate_roadmap_prompt(analysis, "MyProject")

        assert "MyProject" in prompt
        assert "python" in prompt
        assert "poetry" in prompt
        assert "pyproject.toml" in prompt
        assert "ROADMAP.md" in prompt

    def test_best_practices_prompt_contains_project_info(self, service):
        """Test best practices prompt includes project information."""
        analysis = ProjectAnalysis(
            project_type="nodejs",
            language="javascript",
            framework="react",
            key_files=["package.json"],
            directory_structure=["src/"],
            has_tests=True,
            has_docs=False,
            has_ci=True,
        )

        prompt = service._generate_best_practices_prompt(analysis, "WebApp")

        assert "WebApp" in prompt
        assert "javascript" in prompt
        assert "react" in prompt
        assert "BEST_PRACTICES.md" in prompt

    def test_prompt_without_framework(self, service):
        """Test prompts work without framework."""
        analysis = ProjectAnalysis(
            project_type="rust",
            language="rust",
            framework=None,
            key_files=["Cargo.toml"],
            directory_structure=["src/"],
            has_tests=False,
            has_docs=False,
            has_ci=False,
        )

        roadmap_prompt = service._generate_roadmap_prompt(analysis, "RustApp")
        best_practices_prompt = service._generate_best_practices_prompt(analysis, "RustApp")

        assert "RustApp" in roadmap_prompt
        assert "RustApp" in best_practices_prompt
        assert "rust" in roadmap_prompt


class TestResponseParsing:
    """Tests for response parsing."""

    def test_parse_markdown_code_block(self, service):
        """Test extraction of markdown from code block."""
        response = """Here's the roadmap:

```markdown
# Roadmap

## Section 1
Content here
```

Hope this helps!"""

        result = service._parse_response(response)

        assert result.startswith("# Roadmap")
        assert "## Section 1" in result
        assert "```" not in result

    def test_parse_generic_code_block(self, service):
        """Test extraction from generic code block."""
        response = """Here you go:

```
# Best Practices

- Rule 1
- Rule 2
```"""

        result = service._parse_response(response)

        assert result.startswith("# Best Practices")
        assert "Rule 1" in result

    def test_parse_code_block_with_language(self, service):
        """Test extraction from code block with language identifier."""
        response = """```md
# Title

Content
```"""

        result = service._parse_response(response)

        assert result.startswith("# Title")
        assert "```" not in result

    def test_parse_plain_text(self, service):
        """Test handling of plain text response."""
        response = "# Plain Title\n\nSome content here"

        result = service._parse_response(response)

        assert result == response


class TestBootstrapProject:
    """Tests for the main bootstrap_project method."""

    @pytest.mark.asyncio
    async def test_successful_bootstrap(self, service, temp_project, event_bus):
        """Test successful bootstrap operation."""
        roadmap_response = """```markdown
# Test Project - Roadmap

## Current Sprint
### 🔴 Feature 1
Description
```"""
        best_practices_response = """```markdown
# Best Practices

## Code Style
Guidelines here
```"""

        backend = MockBackend(
            {
                "roadmap": roadmap_response,
                "best_practices": best_practices_response,
            }
        )

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
            dry_run=False,
        )

        assert result.success is True
        assert result.error_message is None
        assert len(result.files_written) == 2
        assert any("ROADMAP.md" in f for f in result.files_written)
        assert any("BEST_PRACTICES.md" in f for f in result.files_written)

    @pytest.mark.asyncio
    async def test_dry_run_does_not_write_files(self, service, temp_project, event_bus):
        """Test that dry run mode doesn't create files."""
        backend = MockBackend(
            {
                "roadmap": "# Roadmap",
                "best_practices": "# Best Practices",
            }
        )

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
            dry_run=True,
        )

        assert result.success is True
        assert len(result.files_written) == 0
        assert (temp_project / "ROADMAP.md").exists() is False
        assert (temp_project / "BEST_PRACTICES.md").exists() is False

    @pytest.mark.asyncio
    async def test_backend_not_available(self, service, temp_project, event_bus):
        """Test handling of unavailable backend."""
        backend = MockBackend()
        backend._available = False

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
        )

        assert result.success is False
        assert result.error_message is not None
        assert "not available" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_backend_error_in_roadmap(self, service, temp_project, event_bus):
        """Test handling of backend error during roadmap generation."""
        backend = MockBackend(
            {
                "roadmap": "[ERROR] Backend failed",
                "best_practices": "# Best Practices",
            }
        )

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
        )

        assert result.success is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_backend_error_in_best_practices(self, service, temp_project, event_bus):
        """Test handling of backend error during best practices generation."""
        backend = MockBackend(
            {
                "roadmap": "# Roadmap",
                "best_practices": "[ERROR] Backend failed",
            }
        )

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
        )

        assert result.success is False
        assert "best practices" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_files_actually_written(self, service, temp_project, event_bus):
        """Test that files are actually written to disk."""
        roadmap_content = "# My Roadmap\n\n## Feature 1\n"
        best_practices_content = "# Best Practices\n\n- Rule 1\n"

        backend = MockBackend(
            {
                "roadmap": f"```markdown\n{roadmap_content}\n```",
                "best_practices": f"```markdown\n{best_practices_content}\n```",
            }
        )

        result = await service.bootstrap_project(
            project_path=temp_project,
            backend=backend,
            dry_run=False,
        )

        assert result.success is True

        # Verify files exist and have correct content
        roadmap_path = temp_project / "ROADMAP.md"
        best_practices_path = temp_project / "BEST_PRACTICES.md"

        assert roadmap_path.exists()
        assert best_practices_path.exists()
        assert roadmap_content.strip() in roadmap_path.read_text(encoding="utf-8")
        assert best_practices_content.strip() in best_practices_path.read_text(encoding="utf-8")


class TestBootstrapResult:
    """Tests for BootstrapResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = BootstrapResult(
            success=True,
            roadmap_content="# Roadmap",
            best_practices_content="# Best Practices",
            error_message=None,
            files_written=["/path/ROADMAP.md", "/path/BEST_PRACTICES.md"],
        )

        assert result.success is True
        assert result.error_message is None

    def test_failed_result(self):
        """Test creating a failed result."""
        result = BootstrapResult(
            success=False,
            roadmap_content=None,
            best_practices_content=None,
            error_message="Something went wrong",
            files_written=[],
        )

        assert result.success is False
        assert result.error_message == "Something went wrong"

    def test_partial_result(self):
        """Test creating a partial result (roadmap succeeded, best practices failed)."""
        result = BootstrapResult(
            success=False,
            roadmap_content="# Roadmap",
            best_practices_content=None,
            error_message="Best practices failed",
            files_written=[],
        )

        assert result.success is False
        assert result.roadmap_content is not None
        assert result.best_practices_content is None
