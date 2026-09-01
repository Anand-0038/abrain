"""Bounded agent-to-agent delegation over A-Brain's memory permission layer."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .memory import MemoryRecord

HandoffStatus = Literal["created", "accepted", "working", "completed", "blocked"]


class HandoffContext(BaseModel):
    """The minimum provenance-bearing memory view authorized for a target agent."""

    memory_id: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    key: str = Field(min_length=1)
    value: str = Field(min_length=1, max_length=2_000)
    source_session_id: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime
    evidence_ref: str | None = None
    tier: Literal["entity"] = "entity"
    relevance_reason: str = Field(min_length=1)

    @classmethod
    def from_record(cls, record: MemoryRecord, objective: str) -> HandoffContext:
        return cls(
            memory_id=record.memory_id,
            concept=record.concept,
            key=record.key,
            value=record.value,
            source_session_id=record.source_session_id,
            confidence=record.confidence,
            created_at=record.created_at,
            evidence_ref=record.evidence_ref,
            relevance_reason=(
                f"Explicitly selected by the source agent for the delegated objective: {objective}."
            ),
        )


class ScopedHandoff(BaseModel):
    """An auditable, owner-scoped context handoff between two A-Brain agents."""

    handoff_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    source_agent_id: str = Field(min_length=1)
    target_agent_id: str = Field(min_length=1)
    parent_task_id: str = Field(min_length=1)
    child_task_id: str = Field(min_length=1)
    objective: str = Field(min_length=1, max_length=20_000)
    selected_memory_ids: list[str] = Field(min_length=1, max_length=20)
    selected_context: list[HandoffContext] = Field(min_length=1, max_length=20)
    status: HandoffStatus = "created"
    created_at: datetime
    completed_at: datetime | None = None
    result: str | None = Field(default=None, max_length=8_000)


class HandoffRuntimeError(RuntimeError):
    """Raised when an in-process handoff index cannot satisfy a request."""


class HandoffRuntime:
    """Short-lived handoff index; the adapter is the durable HOT boundary."""

    def __init__(self) -> None:
        self._items: dict[str, ScopedHandoff] = {}
        self._lock = RLock()

    def create(self, handoff: ScopedHandoff) -> ScopedHandoff:
        with self._lock:
            if handoff.handoff_id in self._items:
                raise HandoffRuntimeError("handoff already exists")
            self._items[handoff.handoff_id] = handoff
        return handoff

    def get(self, handoff_id: str) -> ScopedHandoff:
        with self._lock:
            try:
                return self._items[handoff_id]
            except KeyError as exc:
                raise HandoffRuntimeError("handoff not found") from exc

    def restore(self, handoff: ScopedHandoff) -> ScopedHandoff:
        with self._lock:
            existing = self._items.get(handoff.handoff_id)
            if existing is not None and existing != handoff:
                raise HandoffRuntimeError("handoff conflicts with the cached handoff")
            self._items[handoff.handoff_id] = handoff
        return handoff

    def update(self, handoff_id: str, **changes: object) -> ScopedHandoff:
        with self._lock:
            current = self.get(handoff_id)
            updated = current.model_copy(update=changes)
            self._items[handoff_id] = updated
            return updated

    def list(self, owner_id: str) -> list[ScopedHandoff]:
        with self._lock:
            items = [item for item in self._items.values() if item.owner_id == owner_id]
        return sorted(items, key=lambda item: item.created_at, reverse=True)


def new_handoff(
    *,
    owner_id: str,
    source_agent_id: str,
    target_agent_id: str,
    parent_task_id: str,
    child_task_id: str,
    objective: str,
    selected_context: list[HandoffContext],
) -> ScopedHandoff:
    return ScopedHandoff(
        handoff_id=f"handoff_{uuid4().hex}",
        owner_id=owner_id,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        parent_task_id=parent_task_id,
        child_task_id=child_task_id,
        objective=objective.strip(),
        selected_memory_ids=[item.memory_id for item in selected_context],
        selected_context=selected_context,
        status="created",
        created_at=datetime.now(UTC),
    )
