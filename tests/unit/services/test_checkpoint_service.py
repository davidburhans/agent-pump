"""Tests for checkpoint service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from git import GitCommandError

from agent_pump.events.bus import EventBus
from agent_pump.models.checkpoint import Checkpoint
from agent_pump.services.checkpoint_service import (
    CheckpointError,
    CheckpointService,
    RollbackError,
)


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


class TestCheckpointServiceInitialization:
    """Tests for CheckpointService initialization."""

    def test_init_with_path(self, tmp_path, event_bus):
        """Test initialization with repository path."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            assert service.repo_path == tmp_path
            assert service.event_bus == event_bus
            # Repo is lazily loaded
            mock_repo.assert_not_called()

            # Access repo to trigger loading
            _ = service.repo
            mock_repo.assert_called_once_with(tmp_path)


class TestCheckpointServiceWorktree:
    """Tests for worktree status checking."""

    def test_is_worktree_clean_true(self, tmp_path, event_bus):
        """Test clean worktree detection."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = False
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.is_worktree_clean()

            assert result is True
            mock_instance.is_dirty.assert_called_once_with(untracked_files=True)

    def test_is_worktree_clean_false_dirty(self, tmp_path, event_bus):
        """Test dirty worktree detection."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = True
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.is_worktree_clean()

            assert result is False

    def test_is_worktree_clean_false_untracked(self, tmp_path, event_bus):
        """Test worktree with untracked files."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = False
            mock_instance.untracked_files = ["new_file.py"]
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.is_worktree_clean()

            assert result is False


class TestCheckpointServiceModifiedFiles:
    """Tests for getting modified files list."""

    def test_get_modified_files_empty(self, tmp_path, event_bus):
        """Test getting modified files when none exist."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.index.diff.return_value = []
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_modified_files()

            assert result == []

    def test_get_modified_files_with_staged(self, tmp_path, event_bus):
        """Test getting staged files."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()

            # Mock staged files (diff against HEAD)
            staged_item = MagicMock()
            staged_item.a_path = "staged_file.py"
            mock_instance.index.diff = MagicMock(
                side_effect=[
                    [staged_item],  # diff against HEAD (staged)
                    [],  # diff against None (unstaged)
                ]
            )
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_modified_files()

            assert "staged_file.py" in result
            assert len(result) == 1

    def test_get_modified_files_with_unstaged(self, tmp_path, event_bus):
        """Test getting unstaged files."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()

            # Mock unstaged files (diff against None)
            unstaged_item = MagicMock()
            unstaged_item.a_path = "unstaged_file.py"
            mock_instance.index.diff = MagicMock(
                side_effect=[
                    [],  # diff against HEAD (staged)
                    [unstaged_item],  # diff against None (unstaged)
                ]
            )
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_modified_files()

            assert "unstaged_file.py" in result
            assert len(result) == 1

    def test_get_modified_files_with_untracked(self, tmp_path, event_bus):
        """Test getting untracked files."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.index.diff.return_value = []
            mock_instance.untracked_files = ["untracked.py", "new_file.txt"]
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_modified_files()

            assert "untracked.py" in result
            assert "new_file.txt" in result
            assert len(result) == 2

    def test_get_modified_files_deduplication(self, tmp_path, event_bus):
        """Test that duplicate files are removed."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()

            # Create mock items with same path
            item1 = MagicMock()
            item1.a_path = "duplicate.py"
            item2 = MagicMock()
            item2.a_path = "duplicate.py"

            mock_instance.index.diff = MagicMock(
                side_effect=[
                    [item1],  # staged
                    [item2],  # unstaged (duplicate)
                ]
            )
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_modified_files()

            # Should only appear once despite being in both lists
            assert result.count("duplicate.py") == 1
            assert len(result) == 1


