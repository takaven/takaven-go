from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError
from pydantic import SecretStr
from sqlalchemy import select

from app.ai_schemas import ChallengeAssessment
from app.ai_service import concept_input_fingerprint
from app.manual_loop import (
    GATE_NAMES,
    create_creative_run,
    create_signal,
    save_concept,
    shortlist_concept,
)
from app.models import (
    AIExecution,
    AIExecutionStatus,
    AITaskType,
    Challenge,
    Concept,
    ConceptStatus,
    Experiment,
    Signal,
)
from app.seed import seed_leasedesk
from app.services import leasedesk


def signal_values() -> dict[str, str]:
    return {
        "source": "Synthetic owner-operator interview",
        "evidence": "The operator could not answer whether a tenant was in arrears.",
        "audience": "Small commercial landlord",
        "tension_pain": "Operational state is hard to see",
        "why_now": "A lease decision is approaching",
        "product_relevance": "LeaseDesk exposes payment and arrears state",
        "buying_trigger": "An urgent rent-state question",
        "half_life": "One month",
    }


def concept_values(suffix: str = "") -> dict[str, str]:
    return {
        "tension": f"The rent state is invisible{suffix}",
        "creative_mechanic": "A public state-change challenge",
        "artifact": "A physical evidence board",
        "product_proof": "Record a payment and show the arrears state update",
        "participation": "Landlords submit the state question they cannot answer",
        "distribution": "A small owner-operator roundtable",
        "commercial_bridge": "Invite participants to inspect their state in LeaseDesk",
        "dangerous_assumption": "Owners will expose an operational blind spot",
    }


def assessment(with_concern: bool = True) -> ChallengeAssessment:
    verdicts = ("PASS", "WEAK", "FAIL", "PASS", "WEAK")
    refs = (
        "concept.creative_mechanic",
        "concept.artifact",
        "truth.magic_moment",
        "concept.commercial_bridge",
        "concept.dangerous_assumption",
    )
    gates = [
        {
            "verdict": verdict,
            "reasoning": f"Grounded {verdict.lower()} reasoning for gate {index + 1}.",
            "evidence_refs": [refs[index]],
        }
        for index, verdict in enumerate(verdicts)
    ]
    concerns = (
        [
            {
                "concern": "The bridge could imply an unsupported outcome.",
                "evidence_refs": ["concept.commercial_bridge", "truth.prohibited_claims"],
            }
        ]
        if with_concern
        else []
    )
    return ChallengeAssessment(
        remarkable=gates[0],
        logo_off=gates[1],
        product_owned=gates[2],
        commercially_convertible=gates[3],
        buyable_internally_defensible=gates[4],
        strongest_reason="The product visibly changes operational state.",
        strongest_objection="Participation may ask too much of a busy landlord.",
        unsupported_claims=concerns,
        smallest_repair="Reduce the participation burden.",
        recommendation="REVISE",
    )


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.responses = self
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(output_parsed=output, _request_id="challenge-ui-request")


def install_fake_provider(app, monkeypatch, outputs) -> FakeClient:
    app.state.settings.openai_api_key = SecretStr("test-api-key")
    app.state.settings.openai_model = "test-challenge-model"
    fake = FakeClient(outputs)
    monkeypatch.setattr("app.ai_service.openai_client", lambda _settings: fake)
    return fake


def create_concept(app, status: ConceptStatus = ConceptStatus.SHORTLISTED) -> tuple[str, str]:
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        signal = create_signal(db, product.id, signal_values())
        run = create_creative_run(db, product, [signal.id])
        concept = save_concept(db, run, concept_values())
        if status != ConceptStatus.ROUGH:
            shortlist_concept(db, concept)
            if status != ConceptStatus.SHORTLISTED:
                concept.status = status
                db.commit()
        return run.id, concept.id


def csrf_from(html: str) -> str:
    return html.split('name="csrf" value="')[1].split('"')[0]


def manual_challenge_form(csrf: str) -> dict[str, str]:
    form = {"csrf": csrf}
    for index in range(5):
        form[f"gate_{index}"] = "pass"
        form[f"reason_{index}"] = "My independent operator reasoning."
    form.update(
        {
            "strongest_reason": "The product performs in public.",
            "strongest_objection": "Participation could be too demanding.",
            "unsupported_claims": "None identified after manual review.",
            "smallest_repair": "Make the prompt easier to answer.",
            "recommendation": "go",
            "unsupported_resolved": "on",
        }
    )
    return form


@pytest.mark.parametrize(
    "status",
    [ConceptStatus.ROUGH, ConceptStatus.REVISE, ConceptStatus.RETAINED, ConceptStatus.KILLED],
)
def test_only_shortlisted_concepts_expose_initial_ai_challenge(authenticated_client, app, status):
    _, concept_id = create_concept(app, status)
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    assert page.status_code == 200
    assert "Challenge with AI" not in page.text
    assert "Retry AI challenge" not in page.text


