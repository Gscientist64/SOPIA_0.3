"""Central embedding service.

All embedding generation in SOPIA goes through this module so that the
embedding model, its output dimension, and the pgvector column stay in sync.
"""

import logging

from app.ai.base import AIProvider, AIProviderError
from app.ai.router import get_embedding_provider
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when an embedding cannot be produced."""


class EmbeddingService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        if self._provider is None:
            self._provider = get_embedding_provider()
        return self._provider

    @property
    def dimension(self) -> int:
        """Dimension of the vectors produced by the active model."""
        return self.provider.embedding_dim

    @property
    def model_name(self) -> str:
        return getattr(self.provider, "embed_model", self.provider.name)

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError("Cannot embed empty text.")
        try:
            vector = self.provider.embed(text)
        except AIProviderError as exc:
            raise EmbeddingError(str(exc)) from exc
        if len(vector) != self.dimension:
            raise EmbeddingError(
                f"Embedding dimension mismatch: got {len(vector)}, expected {self.dimension}."
            )
        return vector

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        for text in texts:
            if not text or not text.strip():
                raise EmbeddingError("Cannot embed empty text.")
        try:
            vectors = self.provider.embed_batch(texts)
        except AIProviderError as exc:
            raise EmbeddingError(str(exc)) from exc
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingError(
                    f"Embedding dimension mismatch: got {len(vector)}, expected "
                    f"{self.dimension}."
                )
        return vectors

    def check_consistency(self) -> tuple[bool, str]:
        """Verify the model output matches the configured pgvector dimension."""
        try:
            probe = self.embed("dimension probe")
        except EmbeddingError as exc:
            return False, str(exc)
        if len(probe) != settings.EMBEDDING_DIM:
            return (
                False,
                f"Model '{self.model_name}' returns {len(probe)} dims but "
                f"EMBEDDING_DIM is {settings.EMBEDDING_DIM}.",
            )
        return True, f"OK ({len(probe)} dims via {self.model_name})"


def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
