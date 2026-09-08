from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.ai_schemas import ChallengeAssessment
from app.ai_service import (
    AIConfigurationError,
    AIExecutionConflictError,
    AIProviderError,
    challenge_concept,
    concept_input_fingerprint,
    frozen_challenge_input,
)
from app.config import Settings
from app.manual_loop import create_creative_run, create_signal, save_concept, shortlist_concept
from app.models import (
    AIExecution,
    AIExecutionStatus,
    AITaskType,
    Challenge,
    ConceptStatus,
    CreativeRun,
    Experiment,
    Learning,
    LearningStatus,
    Product,
)
from app.seed import seed_leasedesk
from app.services import leasedesk


def settings() -> Settings:
    return Settings(
        database_url="sqlite:///./test.db",
        operator_password="test-password",
        session_secret="test-session-secret-with-more-than-32-characters",
        cookie_secure=False,
        openai_api_key="test-key",
        openai_model="test-model",
    )


def signal_values(index: int = 1) -> dict[str, str]:
    return {
        "source": f"Source {index}",
        "evidence": f"Evidence {index}",
        "audience": "Owner-operators",
        "tension_pain": "Operational ambiguity",
        "why_now": "Renewal pressure",
        "product_relevance": "LeaseDesk state proof",
        "buying_trigger": "An arrears question",
        "half_life": "One week",
    }


def concept_values(suffix: str = "one") -> dict[str, str]:
    return {
        "tension": f"Invisible property state {suffix}",
        "creative_mechanic": "A public state-change challenge",
        "artifact": "A physical evidence board",
        "product_proof": "Record a payment and show the arrears state update",
        "participation": "Landlords submit the state question they cannot answer",
        "distribution": "A small owner-operator roundtable",
        "commercial_bridge": "Invite participants to inspect their state in LeaseDesk",
        "dangerous_assumption": "Owners will expose an operational blind spot",
    }


def assessment(ref: str = "concept.creative_mechanic") -> ChallengeAssessment:
    gate = {"verdict": "PASS", "reasoning": "Grounded assessment.", "evidence_refs": [ref]}
    return ChallengeAssessment(
        remarkable=gate,
        logo_off=gate,
        product_owned=gate,
        commercially_convertible=gate,
        buyable_internally_defensible=gate,
        strongest_reason="The product visibly changes operational state.",
        strongest_objection="Participation may be too demanding.",
        unsupported_claims=[],
        smallest_repair="Reduce the participation burden.",
        recommendation="GO",
    )


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls: list[dict] = []
        self.responses = self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(output_parsed=output, _request_id="challenge-request")


def shortlisted_concept(db):
    seed_leasedesk(db)
    product = leasedesk(db)
    signal = create_signal(db, product.id, signal_values())
    run = create_creative_run(db, product, [signal.id])
    concept = save_concept(db, run, concept_values())
    shortlist_concept(db, concept)
    return product, run, concept


def install_client(monkeypatch, outputs) -> FakeClient:
    fake = FakeClient(outputs)
    monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
    return fake


def test_fingerprint_is_stable_changes_with_content_and_sorts_warnings(app):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        concept.claim_warnings = ["zeta", "alpha"]
        first = concept_input_fingerprint(concept)
        concept.claim_warnings = ["alpha", "zeta"]
        assert concept_input_fingerprint(concept) == first
        concept.tension = f"{concept.tension} changed"
        assert concept_input_fingerprint(concept) != first


