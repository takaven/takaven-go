"""Stage 2 manual operator loop.

Revision ID: 20260907_01
Revises: 20260906_01
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_01"
down_revision: str | None = "20260906_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_events", sa.Column("subject_type", sa.String(length=80), nullable=True))
    op.add_column("audit_events", sa.Column("subject_id", sa.String(length=36), nullable=True))
    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("source", sa.String(length=300), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("audience", sa.String(length=500), nullable=False),
        sa.Column("tension_pain", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("product_relevance", sa.Text(), nullable=False),
        sa.Column("buying_trigger", sa.Text(), nullable=False),
        sa.Column("half_life", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'selected', 'used', 'archived')", name="ck_signal_status"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_product_status", "signals", ["product_id", "status"])
    op.create_table(
        "creative_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("truth_version_id", sa.String(length=36), nullable=False),
        sa.Column("truth_snapshot", sa.JSON(), nullable=False),
        sa.Column("whitespace_snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("closure_learning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'closed', 'abandoned')", name="ck_creative_run_status"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["truth_version_id"], ["truth_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "creative_run_signals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creative_run_id", sa.String(length=36), nullable=False),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("signal_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["creative_run_id"], ["creative_runs.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_run_signal", "creative_run_signals", ["creative_run_id", "signal_id"], unique=True
    )
    op.create_table(
        "concepts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("creative_run_id", sa.String(length=36), nullable=False),
        sa.Column("tension", sa.Text(), nullable=False),
        sa.Column("creative_mechanic", sa.Text(), nullable=False),
        sa.Column("artifact", sa.Text(), nullable=False),
        sa.Column("product_proof", sa.Text(), nullable=False),
        sa.Column("participation", sa.Text(), nullable=False),
        sa.Column("distribution", sa.Text(), nullable=False),
        sa.Column("commercial_bridge", sa.Text(), nullable=False),
        sa.Column("dangerous_assumption", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('rough', 'shortlisted', 'revise', 'killed', 'retained')",
            name="ck_concept_status",
        ),
        sa.ForeignKeyConstraint(["creative_run_id"], ["creative_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_concepts_run_status", "concepts", ["creative_run_id", "status"])
    op.create_table(
        "challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("concept_id", sa.String(length=36), nullable=False),
        sa.Column("gates", sa.JSON(), nullable=False),
        sa.Column("strongest_reason", sa.Text(), nullable=False),
        sa.Column("strongest_objection", sa.Text(), nullable=False),
        sa.Column("unsupported_claims", sa.Text(), nullable=False),
        sa.Column("unsupported_resolved", sa.Boolean(), nullable=False),
        sa.Column("smallest_repair", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "recommendation IN ('go', 'revise', 'kill')", name="ck_challenge_recommendation"
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id"),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("concept_id", sa.String(length=36), nullable=False),
        sa.Column("truth_version_id", sa.String(length=36), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("dangerous_assumption", sa.Text(), nullable=True),
        sa.Column("smoke_test", sa.Text(), nullable=True),
        sa.Column("seed_targets", sa.Text(), nullable=True),
        sa.Column("product_magic_moment", sa.Text(), nullable=True),
        sa.Column("measures", sa.Text(), nullable=True),
        sa.Column("success_thresholds", sa.Text(), nullable=True),
        sa.Column("thresholds_approved", sa.Boolean(), nullable=False),
        sa.Column("test_window", sa.String(length=300), nullable=True),
        sa.Column("execution_references", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("observed_facts", sa.Text(), nullable=True),
        sa.Column("interpretation", sa.Text(), nullable=True),
        sa.Column("final_decision", sa.String(length=20), nullable=True),
        sa.Column("final_reason", sa.Text(), nullable=True),
        sa.Column("postmortem", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'live', 'complete')", name="ck_experiment_status"
        ),
        sa.CheckConstraint(
            "final_decision IS NULL OR final_decision IN ('scale', 'revise', 'kill')",
            name="ck_experiment_final_decision",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts.id"]),
        sa.ForeignKeyConstraint(["truth_version_id"], ["truth_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id"),
    )
    op.create_index("ix_experiments_product_status", "experiments", ["product_id", "status"])
    op.create_table(
        "learnings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("experiment_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=100), nullable=True),
        sa.Column("qualification", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'approved')", name="ck_learning_status"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id"),
    )


def downgrade() -> None:
    op.drop_table("learnings")
    op.drop_index("ix_experiments_product_status", table_name="experiments")
    op.drop_table("experiments")
    op.drop_table("challenges")
    op.drop_index("ix_concepts_run_status", table_name="concepts")
    op.drop_table("concepts")
    op.drop_index("uq_run_signal", table_name="creative_run_signals")
    op.drop_table("creative_run_signals")
    op.drop_table("creative_runs")
    op.drop_index("ix_signals_product_status", table_name="signals")
    op.drop_table("signals")
    op.drop_column("audit_events", "subject_id")
    op.drop_column("audit_events", "subject_type")
