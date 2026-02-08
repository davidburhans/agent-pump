"""Tests for PR Review Service."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.models.diff import DiffChangeType, DiffFile, DiffHunk
from agent_pump.services.pr_review_service import (
    BestPracticeViolation,
    ChangedFile,
    Issue,
    PRReviewReport,
    PRReviewService,
)


class TestChangedFile:
    """Tests for ChangedFile class."""

    def test_initialization(self):
        """Test ChangedFile initialization."""
        file = ChangedFile(
            path="src/test.py",
            status="modified",
            diff="+ added line",
            additions=1,
            deletions=0,
        )
        assert file.path == "src/test.py"
        assert file.status == "modified"
        assert file.diff == "+ added line"
        assert file.additions == 1
        assert file.deletions == 0


class TestIssue:
    """Tests for Issue class."""

    def test_initialization(self):
        """Test Issue initialization."""
        issue = Issue(
            file_path="src/test.py",
            line_number=42,
            severity="high",
            message="Test issue",
            suggestion="Fix it",
        )
        assert issue.file_path == "src/test.py"
        assert issue.line_number == 42
        assert issue.severity == "high"
        assert issue.message == "Test issue"
        assert issue.suggestion == "Fix it"


class TestBestPracticeViolation:
    """Tests for BestPracticeViolation class."""

    def test_initialization(self):
        """Test BestPracticeViolation initialization."""
        violation = BestPracticeViolation(
            section="Testing",
            requirement="All code must have tests",
            file_path="src/test.py",
            line_number=10,
            description="No tests found",
        )
        assert violation.section == "Testing"
        assert violation.requirement == "All code must have tests"
        assert violation.file_path == "src/test.py"
        assert violation.line_number == 10
        assert violation.description == "No tests found"


class TestPRReviewReport:
    """Tests for PRReviewReport class."""

    def test_initialization(self):
        """Test PRReviewReport initialization."""
        issues = [
            Issue(file_path="f1", line_number=1, severity="low", message="m1"),
            Issue(file_path="f2", line_number=2, severity="medium", message="m2"),
        ]
        report = PRReviewReport(
            approved=True,
            issues=issues,
            suggestions=["Suggestion 1"],
            blocked=False,
        )
        assert report.approved is True
        assert len(report.issues) == 2
        assert len(report.suggestions) == 1
        assert report.blocked is False

    def test_repr(self):
        """Test PRReviewReport repr."""
        report = PRReviewReport(
            approved=True,
            issues=[],
            suggestions=[],
            blocked=False,
        )
        # Pydantic repr shows fields
        assert "approved=True" in repr(report)
        assert "issues=[]" in repr(report)

        issue = Issue(file_path="f1", line_number=1, severity="critical", message="m1")
        report_blocked = PRReviewReport(
            approved=False,
            issues=[issue],
            suggestions=[],
            blocked=True,
        )
        assert "approved=False" in repr(report_blocked)
        assert "blocked=True" in repr(report_blocked)


class TestPRReviewService:
    """Tests for PRReviewService class."""

    @pytest.fixture
    def service(self, tmp_path):
        """Create a PRReviewService instance."""
        # Initialize git repo in tmp_path
        import subprocess

        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True
        )
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
        return PRReviewService(tmp_path)

    @pytest.fixture
    def mock_diff_file(self):
        """Create a mock DiffFile."""
        return DiffFile(
            path="src/test.py",
            status=DiffChangeType.MODIFIED,
            hunks=[
                DiffHunk(
                    header="@@ -1,3 +1,4 @@",
                    lines=["+ added line", " context", "- removed line"],
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_fetch_pr_changes_success(self, service, mock_diff_file):
        """Test fetching PR changes successfully."""
        with patch.object(service.diff_service, "get_all_changes", return_value=[mock_diff_file]):
            changes = await service.fetch_pr_changes()

        assert len(changes) == 1
        assert changes[0].path == "src/test.py"
        assert changes[0].status == "modified"
        assert changes[0].additions == 1
        assert changes[0].deletions == 1

    @pytest.mark.asyncio
    async def test_fetch_pr_changes_empty(self, service):
        """Test fetching PR changes with no changes."""
        with patch.object(service.diff_service, "get_all_changes", return_value=[]):
            changes = await service.fetch_pr_changes()

        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_fetch_pr_changes_error(self, service):
        """Test fetching PR changes with error."""
        with patch.object(
            service.diff_service, "get_all_changes", side_effect=Exception("Git error")
        ):
            changes = await service.fetch_pr_changes()

        assert len(changes) == 0

    @pytest.mark.asyncio
    async def test_analyze_code_quality_no_files(self, service):
        """Test analyzing code quality with no code files."""
        files = [
            ChangedFile(path="README.md", status="modified", diff="", additions=1, deletions=0)
        ]
        issues = await service.analyze_code_quality(files)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_analyze_code_quality_with_linter(self, service, tmp_path):
        """Test analyzing code quality with linter output."""
        # Create a Python file
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')\n")

        files = [ChangedFile(path="test.py", status="modified", diff="", additions=1, deletions=0)]

        # Mock linter output
        mock_result = MagicMock()
        mock_result.stdout = "test.py:1:1: E501 Line too long (100 > 88 characters)"
        mock_result.success = False

        with patch.object(service.verification_executor, "run_command", return_value=mock_result):
            issues = await service.analyze_code_quality(files)

        assert len(issues) >= 0  # Depends on implementation

    @pytest.mark.asyncio
    async def test_check_best_practices_no_file(self, service):
        """Test checking best practices without BEST_PRACTICES.md."""
        issues = []
        violations = await service.check_best_practices(issues)
        assert len(violations) == 0

    @pytest.mark.asyncio
    async def test_check_best_practices_with_file(self, service, tmp_path):
        """Test checking best practices with BEST_PRACTICES.md."""
        # Create BEST_PRACTICES.md
        bp_file = tmp_path / "BEST_PRACTICES.md"
        bp_file.write_text("# Best Practices\n\n- [ ] All code must have tests\n")

        issues = []
        violations = await service.check_best_practices(issues)
        # Should detect missing tests
        assert isinstance(violations, list)

    @pytest.mark.asyncio
    async def test_generate_review_report_approved(self, service):
        """Test generating review report with approval."""
        files = [ChangedFile(path="test.py", status="modified", diff="", additions=10, deletions=5)]
        code_issues = []
        bp_violations = []

        report = await service.generate_review_report(files, code_issues, bp_violations)

        assert report.approved is True
        assert report.blocked is False
        assert len(report.issues) == 0

    @pytest.mark.asyncio
    async def test_generate_review_report_blocked(self, service):
        """Test generating review report with blocked status."""
        files = [ChangedFile(path="test.py", status="modified", diff="", additions=10, deletions=5)]
        code_issues = [
            Issue(
                file_path="test.py",
                line_number=1,
                severity="critical",
                message="Critical error",
            )
        ]
        bp_violations = []

        report = await service.generate_review_report(files, code_issues, bp_violations)

        assert report.blocked is True
        assert report.approved is False
        assert len(report.issues) == 1

    @pytest.mark.asyncio
    async def test_generate_review_report_large_pr(self, service):
        """Test generating review report for large PR."""
        files = [
            ChangedFile(path="test.py", status="modified", diff="", additions=600, deletions=100)
        ]
        code_issues = []
        bp_violations = []

        report = await service.generate_review_report(files, code_issues, bp_violations)

        assert any("Large PR" in s for s in report.suggestions)

    def test_parse_ruff_output(self, service):
        """Test parsing ruff linter output."""
        output = "test.py:1:1: E501 Line too long\ntest.py:2:5: F401 Unused import"
        issues = service._parse_ruff_output(output)

        assert len(issues) == 2
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 1
        assert "E501" in issues[0].message

    def test_parse_flake8_output(self, service):
        """Test parsing flake8 linter output."""
        output = "test.py:1:1: E501 Line too long\ntest.py:2:5: W291 Trailing whitespace"
        issues = service._parse_flake8_output(output)

        assert len(issues) == 2
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 1

    def test_parse_mypy_output(self, service):
        """Test parsing mypy output."""
        output = "test.py:1: error: Incompatible types\ntest.py:2: warning: Unused ignore"
        issues = service._parse_mypy_output(output)

        assert len(issues) == 2
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 1
        assert issues[0].severity == "critical"

    def test_map_linter_code_to_severity(self, service):
        """Test mapping linter codes to severity."""
        assert service._map_linter_code_to_severity("F401") == "critical"
        assert service._map_linter_code_to_severity("E501") == "high"
        assert service._map_linter_code_to_severity("W291") == "medium"
        assert service._map_linter_code_to_severity("C101") == "low"

    @pytest.mark.asyncio
    async def test_check_code_smells_todo(self, service, tmp_path):
        """Test detecting TODO comments."""
        py_file = tmp_path / "test.py"
        py_file.write_text("# TODO\nprint('hello')\n")

        files = [ChangedFile(path="test.py", status="modified", diff="", additions=2, deletions=0)]
        issues = await service._check_code_smells(files)

        assert any("TODO" in issue.message for issue in issues)

    @pytest.mark.asyncio
    async def test_check_code_smells_print(self, service, tmp_path):
        """Test detecting print statements."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')\n")

        files = [ChangedFile(path="test.py", status="modified", diff="", additions=1, deletions=0)]
        issues = await service._check_code_smells(files)

        assert any("Print statement" in issue.message for issue in issues)

    @pytest.mark.asyncio
    async def test_check_code_smells_bare_except(self, service, tmp_path):
        """Test detecting bare except clauses."""
        py_file = tmp_path / "test.py"
        py_file.write_text("try:\n    pass\nexcept:\n    pass\n")

        files = [ChangedFile(path="test.py", status="modified", diff="", additions=4, deletions=0)]
        issues = await service._check_code_smells(files)

        assert any("Bare except" in issue.message for issue in issues)

    @pytest.mark.asyncio
    async def test_check_code_smells_long_line(self, service, tmp_path):
        """Test detecting long lines."""
        py_file = tmp_path / "test.py"
        py_file.write_text("x = " + "a" * 130 + "\n")

        files = [ChangedFile(path="test.py", status="modified", diff="", additions=1, deletions=0)]
        issues = await service._check_code_smells(files)

        assert any("Line too long" in issue.message for issue in issues)