def test_initial_input_is_blind_and_learning_scope_and_order_are_deterministic(app):
    with app.state.session_factory() as db:
        product, run, concept = shortlisted_concept(db)
        manual = Challenge(
            concept_id=concept.id,
            gates={"operator": "judgment"},
            strongest_reason="Operator reason",
            strongest_objection="Operator objection",
            unsupported_claims="Operator concern",
            unsupported_resolved=True,
            smallest_repair="Operator repair",
            recommendation="go",
        )
        db.add(manual)
        other = Product(name="Other", slug="other")
        db.add(other)
        db.flush()

        def add_learning(owner: Product, learning_id: str, approved_at):
            if owner.id == product.id:
                other_run = create_creative_run(
                    db, owner, [create_signal(db, owner.id, signal_values()).id]
                )
            else:
                other_run = CreativeRun(
                    product_id=owner.id,
                    truth_version_id=run.truth_version_id,
                    truth_snapshot=run.truth_snapshot,
                    whitespace_snapshot=run.whitespace_snapshot,
                )
                db.add(other_run)
                db.commit()
            other_concept = save_concept(db, other_run, concept_values(learning_id))
            experiment = Experiment(
                product_id=owner.id,
                concept_id=other_concept.id,
                truth_version_id=run.truth_version_id,
            )
            db.add(experiment)
            db.flush()
            db.add(
                Learning(
                    id=learning_id,
                    experiment_id=experiment.id,
                    content=f"Learning {learning_id}",
                    confidence="qualified",
                    qualification="Synthetic",
                    status=LearningStatus.APPROVED,
                    approved_at=approved_at,
                )
            )
            db.commit()

        now = datetime.now(UTC)
        add_learning(product, "00000000-0000-0000-0000-000000000003", now)
        add_learning(product, "00000000-0000-0000-0000-000000000002", None)
        add_learning(product, "00000000-0000-0000-0000-000000000001", now - timedelta(days=1))
        add_learning(other, "00000000-0000-0000-0000-000000000004", now)
        payload = frozen_challenge_input(db, concept)
        assert "challenge" not in payload
        assert "recommendation" not in payload
        assert "gates" not in payload
        assert manual.strongest_reason not in str(payload)
        assert [item["id"] for item in payload["learnings"]] == [
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000003",
        ]


def test_signal_snapshots_are_deterministically_ordered(app):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        first = create_signal(db, product.id, signal_values(1))
        second = create_signal(db, product.id, signal_values(2))
        run = create_creative_run(db, product, [second.id, first.id])
        concept = save_concept(db, run, concept_values())
        shortlist_concept(db, concept)
        payload = frozen_challenge_input(db, concept)
        assert [signal["id"] for signal in payload["signals"]] == sorted([first.id, second.id])


def test_challenge_schema_requires_all_five_gates():
    data = assessment().model_dump(mode="json")
    del data["remarkable"]
    with pytest.raises(ValidationError):
        ChallengeAssessment.model_validate(data)


