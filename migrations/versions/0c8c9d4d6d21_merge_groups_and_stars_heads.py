"""merge groups and stars heads

Revision ID: 0c8c9d4d6d21
Revises: 9d6b3c4a7f12, d0e465947d8d
Create Date: 2026-04-06 12:00:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "0c8c9d4d6d21"
down_revision: Union[str, Sequence[str], None] = ("9d6b3c4a7f12", "d0e465947d8d")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
