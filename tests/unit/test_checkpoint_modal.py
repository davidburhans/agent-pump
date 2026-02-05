"""Tests for checkpoint modal TUI screen."""


from agent_pump.models.checkpoint import Checkpoint
from agent_pump.tui.screens.checkpoint_modal import CheckpointModal


class TestCheckpointModalBasic:
    """Basic tests for CheckpointModal that don't require App context."""

    def test_modal_creation_empty(self):
        """Test that the modal can be created with no checkpoints."""
        modal = CheckpointModal(checkpoints=[])
        assert modal is not None
        assert modal.checkpoints == []

    def test_modal_creation_with_checkpoints(self):
        """Test that the modal can be created with checkpoints."""
        checkpoints = [
            Checkpoint(
                id="chk1",
                phase="planning",
                git_commit_hash="abc123",
                description="Before planning",
            ),
            Checkpoint(
                id="chk2",
                phase="implementing",
                git_commit_hash="def456",
                description="During implementation",
            ),
        ]
        modal = CheckpointModal(checkpoints=checkpoints, current_feature="Test Feature")
        assert modal is not None
        assert len(modal.checkpoints) == 2
        assert modal.current_feature == "Test Feature"

    def test_checkpoint_ordering(self):
        """Test that checkpoints are stored correctly."""
        checkpoints = [
            Checkpoint(
                id="chk1",
                phase="planning",
                git_commit_hash="abc123",
                description="First",
            ),
            Checkpoint(
                id="chk2",
                phase="implementing",
                git_commit_hash="def456",
                description="Second",
            ),
        ]
        modal = CheckpointModal(checkpoints=checkpoints)
        assert modal.checkpoints == checkpoints

    def test_get_selected_checkpoint(self):
        """Test getting the selected checkpoint."""
        checkpoints = [
            Checkpoint(
                id="chk1",
                phase="planning",
                git_commit_hash="abc123",
                description="Test",
            ),
        ]
        modal = CheckpointModal(checkpoints=checkpoints)

        # Initially no selection
        assert modal.get_selected_checkpoint() is None

        # Set selection manually
        modal._selected_checkpoint = checkpoints[0]
        assert modal.get_selected_checkpoint() == checkpoints[0]


class TestCheckpointModalDataHandling:
    """Tests for checkpoint data handling."""

    def test_checkpoint_with_all_fields(self):
        """Test modal with fully populated checkpoint."""
        checkpoints = [
            Checkpoint(
                id="full1",
                phase="verifying",
                feature="Add login page",
                git_commit_hash="abcdef1234567890abcdef1234567890abcdef12",
                description="Verification checkpoint",
                auto_created=False,
                files_modified=["src/auth.py", "tests/test_auth.py", "README.md"],
            ),
        ]
        modal = CheckpointModal(checkpoints=checkpoints, current_feature="Add login page")

        assert len(modal.checkpoints) == 1
        cp = modal.checkpoints[0]
        assert cp.id == "full1"
        assert cp.phase == "verifying"
        assert cp.feature == "Add login page"
        assert len(cp.files_modified) == 3

    def test_multiple_checkpoints(self):
        """Test modal with multiple checkpoints."""
        checkpoints = [
            Checkpoint(
                id=f"chk{i}",
                phase="planning" if i % 2 == 0 else "implementing",
                git_commit_hash=f"hash{i}",
                description=f"Checkpoint {i}",
                auto_created=i % 2 == 0,
            )
            for i in range(5)
        ]
        modal = CheckpointModal(checkpoints=checkpoints)

        assert len(modal.checkpoints) == 5

    def test_auto_vs_manual_checkpoints(self):
        """Test that auto and manual checkpoints are handled correctly."""
        checkpoints = [
            Checkpoint(
                id="auto1",
                phase="planning",
                git_commit_hash="abc123",
                description="Auto checkpoint",
                auto_created=True,
            ),
            Checkpoint(
                id="manual1",
                phase="manual",
                git_commit_hash="def456",
                description="Manual checkpoint",
                auto_created=False,
            ),
        ]
        modal = CheckpointModal(checkpoints=checkpoints)

        auto_cp = modal.checkpoints[0]
        manual_cp = modal.checkpoints[1]

        assert auto_cp.auto_created is True
        assert manual_cp.auto_created is False


