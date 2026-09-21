"""add telegram auth sessions

Revision ID: c3f1d2e4a9b7
Revises: b1d2e3f4a5b6
Create Date: 2026-04-09 15:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c3f1d2e4a9b7"
down_revision: Union[str, Sequence[str], None] = "b1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.String(length=64), nullable=False),
        sa.Column("confirmation_code", sa.String(length=16), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "TUTOR",
                "STUDENT",
                name="user_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_first_name", sa.String(length=255), nullable=True),
        sa.Column("telegram_last_name", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_token",
            name="uq_telegram_auth_sessions_session_token",
        ),
    )
    op.create_index(
        "ix_telegram_auth_sessions_confirmation_code",
        "telegram_auth_sessions",
        ["confirmation_code"],
        unique=False,
    )
    op.create_index(
        "ix_telegram_auth_sessions_expires_at",
        "telegram_auth_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_auth_sessions_expires_at",
        table_name="telegram_auth_sessions",
    )
    op.drop_index(
        "ix_telegram_auth_sessions_confirmation_code",
        table_name="telegram_auth_sessions",
    )
    op.drop_table("telegram_auth_sessions")
