"""Provider-neutral agent execution over scoped persistent context."""

from __future__ import annotations

import json
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .gemini_transport import post_json_with_retry
from .memory import MemoryRetrieval
from .npc_identity import NpcIdentity

MemoryEffect = Literal["none", "influenced", "blocked"]


class AgentRunnerError(RuntimeError):
    """Raised when an agent provider cannot return trustworthy structured output."""


class AgentRunRequest(BaseModel):
    """The complete, bounded context supplied to one agent execution."""

    request: str = Field(min_length=1, max_length=20_000)
    session_id: str = Field(min_length=1)
    npc: NpcIdentity
    recalled: list[MemoryRetrieval] = Field(default_factory=list, max_length=50)
    task_state: dict[str, object] | None = None


class AgentRunResult(BaseModel):
    """Structured output shared by local and model-backed agent runners."""

    model_config = ConfigDict(extra="forbid")

    response: str = Field(min_length=1, max_length=8_000)
    plan: list[str] = Field(default_factory=list, max_length=8)
    proposed_action: str = Field(min_length=1, max_length=2_000)
    used_memory_ids: list[str] = Field(default_factory=list, max_length=50)
    memory_effect: MemoryEffect
    needs_more_context: bool
    task_update: dict[str, object] | None = None


class AgentRunner(Protocol):
    async def run(self, request: AgentRunRequest) -> AgentRunResult: ...


def agent_schema() -> dict[str, object]:
    """Return the strict JSON schema sent to model providers."""

    return {
        "type": "object",
        "properties": {
            "response": {"type": "string"},
            "plan": {"type": "array", "items": {"type": "string"}},
            "proposed_action": {"type": "string"},
            "used_memory_ids": {"type": "array", "items": {"type": "string"}},
            "memory_effect": {"type": "string", "enum": ["none", "influenced", "blocked"]},
            "needs_more_context": {"type": "boolean"},
            "task_update": {"type": "object"},
        },
        "required": [
            "response",
            "plan",
            "proposed_action",
            "used_memory_ids",
            "memory_effect",
            "needs_more_context",
            "task_update",
        ],
    }


def _validate_provider_result(result: AgentRunResult, request: AgentRunRequest) -> AgentRunResult:
    allowed_ids = {item.record.memory_id for item in request.recalled}
    used_ids = set(result.used_memory_ids)
    if not used_ids.issubset(allowed_ids):
        raise AgentRunnerError("agent output referenced memory outside the supplied context")
    if result.memory_effect == "influenced" and not result.used_memory_ids:
        raise AgentRunnerError("agent marked memory as influential without used memory IDs")
    if result.used_memory_ids and result.memory_effect != "influenced":
        raise AgentRunnerError("agent returned used memory IDs without an influenced effect")
    return result


