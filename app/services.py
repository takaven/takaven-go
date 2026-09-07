import logging
from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditEvent, Product, TruthStatus, TruthVersion
from app.truth_schema import TruthContent

logger = logging.getLogger(__name__)


class TruthConflictError(Exception):
    pass


def leasedesk(db: Session) -> Product:
    product = db.scalar(select(Product).where(Product.slug == "leasedesk"))
    if product is None:
        raise RuntimeError("LeaseDesk seed is missing; restart after applying migrations")
    return product


def current_truth(db: Session, product_id: str) -> TruthVersion:
    truth = db.scalar(
        select(TruthVersion)
        .where(
            TruthVersion.product_id == product_id,
            TruthVersion.status == TruthStatus.APPROVED,
        )
        .order_by(TruthVersion.version.desc())
    )
    if truth is None:
        raise RuntimeError("LeaseDesk has no approved Product Truth")
    return truth


def truth_history(db: Session, product_id: str) -> list[TruthVersion]:
    return list(
        db.scalars(
            select(TruthVersion)
            .where(TruthVersion.product_id == product_id)
            .order_by(TruthVersion.version.desc())
        )
    )


def create_draft(db: Session, product: Product) -> TruthVersion:
    existing = db.scalar(
        select(TruthVersion).where(
            TruthVersion.product_id == product.id,
            TruthVersion.status == TruthStatus.DRAFT,
        )
    )
    if existing:
        return existing
    approved = current_truth(db, product.id)
    max_version = db.scalar(
        select(func.max(TruthVersion.version)).where(TruthVersion.product_id == product.id)
    )
    draft = TruthVersion(
        product_id=product.id,
        version=(max_version or 0) + 1,
        status=TruthStatus.DRAFT,
        content=deepcopy(approved.content),
        change_note="",
    )
    db.add(draft)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TruthConflictError("Another draft already exists") from exc
    return draft


def update_draft(
    db: Session, draft: TruthVersion, content: TruthContent, change_note: str
) -> TruthVersion:
    if draft.status != TruthStatus.DRAFT:
        raise TruthConflictError("Only draft Truth versions can be edited")
    draft.content = content.model_dump(mode="json")
    draft.change_note = change_note.strip() or None
    draft.updated_at = datetime.now(UTC)
    db.commit()
    return draft


def approve_draft(db: Session, draft: TruthVersion) -> TruthVersion:
    if draft.status != TruthStatus.DRAFT:
        raise TruthConflictError("Only draft Truth versions can be approved")
    TruthContent.model_validate(draft.content)
    draft.status = TruthStatus.APPROVED
    draft.approved_at = datetime.now(UTC)
    draft.updated_at = draft.approved_at
    event = AuditEvent(
        event_type="truth.approved",
        product_id=draft.product_id,
        truth_version_id=draft.id,
        detail=f"LeaseDesk Product Truth version {draft.version} approved.",
    )
    db.add(event)
    db.commit()
    logger.info(
        "Product Truth approved",
        extra={
            "event": "truth.approved",
            "truth_version_id": draft.id,
            "product_id": draft.product_id,
        },
    )
    return draft
