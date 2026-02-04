"""Context manager for smart context window management.

This module provides intelligent context assembly, file prioritization,
and token budget management for AI backends.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from agent_pump.models.context_config import (
    ContextAnalysis,
    ContextConfig,
    ContextFile,
)
from agent_pump.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages intelligent context assembly for AI backends.

    Analyzes projects, scores files by relevance, and assembles
    context within token budget constraints.
    """

    def __init__(self, project_path: Path, config: ContextConfig | None = None):
        """Initialize the context manager.

        Args:
            project_path: Path to the project directory.
            config: Context configuration. Uses defaults if not provided.
        """
        self.project_path = Path(project_path)
        self.config = config or ContextConfig()
        self.file_scores: dict[str, float] = {}
        self.recently_modified: dict[str, datetime] = {}
        self.manual_includes: set[str] = set(self.config.manual_includes)
        self.manual_excludes: set[str] = set(self.config.manual_excludes)

        # Load persisted modifications
        self.load_modifications()

    def analyze_project(self) -> ContextAnalysis:
        """Analyze the project and return statistics.

        Returns:
            ContextAnalysis with project statistics.
        """
        analysis = ContextAnalysis()

        for filepath in self._walk_project():
            # Check if file is allowed
            if not self.is_file_allowed(filepath):
                analysis.add_file_excluded()
                continue

            # Count tokens
            full_path = self.project_path / filepath
            try:
                content = full_path.read_text(encoding="utf-8")
                token_count = TokenCounter.estimate_tokens(content)
                analysis.add_file_analyzed(token_count)
            except Exception as e:
                logger.warning(f"Failed to analyze {filepath}: {e}")
                analysis.add_file_excluded()

        return analysis

    def get_context_files(self, max_tokens: int | None = None) -> list[ContextFile]:
        """Get prioritized list of files within token budget.

        Args:
            max_tokens: Maximum tokens to use. Defaults to config effective limit.

        Returns:
            List of ContextFile objects within budget.
        """
        if max_tokens is None:
            max_tokens = self.config.get_effective_token_limit()

        # Score all files
        scored_files = self._score_files()

        # Sort by score (descending)
        sorted_files = sorted(scored_files.items(), key=lambda x: x[1], reverse=True)

        # Select files within budget
        selected: list[ContextFile] = []
        remaining_tokens = max_tokens

        for filepath, score in sorted_files:
            if remaining_tokens <= 0:
                break

            # Check if manually excluded
            if filepath in self.manual_excludes:
                continue

            # Load file content
            full_path = self.project_path / filepath
            try:
                content = full_path.read_text(encoding="utf-8")
                content_size = len(content)

                # Check if file should be summarized
                is_summarized = False
                if (
                    self.config.summarize_large_files
                    and content_size > self.config.large_file_threshold
                ):
                    content = self._create_summary(filepath, content)
                    is_summarized = True

                # Count tokens
                token_count = TokenCounter.estimate_tokens(content)

                # Check if within budget
                if token_count > remaining_tokens:
                    # Try to create a summary if not already summarized
                    if not is_summarized and content_size > 1000:
                        content = self._create_summary(filepath, content)
                        token_count = TokenCounter.estimate_tokens(content)
                        is_summarized = True

                    # Skip if still over budget
                    if token_count > remaining_tokens:
                        continue

                context_file = ContextFile(
                    path=filepath,
                    content=content,
                    token_count=token_count,
                    is_summarized=is_summarized,
                    original_length=content_size if is_summarized else None,
                    score=score,
                )

                selected.append(context_file)
                remaining_tokens -= token_count

            except Exception as e:
                logger.warning(f"Failed to load {filepath}: {e}")
                continue

        return selected

    def get_files_by_priority(self) -> list[ContextFile]:
        """Get all files sorted by priority score.

        Returns:
            List of ContextFile objects sorted by score.
        """
        files = self.get_context_files(max_tokens=float("inf"))  # type: ignore
        return sorted(files, key=lambda f: f.score, reverse=True)

    def is_file_allowed(self, filepath: str) -> bool:
        """Check if a file is allowed based on configuration.

        Args:
            filepath: Relative path to the file.

        Returns:
            True if the file should be included.
        """
        # Check manual overrides
        if filepath in self.manual_includes:
            return True
        if filepath in self.manual_excludes:
            return False

        # Use config check
        return self.config.is_file_allowed(filepath)

    def track_file_modification(self, filepath: str) -> None:
        """Track that a file was recently modified by the agent.

        Args:
            filepath: Relative path to the file.
        """
        self.recently_modified[filepath] = datetime.now()
        logger.debug(f"Tracked modification: {filepath}")

    def clear_recent_modifications(self) -> None:
        """Clear the recently modified tracking."""
        self.recently_modified.clear()
        logger.debug("Cleared recent modifications")

    def save_modifications(self) -> None:
        """Save recently modified file tracking to disk."""
        state_path = self.project_path / ".agent-pump" / "context_state.json"
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert datetime objects to ISO strings
            data = {
                "recently_modified": {k: v.isoformat() for k, v in self.recently_modified.items()},
                "manual_includes": list(self.manual_includes),
                "manual_excludes": list(self.manual_excludes),
            }

            state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Saved context state to {state_path}")
        except Exception as e:
            logger.warning(f"Failed to save context state: {e}")

    def load_modifications(self) -> None:
        """Load recently modified file tracking from disk."""
        state_path = self.project_path / ".agent-pump" / "context_state.json"
        if not state_path.exists():
            return

        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))

            # Load recently modified
            for k, v in data.get("recently_modified", {}).items():
                try:
                    self.recently_modified[k] = datetime.fromisoformat(v)
                except (ValueError, TypeError):
                    continue

            # Load manual overrides
            self.manual_includes = set(data.get("manual_includes", []))
            self.manual_excludes = set(data.get("manual_excludes", []))

            logger.debug(f"Loaded context state from {state_path}")
        except Exception as e:
            logger.warning(f"Failed to load context state: {e}")

    def _walk_project(self) -> list[str]:
        """Walk the project directory and return relative file paths.

        Returns:
            List of relative file paths.
        """
        files: list[str] = []

        if not self.project_path.exists():
            return files

        for path in self.project_path.rglob("*"):
            if path.is_file():
                # Get relative path
                rel_path = path.relative_to(self.project_path).as_posix()
                files.append(rel_path)

        return files

    def _score_files(self) -> dict[str, float]:
        """Score all files by relevance.

        Returns:
            Dictionary mapping file paths to scores.
        """
        scores: dict[str, float] = {}

        for filepath in self._walk_project():
            if not self.is_file_allowed(filepath):
                continue

            score = self._calculate_file_score(filepath)
            if score > 0:
                scores[filepath] = score

        return scores

    def _calculate_file_score(self, filepath: str, content_size: int | None = None) -> float:
        """Calculate a relevance score for a file.

        Scoring factors:
        - Source vs test files (source scores higher)
        - Recently modified (boost)
        - File size (smaller is better per token)
        - Depth in directory structure (shallower is better)

        Args:
            filepath: Relative path to the file.
            content_size: Optional content size in characters.

        Returns:
            Relevance score (higher = more relevant).
        """
        score = 1.0
        path = Path(filepath)

        # Directory-based scoring
        path_parts = [p.lower() for p in path.parts]

        # Boost source files over tests
        if any(p in path_parts for p in ["test", "tests", "spec", "__tests__"]):
            score *= 0.5
        elif "src" in path_parts or "source" in path_parts:
            score *= 1.5

        # Boost core/config files
        if path.name.lower() in ["readme.md", "main.py", "index.js", "app.py"]:
            score *= 1.3

        # Penalize deep nesting
        depth = len(path_parts) - 1
        if depth > 3:
            score *= 0.8 ** (depth - 3)

        # Check recency
        if self.config.prioritize_recently_modified and filepath in self.recently_modified:
            modified_time = self.recently_modified[filepath]
            hours_ago = (datetime.now() - modified_time).total_seconds() / 3600

            if hours_ago <= self.config.recently_modified_window_hours:
                score *= self.config.recently_modified_boost

        # Size penalty (if known)
        if content_size and content_size > 0:
            # Prefer files that are information-dense but not too large
            # Sweet spot: 500-5000 chars
            if content_size < 100:
                score *= 0.7  # Too small
            elif content_size > 50000:
                score *= 0.5  # Too large
            elif 500 <= content_size <= 5000:
                score *= 1.2  # Sweet spot

        return score

    def _create_summary(self, filepath: str, content: str) -> str:
        """Create a summary of a large file.

        Args:
            filepath: Path to the file.
            content: Full file content.

        Returns:
            Summarized content.
        """
        if not self.config.summarize_large_files:
            return content[: self.config.max_summary_length]

        max_length = self.config.max_summary_length

        # Simple summarization: header + first part + middle part + last part
        header = f"# Summary of {filepath}\n"
        header += f"(Original file: {len(content)} characters, truncated for context)\n\n"

        available = max_length - len(header) - 100  # Reserve space for separators

        if len(content) <= available:
            return content

        # Take beginning, middle, and end
        third = available // 3
        beginning = content[:third]

        middle_start = len(content) // 2 - third // 2
        middle = content[middle_start : middle_start + third]

        end = content[-third:]

        summary = header
        summary += "## Beginning\n" + beginning + "\n\n"
        summary += "## Middle\n" + middle + "\n\n"
        summary += "## End\n" + end + "\n"

        return summary[:max_length]