class TestCheckpointModalBindings:
    """Tests for key bindings in CheckpointModal."""

    def test_bindings_exist(self):
        """Test that the modal has the expected bindings."""
        modal = CheckpointModal(checkpoints=[])

        # Check that bindings are defined
        assert hasattr(modal, "BINDINGS")
        assert len(modal.BINDINGS) >= 2

        # Check for escape binding
        binding_keys = [b.key for b in modal.BINDINGS]  # type: ignore
        assert "escape" in binding_keys

        # Check for 'r' binding (rollback)
        assert "r" in binding_keys

    def test_binding_actions_exist(self):
        """Test that binding actions have corresponding methods."""
        modal = CheckpointModal(checkpoints=[])

        # Check that action methods exist
        assert hasattr(modal, "action_cancel")
        assert hasattr(modal, "action_rollback_selected")


class TestCheckpointModalStrings:
    """Tests for string representations and formatting."""

    def test_checkpoint_string_auto(self):
        """Test string representation for auto checkpoint."""
        checkpoint = Checkpoint(
            id="chk1",
            phase="planning",
            git_commit_hash="abcdef123456",
            description="Before planning",
            auto_created=True,
        )

        result = str(checkpoint)
        assert "[auto]" in result
        assert "chk1" in result
        assert "Before planning" in result
        assert "abcdef1" in result  # Short hash

    def test_checkpoint_string_manual(self):
        """Test string representation for manual checkpoint."""
        checkpoint = Checkpoint(
            id="chk2",
            phase="manual",
            git_commit_hash="xyz789abc123",
            description="Manual save",
            auto_created=False,
        )

        result = str(checkpoint)
        assert "[manual]" in result
        assert "chk2" in result
        assert "Manual save" in result

    def test_formatted_time(self):
        """Test formatted timestamp."""
        from datetime import datetime

        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        checkpoint = Checkpoint(
            id="chk1",
            phase="planning",
            git_commit_hash="abc123",
            description="Test",
            timestamp=timestamp,
        )

        formatted = checkpoint.get_formatted_time()
        assert formatted == "2024-01-15 14:30:00"

    def test_short_hash(self):
        """Test short hash extraction."""
        checkpoint = Checkpoint(
            id="chk1",
            phase="planning",
            git_commit_hash="abcdef1234567890abcdef1234567890abcdef12",
            description="Test",
        )

        short = checkpoint.get_short_hash()
        assert short == "abcdef1"
        assert len(short) == 7


class TestCheckpointModalDismissal:
    """Tests for modal dismissal behavior."""

    def test_cancel_action_returns_none(self):
        """Test that cancel action dismisses with None."""
        modal = CheckpointModal(checkpoints=[])

        # Mock dismiss method
        dismissed_result = []

        def mock_dismiss(result=None):
            dismissed_result.append(result)

        modal.dismiss = mock_dismiss  # type: ignore

        # Call cancel action
        modal.action_cancel()

        assert len(dismissed_result) == 1
        assert dismissed_result[0] is None

    def test_rollback_without_selection(self):
        """Test rollback action when no checkpoint selected."""
        modal = CheckpointModal(
            checkpoints=[
                Checkpoint(
                    id="chk1",
                    phase="planning",
                    git_commit_hash="abc123",
                    description="Test",
                ),
            ]
        )

        # No selection made
        assert modal._selected_checkpoint is None

        # Mock dismiss to capture result
        dismissed_result = []

        def mock_dismiss(result=None):
            dismissed_result.append(result)

        modal.dismiss = mock_dismiss  # type: ignore

        # Call rollback action
        modal.action_rollback_selected()

        # Should not dismiss when nothing selected
        assert len(dismissed_result) == 0

    def test_rollback_with_selection(self):
        """Test rollback action when checkpoint is selected."""
        checkpoint = Checkpoint(
            id="chk1",
            phase="planning",
            git_commit_hash="abc123",
            description="Test",
        )
        modal = CheckpointModal(checkpoints=[checkpoint])

        # Set selection
        modal._selected_checkpoint = checkpoint

        # Mock dismiss to capture result
        dismissed_result = []

        def mock_dismiss(result=None):
            dismissed_result.append(result)

        modal.dismiss = mock_dismiss  # type: ignore

        # Call rollback action
        modal.action_rollback_selected()

        # Should dismiss with rollback action and checkpoint ID
        assert len(dismissed_result) == 1
        assert dismissed_result[0] == ("rollback", "chk1")
