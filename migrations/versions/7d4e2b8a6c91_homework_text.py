"""Add optional homework text (M-03)."""
from alembic import op
import sqlalchemy as sa

revision = "7d4e2b8a6c91"
down_revision = "17d6c416027c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lesson", sa.Column("homework_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("lesson", "homework_text")
