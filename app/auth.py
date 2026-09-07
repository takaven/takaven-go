import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import OperatorSession

COOKIE_NAME = "takaven_session"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate_password(candidate: str, settings: Settings) -> bool:
    return hmac.compare_digest(candidate, settings.operator_password.get_secret_value())


def create_operator_session(db: Session, settings: Settings) -> tuple[str, OperatorSession]:
    now = datetime.now(UTC)
    db.execute(delete(OperatorSession).where(OperatorSession.expires_at <= now))
    raw_token = secrets.token_urlsafe(48)
    operator_session = OperatorSession(
        token_hash=token_hash(raw_token),
        expires_at=now + timedelta(hours=settings.session_hours),
    )
    db.add(operator_session)
    db.commit()
    return raw_token, operator_session


def current_session(request: Request, db: Session) -> OperatorSession | None:
    raw_token = request.cookies.get(COOKIE_NAME)
    if not raw_token:
        return None
    session = db.scalar(
        select(OperatorSession).where(
            OperatorSession.token_hash == token_hash(raw_token),
            OperatorSession.expires_at > datetime.now(UTC),
        )
    )
    return session


def require_session(request: Request, db: Session) -> OperatorSession:
    session = current_session(request, db)
    if not session:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return session


def csrf_token(request: Request, settings: Settings) -> str:
    raw_token = request.cookies.get(COOKIE_NAME, "")
    return hmac.new(
        settings.session_secret.get_secret_value().encode(),
        f"csrf:{raw_token}".encode(),
        hashlib.sha256,
    ).hexdigest()


def validate_csrf(request: Request, submitted: str, settings: Settings) -> None:
    if not submitted or not hmac.compare_digest(submitted, csrf_token(request, settings)):
        raise HTTPException(
            status_code=403,
            detail="Invalid form token. Refresh the page and try again.",
        )
