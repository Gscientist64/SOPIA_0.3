"""Shared SOP grounding for generated content.

Quiz, exam and interview questions are authored by the model, so they need the
same grounding the SOP answers get: a model working from its own general
knowledge will happily write questions — and mark "correct" answers — that
contradict the organisation's approved procedures.

This module is the single retrieval entry point for generated content. Keeping it
in one place means the routes stay declarative, and it gives tests a single seam
to stub (the vector search itself is PostgreSQL-specific and cannot run on the
SQLite database the unit tests use).
"""

import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.rag.retrieval import RetrievedChunk, build_context, retrieve

logger = logging.getLogger(__name__)

NO_CONTEXT_DETAIL = (
    "No approved SOP content matches this topic, so questions cannot be generated "
    "from your organisation's documents. Add or select a relevant SOP document, or "
    "try a different topic."
)


class NoSOPContextError(RuntimeError):
    """Raised when the knowledge base holds nothing relevant to ground a request."""


def retrieve_grounding(
    query: str,
    db: Session,
    user: User | None = None,
    organization_id: int | None = None,
) -> list[RetrievedChunk]:
    """Retrieve the SOP excerpts relevant to ``query``.

    Only the active version of Active documents in the caller's organisation can
    match, exactly as for question answering.
    """
    return retrieve(query, db=db, user=user, organization_id=organization_id)


def require_grounding(
    query: str,
    db: Session,
    user: User | None = None,
    organization_id: int | None = None,
) -> tuple[list[RetrievedChunk], str]:
    """Return ``(results, context_block)`` or raise :class:`NoSOPContextError`.

    Generated questions must be traceable to a source, so a topic the knowledge
    base cannot support is an error rather than a silent fallback to the model's
    own knowledge.
    """
    results = retrieve_grounding(query, db=db, user=user, organization_id=organization_id)
    if not results:
        logger.info("No SOP grounding found for query %r", query[:120])
        raise NoSOPContextError(NO_CONTEXT_DETAIL)
    return results, build_context(results)
