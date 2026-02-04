"""Unit tests for dry-run report models."""

from datetime import datetime

import pytest

from agent_pump.models.dry_run_report import (
    BackendInvocation,
    DryRunReport,
    FileChange,
    FileChangeType,
    GitOperation,
    PhaseEstimate,
)


class TestFileChange:
    """Tests for FileChange model."""

    def test_file_change_creation(self):
        """Test creating a FileChange instance."""
        change = FileChange(
            path="/test/file.txt",
            change_type="CREATED",
            content_length=100,
        )
        assert change.path == "/test/file.txt"
        assert change.change_type == "CREATED"
        assert change.content_length == 100


class TestGitOperation:
    """Tests for GitOperation model."""

    def test_git_operation_creation(self):
        """Test creating a GitOperation instance."""
        op = GitOperation(
            operation_type="branch_create",
            description="Create feature branch",
            branch_name="feature-branch",
            base_branch="main",
        )
        assert op.operation_type == "branch_create"
        assert op.branch_name == "feature-branch"
        assert op.base_branch == "main"


class TestBackendInvocation:
    """Tests for BackendInvocation model."""

    def test_backend_invocation_creation(self):
        """Test creating a BackendInvocation instance."""
        invocation = BackendInvocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost_usd=0.015,
            phase="planning",
        )
        assert invocation.backend_name == "gemini"
        assert invocation.estimated_tokens == 2000
        assert invocation.estimated_cost_usd == 0.015
        assert invocation.phase == "planning"


class TestPhaseEstimate:
    """Tests for PhaseEstimate model."""

    def test_phase_estimate_creation(self):
        """Test creating a PhaseEstimate instance."""
        estimate = PhaseEstimate(
            phase="planning",
            estimated_input_tokens=1000,
            estimated_output_tokens=2000,
            estimated_cost_usd=0.01,
            backend_name="gemini",
        )
        assert estimate.phase == "planning"
        assert estimate.estimated_total_tokens == 3000


