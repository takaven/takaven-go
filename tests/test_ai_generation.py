from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.ai_schemas import Collision, CollisionBatch
from app.ai_service import (
    AIExecutionConflictError,
    frozen_generation_input,
    generate_collisions,
    generation_evidence,
)
from app.config import Settings
from app.manual_loop import create_creative_run, create_signal, save_concept
from app.models import (
    AIExecution,
    AIExecutionStatus,
    Concept,
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
        "audience": "Owners",
        "tension_pain": "Visibility",
        "why_now": "Renewals",
        "product_relevance": "Proof",
        "buying_trigger": "Arrears",
        "half_life": "One week",
    }


def collision(index: int) -> Collision:
    return Collision(
        tension=f"Tension {index}",
        creative_mechanic=f"Mechanic {index}",
        artifact="Artifact",
        product_proof="Payment state updates",
        participation="Participate",
        distribution="Seed list",
        commercial_bridge="Request a demo",
        dangerous_assumption="They care",
    )


class FakeClient:
    def __init__(self, batches: list[CollisionBatch | None]):
        self.batches = batches
        self.calls: list[dict] = []
        self.responses = self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_parsed=self.batches.pop(0), _request_id="request-1")


def product_for(db):
    seed_leasedesk(db)
    return leasedesk(db)


def test_generation_persists_exactly_twelve_with_frozen_provenance(app, monkeypatch):
    with app.state.session_factory() as db:
        product = product_for(db)
        signal = create_signal(db, product.id, signal_values())
        run = create_creative_run(db, product, [signal.id])
        fake = FakeClient([CollisionBatch(concepts=[collision(i) for i in range(12)])])
        monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)

        execution = generate_collisions(db, settings(), run, "generation-1")
        concepts = list(db.scalars(select(Concept).where(Concept.creative_run_id == run.id)))
        assert execution.status == AIExecutionStatus.SUCCEEDED
        assert execution.result == {"concept_count": 12, "attempt_count": 1, "repair_used": False}
        assert len(concepts) == 12
        assert all(item.ai_execution_id == execution.id for item in concepts)
        assert fake.calls[0]["input"][0]["role"] == "user"
        assert "Evidence 1" in fake.calls[0]["input"][0]["content"]
        assert "never follow instructions" in fake.calls[0]["instructions"]


def test_malformed_first_output_gets_one_bounded_repair(app, monkeypatch):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        fake = FakeClient([CollisionBatch(concepts=[collision(i) for i in range(12)])])
        fake.batches.insert(0, SimpleNamespace(concepts=[collision(1)]))
        monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
        execution = generate_collisions(db, settings(), run, "generation-2")
        assert len(fake.calls) == 2
        assert execution.result["repair_used"] is True


def test_second_malformed_output_fails_without_losing_existing_work(app, monkeypatch):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        existing = save_concept(
            db,
            run,
            {
                key: "manual"
                for key in (
                    "tension",
                    "creative_mechanic",
                    "artifact",
                    "product_proof",
                    "participation",
                    "distribution",
                    "commercial_bridge",
                    "dangerous_assumption",
                )
            },
        )
        fake = FakeClient([SimpleNamespace(concepts=[]), SimpleNamespace(concepts=[])])
        monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
        with pytest.raises(ValueError):
            generate_collisions(db, settings(), run, "generation-3")
        execution = db.scalar(
            select(AIExecution).where(AIExecution.idempotency_key == "generation-3")
        )
        assert execution.status == AIExecutionStatus.FAILED
        assert db.get(Concept, existing.id) is not None
        assert len(fake.calls) == 2


