"""parent cabinet

Revision ID: a7d9b2c4e8f1
Revises: f2b9c7d4a1e6
Create Date: 2026-05-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7d9b2c4e8f1"
down_revision: Union[str, Sequence[str], None] = "f2b9c7d4a1e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PARENT'")
    op.create_table(
        "parent_student",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("parent_student")