def test_shortlisted_concept_shows_explicit_advisory_action(authenticated_client, app):
    _, concept_id = create_concept(app)
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    assert page.status_code == 200
    assert "Challenge with AI" in page.text
    assert (
        "Independent advisory review against the frozen Product Truth and evidence. "
        "It does not decide whether to retain, revise or kill the concept."
    ) in page.text
    assert "Only your saved manual challenge governs RETAIN / REVISE / KILL." in page.text


def test_ai_challenge_post_requires_authentication_and_csrf(client, authenticated_client, app):
    _, concept_id = create_concept(app)
    unauthenticated = TestClient(app)
    with unauthenticated:
        response = unauthenticated.post(
            f"/creative/concepts/{concept_id}/ai-challenge",
            data={"csrf": "invalid"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": "invalid"},
        follow_redirects=False,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("status", [AIExecutionStatus.PENDING, AIExecutionStatus.RUNNING])
def test_current_inflight_execution_shows_state_without_duplicate_action(
    authenticated_client, app, status
):
    _, concept_id = create_concept(app)
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        db.add(
            AIExecution(
                task_type=AITaskType.CHALLENGE_CONCEPT,
                status=status,
                provider="openai",
                model="test-model",
                prompt_version="3c-challenge-v1",
                schema_version="3c-challenge-v1",
                origin_type="concept",
                origin_id=concept.id,
                idempotency_key=f"{status}-ui",
                input_fingerprint=concept_input_fingerprint(concept),
                input_snapshot={"concept": concept_values()},
            )
        )
        db.commit()
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    assert f"AI challenge {status}" in page.text
    assert "Challenge with AI" not in page.text
    assert "Retry AI challenge" not in page.text


def test_provider_failure_is_safe_and_retry_succeeds(authenticated_client, app, monkeypatch):
    _, concept_id = create_concept(app)
    error = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    fake = install_fake_provider(app, monkeypatch, [error])
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
    )
    assert response.status_code == 422
    assert "AI challenge failed" in response.text
    assert "Your concept and manual challenge work are safe." in response.text
    assert "Retry AI challenge" in response.text
    assert "Authorization" not in response.text
    assert "test-api-key" not in response.text
    assert len(fake.calls) == 1

    second = install_fake_provider(app, monkeypatch, [assessment()])
    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(response.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(second.calls) == 1
    with app.state.session_factory() as db:
        executions = list(
            db.scalars(
                select(AIExecution)
                .where(AIExecution.origin_id == concept_id)
                .order_by(AIExecution.created_at)
            )
        )
        assert [item.status for item in executions] == [
            AIExecutionStatus.FAILED,
            AIExecutionStatus.SUCCEEDED,
        ]
        assert executions[0].idempotency_key != executions[1].idempotency_key


def test_successful_rendered_ai_challenge_preserves_human_control(
    authenticated_client, app, monkeypatch
):
    run_id, concept_id = create_concept(app)
    fake = install_fake_provider(app, monkeypatch, [assessment()])
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/creative/concepts/{concept_id}/challenge"
    assert len(fake.calls) == 1

    page = authenticated_client.get(response.headers["location"])
    assert page.status_code == 200
    for gate in GATE_NAMES:
        assert gate in page.text
    for verdict in ("PASS", "WEAK", "FAIL"):
        assert f">{verdict}<" in page.text
    assert "concept.creative_mechanic" in page.text
    assert "truth.magic_moment" in page.text
    assert "The product visibly changes operational state." in page.text
    assert "Participation may ask too much of a busy landlord." in page.text
    assert "The bridge could imply an unsupported outcome." in page.text
    assert "Reduce the participation burden." in page.text
    assert "AI recommendation — advisory only" in page.text
    assert ">REVISE<" in page.text
    assert "Assessment trace" in page.text
    assert "test-challenge-model" in page.text
    assert "3c-challenge-v1" in page.text
    assert "challenge-ui-request" in page.text
    assert "Challenge with AI" not in page.text
    assert "Retry AI challenge" not in page.text
    assert '<option value="go" selected' not in page.text
    assert '<option value="revise" selected' not in page.text
    assert '<option value="pass" selected' not in page.text
    assert (
        "Shortlist up to three concepts, use AI challenge as a second opinion, then save your manual challenge."
        in page.text
    )

    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        assert concept.status == ConceptStatus.SHORTLISTED
        assert concept.challenge is None
        assert db.scalar(select(Experiment).where(Experiment.concept_id == concept_id)) is None
        assert db.scalar(select(Challenge).where(Challenge.concept_id == concept_id)) is None

    manual = authenticated_client.post(
        f"/creative/concepts/{concept_id}/challenge",
        data=manual_challenge_form(csrf_from(page.text)),
        follow_redirects=True,
    )
    assert manual.status_code == 200
    assert "Challenge:</strong> go" in manual.text
    assert 'value="retain"' in manual.text
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        assert concept.status == ConceptStatus.SHORTLISTED
        assert concept.challenge is not None
        assert db.scalar(select(Experiment).where(Experiment.concept_id == concept_id)) is None
    assert f"/creative/runs/{run_id}" in manual.url.path


def test_zero_concerns_copy_does_not_claim_safety(authenticated_client, app, monkeypatch):
    _, concept_id = create_concept(app)
    install_fake_provider(app, monkeypatch, [assessment(with_concern=False)])
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
        follow_redirects=True,
    )
    assert (
        "No unsupported-claim concerns were returned by this AI assessment. "
        "This is not proof that every claim is safe or supported."
    ) in response.text


def test_edited_concept_shows_stale_historical_assessment_without_rechallenge(
    authenticated_client, app, monkeypatch
):
    _, concept_id = create_concept(app)
    install_fake_provider(app, monkeypatch, [assessment()])
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
        follow_redirects=False,
    )
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        old_fingerprint = concept_input_fingerprint(concept)
        save_concept(db, concept.creative_run, concept_values(" after edit"), concept)
        assert concept_input_fingerprint(concept) != old_fingerprint

    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    assert "Previous AI assessment" in page.text
    assert "Concept changed since this AI assessment." in page.text
    assert "earlier concept snapshot, not the current edited concept" in page.text
    assert old_fingerprint in page.text
    assert "Challenge with AI" not in page.text
    assert "Retry AI challenge" not in page.text
    assert ">Rechallenge<" not in page.text


