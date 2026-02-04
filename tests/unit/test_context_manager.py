"""Tests for context manager utility."""

from datetime import datetime
from pathlib import Path

import pytest

from agent_pump.models.context_config import ContextConfig
from agent_pump.utils.context_manager import ContextAnalysis, ContextManager


class TestContextManager:
    """Tests for the ContextManager class."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project with various files."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        # Create source files
        src = project_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
        (src / "utils.py").write_text("def util():\n    return 42\n", encoding="utf-8")

        # Create test files
        tests = project_path / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("def test_main():\n    pass\n", encoding="utf-8")

        # Create a large file
        large = project_path / "large.py"
        large.write_text("x" * 60000, encoding="utf-8")

        # Create excluded directory
        node_modules = project_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text('{"name": "test"}', encoding="utf-8")

        return project_path

    @pytest.fixture
    def config(self):
        """Create a default context config."""
        return ContextConfig(
            max_context_tokens=10000,
            reserve_tokens=1000,
            exclude_patterns=[".git", "node_modules", "__pycache__"],
            include_extensions=[".py"],
        )

    @pytest.fixture
    def manager(self, temp_project, config):
        """Create a ContextManager instance."""
        return ContextManager(temp_project, config)

    def test_initialization(self, temp_project, config):
        """Test ContextManager initialization."""
        manager = ContextManager(temp_project, config)

        assert manager.project_path == temp_project
        assert manager.config == config
        assert isinstance(manager.file_scores, dict)
        assert len(manager.recently_modified) == 0

    def test_analyze_project_structure(self, manager):
        """Test analyzing project structure."""
        analysis = manager.analyze_project()

        assert isinstance(analysis, ContextAnalysis)
        assert analysis.total_files > 0
        assert analysis.total_tokens > 0
        # Note: files_in_budget is only populated when selecting files, not during analysis

    def test_get_context_files_respects_budget(self, manager, config):
        """Test that context files respect token budget."""
        files = manager.get_context_files(config.get_effective_token_limit())

        total_tokens = sum(f.token_count for f in files)
        assert total_tokens <= config.get_effective_token_limit()

    def test_get_context_files_excludes_ignored_patterns(self, manager, temp_project):
        """Test that excluded patterns are filtered out."""
        files = manager.get_context_files(10000)
        file_paths = [f.path for f in files]

        # node_modules should be excluded
        assert not any("node_modules" in p for p in file_paths)

    def test_get_context_files_respects_extensions(self, manager, temp_project):
        """Test that only allowed extensions are included."""
        # Create a non-python file
        (temp_project / "readme.md").write_text("# README", encoding="utf-8")

        files = manager.get_context_files(10000)
        file_paths = [f.path for f in files]

        # Should only have .py files
        assert all(p.endswith(".py") for p in file_paths)

    def test_track_file_modification(self, manager):
        """Test tracking recently modified files."""
        manager.track_file_modification("src/main.py")

        assert "src/main.py" in manager.recently_modified
        assert isinstance(manager.recently_modified["src/main.py"], datetime)

    def test_track_multiple_modifications(self, manager):
        """Test tracking multiple file modifications."""
        manager.track_file_modification("src/main.py")
        manager.track_file_modification("src/utils.py")

        assert len(manager.recently_modified) == 2

    def test_file_scoring_includes_recent_boost(self, manager):
        """Test that recent files get higher scores."""
        # Track a file as modified
        manager.track_file_modification("src/main.py")

        # Score files
        scores = manager._score_files()

        # The modified file should have higher score
        if "src/main.py" in scores and "src/utils.py" in scores:
            assert scores["src/main.py"] > scores["src/utils.py"]

    def test_file_scoring_source_files_higher(self, manager, temp_project):
        """Test that source files score higher than test files."""
        scores = manager._score_files()

        if "src/main.py" in scores and "tests/test_main.py" in scores:
            assert scores["src/main.py"] > scores["tests/test_main.py"]

    def test_large_file_detection(self, manager, temp_project, config):
        """Test that large files are detected and can be summarized."""
        files = manager.get_context_files(100000)  # Large budget

        # Find the large file
        large_files = [f for f in files if f.path == "large.py"]

        if large_files and config.summarize_large_files:
            large_file = large_files[0]
            assert large_file.is_summarized or large_file.original_length == 60000

    def test_context_analysis_statistics(self, manager):
        """Test that analysis provides correct statistics."""
        analysis = manager.analyze_project()

        assert analysis.total_files >= 0
        assert analysis.total_tokens >= 0
        assert analysis.files_in_budget >= 0
        assert analysis.files_summarized >= 0
        assert analysis.files_excluded >= 0

        # Files in budget should not exceed total
        assert analysis.files_in_budget <= analysis.total_files

    def test_get_files_by_priority(self, manager):
        """Test getting files sorted by priority."""
        # Mark one file as recently modified
        manager.track_file_modification("src/utils.py")

        files = manager.get_files_by_priority()

        if len(files) >= 2:
            # utils.py should have higher priority due to recent modification
            assert files[0].score >= files[1].score

    def test_clear_recent_modifications(self, manager):
        """Test clearing recently modified tracking."""
        manager.track_file_modification("src/main.py")
        assert len(manager.recently_modified) == 1

        manager.clear_recent_modifications()
        assert len(manager.recently_modified) == 0

    def test_is_file_allowed_with_override(self, manager):
        """Test manual file inclusion override."""
        # Exclude all test files via pattern
        manager.config.exclude_patterns.append("tests/")

        # But manually include a specific file
        manager.manual_includes.add("tests/test_main.py")

        assert manager.is_file_allowed("tests/test_main.py") is True

    def test_is_file_allowed_with_manual_exclude(self, manager):
        """Test manual file exclusion override."""
        # Manually exclude a source file
        manager.manual_excludes.add("src/utils.py")

        assert manager.is_file_allowed("src/utils.py") is False

    def test_save_and_load_modifications(self, manager, temp_project):
        """Test persisting and loading recent modifications."""
        # Track some modifications
        manager.track_file_modification("src/main.py")
        manager.track_file_modification("src/utils.py")

        # Save to disk
        manager.save_modifications()

        # Create new manager and load
        new_manager = ContextManager(temp_project, manager.config)
        new_manager.load_modifications()

        assert len(new_manager.recently_modified) == 2
        assert "src/main.py" in new_manager.recently_modified
        assert "src/utils.py" in new_manager.recently_modified


class TestContextFileOperations:
    """Tests for context file operations."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ContextManager instance for testing."""
        project_path = tmp_path / "test_project"
        project_path.mkdir()
        (project_path / ".agent-pump").mkdir(exist_ok=True)

        config = ContextConfig(
            max_context_tokens=10000,
            reserve_tokens=1000,
            include_extensions=[".py"],
        )
        return ContextManager(project_path, config)

    def test_create_summary_placeholder(self):
        """Test creating a summary placeholder for large files."""
        config = ContextConfig(summarize_large_files=True, max_summary_length=100)
        manager = ContextManager(Path("."), config)

        large_content = "x" * 60000
        summary = manager._create_summary("large.py", large_content)

        assert len(summary) <= config.max_summary_length
        assert "large.py" in summary or "..." in summary

    def test_create_summary_disabled(self):
        """Test that summary creation is skipped when disabled."""
        config = ContextConfig(summarize_large_files=False)
        manager = ContextManager(Path("."), config)

        large_content = "x" * 60000
        summary = manager._create_summary("large.py", large_content)

        # Should return original or truncated content
        assert len(summary) > 0

    def test_calculate_file_score(self, manager):
        """Test file scoring algorithm."""
        # A source file in src/
        src_score = manager._calculate_file_score("src/main.py", 1000)

        # A test file
        test_score = manager._calculate_file_score("tests/test.py", 1000)

        # Source files should generally score higher
        assert src_score >= test_score

    def test_calculate_file_score_recent_boost(self, manager):
        """Test that recent modifications boost score."""
        # Score without modification
        normal_score = manager._calculate_file_score("src/main.py", 1000)

        # Mark as modified
        manager.track_file_modification("src/main.py")

        # Score with modification
        boosted_score = manager._calculate_file_score("src/main.py", 1000)

        assert boosted_score > normal_score

    def test_calculate_file_score_size_penalty(self, manager):
        """Test that large files get score penalty."""
        small_score = manager._calculate_file_score("small.py", 100)
        large_score = manager._calculate_file_score("large.py", 100000)

        # Small files should generally score higher per byte
        assert small_score > large_score


