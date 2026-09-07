"""Versioned, task-owned structured-output contracts for Stage 3."""

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
