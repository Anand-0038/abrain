from datetime import UTC, datetime

from abrain_api.modules.continuity import ContinuityRequest, assemble_continuity
from abrain_api.modules.memory import MemoryRecord


def test_disabled_memory_requests_context_without_inventing_recall() -> None:
    decision = assemble_continuity(
        ContinuityRequest(owner_id="owner-a", npc_id="nova", query="workspace"), None
    )

    assert decision.action == "request_missing_context"
    assert decision.influenced_by_memory is False
    assert decision.recalled_memory_ids == []
    assert decision.agent_run.needs_more_context is True
    assert "owner context" in decision.agent_response


def test_recalled_memory_changes_continuity_action() -> None:
    memory = MemoryRecord(
        memory_id="m1",
        owner_id="owner-a",
        npc_id="nova",
        concept="preference",
        key="interface_style",
        value="dark interfaces",
        source_session_id="old-session",
        created_at=datetime.now(UTC),
    )
    decision = assemble_continuity(
        ContinuityRequest(owner_id="owner-a", npc_id="nova", query="workspace"), [memory]
    )

    assert decision.action.startswith("Use dark interfaces")
    assert decision.influenced_by_memory is True
    assert decision.recalled_memory_ids == ["m1"]
    assert "agent runner received" in decision.explanation
    assert decision.agent_run.used_memory_ids == ["m1"]
    assert "dark interfaces" in decision.agent_response
