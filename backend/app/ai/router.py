from functools import lru_cache

from app.ai.base import AIProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.local_llm import LocalLLMProvider
from app.core.config import settings

_PROVIDERS: dict[str, type[AIProvider]] = {
    "local": LocalLLMProvider,
    "gemini": GeminiProvider,
}


@lru_cache(maxsize=None)
def get_ai_provider() -> AIProvider:
    """Return the configured AI provider (cached singleton).

    Switching providers is a configuration-only concern: set ``AI_PROVIDER``
    to ``local`` or ``gemini`` and the rest of the app is unaffected.
    """
    provider_cls = _PROVIDERS.get(settings.AI_PROVIDER.lower())
    if provider_cls is None:
        raise ValueError(
            f"Unknown AI_PROVIDER '{settings.AI_PROVIDER}'. "
            f"Valid options: {', '.join(_PROVIDERS)}."
        )
    return provider_cls()


def get_embedding_provider() -> AIProvider:
    """Provider used for embeddings (same instance as the chat provider)."""
    return get_ai_provider()

