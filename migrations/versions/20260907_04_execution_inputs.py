"""Persist frozen AI generation input provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_04"
down_revision: str | None = "20260907_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_executions", sa.Column("input_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_executions", "input_snapshot")
