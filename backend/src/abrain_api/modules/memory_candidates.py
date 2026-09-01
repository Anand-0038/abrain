"""Strict, story-independent memory-candidate policy.

The model/extractor is deliberately an upstream boundary. It must return this
validated structure; this module decides whether the candidate may cross into
durable Sibyl memory. A transcript is never accepted as a memory record.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .memory import MemoryConcept, MemoryRecord

CandidateDisposition = Literal["promote", "confirm", "reject"]


class MemoryCandidate(BaseModel):
    """Structured output expected from a model-backed extraction step."""

    candidate_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)
    source_session_id: str = Field(min_length=1)
    source_turn_id: str = Field(min_length=1)
    concept: MemoryConcept
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    explicit_remember: bool = False
    sensitive: bool = False
    transient: bool = False


class PromotionDecision(BaseModel):
    disposition: CandidateDisposition
    reason: str = Field(min_length=1)


def decide_promotion(candidate: MemoryCandidate) -> PromotionDecision:
    """Apply the A-Brain consent policy to one validated candidate."""

    if candidate.transient:
        return PromotionDecision(disposition="reject", reason="transient context is not durable")
    if candidate.sensitive:
        return PromotionDecision(disposition="confirm", reason="sensitive context requires consent")
    if candidate.explicit_remember:
        return PromotionDecision(disposition="promote", reason="owner explicitly requested memory")
    if candidate.confidence >= 0.9:
        return PromotionDecision(disposition="promote", reason="high-confidence durable context")
    return PromotionDecision(disposition="confirm", reason="inferred context needs confirmation")


def candidate_to_record(candidate: MemoryCandidate, *, confirmed: bool = False) -> MemoryRecord:
    """Convert only a promoted candidate into the provider-neutral record model."""

    decision = decide_promotion(candidate)
    if decision.disposition == "reject":
        raise ValueError("rejected candidates cannot become durable memory records")
    if decision.disposition == "confirm" and not confirmed:
        raise ValueError("candidate confirmation is required before promotion")
    return MemoryRecord(
        memory_id=candidate.candidate_id,
        owner_id=candidate.owner_id,
        npc_id=candidate.npc_id,
        concept=candidate.concept,
        key=candidate.key,
        value=candidate.value,
        confidence=candidate.confidence,
        source_session_id=candidate.source_session_id,
        evidence_ref=candidate.source_turn_id,
        created_at=datetime.now(UTC),
    )
