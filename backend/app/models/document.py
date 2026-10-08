from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.db.base import Base


class DocumentStatus:
    DRAFT = "Draft"
    PROCESSING = "Processing"
    ACTIVE = "Active"
    ARCHIVED = "Archived"
    ERROR = "Error"


class ProcessingStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class Document(Base):
    """Logical document/SOP. Versions live in :class:`DocumentVersion`."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text)
    category = Column(String, index=True)
    department = Column(String, index=True)
    doc_type = Column(String)
    status = Column(String, default=DocumentStatus.DRAFT, nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"))
    active_version_id = Column(
        Integer, ForeignKey("document_versions.id", use_alter=True, name="fk_documents_active_version"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization", back_populates="documents")
    uploader = relationship("User", back_populates="documents")
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
    )
    active_version = relationship("DocumentVersion", foreign_keys=[active_version_id], post_update=True)

    @property
    def active_version_label(self) -> str | None:
        return self.active_version.version_label if self.active_version else None


class DocumentVersion(Base):
    """A single immutable upload of a document, e.g. version "3.2"."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_label", name="uq_document_version_label"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    version_label = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False, index=True)
    processing_status = Column(String, default=ProcessingStatus.PENDING, nullable=False)
    processing_error = Column(Text)
    effective_date = Column(Date)
    review_date = Column(Date)
    file_path = Column(String, nullable=False)
    original_filename = Column(String)
    file_size = Column(Integer)
    page_count = Column(Integer)
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    document = relationship("Document", back_populates="versions", foreign_keys=[document_id])
    chunks = relationship(
        "DocumentChunk", back_populates="version", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """A retrievable slice of a document version, with a pgvector embedding."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    document_version_id = Column(
        Integer, ForeignKey("document_versions.id"), nullable=False, index=True
    )
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    content = Column(Text, nullable=False)
    section = Column(String)
    heading = Column(String)
    page_number = Column(Integer)
    chunk_index = Column(Integer, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document")
    version = relationship("DocumentVersion", back_populates="chunks")


