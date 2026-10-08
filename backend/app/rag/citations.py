"""Structured citation helpers.

Turns retrieval results into API-friendly citation dicts and persists them as
``Citation`` rows attached to an assistant message.
"""

import json

from sqlalchemy.orm import Session

from app.models.chat import Citation
from app.rag.retrieval import RetrievedChunk


def citation_to_dict(item: RetrievedChunk) -> dict:
    chunk = item.chunk
    return {
        "document_id": item.document.id,
        "document_version_id": item.version.id,
        "chunk_id": chunk.id,
        "document_title": item.document.title,
        "version": item.version.version_label,
        "section": chunk.section,
        "heading": chunk.heading,
        "page": chunk.page_number,
        "relevance": round(item.relevance, 4),
        "snippet": (chunk.content[:280] + "...") if len(chunk.content) > 280 else chunk.content,
    }


def build_citation_dicts(results: list[RetrievedChunk]) -> list[dict]:
    return [citation_to_dict(item) for item in results]


def persist_citations(db: Session, message_id: int, results: list[RetrievedChunk]) -> list[Citation]:
    """Persist citations for an assistant message and return them."""
    rows: list[Citation] = []
    for item in results:
        row = Citation(
            message_id=message_id,
            document_id=item.document.id,
            document_version_id=item.version.id,
            chunk_id=item.chunk.id,
            document_title=item.document.title,
            version_label=item.version.version_label,
            section=item.chunk.section,
            heading=item.chunk.heading,
            page_number=item.chunk.page_number,
            relevance=round(item.relevance, 4),
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def citations_to_dicts(citations: list[Citation]) -> list[dict]:
    return [
        {
            "document_id": c.document_id,
            "document_version_id": c.document_version_id,
            "chunk_id": c.chunk_id,
            "document_title": c.document_title,
            "version": c.version_label,
            "section": c.section,
            "heading": c.heading,
            "page": c.page_number,
            "relevance": c.relevance,
        }
        for c in citations
    ]


def sources_to_dicts(raw: str | None) -> list[dict]:
    """Parse the JSON ``sources`` recorded on a generated question.

    Questions store the excerpts they were authored from as a JSON list, so a
    generated question can always be traced back to the responsible SOP.
    """
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []
