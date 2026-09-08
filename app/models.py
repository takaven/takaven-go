import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class TruthStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class SignalStatus(StrEnum):
    NEW = "new"
    SELECTED = "selected"
    USED = "used"
    ARCHIVED = "archived"


class CreativeRunStatus(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    ABANDONED = "abandoned"


class ConceptStatus(StrEnum):
    ROUGH = "rough"
    SHORTLISTED = "shortlisted"
    REVISE = "revise"
    KILLED = "killed"
    RETAINED = "retained"


class GateVerdict(StrEnum):
    PASS = "pass"
    WEAK = "weak"
    FAIL = "fail"


class ChallengeRecommendation(StrEnum):
    GO = "go"
    REVISE = "revise"
    KILL = "kill"


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    LIVE = "live"
    COMPLETE = "complete"


class FinalDecision(StrEnum):
    SCALE = "scale"
    REVISE = "revise"
    KILL = "kill"


class LearningStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class AIExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AITaskType(StrEnum):
    GENERATE_COLLISIONS = "generate_collisions"
    CHALLENGE_CONCEPT = "challenge_concept"
    DRAFT_EXPERIMENT = "draft_experiment"
    DRAFT_LEARNING = "draft_learning"


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    truth_versions: Mapped[list["TruthVersion"]] = relationship(back_populates="product")
    signals: Mapped[list["Signal"]] = relationship(back_populates="product")
    creative_runs: Mapped[list["CreativeRun"]] = relationship(back_populates="product")
    experiments: Mapped[list["Experiment"]] = relationship(back_populates="product")


class TruthVersion(Base):
    __tablename__ = "truth_versions"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'approved')", name="ck_truth_status"),
        CheckConstraint(
            "(status = 'draft' AND approved_at IS NULL) OR "
            "(status = 'approved' AND approved_at IS NOT NULL)",
            name="ck_truth_approval_timestamp",
        ),
        Index("uq_truth_product_version", "product_id", "version", unique=True),
        Index("ix_truth_product_status", "product_id", "status"),
        Index(
            "uq_truth_one_draft_per_product",
            "product_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="truth_versions")


class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    truth_version_id: Mapped[str | None] = mapped_column(ForeignKey("truth_versions.id"))
    subject_type: Mapped[str | None] = mapped_column(String(80))
    subject_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (Index("ix_signals_product_status", "product_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(300), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2000))
    audience: Mapped[str] = mapped_column(String(500), nullable=False)
    tension_pain: Mapped[str] = mapped_column(Text, nullable=False)
    why_now: Mapped[str] = mapped_column(Text, nullable=False)
    product_relevance: Mapped[str] = mapped_column(Text, nullable=False)
    buying_trigger: Mapped[str] = mapped_column(Text, nullable=False)
    half_life: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SignalStatus.NEW)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    product: Mapped[Product] = relationship(back_populates="signals")


class CreativeRun(Base):
    __tablename__ = "creative_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    truth_version_id: Mapped[str] = mapped_column(ForeignKey("truth_versions.id"), nullable=False)
    truth_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    whitespace_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CreativeRunStatus.ACTIVE
    )
    closure_learning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="creative_runs")
    signals: Mapped[list["CreativeRunSignal"]] = relationship(
        back_populates="creative_run", cascade="all, delete-orphan"
    )
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="creative_run", cascade="all, delete-orphan"
    )


class CreativeRunSignal(Base):
    __tablename__ = "creative_run_signals"
    __table_args__ = (Index("uq_run_signal", "creative_run_id", "signal_id", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    creative_run_id: Mapped[str] = mapped_column(ForeignKey("creative_runs.id"), nullable=False)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.id"), nullable=False)
    signal_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)

    creative_run: Mapped[CreativeRun] = relationship(back_populates="signals")
    signal: Mapped[Signal] = relationship()


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (Index("ix_concepts_run_status", "creative_run_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    creative_run_id: Mapped[str] = mapped_column(ForeignKey("creative_runs.id"), nullable=False)
    ai_execution_id: Mapped[str | None] = mapped_column(ForeignKey("ai_executions.id"))
    claim_warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tension: Mapped[str] = mapped_column(Text, nullable=False)
    creative_mechanic: Mapped[str] = mapped_column(Text, nullable=False)
    artifact: Mapped[str] = mapped_column(Text, nullable=False)
    product_proof: Mapped[str] = mapped_column(Text, nullable=False)
    participation: Mapped[str] = mapped_column(Text, nullable=False)
    distribution: Mapped[str] = mapped_column(Text, nullable=False)
    commercial_bridge: Mapped[str] = mapped_column(Text, nullable=False)
    dangerous_assumption: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ConceptStatus.ROUGH)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    creative_run: Mapped[CreativeRun] = relationship(back_populates="concepts")
    challenge: Mapped["Challenge | None"] = relationship(back_populates="concept", uselist=False)
    experiment: Mapped["Experiment | None"] = relationship(back_populates="concept", uselist=False)


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), unique=True, nullable=False)
    gates: Mapped[dict] = mapped_column(JSON, nullable=False)
    strongest_reason: Mapped[str] = mapped_column(Text, nullable=False)
    strongest_objection: Mapped[str] = mapped_column(Text, nullable=False)
    unsupported_claims: Mapped[str] = mapped_column(Text, nullable=False)
    unsupported_resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
    smallest_repair: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    concept: Mapped[Concept] = relationship(back_populates="challenge")


