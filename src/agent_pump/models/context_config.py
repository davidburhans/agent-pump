"""Context configuration models for smart context window management.

This module defines the data models for configuring and tracking
context file management in Agent Pump.
"""

import fnmatch
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class FileInclusionRule(BaseModel):
    """A rule for including or excluding files from context.

    Rules are evaluated in priority order (higher priority first).
    Within the same priority, include rules are evaluated before exclude rules.
    """

    model_config = ConfigDict(strict=True)

    pattern: str = Field(description="Glob pattern to match files")
    action: str = Field(default="include", description="Action to take: 'include' or 'exclude'")
    priority: int = Field(default=0, description="Priority order (higher = evaluated first)")

    def matches(self, filepath: str) -> bool:
        """Check if a filepath matches this rule's pattern.

        Supports standard glob patterns including recursive `**` patterns.

        Args:
            filepath: The file path to check (relative to project root).

        Returns:
            True if the path matches the pattern.
        """
        # Normalize path separators for matching
        normalized_path = filepath.replace("\\", "/")
        normalized_pattern = self.pattern.replace("\\", "/")

        # Check for exact match or glob match
        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True

        # Handle recursive ** patterns (e.g., "**/*.test.js")
        if "**" in normalized_pattern:
            # Split pattern by **
            pattern_parts = normalized_pattern.split("**")
            if len(pattern_parts) == 2:
                prefix, suffix = pattern_parts
                # Check if path ends with suffix
                if suffix and normalized_path.endswith(suffix.lstrip("/")):
                    return True
                # Check if path matches suffix pattern
                if fnmatch.fnmatch(Path(normalized_path).name, suffix.lstrip("/")):
                    return True

        # Check if pattern matches parent directories
        # This handles cases like pattern="src/" matching "src/main.py"
        parts = normalized_path.split("/")
        for i in range(len(parts)):
            partial = "/".join(parts[: i + 1])
            if fnmatch.fnmatch(partial, normalized_pattern):
                return True
            # Also check if the component itself matches (for directory patterns)
            if normalized_pattern.endswith("/"):
                if fnmatch.fnmatch(parts[i], normalized_pattern.rstrip("/")):
                    return True

        return False


class ContextFile(BaseModel):
    """Represents a file included in the context.

    Tracks file content, token count, and whether it has been summarized.
    """

    model_config = ConfigDict(strict=True)

    path: str = Field(description="Relative path to the file")
    content: str = Field(description="File content or summary")
    token_count: int = Field(description="Number of tokens in content")
    is_summarized: bool = Field(default=False, description="Whether the content is a summary")
    original_length: int | None = Field(
        default=None, description="Original file length if summarized"
    )
    score: float = Field(default=0.0, description="Relevance score (higher = more relevant)")

    def get_content_preview(self, max_length: int = 100) -> str:
        """Get a preview of the content.

        Args:
            max_length: Maximum length of the preview.

        Returns:
            Truncated content with ellipsis if needed.
        """
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."

    def get_content_size(self) -> int:
        """Get the size of the content in characters.

        Returns:
            Character count of the content.
        """
        return len(self.content)

    def is_large(self, threshold: int = 50000) -> bool:
        """Check if the file is considered large.

        Args:
            threshold: Size threshold in characters.

        Returns:
            True if the file exceeds the threshold.
        """
        content_size = self.original_length or len(self.content)
        return content_size > threshold

    def get_token_efficiency(self) -> float:
        """Calculate token efficiency (score per token).

        Returns:
            Efficiency ratio (score / token_count).
        """
        if self.token_count == 0:
            return 0.0
        return self.score / self.token_count