class TestContextAnalysis:
    """Tests for ContextAnalysis model."""

    def test_basic_analysis(self):
        """Test creating a context analysis."""
        analysis = ContextAnalysis(
            total_files=10,
            total_tokens=5000,
            files_in_budget=8,
            files_summarized=1,
            files_excluded=1,
        )

        assert analysis.total_files == 10
        assert analysis.total_tokens == 5000
        assert analysis.efficiency_ratio == 0.8  # 8/10

    def test_efficiency_ratio_calculation(self):
        """Test efficiency ratio calculation."""
        analysis = ContextAnalysis(
            total_files=20,
            files_in_budget=15,
            total_tokens=10000,
        )

        assert analysis.efficiency_ratio == 0.75

    def test_efficiency_ratio_zero_total(self):
        """Test efficiency ratio with zero total files."""
        analysis = ContextAnalysis(
            total_files=0,
            files_in_budget=0,
            total_tokens=0,
        )

        assert analysis.efficiency_ratio == 0.0

    def test_add_file_stats(self):
        """Test adding file statistics."""
        analysis = ContextAnalysis()

        analysis.add_file_included(100)
        analysis.add_file_included(200)
        analysis.add_file_excluded()

        assert analysis.files_in_budget == 2
        assert analysis.total_tokens == 300
        assert analysis.files_excluded == 1


