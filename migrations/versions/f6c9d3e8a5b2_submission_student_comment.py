"""submission student comment

Revision ID: f6c9d3e8a5b2
Revises: e5b8c2d7f4a1
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6c9d3e8a5b2"
down_revision: Union[str, Sequence[str], None] = "e5b8c2d7f4a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lesson_file", sa.Column("student_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson_file", "student_comment")
