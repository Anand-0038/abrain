from typing import Literal

from pydantic import BaseModel, Field

from .modules.agent_runner import AgentRunResult
from .modules.continuity import ContinuityDecision, ContinuityRequest
from .modules.conversation import ConversationTurn
from .modules.handoff import ScopedHandoff
from .modules.memory import MemoryRecord, MemoryRetrieval
from .modules.memory_candidates import MemoryCandidate, PromotionDecision
from .modules.npc_identity import NpcAppearance, NpcIdentity, WorkerSpecialization
from .modules.sessions import AgentSession
from .modules.tasks import AgentTask


class StartSessionRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    npc_id: str = Field(min_length=1, max_length=120)


class CreateNpcRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    appearance: NpcAppearance = Field(default_factory=NpcAppearance)
    role: str = Field(default="owner-context companion", min_length=1, max_length=160)
    personality: str = Field(
        default="thoughtful, concise, and honest about uncertainty",
        min_length=1,
        max_length=240,
    )


class CreateWorkerRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    primary_agent_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    specialization: WorkerSpecialization
    appearance: NpcAppearance = Field(default_factory=NpcAppearance)
    role: str | None = Field(default=None, max_length=160)
    personality: str | None = Field(default=None, max_length=240)


class NpcResponse(BaseModel):
    npc: NpcIdentity


class NpcListResponse(BaseModel):
    npcs: list[NpcIdentity]


class HandoffRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    source_agent_id: str = Field(min_length=1, max_length=120)
    target_agent_id: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=20_000)
    selected_memory_ids: list[str] = Field(min_length=1, max_length=20)


class HandoffResponse(BaseModel):
    handoff: ScopedHandoff
    task: AgentTask


class HandoffListResponse(BaseModel):
    handoffs: list[ScopedHandoff]


class TurnRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=20_000)


class TurnResponse(BaseModel):
    turn: ConversationTurn
    agent_response: str
    durable_memory_written: bool = False
    memory_influenced: bool = False
    recalled_memory_ids: list[str] = Field(default_factory=list)
    retrievals: list[MemoryRetrieval] = Field(default_factory=list)
    agent_run: AgentRunResult
    candidates: list[MemoryCandidate] = Field(default_factory=list)
    extraction_status: Literal["disabled", "completed", "failed"] = "disabled"


class CandidateDecisionResponse(BaseModel):
    candidate: MemoryCandidate
    decision: PromotionDecision


class PromoteCandidateRequest(BaseModel):
    candidate: MemoryCandidate
    confirm: bool = False


class PromoteCandidateResponse(BaseModel):
    decision: PromotionDecision
    record: MemoryRecord


class UpdateMemoryRequest(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=2000)
    confidence: float | None = Field(default=None, ge=0, le=1)


class MemoryListResponse(BaseModel):
    memories: list[MemoryRecord]


class MemoryMutationResponse(BaseModel):
    memory_id: str
    operation: str
    verified: bool


class CausalReplayStep(BaseModel):
    step: str
    event_id: str | None = None
    event_type: str
    detail: str


class CausalReplayResponse(BaseModel):
    memory: MemoryRecord
    steps: list[CausalReplayStep]


class SessionResponse(BaseModel):
    session: AgentSession


class SessionListResponse(BaseModel):
    sessions: list[AgentSession]


class RestartResponse(BaseModel):
    terminated: AgentSession
    fresh: AgentSession
    transient_turns_after_restart: int


class RecentEventsResponse(BaseModel):
    events: list[dict[str, object]]


class CreateTaskRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    assigned_agent_id: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=20_000)
    title: str | None = Field(default=None, max_length=160)
    parent_task_id: str | None = Field(default=None, max_length=120)


class RunTaskRequest(BaseModel):
    owner_id: str = Field(min_length=1, max_length=200)
    session_id: str | None = Field(default=None, min_length=1, max_length=120)
    handoff_id: str | None = Field(default=None, min_length=1, max_length=120)


class TaskListResponse(BaseModel):
    tasks: list[AgentTask]


class TaskResponse(BaseModel):
    task: AgentTask


class TaskRunResponse(BaseModel):
    task: AgentTask
    agent_run: AgentRunResult
    retrievals: list[MemoryRetrieval] = Field(default_factory=list)
    persisted_result_memory_id: str | None = None
    handoff: ScopedHandoff | None = None


class ContinuityResponse(ContinuityDecision):
    request: ContinuityRequest


class ContinuityComparisonRequest(ContinuityRequest):
    session_id: str = Field(min_length=1)


class ContinuityComparisonLane(BaseModel):
    session_id: str
    decision: ContinuityDecision


class ContinuityComparisonResponse(BaseModel):
    request: ContinuityRequest
    memory_lane: ContinuityComparisonLane
    memory_disabled_lane: ContinuityComparisonLane
    diverged: bool
