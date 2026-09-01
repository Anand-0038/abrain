import json
from datetime import UTC, datetime
from uuid import uuid4

from .contracts import DomainEvent, EventType


def new_event(
    event_type: EventType,
    *,
    correlation_id: str,
    payload: dict[str, object] | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    proof_ref: str | None = None,
) -> DomainEvent:
    """Create an envelope for a real backend lifecycle event."""
    event_payload = payload or {}
    return DomainEvent(
        event_id=f"evt_{uuid4().hex}",
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        source="abrain-runtime",
        correlation_id=correlation_id,
        agent_id=agent_id or _string_value(event_payload, "agent_id", "npc_id"),
        session_id=session_id
        or _string_value(event_payload, "session_id", "fresh_session_id", "terminated_session_id"),
        proof_ref=proof_ref or _string_value(event_payload, "proof_ref"),
        payload=event_payload,
    )


def _string_value(payload: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def sse_message(event: DomainEvent) -> str:
    return f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