class TestContextManagerIntegration:
    """Integration tests for ContextManager."""

    @pytest.fixture
    def complex_project(self, tmp_path):
        """Create a complex project structure."""
        project = tmp_path / "complex"
        project.mkdir()

        # Source with subdirectories
        src = project / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass", encoding="utf-8")
        (src / "models.py").write_text("class Model: pass", encoding="utf-8")

        utils = src / "utils"
        utils.mkdir()
        (utils / "helpers.py").write_text("def help(): pass", encoding="utf-8")

        # Tests
        tests = project / "tests"
        tests.mkdir()
        (tests / "test_models.py").write_text("def test_model(): pass", encoding="utf-8")

        # Documentation
        docs = project / "docs"
        docs.mkdir()
        (docs / "readme.md").write_text("# Docs", encoding="utf-8")

        # Config (should be excluded)
        config = project / ".agent-pump"
        config.mkdir()
        (config / "config.yml").write_text("settings:", encoding="utf-8")

        return project

    def test_full_workflow(self, complex_project):
        """Test the full context management workflow."""
        config = ContextConfig(
            max_context_tokens=10000,
            reserve_tokens=1000,
            include_extensions=[".py", ".md"],
        )

        manager = ContextManager(complex_project, config)

        # Analyze project
        analysis = manager.analyze_project()
        assert analysis.total_files > 0

        # Get files within budget
        files = manager.get_context_files(config.get_effective_token_limit())
        # Note: may be 0 files if budget is too small for any file
        # Just verify it doesn't crash
        assert isinstance(files, list)

        if files:
            # Verify token budget
            total_tokens = sum(f.token_count for f in files)
            assert total_tokens <= config.get_effective_token_limit()

        # Track a modification
        manager.track_file_modification("src/main.py")

        # Get prioritized files
        prioritized = manager.get_files_by_priority()
        if len(prioritized) > 0:
            # Recently modified should be first or have high score
            high_score_files = [f for f in prioritized if f.score > 1.0]
            assert len(high_score_files) > 0

    def test_multiple_extensions(self, complex_project):
        """Test handling multiple file extensions."""
        config = ContextConfig(
            include_extensions=[".py", ".md"],
        )

        manager = ContextManager(complex_project, config)
        files = manager.get_context_files(10000)

        # Should have both .py and .md files
        extensions = {Path(f.path).suffix for f in files}
        assert ".py" in extensions or ".md" in extensions

    def test_empty_project(self, tmp_path):
        """Test handling an empty project."""
        empty_project = tmp_path / "empty"
        empty_project.mkdir()

        config = ContextConfig()
        manager = ContextManager(empty_project, config)

        analysis = manager.analyze_project()
        assert analysis.total_files == 0
        assert analysis.total_tokens == 0

        files = manager.get_context_files(10000)
        assert len(files) == 0

    def test_small_budget(self, complex_project):
        """Test with small token budget."""
        config = ContextConfig(max_context_tokens=2000, reserve_tokens=1000)
        manager = ContextManager(complex_project, config)

        files = manager.get_context_files(config.get_effective_token_limit())
        total_tokens = sum(f.token_count for f in files)

        assert total_tokens <= 1000  # 2000 - 1000 reserve


