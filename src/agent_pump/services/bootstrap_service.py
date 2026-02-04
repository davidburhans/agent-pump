"""Bootstrap service for initializing projects with AI-generated documentation."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from agent_pump.backends.base import AgentBackend
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


@dataclass
class ProjectAnalysis:
    """Analysis results of a project structure."""

    project_type: str
    language: str
    framework: str | None
    key_files: list[str]
    directory_structure: list[str]
    has_tests: bool
    has_docs: bool
    has_ci: bool


@dataclass
class BootstrapResult:
    """Result of a bootstrap operation."""

    success: bool
    roadmap_content: str | None
    best_practices_content: str | None
    error_message: str | None
    files_written: list[str]


class BootstrapService(BaseService):
    """Service for bootstrapping projects with AI-generated documentation."""

    def __init__(self, event_bus) -> None:
        """Initialize the bootstrap service."""
        super().__init__(event_bus)

    def analyze_project_structure(self, project_path: Path) -> ProjectAnalysis:
        """Analyze project structure to detect type and key files."""
        path = project_path.resolve()

        # Detect project type based on files
        key_files = []
        project_type = "unknown"
        language = "unknown"
        framework = None
        has_tests = False
        has_docs = False
        has_ci = False

        # Check for Python projects
        if (path / "pyproject.toml").exists():
            key_files.append("pyproject.toml")
            project_type = "python"
            language = "python"
            if (path / "poetry.lock").exists():
                framework = "poetry"
            elif (path / "uv.lock").exists():
                framework = "uv"
            elif (path / "Pipfile").exists():
                framework = "pipenv"

        if (path / "setup.py").exists():
            key_files.append("setup.py")
            if project_type == "unknown":
                project_type = "python"
                language = "python"

        if (path / "requirements.txt").exists():
            key_files.append("requirements.txt")
            if project_type == "unknown":
                project_type = "python"
                language = "python"

        # Check for Node.js projects
        if (path / "package.json").exists():
            key_files.append("package.json")
            project_type = "nodejs"
            language = "javascript"
            pkg_json = json.loads((path / "package.json").read_text(encoding="utf-8"))
            deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}
            if "react" in deps:
                framework = "react"
            elif "vue" in deps:
                framework = "vue"
            elif "@angular" in deps:
                framework = "angular"
            elif "next" in deps:
                framework = "nextjs"
            elif "express" in deps:
                framework = "express"

        # Check for Rust projects
        if (path / "Cargo.toml").exists():
            key_files.append("Cargo.toml")
            project_type = "rust"
            language = "rust"

        # Check for Go projects
        if (path / "go.mod").exists():
            key_files.append("go.mod")
            project_type = "go"
            language = "go"

        # Check for Java projects
        if (path / "pom.xml").exists():
            key_files.append("pom.xml")
            project_type = "java"
            language = "java"
            framework = "maven"
        elif (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
            key_files.append("build.gradle")
            project_type = "java"
            language = "java"
            framework = "gradle"

        # Check for tests
        test_dirs = ["tests", "test", "__tests__", "spec", "specs"]
        has_tests = any((path / d).exists() for d in test_dirs)
        if (path / "pytest.ini").exists() or (path / "jest.config.js").exists():
            has_tests = True

        # Check for docs
        doc_dirs = ["docs", "doc", "documentation"]
        has_docs = any((path / d).exists() for d in doc_dirs)
        if (path / "README.md").exists():
            has_docs = True
            key_files.append("README.md")

        # Check for CI
        ci_dirs = [".github", ".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml"]
        has_ci = any((path / d).exists() for d in ci_dirs)

        # Get directory structure (limited depth)
        directory_structure = []
        try:
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    directory_structure.append(f"{item.name}/")
                elif item.is_file():
                    directory_structure.append(item.name)
        except PermissionError:
            logger.warning(f"Permission error reading directory: {path}")

        return ProjectAnalysis(
            project_type=project_type,
            language=language,
            framework=framework,
            key_files=key_files,
            directory_structure=directory_structure,
            has_tests=has_tests,
            has_docs=has_docs,
            has_ci=has_ci,
        )

    def _generate_roadmap_prompt(self, analysis: ProjectAnalysis, project_name: str) -> str:
        """Generate prompt for AI to create roadmap."""
        framework_str = f" with {analysis.framework}" if analysis.framework else ""

        lang_info = f"{analysis.language}{framework_str}"
        key_files_str = chr(10).join(f"- {f}" for f in analysis.key_files)
        dir_struct_str = chr(10).join(f"- {d}" for d in analysis.directory_structure[:20])

        prompt = f"""Analyze this {lang_info} project and create a ROADMAP.md file.