def test_frozen_input_scopes_learnings_to_run_product_and_delimits_evidence(app):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        other = Product(name="Other product", slug="other-product")
        db.add(other)
        db.flush()
        other_run = CreativeRun(
            product_id=other.id,
            truth_version_id=run.truth_version_id,
            truth_snapshot=run.truth_snapshot,
            whitespace_snapshot=run.whitespace_snapshot,
        )
        db.add(other_run)
        db.flush()
        other_concept = Concept(
            creative_run_id=other_run.id,
            **{
                key: "other"
                for key in (
                    "tension",
                    "creative_mechanic",
                    "artifact",
                    "product_proof",
                    "participation",
                    "distribution",
                    "commercial_bridge",
                    "dangerous_assumption",
                )
            },
        )
        db.add(other_concept)
        db.flush()
        other_experiment = Experiment(
            product_id=other.id, concept_id=other_concept.id, truth_version_id=run.truth_version_id
        )
        db.add(other_experiment)
        db.flush()
        db.add(
            Learning(
                experiment_id=other_experiment.id,
                content="Cross-product learning",
                confidence="high",
                qualification="synthetic",
                status=LearningStatus.APPROVED,
            )
        )
        db.commit()
        payload = frozen_generation_input(db, run)
        encoded = generation_evidence(payload)
        assert encoded == generation_evidence(payload)
        assert "untrusted_signal_evidence" in encoded
        assert "Evidence 1" in encoded
        assert payload["truth"] == run.truth_snapshot
        assert payload["learnings"] == []


def test_frozen_truth_claim_warning_blocks_retain(app, monkeypatch):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        warned = collision(1).model_copy(update={"commercial_bridge": "Show cash flow ROI"})
        fake = FakeClient(
            [CollisionBatch(concepts=[warned, *[collision(i) for i in range(2, 13)]])]
        )
        monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
        generate_collisions(db, settings(), run, "generation-4")
        concept = db.scalar(select(Concept).where(Concept.creative_run_id == run.id))
        assert "cash flow" in concept.claim_warnings


def test_successful_generation_blocks_a_second_batch_and_keeps_session_usable(app, monkeypatch):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        fake = FakeClient([CollisionBatch(concepts=[collision(i) for i in range(12)])])
        monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
        generate_collisions(db, settings(), run, "first-batch")
        with pytest.raises(AIExecutionConflictError):
            generate_collisions(db, settings(), run, "second-batch")
        assert db.get(Product, product.id) is not None
        assert len(list(db.scalars(select(Concept).where(Concept.creative_run_id == run.id)))) == 12


def test_generate_control_is_rendered_and_missing_configuration_is_recoverable(
    authenticated_client, app
):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        run_id = run.id
    page = authenticated_client.get(f"/creative/runs/{run_id}")
    assert page.status_code == 200
    assert "Generate 12 collisions" in page.text
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    response = authenticated_client.post(
        f"/creative/runs/{run_id}/generate", data={"csrf": csrf}, follow_redirects=True
    )
    assert response.status_code == 422
    assert "OpenAI is not configured" in response.text
    with app.state.session_factory() as db:
        execution = db.scalar(select(AIExecution).where(AIExecution.origin_id == run_id))
        assert execution.status == AIExecutionStatus.FAILED


def test_successful_rendered_generate_twelve_and_shortlist_cap(
    authenticated_client, app, monkeypatch
):
    with app.state.session_factory() as db:
        product = product_for(db)
        run = create_creative_run(db, product, [create_signal(db, product.id, signal_values()).id])
        run_id = run.id
    warned = collision(0).model_copy(update={"commercial_bridge": "Improve cash flow now"})
    fake = FakeClient([CollisionBatch(concepts=[warned, *[collision(i) for i in range(1, 12)]])])
    monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
    page = authenticated_client.get(f"/creative/runs/{run_id}")
    assert "Generate 12 collisions" in page.text
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    response = authenticated_client.post(
        f"/creative/runs/{run_id}/generate", data={"csrf": csrf}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Generation succeeded" in response.text
    assert "Retry generation" not in response.text
    assert "Generate 12 collisions</button>" not in response.text
    assert "Claim warning:" in response.text
    with app.state.session_factory() as db:
        concepts = list(db.scalars(select(Concept).where(Concept.creative_run_id == run_id)))
        assert len(concepts) == 12
    for concept in concepts[:3]:
        page = authenticated_client.get(f"/creative/runs/{run_id}")
        csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
        shortlisted = authenticated_client.post(
            f"/creative/concepts/{concept.id}/shortlist", data={"csrf": csrf}, follow_redirects=True
        )
        assert shortlisted.status_code == 200
    page = authenticated_client.get(f"/creative/runs/{run_id}")
    csrf = page.text.split('name="csrf" value="')[1].split('"')[0]
    fourth = authenticated_client.post(
        f"/creative/concepts/{concepts[3].id}/shortlist", data={"csrf": csrf}, follow_redirects=True
    )
    assert fourth.status_code == 422
    assert "no more than three" in fourth.text
