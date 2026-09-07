"""Stage 3A AI execution foundation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_02"
down_revision: str | None = "20260907_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_executions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("origin_type", sa.String(length=80), nullable=False),
        sa.Column("origin_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("request_id", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_ai_execution_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_ai_execution_idempotency", "ai_executions", ["idempotency_key"], unique=True
    )
    op.create_index("ix_ai_execution_origin", "ai_executions", ["origin_type", "origin_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_execution_origin", table_name="ai_executions")
    op.drop_index("uq_ai_execution_idempotency", table_name="ai_executions")
    op.drop_table("ai_executions")
