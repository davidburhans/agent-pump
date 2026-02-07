"""Tests for context configuration models."""

from agent_pump.models.context_config import ContextConfig, ContextFile, FileInclusionRule


class TestContextConfig:
    """Tests for the ContextConfig model."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = ContextConfig()

        # Token limits
        assert config.max_context_tokens == 100000
        assert config.reserve_tokens == 10000

        # File filtering
        assert config.include_patterns == []
        assert ".git" in config.exclude_patterns
        assert "node_modules" in config.exclude_patterns
        assert "__pycache__" in config.exclude_patterns
        assert ".agent-pump" in config.exclude_patterns
        assert ".py" in config.include_extensions

        # Prioritization
        assert config.prioritize_recently_modified is True
        assert config.recently_modified_boost == 2.0

        # Large file handling
        assert config.large_file_threshold == 50000
        assert config.summarize_large_files is True
        assert config.max_summary_length == 1000

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = ContextConfig(
            max_context_tokens=200000,
            reserve_tokens=20000,
            include_patterns=["src/"],
            exclude_patterns=[".git", "custom_dir"],
            include_extensions=[".rs", ".toml"],
            prioritize_recently_modified=False,
            recently_modified_boost=3.0,
            large_file_threshold=100000,
            summarize_large_files=False,
            max_summary_length=500,
        )

        assert config.max_context_tokens == 200000
        assert config.reserve_tokens == 20000
        assert config.include_patterns == ["src/"]
        assert config.exclude_patterns == [".git", "custom_dir"]
        assert config.include_extensions == [".rs", ".toml"]
        assert config.prioritize_recently_modified is False
        assert config.recently_modified_boost == 3.0
        assert config.large_file_threshold == 100000
        assert config.summarize_large_files is False
        assert config.max_summary_length == 500

    def test_effective_token_limit(self):
        """Test effective token limit calculation."""
        config = ContextConfig(max_context_tokens=100000, reserve_tokens=10000)
        assert config.get_effective_token_limit() == 90000

    def test_is_file_allowed_by_extension(self):
        """Test file extension filtering."""
        config = ContextConfig(include_extensions=[".py", ".md"])

        assert config.is_file_allowed("test.py") is True
        assert config.is_file_allowed("README.md") is True
        assert config.is_file_allowed("script.js") is False
        assert config.is_file_allowed("data.json") is False

    def test_is_file_allowed_with_empty_extensions(self):
        """Test that all files are allowed when extensions list is empty."""
        config = ContextConfig(include_extensions=[])

        assert config.is_file_allowed("any.file") is True
        assert config.is_file_allowed("test.py") is True
        assert config.is_file_allowed("no_extension") is True

    def test_is_file_allowed_by_exclude_pattern(self):
        """Test exclusion patterns."""
        config = ContextConfig(exclude_patterns=[".git", "node_modules"])

        assert config.is_file_allowed("src/main.py") is True
        assert config.is_file_allowed(".git/config") is False
        assert config.is_file_allowed("node_modules/package.json") is False

    def test_is_file_allowed_by_include_pattern(self):
        """Test inclusion patterns."""
        config = ContextConfig(include_patterns=["src/"], exclude_patterns=[".git"])

        assert config.is_file_allowed("src/main.py") is True
        assert config.is_file_allowed("tests/test.py") is False
        assert config.is_file_allowed(".git/config") is False

    def test_is_file_allowed_empty_include_patterns(self):
        """Test that files pass when include_patterns is empty but extensions match."""
        config = ContextConfig(
            include_patterns=[],
            include_extensions=[".py", ".txt"],  # Need to include .txt
        )

        assert config.is_file_allowed("any/file.txt") is True

    def test_is_file_allowed_no_patterns(self):
        """Test file filtering with no patterns but matching extension."""
        config = ContextConfig(
            exclude_patterns=[],
            include_patterns=[],
            include_extensions=[".file"],  # Match the test file extension
        )

        # Should allow files with matching extension
        assert config.is_file_allowed("any.file") is True

    def test_serialization(self):
        """Test serialization to dict."""
        config = ContextConfig(max_context_tokens=50000)
        data = config.model_dump()

        assert data["max_context_tokens"] == 50000
        assert "reserve_tokens" in data
        assert "exclude_patterns" in data

    def test_deserialization(self):
        """Test deserialization from dict."""
        data = {
            "max_context_tokens": 75000,
            "reserve_tokens": 5000,
            "exclude_patterns": [".git"],
            "include_extensions": [".py"],
        }

        config = ContextConfig.model_validate(data)
        assert config.max_context_tokens == 75000
        assert config.reserve_tokens == 5000
        assert config.exclude_patterns == [".git"]
        assert config.include_extensions == [".py"]


class TestContextFile:
    """Tests for the ContextFile model."""

    def test_basic_creation(self):
        """Test creating a context file."""
        file = ContextFile(
            path="src/main.py",
            content="def main(): pass",
            token_count=10,
        )

        assert file.path == "src/main.py"
        assert file.content == "def main(): pass"
        assert file.token_count == 10
        assert file.is_summarized is False
        assert file.original_length is None
        assert file.score == 0.0

    def test_summarized_file(self):
        """Test creating a summarized context file."""
        file = ContextFile(
            path="src/large.py",
            content="# Summary of large file...",
            token_count=50,
            is_summarized=True,
            original_length=10000,
            score=0.8,
        )

        assert file.is_summarized is True
        assert file.original_length == 10000
        assert file.score == 0.8

    def test_content_preview(self):
        """Test content preview truncation."""
        long_content = "x" * 500
        file = ContextFile(
            path="test.txt",
            content=long_content,
            token_count=125,
        )

        preview = file.get_content_preview(100)
        assert len(preview) <= 103  # 100 + "..."
        assert "..." in preview

    def test_content_preview_short_content(self):
        """Test content preview with short content."""
        file = ContextFile(
            path="test.txt",
            content="Short",
            token_count=2,
        )

        preview = file.get_content_preview(100)
        assert preview == "Short"

    def test_file_size_calculation(self):
        """Test file size calculation."""
        file = ContextFile(
            path="test.txt",
            content="Hello world",
            token_count=3,
        )

        assert file.get_content_size() == 11

    def test_is_large_file(self):
        """Test large file detection."""
        # With default threshold of 50000
        small_file = ContextFile(
            path="small.py",
            content="x" * 1000,
            token_count=250,
        )
        assert small_file.is_large() is False

        large_file = ContextFile(
            path="large.py",
            content="x" * 60000,
            token_count=15000,
        )
        assert large_file.is_large() is True

    def test_is_large_file_custom_threshold(self):
        """Test large file detection with custom threshold."""
        file = ContextFile(
            path="medium.py",
            content="x" * 30000,
            token_count=7500,
        )

        # Below threshold of 50000
        assert file.is_large(threshold=50000) is False
        # Above threshold of 20000
        assert file.is_large(threshold=20000) is True

    def test_serialization(self):
        """Test serialization of ContextFile."""
        file = ContextFile(
            path="test.py",
            content="content",
            token_count=10,
            is_summarized=True,
            original_length=1000,
            score=0.5,
        )

        data = file.model_dump()
        assert data["path"] == "test.py"
        assert data["is_summarized"] is True

    def test_deserialization(self):
        """Test deserialization of ContextFile."""
        data = {
            "path": "test.py",
            "content": "def test(): pass",
            "token_count": 5,
            "is_summarized": False,
            "score": 0.75,
        }

        file = ContextFile.model_validate(data)
        assert file.path == "test.py"
        assert file.score == 0.75


class TestFileInclusionRule:
    """Tests for the FileInclusionRule model."""

    def test_include_rule(self):
        """Test include rule creation."""
        rule = FileInclusionRule(
            pattern="src/",
            action="include",
            priority=10,
        )

        assert rule.pattern == "src/"
        assert rule.action == "include"
        assert rule.priority == 10

    def test_exclude_rule(self):
        """Test exclude rule creation."""
        rule = FileInclusionRule(
            pattern="tests/",
            action="exclude",
            priority=5,
        )

        assert rule.pattern == "tests/"
        assert rule.action == "exclude"
        assert rule.priority == 5

    def test_default_priority(self):
        """Test default priority value."""
        rule = FileInclusionRule(pattern="src/", action="include")
        assert rule.priority == 0

    def test_matches_pattern(self):
        """Test pattern matching."""
        rule = FileInclusionRule(pattern="src/", action="include")

        assert rule.matches("src/main.py") is True
        assert rule.matches("src/utils/helpers.py") is True
        assert rule.matches("tests/test.py") is False
        assert rule.matches("README.md") is False

    def test_matches_glob_pattern(self):
        """Test glob pattern matching."""
        rule = FileInclusionRule(pattern="*.py", action="include")

        assert rule.matches("test.py") is True
        assert rule.matches("src/main.py") is True
        assert rule.matches("README.md") is False

    def test_matches_recursive_pattern(self):
        """Test recursive glob pattern matching."""
        rule = FileInclusionRule(pattern="**/*.test.js", action="include")

        assert rule.matches("component.test.js") is True
        assert rule.matches("src/components/Button.test.js") is True
        assert rule.matches("src/main.js") is False


class TestContextConfigEdgeCases:
    """Edge case tests for ContextConfig."""

    def test_small_max_tokens(self):
        """Test with small max tokens."""
        config = ContextConfig(max_context_tokens=1000, reserve_tokens=500)
        assert config.get_effective_token_limit() == 500

    def test_reserve_greater_than_max(self):
        """Test when reserve exceeds max."""
        config = ContextConfig(max_context_tokens=1000, reserve_tokens=2000)
        # Should not go negative
        assert config.get_effective_token_limit() <= 1000

    def test_hidden_files(self):
        """Test handling of hidden files."""
        # Use empty extensions to allow files without extension
        config = ContextConfig(include_extensions=[])

        # .git should be excluded by default
        assert config.is_file_allowed(".git/config") is False
        assert config.is_file_allowed(".env") is True  # Not excluded by default

    def test_file_without_extension(self):
        """Test files without extension."""
        config = ContextConfig(include_extensions=[".py"])

        # Files without extension should be excluded
        assert config.is_file_allowed("Makefile") is False
        assert config.is_file_allowed("Dockerfile") is False

    def test_case_sensitivity(self):
        """Test case insensitivity in extensions."""
        config = ContextConfig(include_extensions=[".py"])

        # Extensions are case-insensitive
        assert config.is_file_allowed("test.py") is True
        assert config.is_file_allowed("test.PY") is True  # Case-insensitive


class TestContextFileComparison:
    """Tests for comparing and sorting context files."""

    def test_sort_by_score(self):
        """Test sorting files by score."""
        files = [
            ContextFile(path="b.py", content="b", token_count=10, score=0.5),
            ContextFile(path="a.py", content="a", token_count=10, score=0.9),
            ContextFile(path="c.py", content="c", token_count=10, score=0.1),
        ]

        sorted_files = sorted(files, key=lambda f: f.score, reverse=True)
        assert sorted_files[0].path == "a.py"
        assert sorted_files[1].path == "b.py"
        assert sorted_files[2].path == "c.py"

    def test_sort_by_token_count(self):
        """Test sorting files by token count."""
        files = [
            ContextFile(path="large.py", content="x" * 400, token_count=100),
            ContextFile(path="small.py", content="x" * 40, token_count=10),
            ContextFile(path="medium.py", content="x" * 200, token_count=50),
        ]

        sorted_files = sorted(files, key=lambda f: f.token_count)
        assert sorted_files[0].path == "small.py"
        assert sorted_files[1].path == "medium.py"
        assert sorted_files[2].path == "large.py"

    def test_token_efficiency(self):
        """Test calculating token efficiency score."""
        file = ContextFile(
            path="efficient.py",
            content="def test(): pass",
            token_count=4,
            score=1.0,
        )

        # Efficiency = score / token_count
        efficiency = file.get_token_efficiency()
        assert efficiency == 0.25
