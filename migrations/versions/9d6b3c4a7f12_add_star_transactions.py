"""add star transactions

Revision ID: 9d6b3c4a7f12
Revises: 06eed1450efa
Create Date: 2026-03-31 15:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d6b3c4a7f12"
down_revision: Union[str, Sequence[str], None] = "06eed1450efa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tutor_student",
        sa.Column("star_balance", sa.Integer(), server_default="0", nullable=False),
    )

    op.create_table(
        "star_transaction",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tutor_student_id", sa.Integer(), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "ACCRUAL",
                "WRITE_OFF",
                name="star_transaction_type",
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lesson.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tutor_student_id"], ["tutor_student.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_star_transaction_tutor_student_id",
        "star_transaction",
        ["tutor_student_id"],
        unique=False,
    )
    op.create_index(
        "ix_star_transaction_lesson_id",
        "star_transaction",
        ["lesson_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_star_transaction_lesson_id", table_name="star_transaction")
    op.drop_index(
        "ix_star_transaction_tutor_student_id", table_name="star_transaction"
    )
    op.drop_table("star_transaction")
    op.drop_column("tutor_student", "star_balance")

    star_transaction_type = sa.Enum(
        "ACCRUAL",
        "WRITE_OFF",
        name="star_transaction_type",
        create_constraint=True,
    )
    star_transaction_type.drop(op.get_bind(), checkfirst=True)
