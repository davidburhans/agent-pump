"""Token counting utilities for different AI backends.

This module provides token counting functionality for various AI backends
with different tokenization schemes. For backends without specific tokenizers,
it provides a reasonable estimation based on character counts.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenCounter:
    """Count tokens for different AI backends.

    Different backends use different tokenization schemes:
    - Gemini: Uses Google's tokenizer (approx 4 chars per token)
    - Claude: Uses Anthropic's tokenizer (tiktoken-compatible)
    - Qwen: Uses similar to GPT tokenizer
    - OpenCode: Varies by underlying model

    For backends without specific tokenizers, we use estimation.
    """

    # Approximate characters per token for estimation
    CHARS_PER_TOKEN = 4

    # Default context window sizes by backend
    DEFAULT_CONTEXT_WINDOW = 128000

    # Backend-specific context window sizes
    CONTEXT_WINDOW_SIZES: dict[str, int | dict[str, int]] = {
        "gemini": {
            "default": 1_000_000,  # 1M tokens for Flash
            "flash": 1_000_000,
            "pro": 2_000_000,  # 2M tokens for Pro
        },
        "claude": 200_000,
        "qwen": 128_000,
        "opencode": 128_000,
    }

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count using character-based approximation.

        This is a fast, backend-agnostic estimation that assumes
        approximately 4 characters per token on average.

        Args:
            text: The text to estimate tokens for.

        Returns:
            Estimated number of tokens.
        """
        if not text:
            return 0

        # Rough estimate: 4 characters per token on average
        # Add 1 to avoid underestimation on short texts
        return max(1, len(text) // TokenCounter.CHARS_PER_TOKEN)

    @staticmethod
    def count_tokens(text: str, backend: str, model: str | None = None) -> int:
        """Count tokens for a specific backend.

        Uses backend-specific tokenization when available,
        falls back to estimation for unknown backends.

        Args:
            text: The text to count tokens for.
            backend: The backend name (gemini, claude, qwen, opencode).
            model: Optional model name for backend-specific counting.

        Returns:
            Number of tokens in the text.
        """
        if not text:
            return 0

        backend_lower = backend.lower()

        try:
            if backend_lower == "claude":
                return TokenCounter._count_claude_tokens(text)
            elif backend_lower == "gemini":
                return TokenCounter._count_gemini_tokens(text, model)
            elif backend_lower == "qwen":
                return TokenCounter._count_qwen_tokens(text)
            elif backend_lower == "opencode":
                return TokenCounter._count_opencode_tokens(text, model)
            else:
                # Unknown backend - use estimation
                logger.debug(f"Unknown backend '{backend}', using token estimation")
                return TokenCounter.estimate_tokens(text)
        except Exception as e:
            logger.warning(f"Token counting failed for {backend}: {e}, using estimation")
            return TokenCounter.estimate_tokens(text)

    @staticmethod
    def _count_claude_tokens(text: str) -> int:
        """Count tokens for Claude backend.

        Claude uses a tokenizer similar to GPT-4. We try to use
        tiktoken if available, otherwise use estimation.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens.
        """
        try:
            # Try to use tiktoken for accurate counting
            import tiktoken  # type: ignore

            # Claude uses cl100k_base encoding
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # tiktoken not installed, use estimation with slight adjustment
            # Claude tends to have slightly more tokens per char
            return max(1, int(len(text) / 3.5))
        except Exception:
            return TokenCounter.estimate_tokens(text)

    @staticmethod
    def _count_gemini_tokens(text: str, model: str | None = None) -> int:
        """Count tokens for Gemini backend.

        Gemini uses Google's own tokenizer. Without access to the
        actual tokenizer, we use a reasonable estimate.

        Args:
            text: The text to count tokens for.
            model: Optional model variant (flash, pro).

        Returns:
            Number of tokens.
        """
        # Gemini tends to have slightly more tokens per char than GPT
        # Due to different subword tokenization
        return max(1, int(len(text) / 3.8))

    @staticmethod
    def _count_qwen_tokens(text: str) -> int:
        """Count tokens for Qwen backend.

        Qwen uses a tokenizer similar to GPT models.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens.
        """
        try:
            import tiktoken  # type: ignore

            # Qwen uses similar encoding to GPT-3.5
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            return TokenCounter.estimate_tokens(text)

    @staticmethod
    def _count_opencode_tokens(text: str, model: str | None = None) -> int:
        """Count tokens for OpenCode backend.

        OpenCode can use different underlying models, so we
        use a generic estimation.

        Args:
            text: The text to count tokens for.
            model: Optional model name.

        Returns:
            Number of tokens.
        """
        # OpenCode typically uses models similar to GPT
        return TokenCounter.estimate_tokens(text)

    @staticmethod
    def get_context_window_size(backend: str, model: str | None = None) -> int:
        """Get the context window size for a backend.

        Args:
            backend: The backend name.
            model: Optional model name for specific sizing.

        Returns:
            Context window size in tokens.
        """
        backend_lower = backend.lower()
        sizes = TokenCounter.CONTEXT_WINDOW_SIZES.get(backend_lower)

        if sizes is None:
            return TokenCounter.DEFAULT_CONTEXT_WINDOW

        if isinstance(sizes, dict):
            # Backend has model-specific sizes
            if model:
                model_lower = model.lower()
                # Try exact match first
                if model_lower in sizes:
                    return sizes[model_lower]
                # Try partial matches
                for key, size in sizes.items():
                    if key in model_lower or model_lower in key:
                        return size
            # Return default for backend
            return sizes.get("default", TokenCounter.DEFAULT_CONTEXT_WINDOW)

        return sizes

    @staticmethod
    def count_file_tokens(file_path: Path, backend: str = "gemini") -> int:
        """Count tokens in a file.

        Args:
            file_path: Path to the file.
            backend: Backend to use for token counting.

        Returns:
            Number of tokens in the file, or 0 if file cannot be read.
        """
        try:
            text = file_path.read_text(encoding="utf-8")
            return TokenCounter.count_tokens(text, backend)
        except Exception as e:
            logger.warning(f"Failed to count tokens in {file_path}: {e}")
            return 0

    @staticmethod
    def format_token_count(count: int) -> str:
        """Format a token count for display.

        Args:
            count: The token count.

        Returns:
            Formatted string (e.g., "1.5K", "2.3M").
        """
        if count < 1000:
            return str(count)
        elif count < 1_000_000:
            return f"{count / 1000:.1f}K"
        else:
            return f"{count / 1_000_000:.1f}M"


class DefaultTokenCounterService:
    """Default implementation of TokenCounterService using the static TokenCounter."""

    def count_tokens(self, text: str, backend: str, model: str | None = None) -> int:
        """Count tokens for the given text."""
        return TokenCounter.count_tokens(text, backend, model)
