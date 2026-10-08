"""Document / SOP lifecycle service."""

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentStatus,
    DocumentVersion,
    ProcessingStatus,
)
from app.models.user import User
from app.rag.ingestion import ingest_document_version
from app.services.storage import save_upload

logger = logging.getLogger(__name__)


def create_document(
    db: Session,
    user: User,
    file,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    department: str | None = None,
    doc_type: str | None = None,
    version_label: str = "1.0",
    effective_date: date | None = None,
    review_date: date | None = None,
) -> Document:
    """Create a document + its first version, then run ingestion."""
    path, size = save_upload(file)

    document = Document(
        title=(title or file.filename or "Untitled document"),
        description=description,
        category=category,
        department=department,
        doc_type=doc_type or (file.filename or "").rsplit(".", 1)[-1].lower(),
        status=DocumentStatus.PROCESSING,
        organization_id=user.organization_id,
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.flush()

    version = DocumentVersion(
        document_id=document.id,
        organization_id=user.organization_id,
        version_label=version_label or "1.0",
        is_active=True,
        processing_status=ProcessingStatus.PENDING,
        effective_date=effective_date,
        review_date=review_date,
        file_path=path,
        original_filename=file.filename,
        file_size=size,
        created_by_id=user.id,
    )
    db.add(version)
    db.flush()

    document.active_version_id = version.id
    db.commit()
    db.refresh(document)
    db.refresh(version)

    ingest_document_version(db, version)
    db.refresh(document)
    return document


def add_version(
    db: Session,
    user: User,
    document: Document,
    file,
    version_label: str,
    effective_date: date | None = None,
    review_date: date | None = None,
    activate: bool = True,
) -> DocumentVersion:
    """Attach a new version to an existing document and ingest it."""
    path, size = save_upload(file)
    version = DocumentVersion(
        document_id=document.id,
        organization_id=document.organization_id,
        version_label=version_label,
        is_active=False,
        processing_status=ProcessingStatus.PENDING,
        effective_date=effective_date,
        review_date=review_date,
        file_path=path,
        original_filename=file.filename,
        file_size=size,
        created_by_id=user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    ingest_document_version(db, version)

    if activate:
        set_active_version(db, document, version)
    db.refresh(version)
    return version


def set_active_version(db: Session, document: Document, version: DocumentVersion) -> Document:
    """Mark ``version`` active and all sibling versions inactive."""
    db.query(DocumentVersion).filter(
        DocumentVersion.document_id == document.id
    ).update({DocumentVersion.is_active: False}, synchronize_session=False)
    version.is_active = True
    document.active_version_id = version.id
    if document.status != DocumentStatus.PROCESSING:
        document.status = DocumentStatus.ACTIVE
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: Document) -> None:
    db.delete(document)
    db.commit()
