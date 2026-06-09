"""bonus task reward title

Revision ID: d4a1b7c9e2f3
Revises: c3f6a8d2b9e1
Create Date: 2026-05-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4a1b7c9e2f3"
down_revision: Union[str, Sequence[str], None] = "c3f6a8d2b9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bonus_task",
        sa.Column("reward_title", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bonus_task", "reward_title")
