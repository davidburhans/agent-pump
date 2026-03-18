"""Tests for verification config modal."""

from agent_pump.models.verification_config import VerificationConfig
from agent_pump.tui.screens.verification_config_modal import VerificationConfigModal


class TestVerificationConfigModal:
    """Tests for VerificationConfigModal."""

    def test_modal_creation_with_none_config(self):
        """Test creating modal with None config."""
        modal = VerificationConfigModal(config=None)
        assert modal is not None
        assert modal.original_config == VerificationConfig()

    def test_modal_creation_with_config(self):
        """Test creating modal with a config."""
        config = VerificationConfig(
            build_cmd="npm run build",
            lint_cmd="npm run lint",
            test_cmd="npm test",
            skip_verification=True,
        )
        modal = VerificationConfigModal(config=config)
        assert modal is not None
        assert modal.original_config == config
        assert modal.config.build_cmd == "npm run build"
        assert modal.config.lint_cmd == "npm run lint"
        assert modal.config.test_cmd == "npm test"
        assert modal.config.skip_verification is True

    def test_modal_independent_config(self):
        """Test that modal creates independent copy of config."""
        original_config = VerificationConfig(build_cmd="original build", lint_cmd="original lint")

        modal = VerificationConfigModal(config=original_config)

        # Modify the modal's config
        modal.config.build_cmd = "modified build"
        modal.config.lint_cmd = "modified lint"

        # Original config should remain unchanged
        assert original_config.build_cmd == "original build"
        assert original_config.lint_cmd == "original lint"

        # Modal's config should be modified
        assert modal.config.build_cmd == "modified build"
        assert modal.config.lint_cmd == "modified lint"

    def test_bindings_exist(self):
        """Test that modal has expected bindings."""
        modal = VerificationConfigModal()
        # Check that the bindings are properly set up
        assert len(modal.BINDINGS) >= 2  # At least escape and ctrl+s bindings
