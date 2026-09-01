"""Fresh-session continuity assembly and safe decision boundary."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .agent_runner import AgentRunResult
from .memory import MemoryRecord, MemoryRetrieval, MemorySearchVerdict


class ContinuityRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    npc_id: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=20_000)


class ContinuityDecision(BaseModel):
    status: str
    action: str
    memory_enabled: bool
    influenced_by_memory: bool
    recalled_memory_ids: list[str]
    recalled_memories: list[MemoryRecord]
    retrievals: list[MemoryRetrieval]
    search_verdict: MemorySearchVerdict | None = None
    explanation: str
    agent_response: str
    agent_run: AgentRunResult


def _fallback_agent_result(
    request: ContinuityRequest, records: list[MemoryRetrieval]
) -> AgentRunResult:
    """Keep direct module callers safe while the API uses a configured runner."""

    if not records:
        return AgentRunResult(
            response=(
                f"I can help with {request.query!r}, but I do not have the owner context "
                "needed for a tailored decision. Tell me what should guide it."
            ),
            plan=["Ask for the missing owner context before making a tailored decision."],
            proposed_action="request_missing_context",
            memory_effect="none",
            needs_more_context=True,
        )
    first = records[0].record
    action = f"Use {first.value} as relevant context for {request.query!r}."
    ids = [item.record.memory_id for item in records]
    return AgentRunResult(
        response=f"{action} The scoped context is {first.key}: {first.value}.",
        plan=["Match the request to the scoped owner context.", action],
        proposed_action=action,
        used_memory_ids=ids,
        memory_effect="influenced",
        needs_more_context=False,
        task_update={"used_memory_ids": ids},
    )


def _recalled_context_summary(memories: list[MemoryRecord]) -> str:
    """Create a bounded, provenance-backed summary for the fresh agent reply."""

    items = [f"{memory.key} = {memory.value}" for memory in memories[:3]]
    summary = "; ".join(items)
    if len(memories) > 3:
        summary += f"; +{len(memories) - 3} more"
    return summary


def assemble_continuity(
    request: ContinuityRequest,
    memories: list[MemoryRetrieval] | list[MemoryRecord] | None,
    agent_result: AgentRunResult | None = None,
    search_verdict: MemorySearchVerdict | None = None,
) -> ContinuityDecision:
    """Combine scoped recall and one structured agent run into continuity state."""

    retrievals = [
        item
        if isinstance(item, MemoryRetrieval)
        else MemoryRetrieval(
            record=item,
            query=request.query,
            tier="entity",
            source="sibyl_entity_list",
            relevance_reason="Record supplied by the memory provider.",
        )
        for item in memories or []
    ]
    records = [item.record for item in retrievals]
    result = agent_result or _fallback_agent_result(request, retrievals)
    used_ids = [
        memory_id
        for memory_id in result.used_memory_ids
        if memory_id in {item.record.memory_id for item in retrievals}
    ]
    if used_ids != result.used_memory_ids:
        result = result.model_copy(update={"used_memory_ids": used_ids, "memory_effect": "none"})
    influenced = result.memory_effect == "influenced" and bool(result.used_memory_ids)

    if memories is None:
        return ContinuityDecision(
            status="continuity_unavailable",
            action=result.proposed_action,
            memory_enabled=False,
            influenced_by_memory=False,
            recalled_memory_ids=[],
            recalled_memories=[],
            retrievals=[],
            search_verdict=None,
            explanation=(
                "Persistent memory is disabled. The fresh session must ask for context "
                "rather than inventing previous preferences or decisions."
            ),
            agent_response=result.response,
            agent_run=result,
        )
    if not records:
        return ContinuityDecision(
            status="no_relevant_memory",
            action=result.proposed_action,
            memory_enabled=True,
            influenced_by_memory=False,
            recalled_memory_ids=[],
            recalled_memories=[],
            retrievals=[],
            search_verdict=search_verdict,
            explanation=(
                search_verdict.explanation
                if search_verdict is not None
                else "Sibyl is available, but no relevant owner context was recalled."
            ),
            agent_response=result.response,
            agent_run=result,
        )
    return ContinuityDecision(
        status="context_restored",
        action=result.proposed_action,
        memory_enabled=True,
        influenced_by_memory=influenced,
        recalled_memory_ids=[memory.memory_id for memory in records],
        recalled_memories=records,
        retrievals=retrievals,
        search_verdict=search_verdict,
        explanation=(
            "The agent runner received only the Sibyl records relevant to this request. "
            "Used memory IDs identify the records that materially changed its action."
        ),
        agent_response=result.response,
        agent_run=result,
    )
