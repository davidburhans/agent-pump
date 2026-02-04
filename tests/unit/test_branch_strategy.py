"""Tests for branch strategy configuration models."""

from agent_pump.models.branch_strategy import BranchStrategyConfig


class TestBranchStrategyConfig:
    """Tests for BranchStrategyConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = BranchStrategyConfig()

        assert config.enabled is False
        assert config.auto_create_branch is True
        assert config.auto_merge is False
        assert config.branch_prefix == "feature"
        assert config.base_branch == "main"
        assert config.require_clean_worktree is True
        assert config.push_on_merge is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = BranchStrategyConfig(
            enabled=True,
            auto_create_branch=False,
            auto_merge=True,
            branch_prefix="feat",
            base_branch="master",
            require_clean_worktree=False,
            push_on_merge=True,
        )

        assert config.enabled is True
        assert config.auto_create_branch is False
        assert config.auto_merge is True
        assert config.branch_prefix == "feat"
        assert config.base_branch == "master"
        assert config.require_clean_worktree is False
        assert config.push_on_merge is True

    def test_branch_prefix_validation(self):
        """Test branch prefix validation."""
        # Valid prefixes
        valid_prefixes = ["feature", "feat", "task", "bugfix", "hotfix"]
        for prefix in valid_prefixes:
            config = BranchStrategyConfig(branch_prefix=prefix)
            assert config.branch_prefix == prefix

    def test_branch_prefix_with_special_chars(self):
        """Test that special characters are handled in branch prefix."""
        # Prefixes with valid characters
        config = BranchStrategyConfig(branch_prefix="my-feature")
        assert config.branch_prefix == "my-feature"

    def test_serialization(self):
        """Test model serialization."""
        config = BranchStrategyConfig(
            enabled=True,
            auto_create_branch=True,
            auto_merge=True,
        )

        data = config.model_dump()

        assert data["enabled"] is True
        assert data["auto_create_branch"] is True
        assert data["auto_merge"] is True
        assert data["branch_prefix"] == "feature"
        assert data["base_branch"] == "main"

    def test_deserialization(self):
        """Test model deserialization."""
        data = {
            "enabled": True,
            "auto_create_branch": False,
            "auto_merge": True,
            "branch_prefix": "custom",
            "base_branch": "develop",
        }

        config = BranchStrategyConfig.model_validate(data)

        assert config.enabled is True
        assert config.auto_create_branch is False
        assert config.auto_merge is True
        assert config.branch_prefix == "custom"
        assert config.base_branch == "develop"

    def test_partial_deserialization(self):
        """Test deserialization with partial data."""
        data = {"enabled": True}

        config = BranchStrategyConfig.model_validate(data)

        assert config.enabled is True
        assert config.auto_create_branch is True  # default
        assert config.auto_merge is False  # default
        assert config.branch_prefix == "feature"  # default


class TestBranchNameGeneration:
    """Tests for branch name generation utilities."""

    def test_simple_slugify(self):
        """Test basic slugification."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("Add Login Page")
        assert result == "add-login-page"

    def test_slugify_with_special_chars(self):
        """Test slugification with special characters."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("Fix: Memory Leak in Parser!")
        assert result == "fix-memory-leak-in-parser"

    def test_slugify_multiple_spaces(self):
        """Test slugification with multiple spaces."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("Update    Documentation")
        assert result == "update-documentation"

    def test_slugify_leading_trailing_spaces(self):
        """Test slugification with leading/trailing spaces."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("  Clean Up Code  ")
        assert result == "clean-up-code"

    def test_slugify_very_long_name(self):
        """Test slugification with very long feature name."""
        from agent_pump.services.branch_manager import slugify_branch_name

        long_name = "A" * 100
        result = slugify_branch_name(long_name)
        assert len(result) <= 50
        assert result == "a" * 50

    def test_slugify_empty_string(self):
        """Test slugification with empty string."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("")
        assert result == "unknown"

    def test_slugify_only_special_chars(self):
        """Test slugification with only special characters."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("!@#$%^&*()")
        assert result == "unknown"

    def test_slugify_unicode(self):
        """Test slugification with unicode characters."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("添加登录页面")
        assert result == "unknown"  # Unicode chars become empty, fallback to unknown

    def test_slugify_mixed_unicode_and_ascii(self):
        """Test slugification with mixed unicode and ascii."""
        from agent_pump.services.branch_manager import slugify_branch_name

        result = slugify_branch_name("添加 Login Page")
        assert result == "login-page"
