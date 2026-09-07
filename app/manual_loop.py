"""Rules for the Stage 2 manual growth loop.

The service layer deliberately owns consequential workflow rules.  Routes only
translate forms into calls here, so an invalid state cannot be reached through
another screen later.
"""

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuditEvent,
    Challenge,
    ChallengeRecommendation,
    Concept,
    ConceptStatus,
    CreativeRun,
    CreativeRunSignal,
    CreativeRunStatus,
    Experiment,
    ExperimentStatus,
    FinalDecision,
    GateVerdict,
    Learning,
    LearningStatus,
    Product,
    Signal,
    SignalStatus,
)
from app.services import current_truth

GATE_NAMES = (
    "Remarkable",
    "Logo-Off",
    "Product-Owned",
    "Commercially Convertible",
    "Buyable / Internally Defensible",
)


class ManualLoopError(ValueError):
    """A state or validation rule prevents a manual-loop action."""


def _now() -> datetime:
    return datetime.now(UTC)


def _required(values: dict[str, str], fields: tuple[str, ...]) -> dict[str, str]:
    cleaned = {key: (values.get(key) or "").strip() for key in fields}
    missing = [key.replace("_", " ") for key, value in cleaned.items() if not value]
    if missing:
        raise ManualLoopError(f"Complete: {', '.join(missing)}.")
    return cleaned


def audit(
    db: Session,
    event_type: str,
    product_id: str,
    subject_type: str,
    subject_id: str,
    detail: str,
) -> None:
    db.add(
        AuditEvent(
            event_type=event_type,
            product_id=product_id,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=detail,
        )
    )


def signal_snapshot(signal: Signal) -> dict[str, str | None]:
    return {
        "id": signal.id,
        "source": signal.source,
        "evidence": signal.evidence,
        "url": signal.url,
        "audience": signal.audience,
        "tension_pain": signal.tension_pain,
        "why_now": signal.why_now,
        "product_relevance": signal.product_relevance,
        "buying_trigger": signal.buying_trigger,
        "half_life": signal.half_life,
        "status_at_selection": signal.status,
    }


def create_signal(db: Session, product_id: str, values: dict[str, str]) -> Signal:
    fields = (
        "source",
        "evidence",
        "audience",
        "tension_pain",
        "why_now",
        "product_relevance",
        "buying_trigger",
        "half_life",
    )
    value = _required(values, fields)
    signal = Signal(product_id=product_id, url=(values.get("url") or "").strip() or None, **value)
    db.add(signal)
    db.commit()
    return signal


def update_signal(db: Session, signal: Signal, values: dict[str, str]) -> Signal:
    if signal.status == SignalStatus.ARCHIVED:
        raise ManualLoopError("Archived signals cannot be edited.")
    fields = (
        "source",
        "evidence",
        "audience",
        "tension_pain",
        "why_now",
        "product_relevance",
        "buying_trigger",
        "half_life",
    )
    for key, value in _required(values, fields).items():
        setattr(signal, key, value)
    signal.url = (values.get("url") or "").strip() or None
    signal.updated_at = _now()
    db.commit()
    return signal


def archive_signal(db: Session, signal: Signal) -> None:
    if signal.status == SignalStatus.ARCHIVED:
        return
    signal.status = SignalStatus.ARCHIVED
    signal.updated_at = _now()
    audit(db, "signal.archived", signal.product_id, "signal", signal.id, "Signal archived.")
    db.commit()


def create_creative_run(db: Session, product: Product, signal_ids: list[str]) -> CreativeRun:
    unique_ids = list(dict.fromkeys(signal_ids))
    if not 1 <= len(unique_ids) <= 3:
        raise ManualLoopError("Select between one and three active signals.")
    signals = list(
        db.scalars(
            select(Signal).where(
                Signal.product_id == product.id,
                Signal.id.in_(unique_ids),
                Signal.status != SignalStatus.ARCHIVED,
            )
        )
    )
    if len(signals) != len(unique_ids):
        raise ManualLoopError("One or more selected signals are unavailable.")
    truth = current_truth(db, product.id)
    whitespace = truth.content["creative_whitespace"]["value"]
    run = CreativeRun(
        product_id=product.id,
        truth_version_id=truth.id,
        truth_snapshot=deepcopy(truth.content),
        whitespace_snapshot=whitespace,
    )
    db.add(run)
    db.flush()
    for signal in signals:
        db.add(
            CreativeRunSignal(
                creative_run_id=run.id,
                signal_id=signal.id,
                signal_snapshot=signal_snapshot(signal),
            )
        )
        signal.status = SignalStatus.SELECTED
        signal.updated_at = _now()
    db.commit()
    return run