Project Name: {project_name}
Project Type: {analysis.project_type}
Language: {analysis.language}
Framework: {analysis.framework or "none"}

Key Files:
{key_files_str}

Directory Structure:
{dir_struct_str}

Project Features:
- Tests: {"Yes" if analysis.has_tests else "No"}
- Documentation: {"Yes" if analysis.has_docs else "No"}
- CI/CD: {"Yes" if analysis.has_ci else "No"}

Create a ROADMAP.md in this exact format:

```markdown
# {project_name} - Roadmap

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Initial Setup
**Priority: High**

Complete initial project setup and core functionality.

**Acceptance Criteria:**
- [ ] Core features implemented
- [ ] Tests passing
- [ ] Documentation complete

---

## Future Enhancements

### 🔴 Feature 1
**Priority: Medium**

Description of the feature.

**Acceptance Criteria:**
- Criterion 1
- Criterion 2

---

## Notes

Add any additional notes or considerations here.
```

Provide 2-3 realistic features in the Current Sprint based on the project
structure, and 2-3 items in Future Enhancements. Be specific and actionable."""

        return prompt

    def _generate_best_practices_prompt(self, analysis: ProjectAnalysis, project_name: str) -> str:
        """Generate prompt for AI to create best practices."""
        framework_str = f" with {analysis.framework}" if analysis.framework else ""
        lang_info = f"{analysis.language}{framework_str}"

        prompt = f"""Create a BEST_PRACTICES.md file for this {lang_info} project.

Project Name: {project_name}
Language: {analysis.language}
Framework: {analysis.framework or "none"}
Has Tests: {"Yes" if analysis.has_tests else "No"}
Has CI/CD: {"Yes" if analysis.has_ci else "No"}

Create a BEST_PRACTICES.md in this format:

```markdown
# {project_name} - Best Practices

## Code Style

### Formatting
- Use consistent indentation
- Follow language-specific conventions
- Keep functions small and focused

### Naming Conventions
- Use descriptive variable names
- Follow standard naming for the language
- Be consistent across the codebase

---

## Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Run tests before committing

---

## Documentation

- Document public APIs
- Include examples in documentation
- Keep README up to date

---

## Git Practices

- Use conventional commits
- Write descriptive commit messages
- Create feature branches for changes

---

## Verification Checklist

Before committing:
- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No debugging code left in
```