class TestCheckpointServiceCreateCheckpoint:
    """Tests for creating checkpoints."""

    def test_create_checkpoint_with_changes(self, tmp_path, event_bus):
        """Test creating checkpoint when there are changes."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = True
            mock_instance.untracked_files = ["new_file.py"]

            # Mock the commit
            mock_commit = MagicMock()
            mock_commit.hexsha = "abc123def4567890abcdef1234567890abcdef12"
            mock_instance.index.commit.return_value = mock_commit

            mock_instance.index.diff = MagicMock(return_value=[])
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            checkpoint = service.create_checkpoint(
                phase="planning",
                feature="Test Feature",
                auto_created=True,
            )

            assert checkpoint.phase == "planning"
            assert checkpoint.feature == "Test Feature"
            assert checkpoint.git_commit_hash == "abc123def4567890abcdef1234567890abcdef12"
            assert checkpoint.auto_created is True
            assert "planning" in checkpoint.description.lower()

            # Verify git operations
            mock_instance.git.add.assert_called_once_with("-A")
            mock_instance.index.commit.assert_called_once()

    def test_create_checkpoint_clean_worktree(self, tmp_path, event_bus):
        """Test creating checkpoint when worktree is clean."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = False
            mock_instance.untracked_files = []

            # Mock HEAD commit
            mock_head = MagicMock()
            mock_head.commit.hexsha = "def789abc1234567890abcdef1234567890abcdef"
            mock_instance.head = mock_head

            mock_instance.index.diff = MagicMock(return_value=[])
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            checkpoint = service.create_checkpoint(
                phase="implementing",
                auto_created=True,
            )

            assert checkpoint.phase == "implementing"
            assert checkpoint.git_commit_hash == "def789abc1234567890abcdef1234567890abcdef"
            assert checkpoint.auto_created is True

            # Should not stage or commit since no changes
            mock_instance.git.add.assert_not_called()
            mock_instance.index.commit.assert_not_called()

    def test_create_checkpoint_manual(self, tmp_path, event_bus):
        """Test creating manual checkpoint."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = True
            mock_instance.untracked_files = []

            mock_commit = MagicMock()
            mock_commit.hexsha = "manual1234567890abcdef1234567890abcdef12"
            mock_instance.index.commit.return_value = mock_commit
            mock_instance.index.diff = MagicMock(return_value=[])
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            checkpoint = service.create_checkpoint(
                phase="verifying",
                feature="Manual Feature",
                description="User saved checkpoint",
                auto_created=False,
            )

            assert checkpoint.auto_created is False
            assert checkpoint.description == "User saved checkpoint"

            # Check commit message contains "manual"
            call_args = mock_instance.index.commit.call_args[0][0]
            assert "manual" in call_args.lower()

    def test_create_checkpoint_git_error(self, tmp_path, event_bus):
        """Test handling git errors during checkpoint creation."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.side_effect = GitCommandError("git status", 1)
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            with pytest.raises(CheckpointError) as exc_info:
                service.create_checkpoint(phase="planning")

            assert "Failed to create checkpoint" in str(exc_info.value)

    def test_create_checkpoint_custom_description(self, tmp_path, event_bus):
        """Test checkpoint with custom description."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = True
            mock_instance.untracked_files = []

            mock_commit = MagicMock()
            mock_commit.hexsha = "custom1234567890abcdef1234567890abcdef12"
            mock_instance.index.commit.return_value = mock_commit
            mock_instance.index.diff = MagicMock(return_value=[])
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            checkpoint = service.create_checkpoint(
                phase="planning",
                description="Custom checkpoint message",
            )

            # Commit message should use custom description
            call_args = mock_instance.index.commit.call_args[0][0]
            assert "Custom checkpoint message" in call_args
            assert checkpoint.description == "Custom checkpoint message"


class TestCheckpointServiceRollback:
    """Tests for rollback operations."""

    def test_rollback_success_with_backup(self, tmp_path, event_bus):
        """Test successful rollback with backup branch creation."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "feature/test-branch"

            # Mock commit existence check
            mock_instance.commit.return_value = MagicMock()

            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            checkpoint = Checkpoint(
                phase="planning",
                git_commit_hash="abc123def4567890abcdef1234567890abcdef12",
                description="Test checkpoint",
            )

            result = service.rollback_to_checkpoint(checkpoint, create_backup_branch=True)

            assert result is True

            # Verify backup branch was created
            mock_instance.git.branch.assert_called_once()
            branch_call = mock_instance.git.branch.call_args[0][0]
            assert "backup" in branch_call
            assert checkpoint.id in branch_call

            # Verify reset was performed
            mock_instance.git.reset.assert_called_once_with("--hard", checkpoint.git_commit_hash)

    def test_rollback_success_no_backup(self, tmp_path, event_bus):
        """Test successful rollback without backup branch."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            mock_instance.commit.return_value = MagicMock()
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            checkpoint = Checkpoint(
                phase="implementing",
                git_commit_hash="def456abc789",
                description="Test checkpoint",
            )

            result = service.rollback_to_checkpoint(checkpoint, create_backup_branch=False)

            assert result is True
            mock_instance.git.branch.assert_not_called()
            mock_instance.git.reset.assert_called_once()

    def test_rollback_commit_not_found(self, tmp_path, event_bus):
        """Test rollback when checkpoint commit doesn't exist."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.commit.side_effect = Exception("Commit not found")
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            checkpoint = Checkpoint(
                phase="planning",
                git_commit_hash="nonexistent123",
                description="Test checkpoint",
            )

            with pytest.raises(RollbackError) as exc_info:
                service.rollback_to_checkpoint(checkpoint)

            assert "not found" in str(exc_info.value).lower()

    def test_rollback_git_error(self, tmp_path, event_bus):
        """Test handling git errors during rollback."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.commit.return_value = MagicMock()
            mock_instance.git.reset.side_effect = GitCommandError("git reset", 1)
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)

            checkpoint = Checkpoint(
                phase="planning",
                git_commit_hash="abc123",
                description="Test checkpoint",
            )

            with pytest.raises(RollbackError) as exc_info:
                service.rollback_to_checkpoint(checkpoint)

            assert "Git error" in str(exc_info.value)


class TestCheckpointServiceHelperMethods:
    """Tests for helper methods."""

    def test_get_current_commit_hash(self, tmp_path, event_bus):
        """Test getting current commit hash."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.head.commit.hexsha = "current1234567890abcdef1234567890abcdef"
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.get_current_commit_hash()

            assert result == "current1234567890abcdef1234567890abcdef"

    def test_list_checkpoint_commits(self, tmp_path, event_bus):
        """Test listing checkpoint commits."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()

            # Mock some commits
            commit1 = MagicMock()
            commit1.message = "[checkpoint] auto: planning checkpoint"
            commit1.hexsha = "abc123"
            commit1.committed_datetime = datetime(2024, 1, 15, 10, 0, 0)
            commit1.author = "Test User"

            commit2 = MagicMock()
            commit2.message = "[checkpoint] manual: user checkpoint"
            commit2.hexsha = "def456"
            commit2.committed_datetime = datetime(2024, 1, 15, 11, 0, 0)
            commit2.author = "Test User"

            # Regular commit (not a checkpoint)
            commit3 = MagicMock()
            commit3.message = "Regular commit"
            commit3.hexsha = "ghi789"

            mock_instance.iter_commits.return_value = [commit1, commit2, commit3]
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.list_checkpoint_commits()

            # Should only return checkpoint commits
            assert len(result) == 2
            assert result[0]["hash"] == "abc123"
            assert result[0]["short_hash"] == "abc123"
            assert result[1]["hash"] == "def456"

    def test_list_checkpoint_commits_error_handling(self, tmp_path, event_bus):
        """Test error handling when listing commits fails."""
        with patch("agent_pump.services.checkpoint_service.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.iter_commits.side_effect = Exception("Git error")
            mock_repo.return_value = mock_instance

            service = CheckpointService(event_bus, tmp_path)
            result = service.list_checkpoint_commits()

            # Should return empty list on error
            assert result == []


class TestCheckpointServiceExceptions:
    """Tests for custom exceptions."""

    def test_checkpoint_error(self):
        """Test CheckpointError exception."""
        error = CheckpointError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_rollback_error(self):
        """Test RollbackError exception."""
        error = RollbackError("Rollback failed")
        assert str(error) == "Rollback failed"
        assert isinstance(error, CheckpointError)
