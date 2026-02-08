import asyncio
import logging
from pathlib import Path

from agent_pump.services.embeddings_service import EmbeddingsService
from agent_pump.services.vector_store import VectorStore
from agent_pump.utils.code_chunker import CodeChunker

logger = logging.getLogger(__name__)


class ContextService:
    """Service for indexing and retrieving context."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.embeddings_service = EmbeddingsService()
        self.vector_store = VectorStore()

        # Load existing store if available
        self.store_path = project_path / ".agent-pump" / "embeddings" / "index.npz"
        self._load_store()

    def _load_store(self) -> None:
        """Load the vector store from disk."""
        if self.store_path.exists():
            self.vector_store.load(self.store_path)

    async def index_project(self) -> None:
        """Index the project files."""
        logger.info("Indexing project...")

        # Determine files to index
        # For now, just simplistic walk, skipping common ignore dirs
        ignore_dirs = {".git", ".agent-pump", "__pycache__", "node_modules", "venv", ".venv", "dist", "build"}
        files_to_index: list[Path] = []

        for path in self.project_path.rglob("*"):
            if path.is_dir():
                if path.name in ignore_dirs:
                    # Skip dir (rglob doesn't support skipping easily, we filter files)
                    continue
            elif path.is_file():
                # check if in ignored dir
                if any(p.name in ignore_dirs for p in path.parents):
                    continue

                # Filter extensions
                if path.suffix in {".py", ".md", ".js", ".ts", ".html", ".css", ".json", ".yml", ".yaml", ".toml"}:
                    files_to_index.append(path)

        # Map existing files in store to their chunks/embeddings/metadata
        # to avoid re-embedding unchanged files.
        existing_files: dict[str, list[tuple[str, list[float], dict]]] = {}
        if self.vector_store.chunks:
            for i, chunk in enumerate(self.vector_store.chunks):
                meta = self.vector_store.metadata[i]
                file_key = meta.get("file")
                if file_key:
                    if file_key not in existing_files:
                        existing_files[file_key] = []
                    existing_files[file_key].append(
                        (chunk, self.vector_store.embeddings[i], meta)
                    )

        # Process files
        new_store = VectorStore()

        for file_path in files_to_index:
            try:
                rel_path = str(file_path.relative_to(self.project_path))
                current_mtime = file_path.stat().st_mtime

                # Check if file needs re-indexing
                if rel_path in existing_files:
                    # Check if mtime matches (stored in metadata)
                    # We check the first chunk's metadata
                    first_chunk_meta = existing_files[rel_path][0][2]
                    stored_mtime = first_chunk_meta.get("mtime", 0)

                    if abs(current_mtime - stored_mtime) < 1.0:
                        # File unchanged, reuse existing embeddings
                        for chunk, emb, meta in existing_files[rel_path]:
                            new_store.add(chunk, emb, meta)
                        continue

                # File changed or new, re-index
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                chunks = CodeChunker.chunk_content(content, file_path.name)

                for chunk in chunks:
                    if not chunk.strip():
                        continue

                    embedding = await asyncio.to_thread(self.embeddings_service.generate_embeddings, chunk)
                    if embedding:
                        new_store.add(
                            chunk=chunk,
                            embedding=embedding,
                            metadata={"file": rel_path, "mtime": current_mtime},
                        )
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")

        # Swap stores and save
        self.vector_store = new_store
        self.vector_store.save(self.store_path)
        logger.info("Project indexing complete.")

    async def get_relevant_context(self, query: str, k: int = 5) -> list[str]:
        """
        Get relevant context chunks for a query.

        Args:
            query: The query string.
            k: Number of chunks to retrieve.

        Returns:
            List of formatted context strings.
        """
        if not query:
            return []

        embedding = await asyncio.to_thread(self.embeddings_service.generate_embeddings, query)
        if not embedding:
            return []

        results = self.vector_store.search(embedding, k=k)

        context_chunks = []
        for res in results:
            file_path = res.metadata.get("file", "unknown")
            context_chunks.append(f"File: {file_path}\nWait, Score: {res.score:.2f}\n```\n{res.content}\n```")

        return context_chunks
