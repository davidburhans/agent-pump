"""Tests for the bootstrap modal TUI screen."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_pump.tui.screens.bootstrap_modal import BootstrapModal


class TestBootstrapModalBasic:
    """Basic tests for BootstrapModal that don't require App context."""

    def test_modal_creation(self):
        """Test that the modal can be created."""
        modal = BootstrapModal()
        assert modal is not None
        assert modal._selected_path is None

    def test_modal_creation_with_initial_path(self):
        """Test modal creation with initial path."""
        initial_path = Path("/path/to/project")
        modal = BootstrapModal(initial_path=initial_path)
        assert modal._selected_path == initial_path

    def test_modal_css_defined(self):
        """Test that the modal has CSS defined."""
        modal = BootstrapModal()
        assert modal.DEFAULT_CSS is not None
        assert len(modal.DEFAULT_CSS) > 0


class TestBootstrapModalPathValidation:
    """Tests for path validation in bootstrap modal."""

    def test_validate_existing_directory(self, tmp_path):
        """Test validation passes for existing directory."""
        modal = BootstrapModal()
        modal._selected_path = tmp_path

        # Mock the input and UI elements
        with patch.object(modal, "query_one") as mock_query:
            mock_input = MagicMock()
            mock_input.value = str(tmp_path)
            mock_query.return_value = mock_input

            with patch.object(modal, "_clear_error"):
                result = modal._validate_and_bootstrap(preview_only=True)
                assert result is True

    def test_validate_nonexistent_path(self, tmp_path):
        """Test validation fails for nonexistent path."""
        modal = BootstrapModal()
        nonexistent = tmp_path / "nonexistent"

        with patch.object(modal, "query_one") as mock_query:
            mock_input = MagicMock()
            mock_input.value = str(nonexistent)
            mock_query.return_value = mock_input

            with patch.object(modal, "_show_error") as mock_error:
                result = modal._validate_and_bootstrap(preview_only=False)
                assert result is False
                mock_error.assert_called_once()

    def test_validate_empty_path(self):
        """Test validation fails for empty path."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_input = MagicMock()
            mock_input.value = ""
            mock_query.return_value = mock_input

            with patch.object(modal, "_show_error") as mock_error:
                result = modal._validate_and_bootstrap()
                assert result is False
                mock_error.assert_called_once()


class TestBootstrapModalAnalysis:
    """Tests for project analysis functionality."""

    def test_analyze_python_project(self, tmp_path):
        """Test analysis of Python project."""
        # Create a Python project structure
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        (tmp_path / "README.md").write_text("# Test Project")

        modal = BootstrapModal()
        modal._selected_path = tmp_path

        # Mock the preview widget
        with patch.object(modal, "query_one") as mock_query:
            mock_preview = MagicMock()
            mock_error = MagicMock()

            # query_one is called for preview-content and error-label
            def query_side_effect(selector, type=None):
                if selector == "#preview-content":
                    return mock_preview
                if selector == "#error-label":
                    return mock_error
                return MagicMock()

            mock_query.side_effect = query_side_effect

            modal._analyze_project()

            # Verify preview was updated with project info
            mock_preview.update.assert_called_once()
            update_text = mock_preview.update.call_args[0][0]
            assert "python" in update_text.lower()
            assert "pyproject.toml" in update_text

    def test_analyze_node_project(self, tmp_path):
        """Test analysis of Node.js project."""
        # Create a Node.js project structure
        (tmp_path / "package.json").write_text('{"name": "test", "dependencies": {}}')

        modal = BootstrapModal()
        modal._selected_path = tmp_path

        with patch.object(modal, "query_one") as mock_query:
            mock_preview = MagicMock()
            mock_error = MagicMock()

            def query_side_effect(selector, type=None):
                if selector == "#preview-content":
                    return mock_preview
                if selector == "#error-label":
                    return mock_error
                return MagicMock()

            mock_query.side_effect = query_side_effect

            modal._analyze_project()

            update_text = mock_preview.update.call_args[0][0]
            assert "nodejs" in update_text.lower() or "javascript" in update_text.lower()


class TestBootstrapModalFormatAnalysis:
    """Tests for analysis formatting."""

    def test_format_analysis_with_framework(self):
        """Test formatting analysis with framework."""
        modal = BootstrapModal()

        # Create mock analysis
        mock_analysis = MagicMock()
        mock_analysis.project_type = "python"
        mock_analysis.language = "python"
        mock_analysis.framework = "uv"
        mock_analysis.key_files = ["pyproject.toml", "README.md"]
        mock_analysis.has_tests = True
        mock_analysis.has_docs = True
        mock_analysis.has_ci = False

        result = modal._format_analysis(mock_analysis)

        assert "Type: python" in result
        assert "Framework: uv" in result
        assert "Has tests: Yes" in result
        assert "Has docs: Yes" in result
        assert "Has CI/CD: No" in result

    def test_format_analysis_without_framework(self):
        """Test formatting analysis without framework."""
        modal = BootstrapModal()

        mock_analysis = MagicMock()
        mock_analysis.project_type = "unknown"
        mock_analysis.language = "unknown"
        mock_analysis.framework = None
        mock_analysis.key_files = []
        mock_analysis.has_tests = False
        mock_analysis.has_docs = False
        mock_analysis.has_ci = False

        result = modal._format_analysis(mock_analysis)

        assert "Type: unknown" in result
        assert "Framework:" not in result
        assert "Has tests: No" in result

    def test_format_analysis_key_files_limit(self):
        """Test that only first 5 key files are shown."""
        modal = BootstrapModal()

        mock_analysis = MagicMock()
        mock_analysis.project_type = "python"
        mock_analysis.language = "python"
        mock_analysis.framework = None
        mock_analysis.key_files = [f"file{i}.py" for i in range(10)]
        mock_analysis.has_tests = False
        mock_analysis.has_docs = False
        mock_analysis.has_ci = False

        result = modal._format_analysis(mock_analysis)

        # Should show first 5 files plus "and 5 more" message
        assert "file0.py" in result
        assert "file4.py" in result
        assert "and 5 more" in result
        assert "file5.py" not in result  # Should not show 6th file


class TestBootstrapModalBackendAndDryRun:
    """Tests for backend selection and dry-run mode."""

    def test_get_backend_default(self):
        """Test getting default backend."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_select = MagicMock()
            mock_select.value = "gemini"
            mock_query.return_value = mock_select

            result = modal._get_backend()
            assert result == "gemini"

    def test_get_backend_custom(self):
        """Test getting custom backend selection."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_select = MagicMock()
            mock_select.value = "claude"
            mock_query.return_value = mock_select

            result = modal._get_backend()
            assert result == "claude"

    def test_is_dry_run_enabled(self):
        """Test checking if dry-run is enabled."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_checkbox = MagicMock()
            mock_checkbox.value = True
            mock_query.return_value = mock_checkbox

            result = modal._is_dry_run()
            assert result is True

    def test_is_dry_run_disabled(self):
        """Test checking if dry-run is disabled."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_checkbox = MagicMock()
            mock_checkbox.value = False
            mock_query.return_value = mock_checkbox

            result = modal._is_dry_run()
            assert result is False


class TestBootstrapModalErrorHandling:
    """Tests for error handling."""

    def test_show_error(self):
        """Test showing error message."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_label = MagicMock()
            mock_input = MagicMock()
            mock_query.side_effect = [mock_label, mock_input]

            with patch("agent_pump.tui.screens.bootstrap_modal.shake") as mock_shake:
                modal._show_error("Test error message")
                mock_shake.assert_called_once()

            mock_label.update.assert_called_once_with("Test error message")
            mock_label.add_class.assert_called_once_with("visible")

    def test_clear_error(self):
        """Test clearing error message."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_label = MagicMock()
            mock_query.return_value = mock_label

            modal._clear_error()

            mock_label.update.assert_called_once_with("")
            mock_label.remove_class.assert_called_once_with("visible")

    def test_show_status(self):
        """Test showing status message."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_label = MagicMock()
            mock_query.return_value = mock_label

            modal._show_status("Working...")

            mock_label.update.assert_called_once_with("Working...")

    def test_clear_status(self):
        """Test clearing status message."""
        modal = BootstrapModal()

        with patch.object(modal, "query_one") as mock_query:
            mock_label = MagicMock()
            mock_query.return_value = mock_label

            modal._clear_status()

            mock_label.update.assert_called_once_with("")


