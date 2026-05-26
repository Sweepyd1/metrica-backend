"""submission created at

Revision ID: b8c2f1a9d4e7
Revises: a7d9b2c4e8f1
Create Date: 2026-05-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c2f1a9d4e7"
down_revision: Union[str, Sequence[str], None] = "a7d9b2c4e8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lesson_file",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("lesson_file", "created_at")
