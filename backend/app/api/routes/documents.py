from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.document import (
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentVersion,
    ProcessingStatus,
)
from app.rag.ingestion import ingest_document_version
from app.schemas.documents import (
    DocumentDetailOut,
    DocumentOut,
    DocumentUpdate,
    DocumentVersionOut,
    VersionCreateOut,
)
from app.services import documents as doc_service
from app.services.audit import log_audit

router = APIRouter()


def _get_document_for_user(db: Session, document_id: int, user) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if user.organization_id is not None and document.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("/upload", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    admin: AdminUser,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    department: str | None = Form(None),
    doc_type: str | None = Form(None),
    version_label: str = Form("1.0"),
    effective_date: date | None = Form(None),
    review_date: date | None = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a new SOP/document. Administrators only."""
    document = doc_service.create_document(
        db,
        admin,
        file,
        title=title,
        description=description,
        category=category,
        department=department,
        doc_type=doc_type,
        version_label=version_label,
        effective_date=effective_date,
        review_date=review_date,
    )
    log_audit(
        db,
        action="document.upload",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail=f"{document.title} v{version_label}",
    )
    db.refresh(document)
    return document


@router.get("/", response_model=list[DocumentOut])
def list_documents(
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    status_filter: str | None = None,
    department: str | None = None,
    doc_type: str | None = None,
):
    query = db.query(Document)
    if current_user.organization_id is not None:
        query = query.filter(Document.organization_id == current_user.organization_id)
    if not current_user.is_admin:
        query = query.filter(Document.status == DocumentStatus.ACTIVE)
    if status_filter:
        query = query.filter(Document.status == status_filter)
    if department:
        query = query.filter(Document.department == department)
    if doc_type:
        query = query.filter(Document.doc_type == doc_type)
    return query.order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    document = _get_document_for_user(db, document_id, current_user)
    if not current_user.is_admin and document.status != DocumentStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    document = _get_document_for_user(db, document_id, admin)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(document, field, value)
    db.commit()
    db.refresh(document)
    log_audit(db, "document.update", admin, "document", document.id)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    document = _get_document_for_user(db, document_id, admin)
    doc_service.delete_document(db, document)
    log_audit(db, "document.delete", admin, "document", document_id)
    return None


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut])
def list_versions(document_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    document = _get_document_for_user(db, document_id, current_user)
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.created_at.desc())
        .all()
    )


@router.post("/{document_id}/versions", response_model=VersionCreateOut)
def add_version(
    document_id: int,
    admin: AdminUser,
    file: UploadFile = File(...),
    version_label: str = Form(...),
    effective_date: date | None = Form(None),
    review_date: date | None = Form(None),
    activate: bool = Form(True),
    db: Session = Depends(get_db),
):
    document = _get_document_for_user(db, document_id, admin)
    version = doc_service.add_version(
        db,
        admin,
        document,
        file,
        version_label=version_label,
        effective_date=effective_date,
        review_date=review_date,
        activate=activate,
    )
    log_audit(db, "document.version.add", admin, "document_version", version.id, version_label)
    return VersionCreateOut(
        document_id=document.id,
        version_id=version.id,
        version_label=version.version_label,
        processing_status=version.processing_status,
        chunk_count=version.chunk_count,
    )


@router.post("/{document_id}/versions/{version_id}/activate", response_model=DocumentOut)
def activate_version(
    document_id: int, version_id: int, admin: AdminUser, db: Session = Depends(get_db)
):
    document = _get_document_for_user(db, document_id, admin)
    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.id == version_id, DocumentVersion.document_id == document.id)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    if version.processing_status != ProcessingStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only a successfully processed version can be activated.",
        )
    doc_service.set_active_version(db, document, version)
    log_audit(db, "document.version.activate", admin, "document_version", version.id)
    return document


@router.post("/{document_id}/reprocess", response_model=VersionCreateOut)
def reprocess_document(document_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    document = _get_document_for_user(db, document_id, admin)
    version = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id, DocumentVersion.is_active.is_(True))
        .first()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active version")
    ingest_document_version(db, version)
    db.refresh(version)
    return VersionCreateOut(
        document_id=document.id,
        version_id=version.id,
        version_label=version.version_label,
        processing_status=version.processing_status,
        chunk_count=version.chunk_count,
    )


@router.get("/chunks/{chunk_id}")
def get_chunk_source(chunk_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    """Return a single chunk's content so the UI can show the cited source."""
    chunk = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
    if chunk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    if (
        current_user.organization_id is not None
        and chunk.organization_id != current_user.organization_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    document = db.query(Document).filter(Document.id == chunk.document_id).first()
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "document_title": document.title if document else None,
        "section": chunk.section,
        "heading": chunk.heading,
        "page": chunk.page_number,
        "content": chunk.content,
    }


