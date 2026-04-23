"""add parent chat messages

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-04-23 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


parent_chat_sender_role = postgresql.ENUM(
    "PARENT",
    "TUTOR",
    name="parent_chat_sender_role",
    create_constraint=True,
)

parent_chat_sender_role_existing = postgresql.ENUM(
    "PARENT",
    "TUTOR",
    name="parent_chat_sender_role",
    create_type=False,
)


def upgrade() -> None:
    parent_chat_sender_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "parent_chat_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_access_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("sender_role", parent_chat_sender_role_existing, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_access_id"],
            ["parent_access.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_parent_chat_message_parent_access_id",
        "parent_chat_message",
        ["parent_access_id"],
        unique=False,
    )
    op.create_index(
        "ix_parent_chat_message_created_at",
        "parent_chat_message",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_parent_chat_message_created_at",
        table_name="parent_chat_message",
    )
    op.drop_index(
        "ix_parent_chat_message_parent_access_id",
        table_name="parent_chat_message",
    )
    op.drop_table("parent_chat_message")
    parent_chat_sender_role.drop(op.get_bind(), checkfirst=True)