class Experiment(Base):
    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiments_product_status", "product_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id"), unique=True, nullable=False)
    truth_version_id: Mapped[str] = mapped_column(ForeignKey("truth_versions.id"), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    dangerous_assumption: Mapped[str | None] = mapped_column(Text)
    smoke_test: Mapped[str | None] = mapped_column(Text)
    seed_targets: Mapped[str | None] = mapped_column(Text)
    product_magic_moment: Mapped[str | None] = mapped_column(Text)
    measures: Mapped[str | None] = mapped_column(Text)
    success_thresholds: Mapped[str | None] = mapped_column(Text)
    thresholds_approved: Mapped[bool] = mapped_column(nullable=False, default=False)
    test_window: Mapped[str | None] = mapped_column(String(300))
    execution_references: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ExperimentStatus.DRAFT)
    observed_facts: Mapped[str | None] = mapped_column(Text)
    interpretation: Mapped[str | None] = mapped_column(Text)
    final_decision: Mapped[str | None] = mapped_column(String(20))
    final_reason: Mapped[str | None] = mapped_column(Text)
    postmortem: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    product: Mapped[Product] = relationship(back_populates="experiments")
    concept: Mapped[Concept] = relationship(back_populates="experiment")
    learning: Mapped["Learning | None"] = relationship(back_populates="experiment", uselist=False)


class Learning(Base):
    __tablename__ = "learnings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(
        ForeignKey("experiments.id"), unique=True, nullable=False
    )
    content: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(100))
    qualification: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LearningStatus.DRAFT)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    experiment: Mapped[Experiment] = relationship(back_populates="learning")


class AIExecution(Base):
    __tablename__ = "ai_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed')",
            name="ck_ai_execution_status",
        ),
        Index("uq_ai_execution_idempotency", "idempotency_key", unique=True),
        Index("ix_ai_execution_origin", "origin_type", "origin_id"),
        Index(
            "uq_ai_generate_active_or_succeeded",
            "origin_type",
            "origin_id",
            "task_type",
            unique=True,
            postgresql_where=text(
                "task_type = 'generate_collisions' AND status IN ('pending', 'running', 'succeeded')"
            ),
            sqlite_where=text(
                "task_type = 'generate_collisions' AND status IN ('pending', 'running', 'succeeded')"
            ),
        ),
        Index(
            "uq_ai_challenge_snapshot_active_or_succeeded",
            "origin_type",
            "origin_id",
            "task_type",
            "input_fingerprint",
            unique=True,
            postgresql_where=text(
                "task_type = 'challenge_concept' AND "
                "status IN ('pending', 'running', 'succeeded')"
            ),
            sqlite_where=text(
                "task_type = 'challenge_concept' AND "
                "status IN ('pending', 'running', 'succeeded')"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AIExecutionStatus.PENDING
    )
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    origin_type: Mapped[str] = mapped_column(String(80), nullable=False)
    origin_id: Mapped[str] = mapped_column(String(36), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)
    input_snapshot: Mapped[dict | None] = mapped_column(JSON)
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@event.listens_for(Session, "before_flush")
def prevent_approved_truth_mutation(session: Session, *_args: object) -> None:
    for instance in session.dirty.union(session.deleted):
        if isinstance(instance, AIExecution):
            state = instance.__dict__.get("_sa_instance_state")
            task_history = state.attrs.task_type.history
            status_history = state.attrs.status.history
            original_task = task_history.deleted[0] if task_history.deleted else instance.task_type
            original_status = (
                status_history.deleted[0] if status_history.deleted else instance.status
            )
            if original_task == AITaskType.CHALLENGE_CONCEPT and original_status in (
                AIExecutionStatus.SUCCEEDED,
                AIExecutionStatus.FAILED,
            ):
                raise ValueError("Completed AI challenge executions are immutable")
            continue
        if not isinstance(instance, TruthVersion):
            continue
        original_status = instance.status
        history = instance.__dict__.get("_sa_instance_state").attrs.status.history
        if history.deleted:
            original_status = history.deleted[0]
        if original_status == TruthStatus.APPROVED:
            raise ValueError("Approved Truth versions are immutable")
