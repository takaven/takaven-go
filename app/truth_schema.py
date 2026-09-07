from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Confidence(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"


class TruthItem(BaseModel):
    value: str = Field(min_length=2, max_length=3000)
    confidence: Confidence
    basis: str = Field(min_length=2, max_length=1000)

    @field_validator("value", "basis")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class TruthContent(BaseModel):
    icp: TruthItem
    buyer: TruthItem
    user: TruthItem
    buying_trigger: TruthItem
    ugly_workaround: TruthItem
    core_pain: TruthItem
    emotional_tension: TruthItem
    operational_consequence: TruthItem
    magic_moment: TruthItem
    demonstrable_proof: TruthItem
    strongest_defensible_promise: TruthItem
    prohibited_claims: TruthItem
    category_cliches: TruthItem
    creative_whitespace: TruthItem
    initial_distribution_sources: TruthItem


TRUTH_LABELS = {
    "icp": "Ideal customer profile",
    "buyer": "Buyer",
    "user": "User",
    "buying_trigger": "Buying trigger",
    "ugly_workaround": "Ugly workaround",
    "core_pain": "Core pain",
    "emotional_tension": "Emotional tension",
    "operational_consequence": "Operational consequence",
    "magic_moment": "Magic moment",
    "demonstrable_proof": "Demonstrable proof",
    "strongest_defensible_promise": "Strongest defensible promise",
    "prohibited_claims": "Prohibited / unsupported claims",
    "category_cliches": "Category clichés",
    "creative_whitespace": "Creative whitespace",
    "initial_distribution_sources": "Initial distribution sources",
}
