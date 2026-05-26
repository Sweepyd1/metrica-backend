"""homework deadline missed flag

Revision ID: c3f6a8d2b9e1
Revises: b8c2f1a9d4e7
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3f6a8d2b9e1"
down_revision: Union[str, Sequence[str], None] = "b8c2f1a9d4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lesson_file",
        sa.Column(
            "deadline_missed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("lesson_file", "deadline_missed")
