import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from vector search."""

    content: str
    metadata: dict[str, Any]
    score: float


class VectorStore:
    """Simple in-memory vector store using numpy."""

    def __init__(self):
        self.embeddings: list[list[float]] = []  # List of vectors
        self.chunks: list[str] = []
        self.metadata: list[dict[str, Any]] = []
        self._matrix: NDArray[np.float32] | None = None

    def add(
        self, chunk: str, embedding: list[float], metadata: dict[str, Any] | None = None
    ) -> None:
        """Add a chunk and its embedding to the store."""
        self.chunks.append(chunk)
        self.embeddings.append(embedding)
        self.metadata.append(metadata or {})
        self._matrix = None  # Invalidate cached matrix

    def _get_matrix(self) -> NDArray[np.float32]:
        """Get the embeddings as a numpy matrix."""
        if self._matrix is None:
            if not self.embeddings:
                return np.array([], dtype=np.float32).reshape(0, 0)
            self._matrix = np.array(self.embeddings, dtype=np.float32)
        return self._matrix

    def save(self, path: Path) -> None:
        """Save the store to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Save chunks and metadata as JSON
        data = {
            "chunks": self.chunks,
            "metadata": self.metadata,
        }

        json_path = path.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Save embeddings as numpy array
        np.savez_compressed(path, embeddings=self._get_matrix())

        logger.info(f"Saved vector store to {path}")

    def load(self, path: Path) -> None:
        """Load the store from disk."""
        try:
            # Load chunks and metadata
            json_path = path.with_suffix(".json")
            if json_path.exists():
                data = json.loads(json_path.read_text(encoding="utf-8"))
                self.chunks = data.get("chunks", [])
                self.metadata = data.get("metadata", [])

            # Load embeddings
            if path.exists():
                with np.load(path) as loaded:
                    # Convert back to list of lists for consistency
                    matrix = loaded["embeddings"]
                    self.embeddings = matrix.tolist()
                    self._matrix = matrix

            logger.info(f"Loaded vector store from {path} ({len(self.chunks)} items)")
        except Exception as e:
            logger.error(f"Failed to load vector store from {path}: {e}")
            # Reset on failure
            self.embeddings = []
            self.chunks = []
            self.metadata = []
            self._matrix = None

    def search(self, query_vector: list[float], k: int = 5) -> list[SearchResult]:
        """
        Search for most similar chunks.

        Args:
            query_vector: The query embedding.
            k: Number of results to return.

        Returns:
            List of SearchResult objects.
        """
        if not self.chunks:
            return []

        matrix = self._get_matrix()
        if matrix.size == 0:
            return []

        # Convert query to numpy array
        query = np.array(query_vector, dtype=np.float32)

        # Normalize query vector
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Normalize matrix rows (if not already?)
        # For cosine similarity: dot product of normalized vectors
        # Let's assume we normalize on search for now to be safe

        norms = np.linalg.norm(matrix, axis=1)
        # Avoid division by zero
        norms[norms == 0] = 1e-10
        normalized_matrix = matrix / norms[:, np.newaxis]

        # Calculate cosine similarity
        similarities = np.dot(normalized_matrix, query)

        # Get top k indices
        # argsort sorts in ascending order, so take last k and reverse
        top_k_indices = np.argsort(similarities)[-k:][::-1]

        results = []
        for idx in top_k_indices:
            score = float(similarities[idx])
            results.append(
                SearchResult(
                    content=self.chunks[idx],
                    metadata=self.metadata[idx],
                    score=score,
                )
            )

        return results
