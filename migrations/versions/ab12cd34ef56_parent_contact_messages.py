"""parent contact messages

Revision ID: ab12cd34ef56
Revises: f6c9d3e8a5b2
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab12cd34ef56"
down_revision: Union[str, Sequence[str], None] = "f6c9d3e8a5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lesson_file_kind ADD VALUE IF NOT EXISTS 'PARENT_MESSAGE'")
    op.add_column(
        "tutor_student",
        sa.Column("parent_contact_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("lesson", sa.Column("parent_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson", "parent_comment")
    op.drop_column("tutor_student", "parent_contact_enabled")