def test_direct_post_after_historical_success_is_blocked(authenticated_client, app, monkeypatch):
    _, concept_id = create_concept(app)
    install_fake_provider(app, monkeypatch, [assessment()])
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
        follow_redirects=False,
    )
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        save_concept(db, concept.creative_run, concept_values(" revised"), concept)
    page = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    response = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(page.text)},
    )
    assert response.status_code == 422
    assert "already has an AI assessment" in response.text
    with app.state.session_factory() as db:
        executions = list(
            db.scalars(select(AIExecution).where(AIExecution.origin_id == concept_id))
        )
        assert len(executions) == 1


def test_complete_rendered_http_challenge_workflow(authenticated_client, app, monkeypatch):
    install_fake_provider(app, monkeypatch, [assessment(with_concern=False)])

    radar = authenticated_client.get("/radar")
    created_signal = authenticated_client.post(
        "/radar/signals",
        data={"csrf": csrf_from(radar.text), "url": "", **signal_values()},
        follow_redirects=False,
    )
    assert created_signal.status_code == 303
    with app.state.session_factory() as db:
        signal_id = db.scalar(select(Signal.id))

    created_run = authenticated_client.post(
        "/creative/runs",
        data={"csrf": csrf_from(radar.text), "signal_ids": signal_id},
        follow_redirects=False,
    )
    assert created_run.status_code == 303
    run_url = created_run.headers["location"]
    run_page = authenticated_client.get(run_url)
    created_concept = authenticated_client.post(
        f"{run_url}/concepts",
        data={"csrf": csrf_from(run_page.text), **concept_values()},
        follow_redirects=False,
    )
    assert created_concept.status_code == 303
    with app.state.session_factory() as db:
        concept_id = db.scalar(select(Concept.id))

    run_page = authenticated_client.get(run_url)
    shortlisted = authenticated_client.post(
        f"/creative/concepts/{concept_id}/shortlist",
        data={"csrf": csrf_from(run_page.text)},
        follow_redirects=False,
    )
    assert shortlisted.status_code == 303

    workspace = authenticated_client.get(f"/creative/concepts/{concept_id}/challenge")
    assert "Challenge with AI" in workspace.text
    challenged = authenticated_client.post(
        f"/creative/concepts/{concept_id}/ai-challenge",
        data={"csrf": csrf_from(workspace.text)},
        follow_redirects=False,
    )
    assert challenged.status_code == 303
    workspace = authenticated_client.get(challenged.headers["location"])
    assert "Independent AI challenge" in workspace.text
    assert "Remarkable" in workspace.text

    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        assert concept.challenge is None
        assert concept.status == ConceptStatus.SHORTLISTED

    manual = authenticated_client.post(
        f"/creative/concepts/{concept_id}/challenge",
        data=manual_challenge_form(csrf_from(workspace.text)),
        follow_redirects=True,
    )
    assert manual.status_code == 200
    assert 'value="retain"' in manual.text
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        assert concept.challenge is not None
        assert concept.status == ConceptStatus.SHORTLISTED
