"""Prevent concurrent or repeated successful Generate-12 batches per creative run."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_05"
down_revision: str | None = "20260907_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = sa.text(
    "task_type = 'generate_collisions' AND status IN ('pending', 'running', 'succeeded')"
)


def upgrade() -> None:
    op.create_index(
        "uq_ai_generate_active_or_succeeded",
        "ai_executions",
        ["origin_type", "origin_id", "task_type"],
        unique=True,
        postgresql_where=_WHERE,
        sqlite_where=_WHERE,
    )


def downgrade() -> None:
    op.drop_index("uq_ai_generate_active_or_succeeded", table_name="ai_executions")
