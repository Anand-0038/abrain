from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    """Safe proof metadata kept separate from raw provider receipts."""

    evidence_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    recorded_at: datetime
    source_event_id: str = Field(min_length=1)


class ProofStep(BaseModel):
    step: str = Field(min_length=1)
    status: str = Field(min_length=1)
    evidence: EvidenceReference | None = None
