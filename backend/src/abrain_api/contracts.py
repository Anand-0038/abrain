from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "system.ready",
    "system.heartbeat",
    "owner.created",
    "npc.created",
    "npc.customized",
    "conversation.turn_recorded",
    "memory.extraction_failed",
    "memory.candidate_detected",
    "memory.candidate_created",
    "memory.candidate_promoted",
    "memory.candidate_rejected",
    "memory.candidate_confirmed",
    "memory.candidate_undone",
    "memory.write_requested",
    "memory.write_succeeded",
    "memory.write_failed",
    "memory.object_materialized",
    "memory.updated",
    "memory.archived",
    "memory.deleted",
    "npc.session_started",
    "npc.session_restarted",
    "npc.session_terminated",
    "memory.recall_requested",
    "memory.recall_failed",
    "memory.recall_succeeded",
    "continuity.memory_disabled",
    "behavior.changed_by_memory",
    "task.created",
    "task.started",
    "task.step_changed",
    "task.blocked",
    "task.completed",
    "handoff.created",
    "handoff.accepted",
    "handoff.started",
    "handoff.completed",
    "handoff.blocked",
    "agent.run_failed",
    "causal.replay_requested",
    "causal.replay_completed",
    "continuity.failed",
    "conversation.completed",
]


class DomainEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    event_type: EventType
    occurred_at: datetime
    source: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    agent_id: str | None = None
    session_id: str | None = None
    proof_ref: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok"]
    environment: str
    memory_boundary: Literal["not_configured", "sibyl_local", "disabled"]
    checked_at: datetime
