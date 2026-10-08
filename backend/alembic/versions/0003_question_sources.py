"""Ground generated questions in their SOP sources.

Quiz and exam questions are authored from retrieved SOP excerpts, so each
question records which excerpts it was generated from. This lets the UI show the
responsible document alongside the question and its explanation.

Revision ID: 0003_question_sources
Revises: 0002_core_mvp
Create Date: 2026-10-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_question_sources"
down_revision: Union[str, None] = "0002_core_mvp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("sources", sa.Text(), nullable=True))
    op.add_column("interview_questions", sa.Column("sources", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_questions", "sources")
    op.drop_column("questions", "sources")