class TestBootstrapModalDismissal:
    """Tests for modal dismissal."""

    def test_dismiss_cancel(self):
        """Test that cancel dismisses with None."""
        modal = BootstrapModal()

        with patch.object(modal, "dismiss") as mock_dismiss:
            modal.action_cancel()
            mock_dismiss.assert_called_once_with(None)

    def test_dismiss_with_result(self):
        """Test dismissal with valid result."""
        modal = BootstrapModal()
        test_path = Path("/test/project")

        with patch.object(modal, "query_one") as mock_query:
            mock_input = MagicMock()
            mock_input.value = str(test_path)
            mock_error = MagicMock()  # For _clear_error
            mock_select = MagicMock()
            mock_select.value = "gemini"
            mock_checkbox = MagicMock()
            mock_checkbox.value = False

            # Sequence: path-input -> error-label -> backend-select -> dry-run-checkbox
            mock_query.side_effect = [mock_input, mock_error, mock_select, mock_checkbox]

            with patch.object(modal, "dismiss") as mock_dismiss:
                with patch.object(Path, "exists", return_value=True):
                    with patch.object(Path, "is_dir", return_value=True):
                        modal._validate_and_bootstrap(preview_only=False)

                        mock_dismiss.assert_called_once()
                        result = mock_dismiss.call_args[0][0]
                        assert result[0] == test_path.resolve()
                        assert result[1] == "gemini"
                        assert result[2] is False
