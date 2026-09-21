"""AI progress report cache

Revision ID: a3f7e9c1b6d4
Revises: e7a1c4d9b2f6
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f7e9c1b6d4"
down_revision: Union[str, Sequence[str], None] = "e7a1c4d9b2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_progress_report_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("up_to_homework_count", sa.Integer(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "student_id", "up_to_homework_count", name="uq_ai_progress_student_upto"
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_progress_report_cache")
