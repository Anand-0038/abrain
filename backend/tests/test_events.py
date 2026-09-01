import json

from abrain_api.contracts import DomainEvent
from abrain_api.events import new_event, sse_message


def test_event_envelope_is_typed_and_serializable() -> None:
    event = new_event(
        "system.ready",
        correlation_id="correlation-test",
        payload={"boundary": "local"},
    )

    assert isinstance(event, DomainEvent)
    serialized = sse_message(event)
    data = json.loads(serialized.removeprefix("data: ").strip())
    assert data["event_type"] == "system.ready"
    assert data["payload"]["boundary"] == "local"


def test_system_ready_payload_keeps_the_boundary_explicit() -> None:
    event = new_event(
        "system.ready",
        correlation_id="local-startup",
        payload={"boundary": "local", "memory": "not_configured"},
    )
    payload = json.loads(sse_message(event).removeprefix("data: ").strip())

    assert payload["event_type"] == "system.ready"
    assert payload["payload"]["memory"] == "not_configured"


def test_event_envelope_promotes_known_identity_from_payload() -> None:
    event = new_event(
        "behavior.changed_by_memory",
        correlation_id="turn-1",
        payload={
            "owner_id": "owner-a",
            "npc_id": "npc-nova",
            "session_id": "session-2",
            "proof_ref": "memory-1",
        },
    )

    assert event.agent_id == "npc-nova"
    assert event.session_id == "session-2"
    assert event.proof_ref == "memory-1"
