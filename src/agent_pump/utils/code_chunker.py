import re


class CodeChunker:
    """Utility for chunking code and text files."""

    @staticmethod
    def chunk_content(content: str, filename: str) -> list[str]:
        """
        Chunk the content based on file type.

        Args:
            content: The file content.
            filename: The filename (to determine type).

        Returns:
            A list of string chunks.
        """
        if not content.strip():
            return []

        if filename.endswith(".py"):
            return CodeChunker._chunk_python(content)
        elif filename.endswith(".md"):
            return CodeChunker._chunk_markdown(content)
        else:
            # Default to simple line based or paragraph based chunking?
            # For now, just return whole file if small, or split by double newlines.
            if len(content) < 2000:
                return [content]
            return [chunk for chunk in content.split("\n\n") if chunk.strip()]

    @staticmethod
    def _chunk_python(content: str) -> list[str]:
        """
        Chunk Python code by top-level definitions (classes, functions).
        Also includes imports and global code as separate chunks if possible.
        """
        chunks = []
        lines = content.splitlines()
        current_chunk: list[str] = []

        # Simple heuristic: Split on top-level `class ` or `def ` or `@` (decorator)
        # Note: This is fragile but better than nothing without tree-sitter.

        for line in lines:
            # Check if line starts with specific keywords at indent 0
            if (line.startswith("class ") or line.startswith("def ") or line.startswith("@")) and not line.startswith("    "):
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []

            current_chunk.append(line)

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return [c.strip() for c in chunks if c.strip()]

    @staticmethod
    def _chunk_markdown(content: str) -> list[str]:
        """Chunk Markdown by headers."""
        chunks = []
        lines = content.splitlines()
        current_chunk: list[str] = []

        for line in lines:
            if line.startswith("#"):
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
            current_chunk.append(line)

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return [c.strip() for c in chunks if c.strip()]