class TestDryRunReport:
    """Tests for DryRunReport model."""

    @pytest.fixture
    def report(self):
        """Create a basic report for testing."""
        return DryRunReport(
            project_path="/test/project",
            project_name="test-project",
            start_time=datetime.now(),
        )

    def test_report_creation(self, report):
        """Test creating a DryRunReport instance."""
        assert report.project_path == "/test/project"
        assert report.project_name == "test-project"
        assert report.start_time is not None
        assert report.file_changes == []
        assert report.git_operations == []

    def test_add_file_change(self, report):
        """Test adding file changes."""
        report.add_file_change(
            path="/test/file.txt",
            change_type=FileChangeType.CREATED,
            new_content="Hello world",
        )

        assert len(report.file_changes) == 1
        assert report.total_file_changes == 1
        assert report.file_changes[0].path == "/test/file.txt"
        assert report.file_changes[0].change_type == "CREATED"

    def test_add_multiple_file_changes(self, report):
        """Test adding multiple file changes."""
        report.add_file_change(
            path="/test/file1.txt",
            change_type=FileChangeType.CREATED,
        )
        report.add_file_change(
            path="/test/file2.txt",
            change_type=FileChangeType.MODIFIED,
        )
        report.add_file_change(
            path="/test/file3.txt",
            change_type=FileChangeType.DELETED,
        )

        assert len(report.file_changes) == 3
        assert len(report.get_created_files()) == 1
        assert len(report.get_modified_files()) == 1
        assert len(report.get_deleted_files()) == 1

    def test_add_git_operation(self, report):
        """Test adding git operations."""
        report.add_git_operation(
            operation_type="branch_create",
            description="Create feature branch",
            branch_name="feature-branch",
            base_branch="main",
        )

        assert len(report.git_operations) == 1
        assert report.total_git_operations == 1
        assert report.git_operations[0].branch_name == "feature-branch"

    def test_add_backend_invocation(self, report):
        """Test adding backend invocations."""
        report.add_backend_invocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost_usd=0.015,
            phase="planning",
        )

        assert len(report.backend_invocations) == 1
        assert report.total_backend_invocations == 1
        assert report.total_estimated_tokens == 2000
        assert report.total_estimated_cost_usd == 0.015

    def test_add_multiple_backend_invocations(self, report):
        """Test adding multiple backend invocations."""
        report.add_backend_invocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost_usd=0.015,
        )
        report.add_backend_invocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=1000,
            estimated_tokens=4000,
            estimated_cost_usd=0.03,
        )

        assert report.total_estimated_tokens == 6000
        assert report.total_estimated_cost_usd == 0.045

    def test_add_verification_command(self, report):
        """Test adding verification commands."""
        report.add_verification_command(
            command="pytest tests/",
            phase="verifying",
            would_succeed=True,
        )

        assert len(report.verification_commands) == 1
        assert report.total_verification_commands == 1
        assert report.verification_commands[0].command == "pytest tests/"

    def test_add_phase_estimate(self, report):
        """Test adding phase estimates."""
        report.add_phase_estimate(
            phase="planning",
            estimated_input_tokens=1000,
            estimated_output_tokens=2000,
            estimated_cost_usd=0.01,
            backend_name="gemini",
        )

        assert len(report.phase_estimates) == 1
        assert report.total_estimated_input_tokens == 1000
        assert report.total_estimated_output_tokens == 2000
        assert report.total_estimated_tokens == 3000
        assert report.total_estimated_cost_usd == 0.01

    def test_finalize(self, report):
        """Test finalizing the report."""
        report.add_file_change(
            path="/test/file.txt",
            change_type=FileChangeType.CREATED,
        )

        report.finalize(success=True)

        assert report.end_time is not None
        assert report.would_succeed is True
        assert report.duration_seconds >= 0

    def test_finalize_with_failure(self, report):
        """Test finalizing the report with failure."""
        report.finalize(success=False, failure_reason="Backend not available")

        assert report.would_succeed is False
        assert report.failure_reason == "Backend not available"

    def test_to_summary_dict(self, report):
        """Test generating summary dictionary."""
        report.add_file_change(
            path="/test/file1.txt",
            change_type=FileChangeType.CREATED,
        )
        report.add_file_change(
            path="/test/file2.txt",
            change_type=FileChangeType.MODIFIED,
        )
        report.add_backend_invocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost_usd=0.015,
        )
        report.add_phase_estimate(
            phase="planning",
            estimated_input_tokens=1000,
            estimated_output_tokens=2000,
            estimated_cost_usd=0.01,
        )

        report.finalize(success=True)
        summary = report.to_summary_dict()

        assert summary["project"] == "test-project"
        assert summary["would_succeed"] is True
        assert summary["summary"]["files_created"] == 1
        assert summary["summary"]["files_modified"] == 1
        assert summary["summary"]["files_deleted"] == 0
        # Total tokens includes both backend invocation (2000) and phase estimate (3000)
        assert summary["estimates"]["total_tokens"] == 5000

    def test_format_console_output(self, report):
        """Test formatting report for console output."""
        report.add_file_change(
            path="/test/file.txt",
            change_type=FileChangeType.CREATED,
        )
        report.add_git_operation(
            operation_type="commit",
            description="Commit changes",
            commit_message="feat: add feature",
        )
        report.add_backend_invocation(
            backend_name="gemini",
            command="gemini --yolo",
            prompt_length=500,
            estimated_tokens=2000,
            estimated_cost_usd=0.015,
        )

        report.finalize(success=True)
        output = report.format_console_output()

        assert "DRY RUN REPORT" in output
        assert "test-project" in output
        assert "Would Succeed" in output
        assert "1 files" in output or "1 file" in output
        assert "Total Tokens" in output
        assert "2,000" in output

    def test_get_file_changes_by_type(self, report):
        """Test filtering file changes by type."""
        report.add_file_change(
            path="/test/file1.txt",
            change_type=FileChangeType.CREATED,
        )
        report.add_file_change(
            path="/test/file2.txt",
            change_type=FileChangeType.MODIFIED,
        )
        report.add_file_change(
            path="/test/file3.txt",
            change_type=FileChangeType.CREATED,
        )

        created = report.get_file_changes_by_type(FileChangeType.CREATED)
        assert len(created) == 2

        modified = report.get_file_changes_by_type(FileChangeType.MODIFIED)
        assert len(modified) == 1

    def test_empty_report(self, report):
        """Test an empty report."""
        report.finalize(success=True)

        assert report.total_file_changes == 0
        assert report.total_git_operations == 0
        assert report.total_backend_invocations == 0
        assert report.total_estimated_tokens == 0

        summary = report.to_summary_dict()
        assert summary["summary"]["files_created"] == 0

        output = report.format_console_output()
        assert "DRY RUN REPORT" in output
