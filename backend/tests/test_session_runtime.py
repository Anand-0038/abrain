from datetime import UTC, datetime

from abrain_api.modules.conversation import ConversationTurn
from abrain_api.modules.session_runtime import SessionRuntime


def test_two_restarts_create_distinct_empty_sessions() -> None:
    runtime = SessionRuntime()
    first = runtime.start("npc-nova")
    runtime.add_turn(
        ConversationTurn(
            turn_id="turn-1",
            session_id=first.session_id,
            speaker="owner",
            text="Remember that I prefer concise plans.",
            occurred_at=datetime.now(UTC),
        )
    )

    terminated, second = runtime.restart(first.session_id)
    assert terminated.status == "terminated"
    assert second.session_id != first.session_id
    assert runtime.turns(second.session_id) == []
    assert runtime.turns(first.session_id) == []

    terminated_again, third = runtime.restart(second.session_id)
    assert terminated_again.session_id == second.session_id
    assert third.session_id not in {first.session_id, second.session_id}
    assert runtime.turns(third.session_id) == []
