"""email verification and invites

Revision ID: 9a3f5b7c1d2e
Revises: 186c09690afe
Create Date: 2026-09-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9a3f5b7c1d2e"
down_revision: Union[str, Sequence[str], None] = "186c09690afe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


invite_role = sa.Enum("STUDENT", "PARENT", name="invite_role")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "email_verification_token",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_email_verification_token_token"),
    )

    op.create_table(
        "invite",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("tutor_id", sa.Integer(), nullable=False),
        sa.Column("role", invite_role, nullable=False),
        sa.Column("tutor_student_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tutor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tutor_student_id"], ["tutor_student.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["used_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_invite_token"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("invite")
    invite_role.drop(op.get_bind(), checkfirst=True)
    op.drop_table("email_verification_token")
