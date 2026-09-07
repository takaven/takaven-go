import pytest
from sqlalchemy import select

from app.manual_loop import (
    GATE_NAMES,
    ManualLoopError,
    approve_learning,
    archive_signal,
    create_creative_run,
    create_experiment,
    create_signal,
    decide_concept,
    finalize_experiment,
    save_challenge,
    save_concept,
    save_learning,
    save_results,
    shortlist_concept,
    transition_experiment,
    update_experiment,
)
from app.models import (
    AuditEvent,
    Concept,
    ConceptStatus,
    ExperimentStatus,
    LearningStatus,
    SignalStatus,
)
from app.seed import seed_leasedesk
from app.services import leasedesk
from app.workflow import progression


def signal_values(index: int = 1) -> dict[str, str]:
    return {
        "source": f"Operator interview {index}",
        "evidence": f"Evidence {index}",
        "url": "",
        "audience": "Small commercial landlord",
        "tension_pain": "No clear operational state",
        "why_now": "Lease expiry is close",
        "product_relevance": "LeaseDesk makes state visible",
        "buying_trigger": "A rent or renewal decision",
        "half_life": "Evergreen",
    }


def concept_values(index: int = 1) -> dict[str, str]:
    return {
        "tension": f"Tension {index}",
        "creative_mechanic": "Public state change",
        "artifact": "A payment state demo",
        "product_proof": "Payment updates arrears and produces a receipt",
        "participation": "Landlords compare their current state",
        "distribution": "Named landlord community",
        "commercial_bridge": "Invite a LeaseDesk walkthrough",
        "dangerous_assumption": "The proof earns attention",
    }


def challenge_values() -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    gates = {gate: {"verdict": "pass", "reasoning": "Defensible evidence."} for gate in GATE_NAMES}
    values = {
        "strongest_reason": "It makes LeaseDesk perform publicly.",
        "strongest_objection": "The artifact might not travel.",
        "unsupported_claims": "None identified.",
        "smallest_repair": "Tighten the demo.",
        "recommendation": "go",
    }
    return gates, values


def build_retained_concept(app):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        signals = [create_signal(db, product.id, signal_values(index)) for index in range(1, 4)]
        run = create_creative_run(db, product, [signal.id for signal in signals])
        concept = save_concept(db, run, concept_values())
        shortlist_concept(db, concept)
        gates, values = challenge_values()
        save_challenge(db, concept, gates, values, unsupported_resolved=True)
        decide_concept(db, concept, "retain")
        return run.id, concept.id


def test_signal_lifecycle_selection_and_frozen_snapshots(app):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        signals = [create_signal(db, product.id, signal_values(index)) for index in range(1, 5)]
        archive_signal(db, signals[3])
        with pytest.raises(ManualLoopError, match="one and three"):
            create_creative_run(
                db, product, [signals[0].id, signals[1].id, signals[2].id, signals[3].id]
            )
        with pytest.raises(ManualLoopError, match="unavailable"):
            create_creative_run(db, product, [signals[3].id])
        run = create_creative_run(db, product, [signals[0].id, signals[1].id])
        snapshot = run.signals[0].signal_snapshot["evidence"]
        signals[0].evidence = "Changed after selection"
        db.commit()
        assert run.truth_snapshot["creative_whitespace"]["value"] == run.whitespace_snapshot
        assert run.signals[0].signal_snapshot["evidence"] == snapshot
        assert signals[0].status == SignalStatus.SELECTED
        assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "signal.archived"))


def test_shortlist_limit_and_promotion_blockers(app):
    with app.state.session_factory() as db:
        seed_leasedesk(db)
        product = leasedesk(db)
        signal = create_signal(db, product.id, signal_values())
        run = create_creative_run(db, product, [signal.id])
        concepts = [save_concept(db, run, concept_values(index)) for index in range(4)]
        for concept in concepts[:3]:
            shortlist_concept(db, concept)
        with pytest.raises(ManualLoopError, match="no more than three"):
            shortlist_concept(db, concepts[3])
        gates, values = challenge_values()
        gates["Product-Owned"]["verdict"] = "fail"
        save_challenge(db, concepts[0], gates, values, unsupported_resolved=True)
        with pytest.raises(ManualLoopError, match="Product-Owned"):
            decide_concept(db, concepts[0], "retain")
        gates["Product-Owned"]["verdict"] = "pass"
        save_challenge(db, concepts[0], gates, values, unsupported_resolved=False)
        with pytest.raises(ManualLoopError, match="unsupported claims"):
            decide_concept(db, concepts[0], "retain")
        save_challenge(db, concepts[0], gates, values, unsupported_resolved=True)
        decide_concept(db, concepts[0], "retain")
        save_challenge(db, concepts[1], gates, values, unsupported_resolved=True)
        with pytest.raises(ManualLoopError, match="only one"):
            decide_concept(db, concepts[1], "retain")
        assert concepts[0].status == ConceptStatus.RETAINED


def test_experiment_lifecycle_results_learning_and_audit(app):
    _, concept_id = build_retained_concept(app)
    with app.state.session_factory() as db:
        concept = db.get(Concept, concept_id)
        experiment = create_experiment(db, concept)
        with pytest.raises(ManualLoopError, match="Cannot mark READY"):
            transition_experiment(db, experiment, "ready")
        values = {
            "hypothesis": "A state-change demo earns qualified participation.",
            "dangerous_assumption": "The audience cares about visible state.",
            "smoke_test": "One public demo.",
            "seed_targets": "Named landlord group and owner-operator newsletter.",
            "product_magic_moment": "Payment updates state and produces receipt.",
            "measures": "Qualified ICP participation; magic-moment exposure; high-intent product action; qualified opportunity; pipeline/revenue.",
            "success_thresholds": "Five qualified participants and two product actions.",
            "test_window": "10–17 September",
            "execution_references": "https://example.test/demo",
        }
        update_experiment(db, experiment, values, thresholds_approved=True)
        transition_experiment(db, experiment, "ready")
        transition_experiment(db, experiment, "live")
        with pytest.raises(ManualLoopError, match="separate"):
            save_results(db, experiment, "facts", "")
        save_results(
            db, experiment, "Four qualified landlords watched the demo.", "The proof is credible."
        )
        transition_experiment(db, experiment, "complete")
        finalize_experiment(
            db, experiment, "revise", "Interest, but weak conversion.", "Improve the bridge."
        )
        learning = save_learning(
            db,
            experiment,
            {
                "content": "Visible operational proof earns attention.",
                "confidence": "Medium",
                "qualification": "One smoke test only.",
            },
        )
        approve_learning(db, learning)
        assert experiment.status == ExperimentStatus.COMPLETE
        assert learning.status == LearningStatus.APPROVED
        assert (
            len(list(db.scalars(select(AuditEvent).where(AuditEvent.subject_id == experiment.id))))
            >= 3
        )
        rail = progression(db, leasedesk(db), 1)
        assert rail["stages"][-1]["state"] == "complete"