class ContextConfig(BaseModel):
    """Configuration for smart context management.

    Controls how files are selected, prioritized, and summarized
    when building context for AI backends.
    """

    model_config = ConfigDict(strict=True)

    # Token limits
    max_context_tokens: int = Field(
        default=100000,
        description="Maximum context window size in tokens",
        ge=0,
    )
    reserve_tokens: int = Field(
        default=10000,
        description="Tokens to reserve for AI response",
        ge=0,
    )

    # File filtering
    include_patterns: list[str] = Field(
        default_factory=list, description="Glob patterns for files to include (empty = all)"
    )
    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            ".git",
            "node_modules",
            "__pycache__",
            ".agent-pump",
            ".pytest_cache",
            "*.pyc",
            "*.pyo",
            ".coverage",
            "htmlcov",
            ".tox",
            "*.egg-info",
            "dist",
            "build",
        ],
        description="Glob patterns for files to exclude",
    )
    include_extensions: list[str] = Field(
        default_factory=lambda: [
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".md",
            ".mdx",
            ".rst",
            ".yml",
            ".yaml",
            ".json",
            ".toml",
            ".rs",
            ".go",
            ".java",
            ".kt",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".rb",
            ".php",
            ".swift",
        ],
        description="File extensions to include (empty = all)",
    )

    # Prioritization
    prioritize_recently_modified: bool = Field(
        default=True, description="Boost score for recently modified files"
    )
    recently_modified_boost: float = Field(
        default=2.0,
        description="Score multiplier for recent files",
        gt=0,
    )
    recently_modified_window_hours: int = Field(
        default=24,
        description="Time window for 'recently modified' in hours",
        ge=1,
    )

    # Large file handling
    large_file_threshold: int = Field(
        default=50000,
        description="Character threshold for large files",
        ge=1000,
    )
    summarize_large_files: bool = Field(
        default=True, description="Summarize files exceeding threshold"
    )
    max_summary_length: int = Field(
        default=1000,
        description="Maximum length of summaries in characters",
        ge=100,
    )

    # Manual overrides
    manual_includes: list[str] = Field(
        default_factory=list, description="Specific files to always include"
    )
    manual_excludes: list[str] = Field(
        default_factory=list, description="Specific files to always exclude"
    )

    def get_effective_token_limit(self) -> int:
        """Calculate effective token limit after reserve.

        Returns:
            Available tokens for context (max - reserve).
        """
        return max(0, self.max_context_tokens - self.reserve_tokens)

    def is_file_allowed(self, filepath: str) -> bool:
        """Check if a file is allowed based on filters.

        Evaluates manual overrides, exclude patterns, include patterns,
        and file extensions in order.

        Args:
            filepath: Relative path to the file.

        Returns:
            True if the file should be included in context.
        """
        # Check manual overrides first
        if filepath in self.manual_includes:
            return True
        if filepath in self.manual_excludes:
            return False

        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if self._matches_pattern(filepath, pattern):
                return False

        # Check include patterns (if any non-empty patterns are specified)
        if self.include_patterns and any(p.strip() for p in self.include_patterns):
            included = False
            for pattern in self.include_patterns:
                if pattern.strip() and self._matches_pattern(filepath, pattern):
                    included = True
                    break
            if not included:
                return False

        # Check file extension (case-insensitive)
        if self.include_extensions:
            path = Path(filepath)
            file_ext = path.suffix.lower()
            allowed_exts = [ext.lower() for ext in self.include_extensions]
            if file_ext not in allowed_exts:
                return False

        return True

    def _matches_pattern(self, filepath: str, pattern: str) -> bool:
        """Check if a filepath matches a glob pattern.

        Args:
            filepath: The file path to check.
            pattern: The glob pattern to match against.

        Returns:
            True if the path matches the pattern.
        """
        # Normalize separators
        normalized_path = filepath.replace("\\", "/")
        normalized_pattern = pattern.replace("\\", "/")

        # Direct match
        if fnmatch.fnmatch(normalized_path, normalized_pattern):
            return True

        # Check if any directory component matches the pattern
        # This handles cases like pattern="src/" matching "src/main.py"
        parts = normalized_path.split("/")
        for i in range(len(parts)):
            partial_path = "/".join(parts[: i + 1])
            if fnmatch.fnmatch(partial_path, normalized_pattern):
                return True
            # Also check just the directory name
            if fnmatch.fnmatch(parts[i], normalized_pattern.rstrip("/")):
                return True

        return False


class ContextAnalysis(BaseModel):
    """Analysis results for context assembly.

    Provides statistics about the context that was assembled.
    """

    model_config = ConfigDict(strict=True)

    total_files: int = Field(default=0, description="Total files in project")
    total_tokens: int = Field(default=0, description="Total tokens across all files")
    files_in_budget: int = Field(default=0, description="Files included in context")
    files_summarized: int = Field(default=0, description="Files that were summarized")
    files_excluded: int = Field(default=0, description="Files excluded by filters")

    @property
    def efficiency_ratio(self) -> float:
        """Calculate context efficiency ratio.

        Returns:
            Ratio of files in budget to total files (0.0 - 1.0).
        """
        if self.total_files == 0:
            return 0.0
        return self.files_in_budget / self.total_files

    def add_file_included(self, token_count: int, is_summarized: bool = False) -> None:
        """Record an included file.

        Args:
            token_count: Number of tokens in the file.
            is_summarized: Whether the file was summarized.
        """
        self.files_in_budget += 1
        self.total_tokens += token_count
        if is_summarized:
            self.files_summarized += 1

    def add_file_excluded(self) -> None:
        """Record an excluded file."""
        self.files_excluded += 1
        self.total_files += 1

    def add_file_analyzed(self, token_count: int) -> None:
        """Record a file that was analyzed but not necessarily included.

        Args:
            token_count: Number of tokens in the file.
        """
        self.total_files += 1
        self.total_tokens += token_count