CONCEPT_FIELDS = (
    "tension",
    "creative_mechanic",
    "artifact",
    "product_proof",
    "participation",
    "distribution",
    "commercial_bridge",
    "dangerous_assumption",
)


def save_concept(
    db: Session, run: CreativeRun, values: dict[str, str], concept: Concept | None = None
) -> Concept:
    if run.status != CreativeRunStatus.ACTIVE:
        raise ManualLoopError("Only active creative runs can be changed.")
    cleaned = _required(values, CONCEPT_FIELDS)
    if concept is None:
        concept = Concept(creative_run_id=run.id, **cleaned)
        db.add(concept)
    else:
        if concept.creative_run_id != run.id or concept.status == ConceptStatus.RETAINED:
            raise ManualLoopError("This concept cannot be edited here.")
        for key, value in cleaned.items():
            setattr(concept, key, value)
        if concept.ai_execution_id:
            from app.ai_service import Collision, claim_warnings

            concept.claim_warnings = claim_warnings(Collision(**cleaned), run)
        concept.updated_at = _now()
    db.commit()
    return concept


def shortlist_concept(db: Session, concept: Concept) -> None:
    if concept.status not in (ConceptStatus.ROUGH, ConceptStatus.REVISE):
        raise ManualLoopError("Only rough or revised concepts can be shortlisted.")
    shortlisted = db.scalar(
        select(Concept)
        .where(
            Concept.creative_run_id == concept.creative_run_id,
            Concept.status == ConceptStatus.SHORTLISTED,
        )
        .limit(1)
    )
    count = len(
        list(
            db.scalars(
                select(Concept).where(
                    Concept.creative_run_id == concept.creative_run_id,
                    Concept.status == ConceptStatus.SHORTLISTED,
                )
            )
        )
    )
    if shortlisted and count >= 3:
        raise ManualLoopError("A creative run can shortlist no more than three concepts.")
    concept.status = ConceptStatus.SHORTLISTED
    concept.updated_at = _now()
    db.commit()


def save_challenge(
    db: Session,
    concept: Concept,
    gates: dict[str, dict[str, str]],
    values: dict[str, str],
    unsupported_resolved: bool,
) -> Challenge:
    if concept.status not in (ConceptStatus.SHORTLISTED, ConceptStatus.REVISE):
        raise ManualLoopError("Challenge only a shortlisted or revised concept.")
    for gate in GATE_NAMES:
        answer = gates.get(gate, {})
        if answer.get("verdict") not in {item.value for item in GateVerdict}:
            raise ManualLoopError(f"Set a valid verdict for {gate}.")
        if not (answer.get("reasoning") or "").strip():
            raise ManualLoopError(f"Explain the {gate} verdict.")
    cleaned = _required(
        values,
        (
            "strongest_reason",
            "strongest_objection",
            "unsupported_claims",
            "smallest_repair",
            "recommendation",
        ),
    )
    if cleaned["recommendation"] not in {item.value for item in ChallengeRecommendation}:
        raise ManualLoopError("Set a valid challenge recommendation.")
    challenge = concept.challenge
    if challenge is None:
        challenge = Challenge(
            concept_id=concept.id, gates=gates, unsupported_resolved=unsupported_resolved, **cleaned
        )
        db.add(challenge)
        concept.challenge = challenge
    else:
        challenge.gates = gates
        challenge.unsupported_resolved = unsupported_resolved
        for key, value in cleaned.items():
            setattr(challenge, key, value)
        challenge.updated_at = _now()
    db.commit()
    return challenge