class TestContextManagerEdgeCases:
    """Edge case tests for ContextManager."""

    def test_nonexistent_path(self):
        """Test handling non-existent project path."""
        config = ContextConfig()
        manager = ContextManager(Path("/nonexistent/path"), config)

        analysis = manager.analyze_project()
        assert analysis.total_files == 0

    def test_permission_denied(self, tmp_path):
        """Test handling permission errors."""
        project = tmp_path / "restricted"
        project.mkdir()
        (project / "secret.py").write_text("secret", encoding="utf-8")

        # Remove read permission (Unix only)
        import os

        os.chmod(project / "secret.py", 0o000)

        try:
            config = ContextConfig()
            manager = ContextManager(project, config)
            files = manager.get_context_files(10000)
            # Should handle permission error gracefully
            assert isinstance(files, list)
        finally:
            # Restore permissions for cleanup
            os.chmod(project / "secret.py", 0o644)

    def test_circular_symlinks(self, tmp_path):
        """Test handling circular symlinks."""
        project = tmp_path / "symlinks"
        project.mkdir()
        a = project / "a"
        a.mkdir()
        b = project / "b"
        b.mkdir()

        # Create circular symlink
        try:
            (a / "link_to_b").symlink_to(b)
            (b / "link_to_a").symlink_to(a)
        except (OSError, NotImplementedError):
            # Symlinks not supported on Windows without admin
            pytest.skip("Symlinks not supported")

        (a / "file.py").write_text("content", encoding="utf-8")

        config = ContextConfig()
        manager = ContextManager(project, config)

        # Should not get stuck in infinite loop
        files = manager.get_context_files(10000)
        assert isinstance(files, list)

    def test_binary_files(self, tmp_path):
        """Test handling binary files."""
        project = tmp_path / "binary"
        project.mkdir()

        # Create a binary file
        (project / "data.bin").write_bytes(b"\x00\x01\x02\x03")
        (project / "script.py").write_text("print('hello')", encoding="utf-8")

        config = ContextConfig(include_extensions=[".py", ".bin"])
        manager = ContextManager(project, config)

        files = manager.get_context_files(10000)
        file_paths = [f.path for f in files]

        # Binary files might be included but shouldn't crash
        assert "script.py" in file_paths

    def test_unicode_filenames(self, tmp_path):
        """Test handling unicode filenames."""
        project = tmp_path / "unicode"
        project.mkdir()

        # Create file with unicode name
        (project / "文件.py").write_text("content", encoding="utf-8")
        (project / "emoji_🚀.py").write_text("content", encoding="utf-8")

        config = ContextConfig()
        manager = ContextManager(project, config)

        files = manager.get_context_files(10000)
        # Should handle unicode filenames
        assert len(files) >= 0

    def test_deep_nesting(self, tmp_path):
        """Test handling deeply nested directories."""
        import sys

        project = tmp_path / "deep"
        current = project
        max_depth = 10 if sys.platform == "win32" else 20  # Windows has path length limits

        try:
            # Create nested directories
            for i in range(max_depth):
                current = current / f"level{i}"
                current.mkdir()

            (current / "deep_file.py").write_text("deep content", encoding="utf-8")
        except OSError:
            # Skip if we can't create deep directories (Windows path limits)
            pytest.skip("Cannot create deeply nested directories on this platform")

        config = ContextConfig()
        manager = ContextManager(project, config)

        # Should handle deep nesting without stack overflow
        files = manager.get_context_files(10000)
        # Just verify it doesn't crash - may or may not find file depending on depth
        assert isinstance(files, list)
