"""Tests for branch manager service."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from git import GitCommandError

from agent_pump.models.branch_state import BranchState
from agent_pump.models.branch_strategy import BranchStrategyConfig
from agent_pump.services.branch_manager import BranchManager, MergeResult, slugify_branch_name


class TestSlugifyBranchName:
    """Tests for branch name slugification."""

    def test_simple_name(self):
        """Test simple feature name."""
        result = slugify_branch_name("Add Login Page")
        assert result == "add-login-page"

    def test_special_chars(self):
        """Test name with special characters."""
        result = slugify_branch_name("Fix: Memory Leak in Parser!")
        assert result == "fix-memory-leak-in-parser"

    def test_multiple_spaces(self):
        """Test name with multiple spaces."""
        result = slugify_branch_name("Update    Documentation")
        assert result == "update-documentation"

    def test_leading_trailing_spaces(self):
        """Test name with leading/trailing spaces."""
        result = slugify_branch_name("  Clean Up Code  ")
        assert result == "clean-up-code"

    def test_very_long_name(self):
        """Test very long name truncation."""
        long_name = "A" * 100
        result = slugify_branch_name(long_name)
        assert len(result) <= 50
        assert result == "a" * 50

    def test_empty_string(self):
        """Test empty string."""
        result = slugify_branch_name("")
        assert result == "unknown"

    def test_only_special_chars(self):
        """Test only special characters."""
        result = slugify_branch_name("!@#$%^&*()")
        assert result == "unknown"


class TestBranchManagerInitialization:
    """Tests for BranchManager initialization."""

    def test_init_with_path(self, tmp_path):
        """Test initialization with repository path."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)

            assert manager.repo_path == tmp_path
            # Repo is lazily loaded, so it's not called during init
            mock_repo.assert_not_called()

            # Access repo to trigger loading
            _ = manager.repo
            mock_repo.assert_called_once_with(tmp_path)

    def test_init_with_config(self, tmp_path):
        """Test initialization with custom config."""
        with patch("agent_pump.services.branch_manager.Repo"):
            config = BranchStrategyConfig(
                branch_prefix="feat",
                base_branch="develop",
            )
            manager = BranchManager(tmp_path, config=config)

            assert manager.config.branch_prefix == "feat"
            assert manager.config.base_branch == "develop"


class TestBranchManagerOperations:
    """Tests for branch manager git operations."""

    def test_get_current_branch(self, tmp_path):
        """Test getting current branch name."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.get_current_branch()

            assert result == "main"

    def test_is_worktree_clean_true(self, tmp_path):
        """Test checking clean worktree."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = False
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.is_worktree_clean()

            assert result is True
            mock_instance.is_dirty.assert_called_once_with(untracked_files=True)

    def test_is_worktree_clean_false_dirty(self, tmp_path):
        """Test checking dirty worktree."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = True
            mock_instance.untracked_files = []
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.is_worktree_clean()

            assert result is False

    def test_is_worktree_clean_false_untracked(self, tmp_path):
        """Test checking worktree with untracked files."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.is_dirty.return_value = False
            mock_instance.untracked_files = ["new_file.py"]
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.is_worktree_clean()

            assert result is False

    def test_create_feature_branch_success(self, tmp_path):
        """Test successful feature branch creation."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.create_feature_branch("Add Login Page")

            assert result == "feature/add-login-page"
            mock_instance.git.checkout.assert_any_call("main")
            mock_instance.git.checkout.assert_any_call("-b", "feature/add-login-page")

    def test_create_feature_branch_custom_prefix(self, tmp_path):
        """Test branch creation with custom prefix."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "develop"
            mock_repo.return_value = mock_instance

            config = BranchStrategyConfig(branch_prefix="feat", base_branch="develop")
            manager = BranchManager(tmp_path, config=config)
            result = manager.create_feature_branch("Update API")

            assert result == "feat/update-api"
            mock_instance.git.checkout.assert_any_call("develop")

    def test_create_feature_branch_already_exists(self, tmp_path):
        """Test branch creation when branch already exists - adds numeric suffix."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            # Simulate that feature/test-branch already exists
            mock_branch = MagicMock()
            mock_branch.name = "feature/test-branch"
            mock_instance.branches = [mock_branch]
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.create_feature_branch("Test Branch")

            # Should return branch name with numeric suffix
            assert result == "feature/test-branch-2"
            mock_instance.git.checkout.assert_any_call("-b", "feature/test-branch-2")

    def test_switch_to_branch_success(self, tmp_path):
        """Test successful branch switch."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.switch_to_branch("feature/test")

            assert result is True
            mock_instance.git.checkout.assert_called_once_with("feature/test")

    def test_switch_to_branch_failure(self, tmp_path):
        """Test failed branch switch."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.git.checkout.side_effect = GitCommandError(
                "checkout",
                "feature/nonexistent",
                "error: pathspec 'feature/nonexistent' did not match",
            )
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.switch_to_branch("feature/nonexistent")

            assert result is False

    def test_delete_branch_success(self, tmp_path):
        """Test successful branch deletion."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.delete_branch("feature/old-branch")

            assert result is True
            mock_instance.git.branch.assert_called_once_with("-d", "feature/old-branch")

    def test_delete_branch_force(self, tmp_path):
        """Test forced branch deletion."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "main"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.delete_branch("feature/old-branch", force=True)

            assert result is True
            mock_instance.git.branch.assert_called_once_with("-D", "feature/old-branch")

    def test_delete_branch_current_branch(self, tmp_path):
        """Test deleting current branch (should fail)."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "feature/current"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.delete_branch("feature/current")

            assert result is False
            mock_instance.git.branch.assert_not_called()


