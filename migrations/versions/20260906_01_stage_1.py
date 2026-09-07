"""Stage 1 foundation.

Revision ID: 20260906_01
Revises:
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "operator_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operator_sessions_expires_at", "operator_sessions", ["expires_at"])
    op.create_index(
        "ix_operator_sessions_token_hash", "operator_sessions", ["token_hash"], unique=True
    )
    op.create_table(
        "truth_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_at IS NULL) OR "
            "(status = 'approved' AND approved_at IS NOT NULL)",
            name="ck_truth_approval_timestamp",
        ),
        sa.CheckConstraint("status IN ('draft', 'approved')", name="ck_truth_status"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_truth_product_status", "truth_versions", ["product_id", "status"])
    op.create_index(
        "uq_truth_product_version", "truth_versions", ["product_id", "version"], unique=True
    )
    op.create_index(
        "uq_truth_one_draft_per_product",
        "truth_versions",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("truth_version_id", sa.String(length=36), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["truth_version_id"], ["truth_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_approved_truth_mutation() RETURNS trigger AS $$
            BEGIN
                IF OLD.status = 'approved' THEN
                    RAISE EXCEPTION 'Approved Truth versions are immutable';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER truth_versions_immutable
            BEFORE UPDATE OR DELETE ON truth_versions
            FOR EACH ROW EXECUTE FUNCTION prevent_approved_truth_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS truth_versions_immutable ON truth_versions")
        op.execute("DROP FUNCTION IF EXISTS prevent_approved_truth_mutation()")
    op.drop_index("ix_audit_events_event_type", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_truth_one_draft_per_product", table_name="truth_versions")
    op.drop_index("uq_truth_product_version", table_name="truth_versions")
    op.drop_index("ix_truth_product_status", table_name="truth_versions")
    op.drop_table("truth_versions")
    op.drop_index("ix_operator_sessions_token_hash", table_name="operator_sessions")
    op.drop_index("ix_operator_sessions_expires_at", table_name="operator_sessions")
    op.drop_table("operator_sessions")
    op.drop_table("products")
