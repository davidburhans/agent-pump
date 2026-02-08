import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from agent_pump.models.workspace import ProjectConfig, KnowledgeBaseConfig
from agent_pump.services.embeddings_service import EmbeddingsService
from agent_pump.services.vector_store import VectorStore
from agent_pump.utils.code_chunker import CodeChunker

logger = logging.getLogger(__name__)


class ContextService:
    """Service for indexing and retrieving context."""

    def __init__(self, project_path: Path, config: ProjectConfig | None = None):
        self.project_path = project_path
        self.config = config
        self.kb_config = config.knowledge_base if config else KnowledgeBaseConfig()
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
        """Index the project files and external resources."""
        logger.info("Indexing project...")

        # Determine files to index
        ignore_dirs = {".git", ".agent-pump", "__pycache__", "node_modules", "venv", ".venv", "dist", "build"}
        files_to_index: list[tuple[Path, str]] = []  # (path, type)

        # 1. Index codebase
        allowed_extensions = {".py", ".md", ".js", ".ts", ".html", ".css", ".json", ".yml", ".yaml", ".toml"}
        if self.kb_config.enabled:
             allowed_extensions.update(self.kb_config.file_extensions)

        for path in self.project_path.rglob("*"):
            if path.is_dir():
                if path.name in ignore_dirs:
                    continue
            elif path.is_file():
                if any(p.name in ignore_dirs for p in path.parents):
                    continue

                # Check if it's a doc file
                is_doc = False
                try:
                    rel_path = path.relative_to(self.project_path)
                    if self.kb_config.enabled:
                        # Check if in docs_dirs
                        if any(str(rel_path).startswith(d) for d in self.kb_config.docs_dirs):
                            is_doc = True
                except ValueError:
                    pass

                if path.suffix in allowed_extensions:
                    file_type = "docs" if is_doc else "code"
                    files_to_index.append((path, file_type))

        # Map existing files in store
        existing_items: dict[str, list[tuple[str, list[float], dict[str, Any]]]] = {}
        if self.vector_store.chunks:
            for i, chunk in enumerate(self.vector_store.chunks):
                meta = self.vector_store.metadata[i]
                # Key by 'file' (path or url)
                key = meta.get("file")
                if key:
                    if key not in existing_items:
                        existing_items[key] = []
                    existing_items[key].append(
                        (chunk, self.vector_store.embeddings[i], meta)
                    )

        new_store = VectorStore()

        # 2. Process local files
        for file_path, file_type in files_to_index:
            try:
                rel_path = str(file_path.relative_to(self.project_path))
                current_mtime = file_path.stat().st_mtime

                if rel_path in existing_items:
                    # Check if mtime matches (stored in metadata)
                    # We check the first chunk's metadata
                    if existing_items[rel_path]:
                        first_chunk_meta = existing_items[rel_path][0][2]
                        stored_mtime = first_chunk_meta.get("mtime", 0)

                        if abs(current_mtime - stored_mtime) < 1.0:
                            for chunk, emb, meta in existing_items[rel_path]:
                                new_store.add(chunk, emb, meta)
                            continue

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
                            metadata={
                                "file": rel_path,
                                "mtime": current_mtime,
                                "type": file_type
                            },
                        )
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")

        # 3. Process external resources
        if self.kb_config.enabled and self.kb_config.external_resources:
            await self._index_external_resources(new_store, existing_items)

        # Swap stores and save
        self.vector_store = new_store
        self.vector_store.save(self.store_path)
        logger.info("Project indexing complete.")

    async def _index_external_resources(
        self,
        store: VectorStore,
        existing_items: dict[str, list[tuple[str, list[float], dict[str, Any]]]]
    ) -> None:
        """Index configured external resources."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            for url in self.kb_config.external_resources:
                try:
                    # Check existing (we use URL as key)
                    # For now, simplistic check: if it exists, assume it's good?
                    # Or fetch HEAD to check Last-Modified?
                    # Let's re-fetch to ensure freshness as we don't persist check time well.

                    response = await client.get(url)
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    text = ""
                    if "text/html" in content_type:
                        soup = BeautifulSoup(response.text, "html.parser")
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        text = soup.get_text(separator="\n\n")
                    else:
                        text = response.text

                    chunks = CodeChunker.chunk_content(text, "external.txt") # force text chunking

                    for chunk in chunks:
                        if not chunk.strip():
                            continue

                        embedding = await asyncio.to_thread(self.embeddings_service.generate_embeddings, chunk)
                        if embedding:
                            store.add(
                                chunk=chunk,
                                embedding=embedding,
                                metadata={
                                    "file": url,
                                    "type": "external_doc",
                                    "source": "url"
                                },
                            )

                except Exception as e:
                    logger.warning(f"Failed to index external resource {url}: {e}")

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
            source = res.metadata.get("file", "unknown")
            doc_type = res.metadata.get("type", "code")

            header = f"File: {source}"
            if doc_type == "external_doc":
                 header = f"External Resource: {source}"
            elif doc_type == "docs":
                 header = f"Documentation: {source}"

            context_chunks.append(f"{header}\nWait, Score: {res.score:.2f}\n```\n{res.content}\n```")

        return context_chunks
