import asyncio
from datetime import UTC, datetime

import pytest

from abrain_api.modules.agent_runner import (
    AgentRunnerError,
    AgentRunRequest,
    AgentRunResult,
    LocalAgentRunner,
    _validate_provider_result,
)
from abrain_api.modules.memory import MemoryRecord, MemoryRetrieval
from abrain_api.modules.npc_identity import NpcIdentity


def retrieval(memory_id: str, value: str, concept: str = "preference") -> MemoryRetrieval:
    return MemoryRetrieval(
        record=MemoryRecord(
            memory_id=memory_id,
            owner_id="owner-a",
            npc_id="nova",
            concept=concept,  # type: ignore[arg-type]
            key="context",
            value=value,
            source_session_id="old-session",
            created_at=datetime.now(UTC),
        ),
        query="current task",
        tier="entity",
        source="sibyl_search",
        provider_rank=1.0,
        provider_snippet=value,
        relevance_reason="Sibyl search returned this WARM entity.",
    )


def request(records: list[MemoryRetrieval]) -> AgentRunRequest:
    return AgentRunRequest(
        request="How should I plan this workspace?",
        session_id="fresh-session",
        npc=NpcIdentity(npc_id="nova", owner_id="owner-a", name="Nova"),
        recalled=records,
        task_state={"fresh_session": True, "turn_count": 0},
    )


def test_local_runner_changes_action_when_scoped_memory_is_available() -> None:
    runner = LocalAgentRunner()
    without_memory = asyncio.run(runner.run(request([])))
    with_memory = asyncio.run(runner.run(request([retrieval("m-dark", "dark interfaces")])))

    assert without_memory.needs_more_context is True
    assert without_memory.used_memory_ids == []
    assert with_memory.needs_more_context is False
    assert with_memory.used_memory_ids == ["m-dark"]
    assert with_memory.memory_effect == "influenced"
    assert with_memory.proposed_action != without_memory.proposed_action
    assert "dark interfaces" in with_memory.response


def test_local_runner_prefers_owner_context_over_derived_task_result() -> None:
    runner = LocalAgentRunner()
    result = asyncio.run(
        runner.run(
            request(
                [
                    retrieval(
                        "m-task-result",
                        "A previous verbose generated answer",
                        concept="decision",
                    ).model_copy(
                        update={
                            "record": retrieval(
                                "m-task-result",
                                "A previous verbose generated answer",
                                concept="decision",
                            ).record.model_copy(update={"key": "task:old:result"})
                        }
                    ),
                    retrieval("m-dark", "calm dark interfaces with clear hierarchy"),
                ]
            )
        )
    )

    assert result.used_memory_ids == ["m-dark"]
    assert "calm dark interfaces" in result.response
    assert "previous verbose" not in result.response


def test_runner_rejects_memory_ids_outside_the_scoped_input() -> None:
    supplied = request([retrieval("m-allowed", "dark interfaces")])
    result = AgentRunResult(
        response="unsafe",
        proposed_action="use hidden memory",
        used_memory_ids=["m-not-supplied"],
        memory_effect="influenced",
        needs_more_context=False,
    )

    with pytest.raises(AgentRunnerError, match="outside the supplied context"):
        _validate_provider_result(result, supplied)
