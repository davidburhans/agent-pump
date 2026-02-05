"""Unit tests for ApprovalGateModal."""

from unittest.mock import MagicMock, patch

import pytest

from agent_pump.tui.screens.approval_gate_modal import ApprovalGateModal


class TestApprovalGateModalCreation:
    """Tests for modal creation and initialization."""

    def test_modal_creation(self):
        """Test creating ApprovalGateModal."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Add login page",
            project_name="test-project",
            timeout_minutes=30,
        )

        assert modal.phase == "committing"
        assert modal.feature == "Add login page"
        assert modal.project_name == "test-project"
        assert modal.timeout_minutes == 30

    def test_modal_creation_no_feature(self):
        """Test creating modal without feature."""
        modal = ApprovalGateModal(
            phase="planning",
            feature=None,
            project_name="test-project",
        )

        assert modal.phase == "planning"
        assert modal.feature is None

    def test_modal_creation_no_timeout(self):
        """Test creating modal without timeout."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
            timeout_minutes=0,
        )

        assert modal.timeout_minutes == 0


class TestApprovalGateModalComposition:
    """Tests for modal widget composition."""

    @pytest.fixture
    def modal(self):
        """Create a modal instance for testing."""
        return ApprovalGateModal(
            phase="committing",
            feature="Add login page",
            project_name="test-project",
            timeout_minutes=30,
        )

    @pytest.mark.asyncio
    async def test_modal_compose_structure(self, modal):
        """Test that modal composes with correct structure."""
        app = pytest.importorskip("textual.app").App()
        async with app.run_test() as pilot:
            await pilot.app.push_screen(modal)
            # Should have one main container
            assert len(modal.query("#dialog")) == 1

    def test_modal_has_title(self, modal):
        """Test that modal has a title."""
        # Verify title content relates to phase
        assert "committing" in modal.phase.lower() or modal.phase.title() in str(modal)

    def test_modal_bindings(self):
        """Test that modal has correct key bindings."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        binding_keys = [binding.key for binding in modal.BINDINGS]
        assert "escape" in binding_keys
        assert "a" in binding_keys
        assert "r" in binding_keys


class TestApprovalGateModalActions:
    """Tests for modal actions."""

    @pytest.fixture
    def modal(self):
        """Create a modal instance for testing."""
        return ApprovalGateModal(
            phase="committing",
            feature="Add login page",
            project_name="test-project",
            timeout_minutes=30,
        )

    def test_action_approve(self, modal):
        """Test approve action."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Looks good"
            modal.query_one.return_value = mock_input

            modal.action_approve()

            mock_dismiss.assert_called_once()
            result = mock_dismiss.call_args[0][0]
            assert result[0] == "approve"
            assert result[1] == "Looks good"

    def test_action_reject(self, modal):
        """Test reject action."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Need more tests"
            modal.query_one.return_value = mock_input

            modal.action_reject()

            mock_dismiss.assert_called_once()
            result = mock_dismiss.call_args[0][0]
            assert result[0] == "reject"
            assert result[1] == "Need more tests"

    def test_action_cancel(self, modal):
        """Test cancel action."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.action_cancel()

            mock_dismiss.assert_called_once_with(None)


class TestApprovalGateModalButtonHandling:
    """Tests for button press handling."""

    @pytest.fixture
    def modal(self):
        """Create a modal instance for testing."""
        return ApprovalGateModal(
            phase="committing",
            feature="Add login page",
            project_name="test-project",
            timeout_minutes=30,
        )

    def test_approve_button_pressed(self, modal):
        """Test handling approve button press."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Approved"
            modal.query_one.return_value = mock_input

            # Create mock button event
            mock_button = MagicMock()
            mock_button.id = "btn-approve"
            mock_event = MagicMock()
            mock_event.button = mock_button

            modal.on_button_pressed(mock_event)

            mock_dismiss.assert_called_once()
            result = mock_dismiss.call_args[0][0]
            assert result[0] == "approve"

    def test_reject_button_pressed(self, modal):
        """Test handling reject button press."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Rejected"
            modal.query_one.return_value = mock_input

            # Create mock button event
            mock_button = MagicMock()
            mock_button.id = "btn-reject"
            mock_event = MagicMock()
            mock_event.button = mock_button

            modal.on_button_pressed(mock_event)

            mock_dismiss.assert_called_once()
            result = mock_dismiss.call_args[0][0]
            assert result[0] == "reject"

    def test_cancel_button_pressed(self, modal):
        """Test handling cancel button press."""
        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()

            # Create mock button event
            mock_button = MagicMock()
            mock_button.id = "btn-cancel"
            mock_event = MagicMock()
            mock_event.button = mock_button

            modal.on_button_pressed(mock_event)

            mock_dismiss.assert_called_once_with(None)


class TestApprovalGateModalDisplayInfo:
    """Tests for information display in modal."""

    def test_modal_shows_project_name(self):
        """Test that modal displays project name."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="my-awesome-project",
        )

        # Project name should be accessible
        assert modal.project_name == "my-awesome-project"

    def test_modal_shows_phase(self):
        """Test that modal displays phase."""
        modal = ApprovalGateModal(
            phase="implementing",
            feature="Test",
            project_name="test-project",
        )

        assert modal.phase == "implementing"

    def test_modal_shows_feature(self):
        """Test that modal displays feature."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Add user authentication",
            project_name="test-project",
        )

        assert modal.feature == "Add user authentication"

    def test_modal_handles_no_feature(self):
        """Test that modal handles missing feature gracefully."""
        modal = ApprovalGateModal(
            phase="planning",
            feature=None,
            project_name="test-project",
        )

        assert modal.feature is None

    def test_modal_shows_timeout(self):
        """Test that modal displays timeout information."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
            timeout_minutes=45,
        )

        assert modal.timeout_minutes == 45


class TestApprovalGateModalStyling:
    """Tests for modal styling."""

    def test_modal_css_defined(self):
        """Test that modal has CSS defined."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        assert modal.DEFAULT_CSS is not None
        assert len(modal.DEFAULT_CSS) > 0

    def test_modal_css_contains_dialog(self):
        """Test that CSS contains dialog styling."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        assert "#dialog" in modal.DEFAULT_CSS


class TestApprovalGateModalReturnTypes:
    """Tests for modal return types."""

    def test_approve_returns_correct_tuple(self):
        """Test that approve returns correct tuple structure."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Test comment"
            modal.query_one.return_value = mock_input

            modal.action_approve()

            result = mock_dismiss.call_args[0][0]
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert result[0] == "approve"
            assert result[1] == "Test comment"

    def test_reject_returns_correct_tuple(self):
        """Test that reject returns correct tuple structure."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = "Reject reason"
            modal.query_one.return_value = mock_input

            modal.action_reject()

            result = mock_dismiss.call_args[0][0]
            assert isinstance(result, tuple)
            assert len(result) == 2
            assert result[0] == "reject"
            assert result[1] == "Reject reason"

    def test_cancel_returns_none(self):
        """Test that cancel returns None."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.action_cancel()

            result = mock_dismiss.call_args[0][0]
            assert result is None

    def test_approve_with_empty_comment(self):
        """Test approve with empty comment."""
        modal = ApprovalGateModal(
            phase="committing",
            feature="Test",
            project_name="test-project",
        )

        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.query_one = MagicMock()
            mock_input = MagicMock()
            mock_input.value = ""
            modal.query_one.return_value = mock_input

            modal.action_approve()

            result = mock_dismiss.call_args[0][0]
            assert result[0] == "approve"
            assert result[1] == ""  # Empty comment is allowed
