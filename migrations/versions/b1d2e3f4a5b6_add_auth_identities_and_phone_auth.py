"""add auth identities and phone auth

Revision ID: b1d2e3f4a5b6
Revises: 0c8c9d4d6d21
Create Date: 2026-04-06 12:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "0c8c9d4d6d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


auth_provider = sa.Enum(
    "PASSWORD",
    "PHONE",
    "VK",
    "YANDEX",
    "TELEGRAM",
    name="auth_provider",
    create_constraint=True,
)


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_phone_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=200),
        nullable=True,
    )
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=200),
        nullable=True,
    )
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])

    op.create_table(
        "auth_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", auth_provider, nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=200), nullable=True),
        sa.Column("provider_phone", sa.String(length=32), nullable=True),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_auth_identity_provider_user_id"
        ),
    )

    op.create_table(
        "phone_auth_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("resend_available_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        """
        INSERT INTO auth_identities (
            user_id,
            provider,
            provider_user_id,
            provider_email,
            is_verified,
            created_at,
            last_login_at
        )
        SELECT
            id,
            'PASSWORD',
            email,
            email,
            true,
            now(),
            now()
        FROM users
        WHERE email IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("phone_auth_codes")
    op.drop_table("auth_identities")
    op.drop_constraint("uq_users_phone", "users", type_="unique")

    op.execute(
        """
        UPDATE users
        SET email = CONCAT('restored_user_', id, '@placeholder.local')
        WHERE email IS NULL
        """
    )
    op.execute("UPDATE users SET password = '__disabled__' WHERE password IS NULL")

    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=200),
        nullable=False,
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    op.drop_column("users", "is_phone_verified")
    op.drop_column("users", "is_email_verified")
    op.drop_column("users", "is_active")
    op.drop_column("users", "phone")

    auth_provider.drop(op.get_bind(), checkfirst=True)
