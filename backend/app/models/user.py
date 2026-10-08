import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class RoleEnum(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    CONTENT_ADMIN = "CONTENT_ADMIN"
    USER = "USER"


# Roles allowed to manage documents / SOPs.
CONTENT_ROLES = (RoleEnum.SUPER_ADMIN, RoleEnum.CONTENT_ADMIN)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="organization")
    documents = relationship("Document", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default=RoleEnum.USER.value, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True, nullable=False)

    organization = relationship("Organization", back_populates="users")
    documents = relationship("Document", back_populates="uploader")
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    learning_sessions = relationship(
        "LearningSession", back_populates="user", cascade="all, delete-orphan"
    )

    # ------------------------------------------------------------------ helpers
    @property
    def is_admin(self) -> bool:
        return self.role in (RoleEnum.SUPER_ADMIN.value, RoleEnum.CONTENT_ADMIN.value)

    @property
    def is_super_admin(self) -> bool:
        return self.role == RoleEnum.SUPER_ADMIN.value