class TestMergeOperations:
    """Tests for merge operations."""

    def test_merge_to_base_success(self, tmp_path):
        """Test successful merge to base branch."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "feature/test"
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.merge_to_base("feature/test", "Merge feature: Test feature")

            assert isinstance(result, MergeResult)
            assert result.success is True
            assert result.has_conflicts is False
            assert result.error is None
            mock_instance.git.checkout.assert_called_with("main")
            mock_instance.git.merge.assert_called_once_with(
                "feature/test", "-m", "Merge feature: Test feature"
            )

    def test_merge_to_base_with_conflicts(self, tmp_path):
        """Test merge with conflicts."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "feature/test"
            mock_instance.git.merge.side_effect = GitCommandError(
                "merge",
                "feature/test",
                "Auto-merging file.txt\nCONFLICT (content): Merge conflict in file.txt",
            )
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.merge_to_base("feature/test", "Merge feature: Test")

            assert isinstance(result, MergeResult)
            assert result.success is False
            assert result.has_conflicts is True
            assert result.error is not None
            assert "CONFLICT" in result.error

    def test_merge_to_base_other_error(self, tmp_path):
        """Test merge with non-conflict error."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.active_branch.name = "feature/test"
            mock_instance.git.merge.side_effect = GitCommandError(
                "merge", "feature/test", "fatal: refusing to merge unrelated histories"
            )
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.merge_to_base("feature/test", "Merge feature: Test")

            assert isinstance(result, MergeResult)
            assert result.success is False
            assert result.has_conflicts is False
            assert result.error is not None
            assert "unrelated histories" in result.error

    def test_has_merge_conflicts_true(self, tmp_path):
        """Test detecting merge conflicts."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.index.unmerged_blobs.return_value = {
                "conflicted_file.txt": [
                    (0, None, None, None),  # Stage 0: base
                    (1, None, None, None),  # Stage 1: ours
                    (2, None, None, None),  # Stage 2: theirs
                ]
            }
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.has_merge_conflicts()

            assert result is True

    def test_has_merge_conflicts_false(self, tmp_path):
        """Test detecting no merge conflicts."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_instance.index.unmerged_blobs.return_value = {}
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            result = manager.has_merge_conflicts()

            assert result is False

    def test_abort_merge(self, tmp_path):
        """Test aborting a merge."""
        with patch("agent_pump.services.branch_manager.Repo") as mock_repo:
            mock_instance = MagicMock()
            mock_repo.return_value = mock_instance

            manager = BranchManager(tmp_path)
            manager.abort_merge()

            mock_instance.git.merge.assert_called_once_with("--abort")


class TestBranchState:
    """Tests for BranchState model."""

    def test_create_state(self):
        """Test creating branch state."""
        state = BranchState(
            feature_branch="feature/test",
            base_branch="main",
        )

        assert state.feature_branch == "feature/test"
        assert state.base_branch == "main"
        assert state.created_at is not None
        assert state.merged_at is None
        assert state.has_conflicts is False

    def test_mark_merged(self):
        """Test marking branch as merged."""
        state = BranchState(
            feature_branch="feature/test",
            base_branch="main",
        )

        state.mark_merged()

        assert state.merged_at is not None
        assert isinstance(state.merged_at, datetime)

    def test_mark_conflicts(self):
        """Test marking branch as having conflicts."""
        state = BranchState(
            feature_branch="feature/test",
            base_branch="main",
        )

        state.mark_conflicts()

        assert state.has_conflicts is True

    def test_serialization(self):
        """Test branch state serialization."""
        state = BranchState(
            feature_branch="feature/test",
            base_branch="main",
        )

        data = state.model_dump()

        assert data["feature_branch"] == "feature/test"
        assert data["base_branch"] == "main"
        assert "created_at" in data


class TestMergeResult:
    """Tests for MergeResult model."""

    def test_success_result(self):
        """Test successful merge result."""
        result = MergeResult(success=True)

        assert result.success is True
        assert result.has_conflicts is False
        assert result.error is None

    def test_conflict_result(self):
        """Test conflict merge result."""
        result = MergeResult(success=False, has_conflicts=True, error="CONFLICT in file.txt")

        assert result.success is False
        assert result.has_conflicts is True
        assert result.error == "CONFLICT in file.txt"

    def test_error_result(self):
        """Test error merge result (not conflict)."""
        result = MergeResult(success=False, has_conflicts=False, error="Some other error")

        assert result.success is False
        assert result.has_conflicts is False
        assert result.error == "Some other error"
