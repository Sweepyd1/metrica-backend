"""lesson subject

Revision ID: e5b8c2d7f4a1
Revises: d4a1b7c9e2f3
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5b8c2d7f4a1"
down_revision: Union[str, Sequence[str], None] = "d4a1b7c9e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lesson", sa.Column("subject", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson", "subject")
