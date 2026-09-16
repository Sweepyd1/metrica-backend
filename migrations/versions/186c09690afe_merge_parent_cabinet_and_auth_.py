"""merge parent cabinet and auth identities heads

Revision ID: 186c09690afe
Revises: ab12cd34ef56, f6a7b8c9d0e1
Create Date: 2026-09-16 14:06:53.634647

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '186c09690afe'
down_revision: Union[str, Sequence[str], None] = ('ab12cd34ef56', 'f6a7b8c9d0e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