def decide_concept(db: Session, concept: Concept, decision: str) -> None:
    if decision == "retain":
        challenge = concept.challenge
        if challenge is None:
            raise ManualLoopError("Save the manual challenge before retaining a concept.")
        if concept.claim_warnings:
            raise ManualLoopError("Resolve generated claim warnings before promotion.")
        if challenge.gates["Product-Owned"]["verdict"] == GateVerdict.FAIL:
            raise ManualLoopError("Product-Owned = FAIL blocks promotion.")
        if not challenge.unsupported_resolved:
            raise ManualLoopError("Resolve unsupported claims before promotion.")
        retained = db.scalar(
            select(Concept).where(
                Concept.creative_run_id == concept.creative_run_id,
                Concept.status == ConceptStatus.RETAINED,
            )
        )
        if retained and retained.id != concept.id:
            raise ManualLoopError("A creative run can retain only one concept.")
        concept.status = ConceptStatus.RETAINED
        event = "concept.retained"
        detail = "Concept retained for experiment design."
    elif decision == "kill":
        concept.status = ConceptStatus.KILLED
        event = "concept.killed"
        detail = "Concept killed after manual challenge."
    elif decision == "revise":
        concept.status = ConceptStatus.REVISE
        event = "concept.revise"
        detail = "Concept returned for repair."
    else:
        raise ManualLoopError("Choose retain, revise, or kill.")
    concept.updated_at = _now()
    audit(db, event, concept.creative_run.product_id, "concept", concept.id, detail)
    db.commit()


def close_creative_run(
    db: Session, run: CreativeRun, learning: str, abandoned: bool = False
) -> None:
    if run.status != CreativeRunStatus.ACTIVE:
        raise ManualLoopError("This creative run is already closed.")
    if not learning.strip():
        raise ManualLoopError("Record one short run learning before closing the run.")
    if not abandoned and any(item.status == ConceptStatus.RETAINED for item in run.concepts):
        raise ManualLoopError("The retained concept should continue into its experiment.")
    run.status = CreativeRunStatus.ABANDONED if abandoned else CreativeRunStatus.CLOSED
    run.closure_learning = learning.strip()
    run.closed_at = _now()
    for item in run.signals:
        if item.signal.status == SignalStatus.SELECTED:
            item.signal.status = SignalStatus.USED
            item.signal.updated_at = run.closed_at
    audit(db, "creative_run.closed", run.product_id, "creative_run", run.id, "Creative run closed.")
    db.commit()


def create_experiment(db: Session, concept: Concept) -> Experiment:
    if concept.status != ConceptStatus.RETAINED:
        raise ManualLoopError("Only a retained concept can become an experiment.")
    if concept.experiment:
        return concept.experiment
    experiment = Experiment(
        product_id=concept.creative_run.product_id,
        concept_id=concept.id,
        truth_version_id=concept.creative_run.truth_version_id,
        dangerous_assumption=concept.dangerous_assumption,
    )
    db.add(experiment)
    concept.experiment = experiment
    db.commit()
    return experiment


EXPERIMENT_FIELDS = (
    "hypothesis",
    "dangerous_assumption",
    "smoke_test",
    "seed_targets",
    "product_magic_moment",
    "measures",
    "success_thresholds",
    "test_window",
    "execution_references",
)


def update_experiment(
    db: Session, experiment: Experiment, values: dict[str, str], thresholds_approved: bool
) -> Experiment:
    if experiment.status != ExperimentStatus.DRAFT:
        raise ManualLoopError("Only draft experiments can be configured.")
    for field in EXPERIMENT_FIELDS:
        setattr(experiment, field, (values.get(field) or "").strip() or None)
    experiment.thresholds_approved = thresholds_approved
    experiment.updated_at = _now()
    db.commit()
    return experiment


def _ready_errors(experiment: Experiment) -> list[str]:
    required = (
        ("hypothesis", "hypothesis"),
        ("dangerous_assumption", "dangerous assumption"),
        ("smoke_test", "smoke test"),
        ("seed_targets", "named seed audience / distribution targets"),
        ("product_magic_moment", "product magic moment"),
        ("measures", "measures"),
        ("success_thresholds", "success thresholds"),
        ("test_window", "test window"),
    )
    errors = [label for field, label in required if not getattr(experiment, field)]
    if not experiment.thresholds_approved:
        errors.append("explicitly approved thresholds")
    return errors