Customize the content for {analysis.language} specifically."""

        return prompt

    def _parse_response(self, response: str) -> str:
        """Extract markdown content from AI response."""
        # Look for markdown code blocks
        if "```markdown" in response:
            start = response.find("```markdown") + len("```markdown")
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()

        # Look for any code blocks
        if "```" in response:
            start = response.find("```") + 3
            # Skip language identifier if present
            first_line_end = response.find("\n", start)
            if first_line_end != -1:
                lang = response[start:first_line_end].strip()
                if lang and " " not in lang:
                    start = first_line_end + 1
            end = response.find("```", start)
            if end != -1:
                return response[start:end].strip()

        # Return full response if no code blocks
        return response.strip()

    async def bootstrap_project(
        self,
        project_path: Path,
        backend: AgentBackend,
        dry_run: bool = False,
        timeout: int = 300,
    ) -> BootstrapResult:
        """Bootstrap a project with AI-generated documentation.

        Args:
            project_path: Path to the project directory
            backend: AI backend to use for generation
            dry_run: If True, don't write files, just return content
            timeout: Timeout for backend calls in seconds

        Returns:
            BootstrapResult with success status and content
        """
        path = project_path.resolve()
        project_name = path.name or str(path)

        logger.info(f"Bootstrapping project: {project_name}")

        # Check if backend is available
        if not await backend.is_available():
            setup_help = backend.get_setup_instructions()
            return BootstrapResult(
                success=False,
                roadmap_content=None,
                best_practices_content=None,
                error_message=f"Backend '{backend.name}' is not available. {setup_help}",
                files_written=[],
            )

        # Analyze project
        analysis = self.analyze_project_structure(path)
        logger.info(f"Detected project type: {analysis.project_type} ({analysis.language})")

        # Generate roadmap
        roadmap_prompt = self._generate_roadmap_prompt(analysis, project_name)
        logger.info("Generating roadmap...")

        roadmap_content = ""
        try:
            async for line in backend.run(
                project_path=path,
                prompt=roadmap_prompt,
                timeout=timeout,
            ):
                roadmap_content += line

            # Check for errors in output
            if "[ERROR]" in roadmap_content or "not found in PATH" in roadmap_content:
                err_msg = "Backend failed to generate roadmap. Check backend configuration."
                return BootstrapResult(
                    success=False,
                    roadmap_content=None,
                    best_practices_content=None,
                    error_message=err_msg,
                    files_written=[],
                )
        except Exception as e:
            logger.error(f"Error generating roadmap: {e}")
            return BootstrapResult(
                success=False,
                roadmap_content=None,
                best_practices_content=None,
                error_message=f"Failed to generate roadmap: {e}",
                files_written=[],
            )

        roadmap_parsed = self._parse_response(roadmap_content)

        # Generate best practices
        best_practices_prompt = self._generate_best_practices_prompt(analysis, project_name)
        logger.info("Generating best practices...")

        best_practices_content = ""
        try:
            async for line in backend.run(
                project_path=path,
                prompt=best_practices_prompt,
                timeout=timeout,
            ):
                best_practices_content += line

            # Check for errors in output
            if "[ERROR]" in best_practices_content or "not found in PATH" in best_practices_content:
                err_msg = "Backend failed to generate best practices. Check backend configuration."
                return BootstrapResult(
                    success=False,
                    roadmap_content=roadmap_parsed,
                    best_practices_content=None,
                    error_message=err_msg,
                    files_written=[],
                )
        except Exception as e:
            logger.error(f"Error generating best practices: {e}")
            return BootstrapResult(
                success=False,
                roadmap_content=roadmap_parsed,
                best_practices_content=None,
                error_message=f"Failed to generate best practices: {e}",
                files_written=[],
            )

        best_practices_parsed = self._parse_response(best_practices_content)

        files_written = []

        if not dry_run:
            # Write ROADMAP.md
            roadmap_path = path / "ROADMAP.md"
            try:
                roadmap_path.write_text(roadmap_parsed, encoding="utf-8")
                files_written.append(str(roadmap_path))
                logger.info(f"Created: {roadmap_path}")
            except Exception as e:
                logger.error(f"Failed to write ROADMAP.md: {e}")
                return BootstrapResult(
                    success=False,
                    roadmap_content=roadmap_parsed,
                    best_practices_content=best_practices_parsed,
                    error_message=f"Failed to write ROADMAP.md: {e}",
                    files_written=files_written,
                )

            # Write BEST_PRACTICES.md
            best_practices_path = path / "BEST_PRACTICES.md"
            try:
                best_practices_path.write_text(best_practices_parsed, encoding="utf-8")
                files_written.append(str(best_practices_path))
                logger.info(f"Created: {best_practices_path}")
            except Exception as e:
                logger.error(f"Failed to write BEST_PRACTICES.md: {e}")
                return BootstrapResult(
                    success=False,
                    roadmap_content=roadmap_parsed,
                    best_practices_content=best_practices_parsed,
                    error_message=f"Failed to write BEST_PRACTICES.md: {e}",
                    files_written=files_written,
                )
        else:
            logger.info("Dry run mode - no files written")

        return BootstrapResult(
            success=True,
            roadmap_content=roadmap_parsed,
            best_practices_content=best_practices_parsed,
            error_message=None,
            files_written=files_written,
        )
