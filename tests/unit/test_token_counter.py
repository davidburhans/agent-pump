"""Tests for token counter utility."""


from agent_pump.utils.token_counter import TokenCounter


class TestTokenCounter:
    """Tests for the TokenCounter class."""

    def test_estimate_tokens_basic(self):
        """Test basic token estimation."""
        text = "Hello world"
        tokens = TokenCounter.estimate_tokens(text)
        # Roughly len(text) / 4
        assert tokens > 0
        assert tokens >= len(text) // 4

    def test_estimate_tokens_empty(self):
        """Test token estimation with empty string."""
        assert TokenCounter.estimate_tokens("") == 0

    def test_estimate_tokens_unicode(self):
        """Test token estimation with unicode characters."""
        text = "Hello 世界 🌍"
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens > 0

    def test_estimate_tokens_long_text(self):
        """Test token estimation with long text."""
        text = "word " * 1000  # 5000 characters
        tokens = TokenCounter.estimate_tokens(text)
        expected = 5000 // 4  # 1250
        assert tokens >= expected * 0.9  # Allow 10% variance
        assert tokens <= expected * 1.1

    def test_count_tokens_with_backend_gemini(self):
        """Test token counting for Gemini backend."""
        text = "Test prompt for Gemini"
        tokens = TokenCounter.count_tokens(text, "gemini")
        assert tokens > 0

    def test_count_tokens_with_backend_claude(self):
        """Test token counting for Claude backend."""
        text = "Test prompt for Claude"
        tokens = TokenCounter.count_tokens(text, "claude")
        assert tokens > 0

    def test_count_tokens_with_backend_qwen(self):
        """Test token counting for Qwen backend."""
        text = "Test prompt for Qwen"
        tokens = TokenCounter.count_tokens(text, "qwen")
        assert tokens > 0

    def test_count_tokens_with_backend_opencode(self):
        """Test token counting for OpenCode backend."""
        text = "Test prompt for OpenCode"
        tokens = TokenCounter.count_tokens(text, "opencode")
        assert tokens > 0

    def test_count_tokens_unknown_backend(self):
        """Test token counting with unknown backend defaults to estimate."""
        text = "Test prompt"
        tokens = TokenCounter.count_tokens(text, "unknown")
        assert tokens == TokenCounter.estimate_tokens(text)

    def test_get_context_window_size_gemini(self):
        """Test getting context window size for Gemini."""
        size = TokenCounter.get_context_window_size("gemini")
        assert size >= 1000000  # At least 1M tokens

    def test_get_context_window_size_claude(self):
        """Test getting context window size for Claude."""
        size = TokenCounter.get_context_window_size("claude")
        assert size == 200000

    def test_get_context_window_size_qwen(self):
        """Test getting context window size for Qwen."""
        size = TokenCounter.get_context_window_size("qwen")
        assert size >= 100000

    def test_get_context_window_size_opencode(self):
        """Test getting context window size for OpenCode."""
        size = TokenCounter.get_context_window_size("opencode")
        assert size >= 100000

    def test_get_context_window_size_unknown(self):
        """Test getting context window size for unknown backend."""
        size = TokenCounter.get_context_window_size("unknown")
        assert size == TokenCounter.DEFAULT_CONTEXT_WINDOW

    def test_get_context_window_size_with_model(self):
        """Test getting context window size with specific model."""
        # Gemini Flash vs Pro
        flash_size = TokenCounter.get_context_window_size("gemini", "flash")
        pro_size = TokenCounter.get_context_window_size("gemini", "pro")
        assert pro_size >= flash_size

    def test_count_tokens_code(self):
        """Test token counting with code content."""
        code = """
def hello_world():
    print("Hello, World!")
    return 42
"""
        tokens = TokenCounter.count_tokens(code, "claude")
        assert tokens > 0
        # Code has many special characters, so should be reasonable count
        assert tokens >= len(code) // 8  # At least half of estimate

    def test_count_tokens_multiline(self):
        """Test token counting with multiline text."""
        text = """Line 1
Line 2
Line 3"""
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens > 0

    def test_consistency_across_backends(self):
        """Test that all backends return consistent token counts."""
        text = "This is a test of consistency across different AI backends."
        gemini = TokenCounter.count_tokens(text, "gemini")
        claude = TokenCounter.count_tokens(text, "claude")
        qwen = TokenCounter.count_tokens(text, "qwen")
        opencode = TokenCounter.count_tokens(text, "opencode")

        # All should be positive and relatively close
        assert gemini > 0
        assert claude > 0
        assert qwen > 0
        assert opencode > 0

        # Should be within 50% of each other
        values = [gemini, claude, qwen, opencode]
        max_val = max(values)
        min_val = min(values)
        assert min_val >= max_val * 0.5


class TestTokenCounterEdgeCases:
    """Edge case tests for TokenCounter."""

    def test_newlines_only(self):
        """Test with only newlines."""
        text = "\n\n\n"
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens >= 0

    def test_whitespace_only(self):
        """Test with only whitespace."""
        text = "   \t\n  "
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens >= 0

    def test_special_characters(self):
        """Test with special characters."""
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens > 0

    def test_mixed_content(self):
        """Test with mixed content types."""
        text = """# Heading

Some text with **bold** and *italic*.

```python
def test():
    pass
```
"""
        tokens = TokenCounter.estimate_tokens(text)
        assert tokens > 0
