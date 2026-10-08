from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class AIProviderError(RuntimeError):
    """Raised when an AI provider is unavailable or misconfigured."""


class AIProvider(ABC):
    """Abstract interface every AI provider must implement.

    The rest of the application depends only on this interface, never on a
    concrete provider, so providers can be swapped via configuration.
    """

    name: str = "base"

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimension of the vectors produced by :meth:`embed`."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> str:
        """Return a full (non-streamed) completion."""

    @abstractmethod
    def stream(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "",
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Yield incremental text chunks for a completion."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for ``text``."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed several texts. Providers may override for efficiency."""
        return [self.embed(t) for t in texts]

    @abstractmethod
    def evaluate_answer(self, question: str, answer: str, context: str = "") -> dict[str, Any]:
        """Return structured feedback for a user's answer."""

    def generate_questions(
        self, topic: str, count: int, difficulty: str = "medium", question_type: str = "mcq"
    ) -> list[dict[str, Any]]:
        """Generate practice/exam questions. Overridden by providers."""
        raise NotImplementedError


