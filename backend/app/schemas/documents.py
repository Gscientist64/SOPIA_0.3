from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_label: str
    is_active: bool
    processing_status: str
    processing_error: str | None = None
    effective_date: date | None = None
    review_date: date | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    original_filename: str | None = None
    created_at: datetime | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    category: str | None = None
    department: str | None = None
    doc_type: str | None = None
    status: str
    organization_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    active_version_label: str | None = None


class DocumentDetailOut(DocumentOut):
    versions: list[DocumentVersionOut] = []


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    category: str | None = None
    department: str | None = None
    doc_type: str | None = None
    status: str | None = None


class VersionCreateOut(BaseModel):
    document_id: int
    version_id: int
    version_label: str
    processing_status: str
    chunk_count: int | None = None