def transition_experiment(db: Session, experiment: Experiment, target: str) -> None:
    legal = {
        ExperimentStatus.DRAFT.value: ExperimentStatus.READY.value,
        ExperimentStatus.READY.value: ExperimentStatus.LIVE.value,
        ExperimentStatus.LIVE.value: ExperimentStatus.COMPLETE.value,
    }
    if legal.get(experiment.status) != target:
        raise ManualLoopError("That experiment lifecycle transition is not allowed.")
    if target == ExperimentStatus.READY and (errors := _ready_errors(experiment)):
        raise ManualLoopError(f"Cannot mark READY until there is: {', '.join(errors)}.")
    experiment.status = target
    experiment.updated_at = _now()
    if target in (ExperimentStatus.READY, ExperimentStatus.LIVE):
        audit(
            db,
            f"experiment.{target}",
            experiment.product_id,
            "experiment",
            experiment.id,
            f"Experiment marked {target.upper()}.",
        )
    db.commit()


def save_results(
    db: Session, experiment: Experiment, observed_facts: str, interpretation: str
) -> None:
    if experiment.status not in (ExperimentStatus.LIVE, ExperimentStatus.COMPLETE):
        raise ManualLoopError("Results can be recorded only once the experiment is LIVE.")
    if not observed_facts.strip() or not interpretation.strip():
        raise ManualLoopError("Keep observed facts and interpretation separate, and complete both.")
    experiment.observed_facts = observed_facts.strip()
    experiment.interpretation = interpretation.strip()
    experiment.updated_at = _now()
    db.commit()


def finalize_experiment(
    db: Session, experiment: Experiment, decision: str, reason: str, postmortem: str
) -> None:
    if experiment.status != ExperimentStatus.COMPLETE:
        raise ManualLoopError("Complete the experiment before recording its final decision.")
    if not experiment.observed_facts or not experiment.interpretation:
        raise ManualLoopError("Record results before the final decision.")
    if decision not in {item.value for item in FinalDecision}:
        raise ManualLoopError("Choose SCALE, REVISE, or KILL.")
    if not reason.strip() or not postmortem.strip():
        raise ManualLoopError("A final decision needs a reason and postmortem.")
    experiment.final_decision = decision
    experiment.final_reason = reason.strip()
    experiment.postmortem = postmortem.strip()
    experiment.updated_at = _now()
    audit(
        db,
        "experiment.finalized",
        experiment.product_id,
        "experiment",
        experiment.id,
        f"Final decision: {decision.upper()}.",
    )
    db.commit()


def save_learning(db: Session, experiment: Experiment, values: dict[str, str]) -> Learning:
    if experiment.status != ExperimentStatus.COMPLETE or not experiment.final_decision:
        raise ManualLoopError("A reusable learning follows a completed final decision.")
    fields = _required(values, ("content", "confidence", "qualification"))
    learning = experiment.learning
    if learning is None:
        learning = Learning(experiment_id=experiment.id, **fields)
        db.add(learning)
        experiment.learning = learning
    elif learning.status == LearningStatus.APPROVED:
        raise ManualLoopError("Approved learnings are not silently changed.")
    else:
        for key, value in fields.items():
            setattr(learning, key, value)
        learning.updated_at = _now()
    db.commit()
    return learning


def approve_learning(db: Session, learning: Learning) -> None:
    if learning.status != LearningStatus.DRAFT or not all(
        (learning.content, learning.confidence, learning.qualification)
    ):
        raise ManualLoopError("Complete the draft learning before approval.")
    learning.status = LearningStatus.APPROVED
    learning.approved_at = _now()
    learning.updated_at = learning.approved_at
    audit(
        db,
        "learning.approved",
        learning.experiment.product_id,
        "learning",
        learning.id,
        "Reusable learning approved.",
    )
    db.commit()


def active_runs(db: Session, product_id: str) -> list[CreativeRun]:
    return list(
        db.scalars(
            select(CreativeRun)
            .where(CreativeRun.product_id == product_id)
            .options(
                selectinload(CreativeRun.signals).selectinload(CreativeRunSignal.signal),
                selectinload(CreativeRun.concepts).selectinload(Concept.challenge),
            )
            .order_by(CreativeRun.created_at.desc())
        )
    )
