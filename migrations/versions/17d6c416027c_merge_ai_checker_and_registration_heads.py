"""merge ai checker and registration heads

Revision ID: 17d6c416027c
Revises: 9a3f5b7c1d2e, a3f7e9c1b6d4
Create Date: 2026-09-21 16:22:55.205977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17d6c416027c'
down_revision: Union[str, Sequence[str], None] = ('9a3f5b7c1d2e', 'a3f7e9c1b6d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
