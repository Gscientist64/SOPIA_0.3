import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.router import get_ai_provider
from app.core.config import settings
from app.db.session import get_db
from app.rag.embeddings import get_embedding_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logger.error("Database health check failed: %s", exc)
        db_ok = False

    provider = get_ai_provider()
    provider_ok = getattr(provider, "health", lambda: None)()
    consistent, message = get_embedding_service().check_consistency() if provider_ok else (False, "provider unavailable")

    return {
        "status": "ok" if db_ok and provider_ok and consistent else "degraded",
        "database": "ok" if db_ok else "unavailable",
        "ai_provider": provider.name,
        "ai_available": bool(provider_ok),
        "embedding_ok": consistent,
        "embedding_detail": message,
        "embedding_dim": settings.EMBEDDING_DIM,
    }


@router.get("/provider")
def provider_info():
    provider = get_ai_provider()
    return {
        "provider": provider.name,
        "configured_provider": settings.AI_PROVIDER,
        "chat_model": getattr(provider, "model", None),
        "embedding_model": getattr(provider, "embed_model", None),
        "embedding_dim": getattr(provider, "embedding_dim", settings.EMBEDDING_DIM),
        "gemini_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here"),
    }
