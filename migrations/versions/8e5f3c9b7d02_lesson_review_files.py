"""Keep all reviewed attachments, including annotated photo copies (M-14)."""
from alembic import op
import sqlalchemy as sa

revision = "8e5f3c9b7d02"
down_revision = "7d4e2b8a6c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_review_file",
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lesson.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("file.id", ondelete="CASCADE"), primary_key=True),
    )
    op.execute("""INSERT INTO lesson_review_file (lesson_id, file_id)
        SELECT DISTINCT lesson_id, checked_file_id FROM lesson_file
        WHERE checked_file_id IS NOT NULL""")


def downgrade() -> None:
    op.drop_table("lesson_review_file")
