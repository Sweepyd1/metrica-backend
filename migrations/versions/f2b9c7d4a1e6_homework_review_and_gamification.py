"""homework review and gamification

Revision ID: f2b9c7d4a1e6
Revises: d0e465947d8d
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2b9c7d4a1e6"
down_revision: Union[str, Sequence[str], None] = "d0e465947d8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tutor_student",
        sa.Column(
            "star_rewards_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("tutor_student", sa.Column("star_goal", sa.Float(), nullable=True))
    op.add_column(
        "tutor_student",
        sa.Column("star_reward_title", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "lesson_file", sa.Column("checked_file_id", sa.Integer(), nullable=True)
    )
    op.add_column("lesson_file", sa.Column("grade", sa.Float(), nullable=True))
    op.add_column(
        "lesson_file",
        sa.Column(
            "stars_awarded",
            sa.Float(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_lesson_file_checked_file_id_file",
        "lesson_file",
        "file",
        ["checked_file_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "bonus_task",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tutor_student_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stars", sa.Float(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "is_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tutor_student_id"], ["tutor_student.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("bonus_task")
    op.drop_constraint(
        "fk_lesson_file_checked_file_id_file", "lesson_file", type_="foreignkey"
    )
    op.drop_column("lesson_file", "stars_awarded")
    op.drop_column("lesson_file", "grade")
    op.drop_column("lesson_file", "checked_file_id")
    op.drop_column("tutor_student", "star_reward_title")
    op.drop_column("tutor_student", "star_goal")
    op.drop_column("tutor_student", "star_rewards_enabled")
