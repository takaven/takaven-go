"""Stage 3B AI collision provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_03"
down_revision: str | None = "20260907_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("concepts") as batch:
        batch.add_column(sa.Column("ai_execution_id", sa.String(length=36), nullable=True))
        batch.add_column(
            sa.Column("claim_warnings", sa.JSON(), nullable=False, server_default=sa.text("'[]'"))
        )
        batch.create_foreign_key(
            "fk_concepts_ai_execution", "ai_executions", ["ai_execution_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("concepts") as batch:
        batch.drop_constraint("fk_concepts_ai_execution", type_="foreignkey")
        batch.drop_column("claim_warnings")
        batch.drop_column("ai_execution_id")
