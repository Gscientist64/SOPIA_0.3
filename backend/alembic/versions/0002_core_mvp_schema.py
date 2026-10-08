"""Core MVP schema: versioning, chat persistence, learning, exams, interviews.

This revision supersedes the initial schema. At the time of writing the legacy
tables contained no rows (0 users, 0 chunks), so they are dropped and the full
MVP schema is created from the current SQLAlchemy models.

Revision ID: 0002_core_mvp
Revises: 1fa2007a34a1
Create Date: 2026-09-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_mvp"
down_revision: Union[str, None] = "1fa2007a34a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_TABLES = ("document_chunks", "documents", "users", "organizations")


def upgrade() -> None:
    bind = op.get_bind()

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Drop the pre-MVP schema (verified empty before this migration was authored).
    for table in _LEGACY_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP TYPE IF EXISTS roleenum CASCADE")

    # Import here so Alembic autogenerate/env import order stays clean.
    from app.db.base import Base
    import app.models  # noqa: F401  (ensures all models are registered)

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()

    from app.db.base import Base
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=bind)

    # Restore the legacy initial schema so downgrade returns to revision 1.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="organizations_name_key"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String()),
        sa.Column("role", sa.String()),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Integer()),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String()),
        sa.Column("department", sa.String()),
        sa.Column("doc_type", sa.String()),
        sa.Column("version", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.Column("file_path", sa.String(), nullable=False),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section", sa.String()),
        sa.Column("page_number", sa.Integer()),
        sa.Column("heading", sa.String()),
        sa.Column("chunk_index", sa.Integer()),
        sa.Column("embedding", sa.Text()),
    )
