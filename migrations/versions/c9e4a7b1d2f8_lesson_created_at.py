"""lesson created at

Revision ID: c9e4a7b1d2f8
Revises: ab12cd34ef56
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9e4a7b1d2f8"
down_revision: Union[str, Sequence[str], None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lesson",
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Backfill: у существующих строк нет реального времени создания.
    # Используем детерминированный ПРОКСИ по возрастанию id (id — автоинкремент,
    # порядок создания = порядок id). Значения заведомо старше любых новых записей,
    # чтобы сортировка "новые сверху" оставалась корректной.
    op.execute(
        "UPDATE lesson "
        "SET created_at = TIMESTAMP '2000-01-01 00:00:00' + id * INTERVAL '1 second'"
    )


def downgrade() -> None:
    op.drop_column("lesson", "created_at")
