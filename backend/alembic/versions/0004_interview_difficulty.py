"""Interview questions gain a difficulty, so the interview can escalate.

Practice is more useful when it builds: a warm-up the candidate can settle into,
then increasingly demanding questions. Storing the difficulty per question (rather
than inferring it from the order) means the escalation is real and visible, and
survives reloading a session.

Revision ID: 0004_interview_difficulty
Revises: 0003_question_sources
Create Date: 2026-10-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_interview_difficulty"
down_revision: Union[str, None] = "0003_question_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "interview_questions",
        sa.Column("difficulty", sa.String(), nullable=False, server_default="medium"),
    )


def downgrade() -> None:
    op.drop_column("interview_questions", "difficulty")
