from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ChatMode:
    SOP = "SOP_MODE"
    LEARNING = "LEARNING_MODE"
    EXAM = "EXAM_MODE"
    INTERVIEW = "INTERVIEW_MODE"
    RESEARCH = "RESEARCH_MODE"
    COMPARE = "COMPARE_MODE"

    ALL = (SOP, LEARNING, EXAM, INTERVIEW, RESEARCH, COMPARE)
    # Modes the backend can currently serve end-to-end.
    IMPLEMENTED = (SOP, LEARNING)


class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    title = Column(String, default="New conversation", nullable=False)
    mode = Column(String, default=ChatMode.SOP, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    mode = Column(String)
    provider = Column(String)
    error = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
    citations = relationship(
        "Citation", back_populates="message", cascade="all, delete-orphan"
    )


class Citation(Base):
    """A structured reference from an assistant message back to a source chunk."""

    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    document_version_id = Column(Integer, ForeignKey("document_versions.id"))
    chunk_id = Column(Integer, ForeignKey("document_chunks.id"))
    document_title = Column(String)
    version_label = Column(String)
    section = Column(String)
    heading = Column(String)
    page_number = Column(Integer)
    relevance = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message", back_populates="citations")
