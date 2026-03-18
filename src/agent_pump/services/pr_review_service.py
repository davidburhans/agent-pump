"""PR Review service for automated code review."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

try:
    from github import GithubException, RateLimitExceededException, UnknownObjectException
except ImportError:
    GithubException = Exception
    RateLimitExceededException = Exception
    UnknownObjectException = Exception

from agent_pump.models.review import (
    BestPracticeViolationModel,
    IssueModel,
    ReviewReportModel,
)
from agent_pump.orchestrator.verification_executor import VerificationExecutor

# Aliases for backward compatibility
PRReviewReport = ReviewReportModel
Issue = IssueModel
BestPracticeViolation = BestPracticeViolationModel
from agent_pump.services.diff_service import DiffService
from agent_pump.utils.diff_parser import parse_git_diff

logger = logging.getLogger(__name__)


class ChangedFile:
    """Represents a file that was changed in a PR."""

    def __init__(
        self,
        path: str,
        status: str,
        diff: str = "",
        additions: int = 0,
        deletions: int = 0,
    ):
        """Initialize a changed file.

        Args:
            path: File path relative to project root
            status: Status (added, modified, deleted)
            diff: Unified diff of changes
            additions: Number of lines added
            deletions: Number of lines deleted
        """
        self.path = path
        self.status = status
        self.diff = diff
        self.additions = additions
        self.deletions = deletions


class PRReviewService:
    """Service for automated PR review with code quality checks.

    This service reviews pull requests by:
    - Analyzing code changes for quality issues
    - Checking against BEST_PRACTICES.md requirements
    - Suggesting improvements and refactoring opportunities
    - Blocking merge if critical issues found

    Args:
        project_path: Path to the project being reviewed
    """

    def __init__(self, project_path: Path, github_config: Any | None = None):
        """Initialize the PR review service.

        Args:
            project_path: Path to the project being reviewed
            github_config: Optional GitHub integration configuration
        """
        self.project_path = project_path
        self.github_config = github_config
        self.diff_service = DiffService(project_path)
        self.verification_executor = VerificationExecutor(project_path)

    async def fetch_pr_changes(
        self, base_branch: str | None = None, head_branch: str | None = None
    ) -> list[ChangedFile]:
        """Fetch changes for review.

        Args:
            base_branch: Base branch to compare against. If None, uses working tree changes.
            head_branch: Feature branch to compare (None for current branch)

        Returns:
            List of changed files with their diff content
        """
        try:
            if base_branch:
                # Use git diff to get changes between branches
                # base...head shows changes in head since it diverged from base
                diff_args = [f"{base_branch}...{head_branch or ''}"]
                diff_output = self.diff_service.repo.git.diff(*diff_args, "--unified=3")
                diff_files = parse_git_diff(diff_output)
            else:
                # Get all changes (staged and unstaged) in working tree
                diff_files = self.diff_service.get_all_changes()

            changed_files = []
            for diff_file in diff_files:
                # Calculate additions and deletions from hunks
                additions = 0
                deletions = 0
                diff_content = ""

                for hunk in diff_file.hunks:
                    hunk_text = "\n".join(hunk.lines)
                    diff_content += hunk_text + "\n"
                    for line in hunk.lines:
                        if line.startswith("+") and not line.startswith("+++"):
                            additions += 1
                        elif line.startswith("-") and not line.startswith("---"):
                            deletions += 1

                # Determine status based on diff file
                status = "modified"
                if diff_file.status.value == "ADDED":
                    status = "added"
                elif diff_file.status.value == "DELETED":
                    status = "deleted"
                elif diff_file.status.value == "RENAMED":
                    status = "renamed"

                changed_files.append(
                    ChangedFile(
                        path=diff_file.path,
                        status=status,
                        diff=diff_content,
                        additions=additions,
                        deletions=deletions,
                    )
                )

            return changed_files

        except (
            RateLimitExceededException,
            UnknownObjectException,
            GithubException,
            Exception,
        ) as e:
            logger.warning(f"Failed to fetch PR changes: {e}")
            return []

    async def analyze_code_quality(self, files: list[ChangedFile]) -> list[IssueModel]:
        """Analyze code for quality issues.

        Args:
            files: List of changed files to analyze

        Returns:
            List of identified issues
        """
        issues = []

        # Filter for code files only
        code_files = [
            f
            for f in files
            if f.path.endswith(
                (".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h")
            )
        ]

        if not code_files:
            return issues

        # Run linting if available
        lint_issues = await self._run_linter()
        issues.extend(lint_issues)

        # Run type checking if available
        type_issues = await self._run_type_checker()
        issues.extend(type_issues)

        # Check for common code smells
        smell_issues = await self._check_code_smells(code_files)
        issues.extend(smell_issues)

        return issues

    async def _run_linter(self) -> list[IssueModel]:
        """Run linter and parse output for issues."""
        issues = []

        # Try ruff first (fast Python linter)
        try:
            result = await self.verification_executor.run_command("ruff check .", timeout=60)
            if result.stdout:
                ruff_issues = self._parse_ruff_output(result.stdout)
                issues.extend(ruff_issues)
        except Exception as e:
            logger.debug(f"Ruff linting failed or not available: {e}")

        # Try flake8 as fallback
        if not issues:
            try:
                result = await self.verification_executor.run_command("flake8 .", timeout=60)
                if result.stdout:
                    flake8_issues = self._parse_flake8_output(result.stdout)
                    issues.extend(flake8_issues)
            except Exception as e:
                logger.debug(f"Flake8 linting failed or not available: {e}")

        return issues

    async def _run_type_checker(self) -> list[IssueModel]:
        """Run type checker and parse output for issues."""
        issues = []

        # Try mypy
        try:
            result = await self.verification_executor.run_command("mypy .", timeout=120)
            if not result.success and result.stdout:
                mypy_issues = self._parse_mypy_output(result.stdout)
                issues.extend(mypy_issues)
        except Exception as e:
            logger.debug(f"Mypy type checking failed or not available: {e}")

        return issues

    async def _check_code_smells(self, files: list[ChangedFile]) -> list[IssueModel]:
        """Check for common code smells in changed files."""
        issues = []

        for file in files:
            # Only check Python files for now
            if not file.path.endswith(".py"):
                continue

            file_path = self.project_path / file.path
            if not file_path.exists():
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.split("\n")

                for line_num, line in enumerate(lines, 1):
                    line = line.rstrip()

                    # Check for TODO/FIXME without issue reference
                    if re.search(r"#\s*(TODO|FIXME)\s*$", line, re.IGNORECASE):
                        issues.append(
                            IssueModel(
                                file_path=file.path,
                                line_number=line_num,
                                severity="medium",
                                message="TODO/FIXME comment without issue reference",
                                suggestion="Add an issue number or remove the comment",
                            )
                        )

                    # Check for print statements (should use logging)
                    if re.search(r"\bprint\s*\(", line) and not line.strip().startswith("#"):
                        issues.append(
                            IssueModel(
                                file_path=file.path,
                                line_number=line_num,
                                severity="low",
                                message="Print statement found",
                                suggestion="Consider using logging instead of print",
                            )
                        )

                    # Check for bare except clauses
                    if re.search(r"except\s*:", line):
                        issues.append(
                            IssueModel(
                                file_path=file.path,
                                line_number=line_num,
                                severity="high",
                                message="Bare except clause found",
                                suggestion="Use 'except Exception:' or specify the exception type",
                            )
                        )

                    # Check for very long lines
                    if len(line) > 120:
                        issues.append(
                            IssueModel(
                                file_path=file.path,
                                line_number=line_num,
                                severity="low",
                                message=f"Line too long ({len(line)} characters)",
                                suggestion="Consider breaking the line into multiple lines",
                            )
                        )

            except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to check code smells in {file.path}: {e}")

        return issues

    def _parse_ruff_output(self, output: str) -> list[IssueModel]:
        """Parse ruff linter output."""
        issues = []
        # Ruff format: file.py:1:1: E501 Line too long
        pattern = r"^(.+?):(\d+):(\d+):\s*(\w+)\s*(.+)$"

        for line in output.strip().split("\n"):
            match = re.match(pattern, line)
            if match:
                file_path, line_num, col, code, message = match.groups()
                severity = self._map_linter_code_to_severity(code)
                issues.append(
                    IssueModel(
                        file_path=file_path,
                        line_number=int(line_num),
                        severity=severity,
                        message=f"[{code}] {message}",
                        code=code,
                    )
                )

        return issues

    def _parse_flake8_output(self, output: str) -> list[IssueModel]:
        """Parse flake8 linter output."""
        issues = []
        # Flake8 format: file.py:1:1: E501 Line too long
        pattern = r"^(.+?):(\d+):(\d+):\s*(\w+)\s*(.+)$"

        for line in output.strip().split("\n"):
            match = re.match(pattern, line)
            if match:
                file_path, line_num, col, code, message = match.groups()
                severity = self._map_linter_code_to_severity(code)
                issues.append(
                    IssueModel(
                        file_path=file_path,
                        line_number=int(line_num),
                        severity=severity,
                        message=f"[{code}] {message}",
                        code=code,
                    )
                )

        return issues

    def _parse_mypy_output(self, output: str) -> list[IssueModel]:
        """Parse mypy type checker output."""
        issues = []
        # Mypy format: file.py:1: error: Message
        pattern = r"^(.+?):(\d+):\s*(error|warning|note):\s*(.+)$"

        for line in output.strip().split("\n"):
            match = re.match(pattern, line)
            if match:
                file_path, line_num, level, message = match.groups()
                severity = "critical" if level == "error" else "medium"
                issues.append(
                    IssueModel(
                        file_path=file_path,
                        line_number=int(line_num),
                        severity=severity,
                        message=f"[mypy] {message}",
                    )
                )

        return issues

    def _map_linter_code_to_severity(self, code: str) -> str:
        """Map linter error codes to severity levels."""
        # Critical errors
        if code.startswith(("F", "E9")):
            return "critical"
        # High severity
        elif code.startswith(("E", "W9")):
            return "high"
        # Medium severity
        elif code.startswith(("W", "C9")):
            return "medium"
        # Low severity (style)
        else:
            return "low"

    async def check_best_practices(
        self, issues: list[IssueModel]
    ) -> list[BestPracticeViolationModel]:
        """Check changes against BEST_PRACTICES.md requirements.

        Args:
            issues: List of identified issues

        Returns:
            List of best practice violations
        """
        violations = []

        # Read BEST_PRACTICES.md if it exists
        best_practices_path = self.project_path / "BEST_PRACTICES.md"
        if not best_practices_path.exists():
            logger.debug("BEST_PRACTICES.md not found, skipping best practice checks")
            return violations

        try:
            content = best_practices_path.read_text(encoding="utf-8")

            # Parse common requirements from BEST_PRACTICES.md
            # Look for checklist items or requirement patterns
            requirements = self._parse_best_practices(content)

            # Check each requirement against the code
            for req in requirements:
                violation = self._check_requirement(req)
                if violation:
                    violations.append(violation)

        except Exception as e:
            logger.warning(f"Failed to check best practices: {e}")

        return violations

    def _parse_best_practices(self, content: str) -> list[dict]:
        """Parse BEST_PRACTICES.md content for requirements."""
        requirements = []

        # Look for common patterns like:
        # - [ ] Requirement text
        # - [x] Requirement text
        # * Requirement: description

        lines = content.split("\n")
        current_section = "General"

        for line in lines:
            line = line.strip()

            # Update current section on headers
            if line.startswith("#"):
                current_section = line.lstrip("#").strip()
                continue

            # Check for checklist items
            checklist_match = re.match(r"^[\-\*]\s*\[([ xX])\]\s*(.+)$", line)
            if checklist_match:
                checked, text = checklist_match.groups()
                requirements.append(
                    {
                        "section": current_section,
                        "text": text,
                        "required": checked.lower() != "x",  # Unchecked items are requirements
                    }
                )

        return requirements

    def _check_requirement(self, req: dict) -> BestPracticeViolationModel | None:
        """Check if a requirement is violated."""
        # This is a simplified check - in practice, you'd have more sophisticated
        # logic to verify each type of requirement
        text = req["text"].lower()

        # Example checks based on common best practices
        if "test" in text or "testing" in text:
            # Check if tests exist
            test_paths = [
                self.project_path / "tests",
                self.project_path / "test",
            ]
            has_tests = any(p.exists() and p.is_dir() for p in test_paths)
            if not has_tests and req.get("required", False):
                return BestPracticeViolationModel(
                    section=req["section"],
                    requirement=req["text"],
                    file_path="",
                    line_number=None,
                    description="No test directory found",
                )

        if "docstring" in text or "documentation" in text:
            # Check for docstrings in Python files
            python_files = list(self.project_path.rglob("*.py"))
            files_without_docstrings = []

            for py_file in python_files:
                if "test" in py_file.name or py_file.name.startswith("__"):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    if not re.search(r'"""[\s\S]*?"""', content):
                        files_without_docstrings.append(py_file.relative_to(self.project_path))
                except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                    continue

            if files_without_docstrings and req.get("required", False):
                return BestPracticeViolationModel(
                    section=req["section"],
                    requirement=req["text"],
                    file_path=str(files_without_docstrings[0]),
                    line_number=1,
                    description=f"{len(files_without_docstrings)} files without module docstrings",
                )

        return None

    async def generate_review_report(
        self,
        files: list[ChangedFile],
        code_quality_issues: list[IssueModel],
        best_practice_violations: list[BestPracticeViolationModel],
    ) -> ReviewReportModel:
        """Generate a comprehensive review report.

        Args:
            files: List of changed files
            code_quality_issues: Code quality issues found
            best_practice_violations: Best practice violations found

        Returns:
            ReviewReportModel with all findings and suggestions
        """
        suggestions = []
        blocked = False

        # Process code quality issues
        critical_count = 0
        high_count = 0

        for issue in code_quality_issues:
            if issue.suggestion:
                suggestions.append(f"{issue.file_path}: {issue.suggestion}")

            if issue.severity == "critical":
                critical_count += 1
            elif issue.severity == "high":
                high_count += 1

        # Block if critical issues found
        if critical_count > 0:
            blocked = True

        # Determine if approved
        approved = not blocked and high_count < 5  # Allow up to 5 high severity issues

        # Add summary suggestions
        if critical_count > 0:
            suggestions.insert(0, f"Fix {critical_count} critical issue(s) before merging")

        if high_count > 0:
            suggestions.append(f"Address {high_count} high severity issue(s)")

        # Add file statistics suggestion
        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)
        if total_additions > 500:
            suggestions.append(
                f"Large PR: +{total_additions}/-{total_deletions} lines. "
                "Consider splitting into smaller PRs"
            )

        return ReviewReportModel(
            approved=approved,
            issues=code_quality_issues,
            violations=best_practice_violations,
            suggestions=suggestions,
            blocked=blocked,
        )
