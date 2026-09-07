"""Small, deterministic progression rail state for the current operator loop."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Concept,
    ConceptStatus,
    CreativeRun,
    Experiment,
    ExperimentStatus,
    Learning,
    LearningStatus,
    Product,
    Signal,
)

STAGES = ("Truth", "Signals", "Concepts", "Challenge", "Experiment", "Result", "Learning")


def progression(db: Session, product: Product, truth_version: int) -> dict:
    signals = list(db.scalars(select(Signal).where(Signal.product_id == product.id)))
    run = db.scalar(
        select(CreativeRun)
        .where(CreativeRun.product_id == product.id)
        .order_by(CreativeRun.created_at.desc())
    )
    concepts = (
        []
        if run is None
        else list(db.scalars(select(Concept).where(Concept.creative_run_id == run.id)))
    )
    experiment = (
        None
        if run is None
        else db.scalar(
            select(Experiment)
            .join(Concept, Experiment.concept_id == Concept.id)
            .where(Concept.creative_run_id == run.id)
            .order_by(Experiment.updated_at.desc())
        )
    )
    learning = (
        None
        if experiment is None
        else db.scalar(select(Learning).where(Learning.experiment_id == experiment.id))
    )

    completed: set[str] = {"Truth"}
    if signals:
        completed.add("Signals")
    if concepts:
        completed.add("Concepts")
    if any(item.challenge for item in concepts):
        completed.add("Challenge")
    if experiment:
        completed.add("Experiment")
    if experiment and experiment.observed_facts and experiment.interpretation:
        completed.add("Result")
    if learning and learning.status == LearningStatus.APPROVED:
        completed.add("Learning")

    if not signals:
        current, next_action, latest = (
            "Signals",
            "Capture a signal with evidence.",
            f"Truth v{truth_version} approved",
        )
    elif run is None:
        current, next_action, latest = (
            "Signals",
            "Select one to three signals for a creative run.",
            "Signals ready",
        )
    elif not concepts:
        current, next_action, latest = (
            "Concepts",
            "Generate 12 collisions from this run's frozen evidence.",
            "Creative run active",
        )
    elif not any(item.challenge for item in concepts if item.status == ConceptStatus.SHORTLISTED):
        current, next_action, latest = (
            "Challenge",
            "Shortlist up to three concepts, then challenge one.",
            "Concepts in play",
        )
    elif experiment is None:
        current, next_action, latest = (
            "Experiment",
            "Retain one defensible concept or close the run.",
            "Manual challenge recorded",
        )
    elif experiment.status == ExperimentStatus.DRAFT:
        current, next_action, latest = (
            "Experiment",
            "Define targets, thresholds and a test window.",
            "Experiment draft",
        )
    elif experiment.status == ExperimentStatus.READY:
        current, next_action, latest = (
            "Experiment",
            "Confirm external execution has started.",
            "Experiment READY",
        )
    elif experiment.status == ExperimentStatus.LIVE:
        current, next_action, latest = (
            "Result",
            "Record observed facts and interpretation.",
            "Experiment LIVE",
        )
    elif not experiment.final_decision:
        current, next_action, latest = (
            "Learning",
            "Make the final decision and record a reusable learning.",
            "Experiment COMPLETE",
        )
    elif not learning or learning.status != LearningStatus.APPROVED:
        current, next_action, latest = (
            "Learning",
            "Approve the reusable learning.",
            f"Decision: {experiment.final_decision.upper()}",
        )
    else:
        current, next_action, latest = (
            "Learning",
            "Use the approved learning in the next creative run.",
            "Learning approved",
        )

    return {
        "stages": [
            {
                "label": stage,
                "state": (
                    "complete"
                    if stage in completed
                    else "current" if stage == current else "upcoming"
                ),
            }
            for stage in STAGES
        ],
        "latest": latest,
        "next_action": next_action,
    }
