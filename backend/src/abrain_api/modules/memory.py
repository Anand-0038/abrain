from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field

MemoryConcept = Literal[
    "person",
    "preference",
    "relationship",
    "habit",
    "decision",
    "constraint",
    "value",
    "goal",
    "project",
    "event",
]


class MemoryRecord(BaseModel):
    """Generic owner-context record persisted through the application memory boundary."""

    memory_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)
    concept: MemoryConcept
    subject_id: str | None = None
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_session_id: str = Field(min_length=1)
    created_at: datetime
    supersedes: str | None = None
    evidence_ref: str | None = None


class MemoryRetrieval(BaseModel):
    """A provider-backed match with enough provenance to explain the recall."""

    record: MemoryRecord
    query: str
    tier: str
    source: Literal["sibyl_search", "sibyl_entity_list", "abrain_scoped_handoff"]
    provider_rank: float | None = None
    provider_snippet: str | None = None
    relevance_reason: str = Field(min_length=1)


class MemoryProvider(Protocol):
    async def write(self, record: MemoryRecord) -> None:
        """Persist a promoted record through the verified Sibyl boundary."""

    async def recall(self, owner_id: str, npc_id: str, query: str) -> list[MemoryRecord]:
        """Recall records for a genuinely fresh session."""


class MemoryProviderNotConfigured(RuntimeError):
    """Raised instead of pretending that local process state is persistent memory."""
