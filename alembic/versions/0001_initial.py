"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Prefer metadata create for SQLite/Postgres parity in MVP.
    from pokequant.db.base import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from pokequant.db.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