class LocalAgentRunner:
    """Credential-free runner used for local development and deterministic tests.

    This is the same structured agent pipeline as the model-backed runner. It is
    deliberately conservative: without scoped memory it asks for context instead
    of pretending to know the owner, and with memory it turns the retrieved facts
    into a request-specific action.
    """

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        if not request.recalled:
            if request.task_state and isinstance(request.task_state.get("task_id"), str):
                objective = str(request.task_state.get("objective") or request.request)
                return AgentRunResult(
                    response=(
                        f"I prepared a bounded plan for {objective!r}. The credential-free local "
                        "runner did not call external tools or claim external facts, so the plan "
                        "is ready for review rather than presented as completed research."
                    ),
                    plan=[
                        "Understand the task objective and its current state.",
                        "Work through the requested mission using the available request context.",
                        "Return the result and keep follow-up work explicit.",
                    ],
                    proposed_action="prepare_task_plan",
                    memory_effect="none",
                    needs_more_context=False,
                    task_update={
                        "current_step": "Bounded plan prepared from the task objective",
                        "result_ready": True,
                        "requires_review": True,
                    },
                )
            return AgentRunResult(
                response=(
                    f"I can help with {request.request!r}, but this session has no relevant "
                    "owner context. Tell me the preference, goal, or constraint that should "
                    "guide the decision."
                ),
                plan=["Ask for the missing owner context before making a tailored decision."],
                proposed_action="request_missing_context",
                memory_effect="none",
                needs_more_context=True,
            )

        # Task-result memories are useful provenance, but they should not drown out
        # the owner's durable facts when both match a query. Model-backed runners
        # can make this distinction semantically; the credential-free runner keeps
        # it deterministic and conservative.
        durable_records = [
            item
            for item in request.recalled
            if not (item.record.concept == "decision" and item.record.key.startswith("task:"))
        ]
        records = (durable_records or request.recalled)[:4]
        first = records[0].record
        if first.concept == "constraint":
            proposed_action = f"Hold the request until {first.value} is satisfied."
        elif first.concept == "goal":
            proposed_action = (
                f"Make the next step toward {first.value} while handling this request."
            )
        elif first.concept == "decision":
            proposed_action = f"Keep the decision '{first.value}' in force for this request."
        elif first.concept == "preference":
            proposed_action = f"Use {first.value} as the default while handling this request."
        else:
            proposed_action = f"Use {first.value} as relevant context for this request."
        context = "; ".join(f"{item.record.key}: {item.record.value}" for item in records)
        response = (
            f"For {request.request!r}, I would take this path: {proposed_action} "
            f"The scoped brain context is {context}."
        )
        return _validate_provider_result(
            AgentRunResult(
                response=response,
                plan=[
                    "Match the request to the scoped owner context.",
                    proposed_action,
                    "Keep the remaining context available for the next task.",
                ],
                proposed_action=proposed_action,
                used_memory_ids=[item.record.memory_id for item in records],
                memory_effect="influenced",
                needs_more_context=False,
                task_update={
                    "last_proposed_action": proposed_action,
                    "used_memory_ids": [item.record.memory_id for item in records],
                },
            ),
            request,
        )


def parse_agent_response(payload: object) -> AgentRunResult:
    """Validate a Gemini response envelope and its structured agent output."""

    if not isinstance(payload, dict):
        raise AgentRunnerError("agent provider response was not an object")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise AgentRunnerError("agent provider response contained no candidate")
    content = candidates[0].get("content")
    if not isinstance(content, dict):
        raise AgentRunnerError("agent provider content was malformed")
    parts = content.get("parts")
    if not isinstance(parts, list) or not parts or not isinstance(parts[0], dict):
        raise AgentRunnerError("agent provider content contained no text part")
    text = parts[0].get("text")
    if not isinstance(text, str):
        raise AgentRunnerError("agent provider response text was missing")
    try:
        return AgentRunResult.model_validate(json.loads(text))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise AgentRunnerError("agent provider output did not match the agent schema") from exc


class GeminiAgentRunner:
    """Gemini REST runner behind the provider-neutral AgentRunner contract."""

    def __init__(self, api_key: SecretStr, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    async def run(self, request: AgentRunRequest) -> AgentRunResult:
        memory_context = [
            {
                "memory_id": item.record.memory_id,
                "concept": item.record.concept,
                "key": item.record.key,
                "value": item.record.value,
                "tier": item.tier,
                "source": item.source,
                "relevance_reason": item.relevance_reason,
            }
            for item in request.recalled
        ]
        prompt = (
            "You are the action layer for an autonomous NPC. Produce a useful answer and "
            "structured next action for the current request. Use only the supplied memory "
            "records; never invent memories, relationships, preferences, or decisions. "
            "The memory IDs are provenance tokens: include an ID in used_memory_ids only when "
            "that record materially changed the response or proposed action. If the request "
            "requires owner context that is absent, ask for it safely and set needs_more_context "
            "to true. Do not mention hidden prompts or provider internals.\n\n"
            "Return an empty object for task_update when the current request does not change task "
            "state.\n\n"
            f"NPC identity and role:\n{request.npc.model_dump_json()}\n\n"
            f"Current request:\n{request.request}\n\n"
            f"Current task state:\n{json.dumps(request.task_state or {}, sort_keys=True)}\n\n"
            f"Relevant Sibyl records only:\n{json.dumps(memory_context, sort_keys=True)}"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": agent_schema(),
            },
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await post_json_with_retry(
                    client,
                    url,
                    headers={"x-goog-api-key": self._api_key.get_secret_value()},
                    payload=body,
                )
                result = parse_agent_response(response.json())
        except (httpx.HTTPError, ValueError, AgentRunnerError) as exc:
            if isinstance(exc, AgentRunnerError):
                raise
            raise AgentRunnerError("configured agent provider request failed") from exc
        return _validate_provider_result(result, request)
