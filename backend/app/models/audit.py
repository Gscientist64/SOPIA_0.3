from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String)
    entity_id = Column(Integer)
    detail = Column(Text)
    ip_address = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AIProviderLog(Base):
    __tablename__ = "ai_provider_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)
    model = Column(String)
    operation = Column(String, nullable=False)
    mode = Column(String)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    latency_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
