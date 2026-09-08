"""Add Stage 3C concept-snapshot challenge identity."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_01"
down_revision: str | None = "20260907_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = sa.text(
    "task_type = 'challenge_concept' " "AND status IN ('pending', 'running', 'succeeded')"
)


def upgrade() -> None:
    op.add_column(
        "ai_executions", sa.Column("input_fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_index(
        "uq_ai_challenge_snapshot_active_or_succeeded",
        "ai_executions",
        ["origin_type", "origin_id", "task_type", "input_fingerprint"],
        unique=True,
        postgresql_where=_WHERE,
        sqlite_where=_WHERE,
    )
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION prevent_terminal_ai_challenge_mutation()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.task_type = 'challenge_concept'
                   AND OLD.status IN ('succeeded', 'failed') THEN
                    RAISE EXCEPTION 'Completed AI challenge executions are immutable';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER ai_challenge_executions_immutable
            BEFORE UPDATE OR DELETE ON ai_executions
            FOR EACH ROW EXECUTE FUNCTION prevent_terminal_ai_challenge_mutation();
            """
        )
    elif dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"""
                CREATE TRIGGER ai_challenge_executions_immutable_{action.lower()}
                BEFORE {action} ON ai_executions
                WHEN OLD.task_type = 'challenge_concept'
                  AND OLD.status IN ('succeeded', 'failed')
                BEGIN
                    SELECT RAISE(ABORT, 'Completed AI challenge executions are immutable');
                END;
                """
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER ai_challenge_executions_immutable ON ai_executions")
        op.execute("DROP FUNCTION prevent_terminal_ai_challenge_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER ai_challenge_executions_immutable_update")
        op.execute("DROP TRIGGER ai_challenge_executions_immutable_delete")
    op.drop_index("uq_ai_challenge_snapshot_active_or_succeeded", table_name="ai_executions")
    op.drop_column("ai_executions", "input_fingerprint")
