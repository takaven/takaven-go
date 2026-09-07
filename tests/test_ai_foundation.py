import pytest
from sqlalchemy import select

from app.ai_service import (
    AIConfigurationError,
    AIExecutionConflictError,
    begin_execution,
    mark_failed,
    openai_client,
)
from app.config import Settings
from app.models import AIExecution, AIExecutionStatus, AITaskType
from app.seed import seed_leasedesk
from app.services import leasedesk


def ai_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "sqlite:///./test.db",
        "operator_password": "stage-three-test-password",
        "session_secret": "stage-three-test-secret-with-more-than-32-characters",
        "cookie_secure": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_missing_key_fails_without_breaking_non_ai_application(authenticated_client):
    assert authenticated_client.get("/truth").status_code == 200
    assert authenticated_client.get("/radar").status_code == 200
    with pytest.raises(AIConfigurationError, match="not configured"):
        openai_client(ai_settings())


def test_missing_or_blank_model_configuration_fails_safely():
    with pytest.raises(AIConfigurationError, match="model is not configured"):
        openai_client(ai_settings(openai_api_key="test-key"))
    with pytest.raises(AIConfigurationError, match="model is not configured"):
        openai_client(ai_settings(openai_api_key="test-key", openai_model=""))


def test_execution_is_idempotent_and_failure_is_persisted(app):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        execution = begin_execution(
            db,
            ai_settings(openai_model="test-model"),
            AITaskType.GENERATE_COLLISIONS,
            "creative_run",
            product.id,
            "same-action",
            "stage3a-v1",
            "stage3a-v1",
        )
        with pytest.raises(AIExecutionConflictError):
            begin_execution(
                db,
                ai_settings(openai_model="test-model"),
                AITaskType.GENERATE_COLLISIONS,
                "creative_run",
                product.id,
                "same-action",
                "stage3a-v1",
                "stage3a-v1",
            )
        mark_failed(db, execution, AIConfigurationError("OpenAI is not configured."))
        stored = db.scalar(select(AIExecution).where(AIExecution.id == execution.id))
        assert stored is not None
        assert stored.status == AIExecutionStatus.FAILED
        assert stored.completed_at is not None
        assert stored.error_code == "AIConfigurationError"
