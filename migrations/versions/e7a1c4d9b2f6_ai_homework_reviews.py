"""AI homework reviews

Revision ID: e7a1c4d9b2f6
Revises: c9e4a7b1d2f8
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a1c4d9b2f6"
down_revision: Union[str, Sequence[str], None] = "c9e4a7b1d2f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ai_review_status = sa.Enum(
        "PENDING", "RUNNING", "COMPLETED", "FAILED", name="ai_review_status"
    )

    op.create_table(
        "ai_homework_review",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "lesson_id",
            sa.Integer(),
            sa.ForeignKey("lesson.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "tutor_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", ai_review_status, nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("reserved_task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
    )
    op.create_index(
        "ix_ai_review_student_usage_date",
        "ai_homework_review",
        ["student_id", "usage_date"],
    )

    op.create_table(
        "ai_homework_task",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "review_id",
            sa.Integer(),
            sa.ForeignKey("ai_homework_review.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("task_label", sa.Text(), nullable=False),
        sa.Column("transcription", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("task_types", sa.JSON(), nullable=False),
        sa.Column("topic_groups", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ai_task_review_position", "ai_homework_task", ["review_id", "position"])


def downgrade() -> None:
    op.drop_index("ix_ai_task_review_position", table_name="ai_homework_task")
    op.drop_table("ai_homework_task")
    op.drop_index("ix_ai_review_student_usage_date", table_name="ai_homework_review")
    op.drop_table("ai_homework_review")
    sa.Enum(name="ai_review_status").drop(op.get_bind(), checkfirst=True)