def test_unknown_evidence_reference_gets_one_repair(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        fake = install_client(monkeypatch, [assessment("invented:reference"), assessment()])
        execution = challenge_concept(db, settings(), concept, "challenge-repair")
        assert len(fake.calls) == 2
        assert execution.result["attempt_count"] == 2
        assert execution.result["repair_used"] is True


def test_unsupported_claim_must_reference_concept_and_truth(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        invalid_data = assessment().model_dump(mode="json")
        invalid_data["unsupported_claims"] = [
            {
                "concern": "A claim concern without its Truth basis.",
                "evidence_refs": [
                    "concept.commercial_bridge",
                    "concept.product_proof",
                ],
            }
        ]
        invalid = ChallengeAssessment.model_validate(invalid_data)
        fake = install_client(monkeypatch, [invalid, assessment()])
        execution = challenge_concept(db, settings(), concept, "challenge-claim-ref-repair")
        assert len(fake.calls) == 2
        assert execution.result["repair_used"] is True


def test_sdk_schema_validation_failure_gets_one_repair(app, monkeypatch):
    with pytest.raises(ValidationError) as captured:
        ChallengeAssessment.model_validate({})
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        fake = install_client(monkeypatch, [captured.value, assessment()])
        execution = challenge_concept(db, settings(), concept, "challenge-schema-repair")
        assert len(fake.calls) == 2
        assert execution.result["repair_used"] is True


def test_second_malformed_challenge_fails_and_same_fingerprint_can_retry(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        first = install_client(
            monkeypatch, [assessment("invented:first"), assessment("invented:second")]
        )
        with pytest.raises(ValueError):
            challenge_concept(db, settings(), concept, "challenge-failed")
        failed = db.scalar(
            select(AIExecution).where(AIExecution.idempotency_key == "challenge-failed")
        )
        assert failed.status == AIExecutionStatus.FAILED
        assert len(first.calls) == 2
        second = install_client(monkeypatch, [assessment()])
        succeeded = challenge_concept(db, settings(), concept, "challenge-retry")
        assert succeeded.status == AIExecutionStatus.SUCCEEDED
        assert len(second.calls) == 1


def test_provider_failure_is_failed_without_repair_and_preserves_snapshot(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
        fake = install_client(monkeypatch, [error])
        with pytest.raises(AIProviderError):
            challenge_concept(db, settings(), concept, "challenge-provider")
        execution = db.scalar(
            select(AIExecution).where(AIExecution.idempotency_key == "challenge-provider")
        )
        assert execution.status == AIExecutionStatus.FAILED
        assert execution.input_snapshot["concept"]["tension"] == concept.tension
        assert len(fake.calls) == 1


def test_missing_configuration_records_failure_without_calling_provider(app):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        missing = settings().model_copy(update={"openai_api_key": None})
        with pytest.raises(AIConfigurationError, match="OpenAI is not configured"):
            challenge_concept(db, missing, concept, "challenge-unconfigured")
        execution = db.scalar(
            select(AIExecution).where(AIExecution.idempotency_key == "challenge-unconfigured")
        )
        assert execution.status == AIExecutionStatus.FAILED
        assert execution.input_snapshot["concept"]["tension"] == concept.tension


def test_challenge_input_is_persisted_atomically_with_pending_execution(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        fake = FakeClient([assessment()])

        def inspect_initial_persistence(_settings):
            with app.state.session_factory() as verification_db:
                execution = verification_db.scalar(
                    select(AIExecution).where(
                        AIExecution.idempotency_key == "challenge-atomic-input"
                    )
                )
                assert execution.status == AIExecutionStatus.PENDING
                assert execution.input_fingerprint
                assert execution.input_snapshot["concept"]["tension"] == concept.tension
            return fake

        monkeypatch.setattr("app.ai_service.openai_client", inspect_initial_persistence)
        challenge_concept(db, settings(), concept, "challenge-atomic-input")


def test_database_requires_fingerprint_only_for_challenge_executions(app):
    with app.state.session_factory() as db:
        common = {
            "status": AIExecutionStatus.PENDING,
            "provider": "openai",
            "model": "test-model",
            "prompt_version": "test-prompt",
            "schema_version": "test-schema",
            "origin_type": "concept",
            "origin_id": "00000000-0000-0000-0000-000000000001",
        }
        db.add(
            AIExecution(
                task_type=AITaskType.CHALLENGE_CONCEPT,
                idempotency_key="missing-challenge-fingerprint",
                **common,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(
            AIExecution(
                task_type=AITaskType.GENERATE_COLLISIONS,
                idempotency_key="generation-without-fingerprint",
                **common,
            )
        )
        db.commit()


def test_success_blocks_same_snapshot_but_edit_allows_new_challenge_without_side_effects(
    app, monkeypatch
):
    with app.state.session_factory() as db:
        _, run, concept = shortlisted_concept(db)
        original_status = concept.status
        install_client(monkeypatch, [assessment()])
        first = challenge_concept(db, settings(), concept, "challenge-first")
        assert first.status == AIExecutionStatus.SUCCEEDED
        assert concept.status == original_status == ConceptStatus.SHORTLISTED
        assert concept.challenge is None
        assert db.scalar(select(Experiment).where(Experiment.concept_id == concept.id)) is None
        with pytest.raises(
            AIExecutionConflictError,
            match=(
                "A challenge for this unchanged concept is already in progress or has already "
                "succeeded."
            ),
        ):
            challenge_concept(db, settings(), concept, "challenge-duplicate")
        assert db.get(Product, run.product_id) is not None

        save_concept(db, run, concept_values("revised"), concept)
        install_client(monkeypatch, [assessment()])
        second = challenge_concept(db, settings(), concept, "challenge-revised")
        assert second.status == AIExecutionStatus.SUCCEEDED
        assert second.input_fingerprint != first.input_fingerprint
        assert concept.status == ConceptStatus.SHORTLISTED


def test_rough_concept_cannot_initial_challenge(app, monkeypatch):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        concept = save_concept(db, run, concept_values())
        fake = install_client(monkeypatch, [assessment()])
        with pytest.raises(AIExecutionConflictError):
            challenge_concept(db, settings(), concept, "rough-challenge")
        assert fake.calls == []


def test_completed_challenge_execution_is_immutable(app, monkeypatch):
    with app.state.session_factory() as db:
        _, _, concept = shortlisted_concept(db)
        install_client(monkeypatch, [assessment()])
        execution = challenge_concept(db, settings(), concept, "challenge-immutable")
        execution.result = {"overwritten": True}
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
