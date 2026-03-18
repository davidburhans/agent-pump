import logging

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """Service for generating text embeddings using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the service.

        Args:
            model_name: Name of the Hugging Face model to use.
        """
        self.model_name = model_name
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to load embedding model {self.model_name}: {e}")
                # Fallback or raise? For now raise.
                raise
        return self._model

    def generate_embeddings(self, text: str) -> list[float]:
        """
        Generate embeddings for a given text.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        try:
            # Generate embedding as numpy array
            embedding = self.model.encode(text, convert_to_numpy=True)

            # Convert to standard list for JSON serialization compatibility if needed,
            # though vector store handles numpy.
            if isinstance(embedding, np.ndarray):
                return embedding.tolist()
            return embedding  # type: ignore
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []
