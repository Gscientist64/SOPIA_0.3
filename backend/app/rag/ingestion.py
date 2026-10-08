"""Document ingestion: extract -> chunk -> embed -> persist."""

import logging

from sqlalchemy.orm import Session

from app.ai.base import AIProviderError
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ProcessingStatus,
)
from app.rag.chunking import Chunk, chunk_blocks
from app.rag.embeddings import EmbeddingError, get_embedding_service
from app.rag.extractors import extract_blocks

logger = logging.getLogger(__name__)

# Chunks are committed in batches so a long ingestion never holds one transaction
# open for minutes. Managed Postgres (e.g. Neon) closes idle-in-transaction
# connections, which would otherwise abort the whole run at the final commit.
_COMMIT_BATCH = 50
# Chunks are embedded in batches: one request per chunk is far slower than the
# provider needs to be.
_EMBED_BATCH = 32


def ingest_document_version(db: Session, version: DocumentVersion) -> Document:
    """Process ``version`` end-to-end and update processing status.

    Any failure is recorded on the version rather than raised, so a bad upload
    never crashes the request or leaves the document half-indexed.
    """
    document = db.query(Document).filter(Document.id == version.document_id).first()
    if document is None:
        raise ValueError(f"Document {version.document_id} not found")

    version.processing_status = ProcessingStatus.PROCESSING
    version.processing_error = None
    db.commit()

    try:
        blocks, page_count = extract_blocks(version.file_path, _extension(version))
        if not blocks:
            raise ValueError("No extractable text found in document.")

        chunks = chunk_blocks(blocks)
        if not chunks:
            raise ValueError("Document produced no chunks.")

        # Re-ingestion safety: replace any previous chunks for this version.
        db.query(DocumentChunk).filter(
            DocumentChunk.document_version_id == version.id
        ).delete(synchronize_session=False)
        db.commit()

        embedder = get_embedding_service()
        stored = 0
        for start in range(0, len(chunks), _EMBED_BATCH):
            batch = chunks[start : start + _EMBED_BATCH]
            try:
                vectors: list[list[float] | None] = embedder.embed_many(
                    [chunk.content for chunk in batch]
                )
            except EmbeddingError as exc:
                # One bad chunk must not cost us the whole batch.
                logger.warning(
                    "Batch embedding failed (%s); retrying %d chunk(s) individually.",
                    exc,
                    len(batch),
                )
                vectors = _embed_individually(embedder, batch)

            for chunk, vector in zip(batch, vectors):
                if vector is None:
                    if stored == 0:
                        raise EmbeddingError(
                            "The embedding provider could not embed the first chunks "
                            "of this document."
                        )
                    continue
                db.add(
                    DocumentChunk(
                        document_id=document.id,
                        document_version_id=version.id,
                        organization_id=version.organization_id,
                        content=chunk.content,
                        section=_truncate(chunk.section),
                        heading=_truncate(chunk.heading),
                        page_number=chunk.page_number,
                        chunk_index=chunk.chunk_index,
                        embedding=vector,
                    )
                )
                stored += 1
                if stored % _COMMIT_BATCH == 0:
                    db.commit()

        version.page_count = page_count
        version.chunk_count = stored
        version.embedding_model = embedder.model_name
        version.processing_status = ProcessingStatus.READY
        if version.is_active:
            document.status = DocumentStatus.ACTIVE
        db.commit()
        db.refresh(document)
        logger.info(
            "Ingested document=%s version=%s chunks=%s", document.id, version.id, stored
        )
    except (EmbeddingError, AIProviderError) as exc:
        _mark_error(db, version, document, f"AI provider error: {exc}")
    except Exception as exc:  # noqa: BLE001 - record, never crash
        logger.exception("Ingestion failed for version %s", version.id)
        _mark_error(db, version, document, str(exc))

    return document


def _mark_error(db: Session, version: DocumentVersion, document: Document, message: str) -> None:
    # The session may be in a failed state (or holding a dead connection); clear
    # it first so the error itself can be persisted instead of raising again and
    # leaving the version stuck in "processing".
    db.rollback()
    version.processing_status = ProcessingStatus.ERROR
    version.processing_error = message[:2000]
    document.status = DocumentStatus.ERROR
    db.commit()


def _embed_individually(
    embedder, chunks: list[Chunk]
) -> list[list[float] | None]:
    """Embed chunk by chunk, returning ``None`` for any chunk that fails."""
    vectors: list[list[float] | None] = []
    for chunk in chunks:
        try:
            vectors.append(embedder.embed(chunk.content))
        except EmbeddingError as exc:
            logger.warning("Skipping chunk %s after embedding error: %s", chunk.chunk_index, exc)
            vectors.append(None)
    return vectors


def _extension(version: DocumentVersion) -> str:
    name = version.original_filename or version.file_path
    return name.rsplit(".", 1)[-1].lower()


def _truncate(value: str | None, limit: int = 255) -> str | None:
    if value is None:
        return None
    return value[:limit]


