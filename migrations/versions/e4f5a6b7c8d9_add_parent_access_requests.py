"""add parent access requests

Revision ID: e4f5a6b7c8d9
Revises: c3f1d2e4a9b7
Create Date: 2026-04-22 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "c3f1d2e4a9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


parent_access_status = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="parent_access_status",
    create_constraint=True,
)

parent_access_status_existing = postgresql.ENUM(
    "PENDING",
    "APPROVED",
    "REJECTED",
    name="parent_access_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'PARENT'")

    parent_access_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "parent_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("tutor_student_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            parent_access_status_existing,
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column("request_message", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["tutor_student_id"],
            ["tutor_student.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_id",
            "tutor_student_id",
            name="uq_parent_access_parent_tutor_student",
        ),
    )
    op.create_index(
        "ix_parent_access_parent_id",
        "parent_access",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_parent_access_status",
        "parent_access",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_parent_access_tutor_student_id",
        "parent_access",
        ["tutor_student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_parent_access_tutor_student_id", table_name="parent_access")
    op.drop_index("ix_parent_access_status", table_name="parent_access")
    op.drop_index("ix_parent_access_parent_id", table_name="parent_access")
    op.drop_table("parent_access")
    parent_access_status.drop(op.get_bind(), checkfirst=True)
