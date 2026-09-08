"""Versioned, task-owned structured-output contracts for Stage 3."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Collision(AIModel):
    tension: str = Field(min_length=1)
    creative_mechanic: str = Field(min_length=1)
    artifact: str = Field(min_length=1)
    product_proof: str = Field(min_length=1)
    participation: str = Field(min_length=1)
    distribution: str = Field(min_length=1)
    commercial_bridge: str = Field(min_length=1)
    dangerous_assumption: str = Field(min_length=1)


class CollisionBatch(AIModel):
    concepts: list[Collision] = Field(min_length=12, max_length=12)


class ChallengeGateVerdict(StrEnum):
    PASS = "PASS"
    WEAK = "WEAK"
    FAIL = "FAIL"


class AIChallengeRecommendation(StrEnum):
    GO = "GO"
    REVISE = "REVISE"
    KILL = "KILL"


class GateAssessment(AIModel):
    verdict: ChallengeGateVerdict
    reasoning: str = Field(min_length=1, max_length=1200)
    evidence_refs: list[str] = Field(min_length=1, max_length=5)


class UnsupportedClaimConcern(AIModel):
    concern: str = Field(min_length=1, max_length=1200)
    evidence_refs: list[str] = Field(min_length=2, max_length=5)


class ChallengeAssessment(AIModel):
    remarkable: GateAssessment
    logo_off: GateAssessment
    product_owned: GateAssessment
    commercially_convertible: GateAssessment
    buyable_internally_defensible: GateAssessment
    strongest_reason: str = Field(min_length=1, max_length=1500)
    strongest_objection: str = Field(min_length=1, max_length=1500)
    unsupported_claims: list[UnsupportedClaimConcern] = Field(max_length=8)
    smallest_repair: str = Field(min_length=1, max_length=1500)
    recommendation: AIChallengeRecommendation
