import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .api_models import (
    CandidateDecisionResponse,
    CausalReplayResponse,
    CausalReplayStep,
    ContinuityComparisonLane,
    ContinuityComparisonRequest,
    ContinuityComparisonResponse,
    ContinuityResponse,
    CreateNpcRequest,
    CreateTaskRequest,
    CreateWorkerRequest,
    HandoffListResponse,
    HandoffRequest,
    HandoffResponse,
    MemoryListResponse,
    MemoryMutationResponse,
    NpcListResponse,
    NpcResponse,
    PromoteCandidateRequest,
    PromoteCandidateResponse,
    RecentEventsResponse,
    RestartResponse,
    RunTaskRequest,
    SessionListResponse,
    SessionResponse,
    StartSessionRequest,
    TaskListResponse,
    TaskResponse,
    TaskRunResponse,
    TurnRequest,
    TurnResponse,
    UpdateMemoryRequest,
)
from .config import Settings, get_settings
from .contracts import DomainEvent, HealthResponse
from .events import new_event, sse_message
from .memory import MemoryAdapterError, SibylMemoryAdapter
from .modules.agent_runner import (
    AgentRunner,
    AgentRunnerError,
    AgentRunRequest,
    AgentRunResult,
    GeminiAgentRunner,
    LocalAgentRunner,
)
from .modules.continuity import ContinuityRequest, assemble_continuity
from .modules.conversation import ConversationTurn
from .modules.extraction import ExtractionError, GeminiCandidateExtractor
from .modules.handoff import (
    HandoffContext,
    HandoffRuntime,
    HandoffRuntimeError,
    ScopedHandoff,
    new_handoff,
)
from .modules.memory import MemoryRecord, MemoryRetrieval
from .modules.memory_candidates import candidate_to_record, decide_promotion
from .modules.npc_identity import NpcIdentity, WorkerSpecialization
from .modules.npc_runtime import NpcRuntime
from .modules.session_runtime import SessionRuntime, SessionRuntimeError
from .modules.tasks import AgentTask, TaskRuntime, TaskRuntimeError, new_task

_MAX_IN_PROCESS_EVENTS = 500


def create_app(
    settings: Settings | None = None,
    agent_runner: AgentRunner | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        adapter = None
        extractor = None
        runner = agent_runner
        if runtime_settings.memory_enabled:
            adapter = SibylMemoryAdapter(Path(runtime_settings.sibyl_db_path))
        if runtime_settings.model_provider == "gemini":
            if (
                runtime_settings.gemini_api_key is None
                or not runtime_settings.gemini_api_key.get_secret_value().strip()
            ):
                raise RuntimeError("ABRAIN_MODEL_PROVIDER=gemini requires ABRAIN_GEMINI_API_KEY")
            extractor = GeminiCandidateExtractor(
                runtime_settings.gemini_api_key,
                runtime_settings.gemini_model,
                runtime_settings.model_timeout_seconds,
            )
        if runner is None:
            if runtime_settings.agent_provider == "gemini":
                if (
                    runtime_settings.gemini_api_key is None
                    or not runtime_settings.gemini_api_key.get_secret_value().strip()
                ):
                    raise RuntimeError(
                        "ABRAIN_AGENT_PROVIDER=gemini requires ABRAIN_GEMINI_API_KEY"
                    )
                runner = GeminiAgentRunner(
                    runtime_settings.gemini_api_key,
                    runtime_settings.gemini_model,
                    runtime_settings.model_timeout_seconds,
                )
            else:
                runner = LocalAgentRunner()
        app.state.memory_adapter = adapter
        app.state.extractor = extractor
        app.state.agent_runner = runner
        app.state.sessions = SessionRuntime()
        app.state.npcs = NpcRuntime()
        app.state.tasks = TaskRuntime()
        app.state.handoffs = HandoffRuntime()
        app.state.events = []
        yield
        if adapter is not None:
            adapter.close()

    app = FastAPI(title="A-Brain Runtime", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        boundary: Literal["not_configured", "sibyl_local"] = (
            "sibyl_local" if runtime_settings.memory_enabled else "not_configured"
        )
        return HealthResponse(
            service="abrain-runtime",
            status="ok",
            environment=runtime_settings.environment,
            memory_boundary=boundary,
            checked_at=datetime.now(UTC),
        )

    @app.get("/api/events/stream")
    async def event_stream(request: Request) -> StreamingResponse:
        async def generate() -> AsyncIterator[str]:
            yield sse_message(
                new_event(
                    "system.ready",
                    correlation_id="local-startup",
                    payload={
                        "boundary": "local",
                        "memory": "sibyl_local"
                        if runtime_settings.memory_enabled
                        else "not_configured",
                    },
                )
            )
            while not await request.is_disconnected():
                await asyncio.sleep(15)
                if await request.is_disconnected():
                    break
                yield sse_message(
                    new_event(
                        "system.heartbeat",
                        correlation_id="local-heartbeat",
                        payload={"boundary": "local"},
                    )
                )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    def emit(event_type: str, *, correlation_id: str, payload: dict[str, object]) -> None:
        event = new_event(event_type, correlation_id=correlation_id, payload=payload)  # type: ignore[arg-type]
        app.state.events.append(event)
        del app.state.events[:-_MAX_IN_PROCESS_EVENTS]

    def event_visible(event: DomainEvent, owner_id: str | None, npc_id: str | None) -> bool:
        """Keep owner-scoped event metadata on the server, not only in the browser."""

        if event.event_type.startswith("system."):
            return True
        if not owner_id:
            return False
        payload = event.payload
        event_owner = payload.get("owner_id")
        if isinstance(event_owner, str) and event_owner != owner_id:
            return False
        event_agents = {
            value
            for key in ("npc_id", "source_agent_id", "target_agent_id")
            if isinstance((value := payload.get(key)), str)
        }
        if event_agents and npc_id and npc_id not in event_agents:
            return False
        return bool(event_owner and event_agents) or bool(event_agents and npc_id)

    def memory_adapter() -> SibylMemoryAdapter:
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="persistent memory is not enabled; no continuity claim is available",
            )
        return adapter

    async def run_agent(
        npc: NpcIdentity,
        session_id: str,
        request_text: str,
        recalled: list[MemoryRetrieval],
        *,
        correlation_id: str,
        task_state: dict[str, object] | None = None,
    ) -> AgentRunResult:
        session = app.state.sessions.get(session_id)
        try:
            current_task_state: dict[str, object] = {
                "session_status": session.status,
                "fresh_session": not app.state.sessions.turns(session_id),
                "turn_count": len(app.state.sessions.turns(session_id)),
            }
            if task_state:
                current_task_state.update(task_state)
            return await app.state.agent_runner.run(
                AgentRunRequest(
                    request=request_text,
                    session_id=session_id,
                    npc=npc,
                    recalled=recalled,
                    task_state=current_task_state,
                )
            )
        except AgentRunnerError as exc:
            emit(
                "agent.run_failed",
                correlation_id=correlation_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "session_id": session_id,
                },
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def resolve_npc(owner_id: str, npc_id: str) -> NpcIdentity:
        try:
            npc = app.state.npcs.get(npc_id)
        except KeyError:
            adapter = getattr(app.state, "memory_adapter", None)
            if adapter is None:
                raise HTTPException(status_code=404, detail="NPC identity not found") from None
            try:
                npc = adapter.get_npc(owner_id, npc_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if npc is None:
                raise HTTPException(status_code=404, detail="NPC identity not found") from None
            try:
                app.state.npcs.restore(npc)
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if npc.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="NPC does not belong to this owner")
        return npc

    def resolve_source_session(owner_id: str, npc_id: str, session_id: str) -> NpcIdentity:
        """Validate that a client-owned write points at its own NPC session."""

        npc = resolve_npc(owner_id, npc_id)
        try:
            session = app.state.sessions.get(session_id)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail="source session not found") from exc
        if session.npc_id != npc.npc_id:
            raise HTTPException(
                status_code=403, detail="source session does not belong to this NPC"
            )
        return npc

    def resolve_task(owner_id: str, task_id: str) -> AgentTask:
        """Resolve an owner-scoped task from the runtime or Sibyl HOT state."""

        try:
            task = app.state.tasks.get(task_id)
        except TaskRuntimeError:
            adapter = getattr(app.state, "memory_adapter", None)
            if adapter is None:
                raise HTTPException(status_code=404, detail="task not found") from None
            try:
                task = adapter.get_task_state(owner_id, task_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if task is None:
                raise HTTPException(status_code=404, detail="task not found") from None
            try:
                app.state.tasks.restore(task)
            except TaskRuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if task.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="task does not belong to this owner")
        return task

    def persist_task(task: AgentTask) -> AgentTask:
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is None:
            return task
        try:
            return adapter.write_task_state(task)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def resolve_handoff(owner_id: str, handoff_id: str) -> ScopedHandoff:
        """Resolve a delegation grant without allowing cross-owner lookup."""

        try:
            handoff = app.state.handoffs.get(handoff_id)
        except HandoffRuntimeError:
            adapter = getattr(app.state, "memory_adapter", None)
            if adapter is None:
                raise HTTPException(status_code=404, detail="handoff not found") from None
            try:
                handoff = adapter.get_handoff_state(owner_id, handoff_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if handoff is None:
                raise HTTPException(status_code=404, detail="handoff not found") from None
            try:
                app.state.handoffs.restore(handoff)
            except HandoffRuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        if handoff.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="handoff does not belong to this owner")
        return handoff

    def persist_handoff(handoff: ScopedHandoff) -> ScopedHandoff:
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="scoped handoff requires the persistent Sibyl memory boundary",
            )
        try:
            return adapter.write_handoff_state(handoff)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    def emit_handoff_event(
        event_type: str,
        handoff: ScopedHandoff,
        *,
        correlation_id: str,
        session_id: str | None = None,
        reason: str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "owner_id": handoff.owner_id,
            "npc_id": handoff.target_agent_id,
            "source_agent_id": handoff.source_agent_id,
            "target_agent_id": handoff.target_agent_id,
            "handoff_id": handoff.handoff_id,
            "parent_task_id": handoff.parent_task_id,
            "child_task_id": handoff.child_task_id,
            "selected_memory_ids": handoff.selected_memory_ids,
            "status": handoff.status,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if reason is not None:
            payload["reason"] = reason
        emit(event_type, correlation_id=correlation_id, payload=payload)

    def owner_npcs(owner_id: str) -> list[NpcIdentity]:
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is not None:
            try:
                return adapter.list_npcs(owner_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        return app.state.npcs.list(owner_id)

    def emit_task_event(
        event_type: str,
        task: AgentTask,
        *,
        correlation_id: str,
        session_id: str | None = None,
        extra: dict[str, object] | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "owner_id": task.owner_id,
            "npc_id": task.assigned_agent_id,
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "current_step": task.current_step,
            "relevant_memory_ids": task.relevant_memory_ids,
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if extra:
            payload.update(extra)
        emit(event_type, correlation_id=correlation_id, payload=payload)

    @app.post("/api/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
    async def create_task(request: CreateTaskRequest) -> TaskResponse:
        resolve_npc(request.owner_id, request.assigned_agent_id)
        if request.parent_task_id is not None:
            parent = resolve_task(request.owner_id, request.parent_task_id)
            if parent.assigned_agent_id != request.assigned_agent_id:
                raise HTTPException(
                    status_code=409,
                    detail="parent task must belong to the same assigned agent",
                )
        task = new_task(
            owner_id=request.owner_id,
            assigned_agent_id=request.assigned_agent_id,
            objective=request.objective,
            title=request.title,
            parent_task_id=request.parent_task_id,
        )
        try:
            app.state.tasks.create(task)
        except TaskRuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        task = persist_task(task)
        emit_task_event("task.created", task, correlation_id=task.task_id)
        return TaskResponse(task=task)

    @app.get("/api/tasks", response_model=TaskListResponse)
    async def list_tasks(owner_id: str, assigned_agent_id: str | None = None) -> TaskListResponse:
        if assigned_agent_id is not None:
            resolve_npc(owner_id, assigned_agent_id)
        return TaskListResponse(tasks=app.state.tasks.list(owner_id, assigned_agent_id))

    @app.get("/api/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(task_id: str, owner_id: str) -> TaskResponse:
        return TaskResponse(task=resolve_task(owner_id, task_id))

    @app.post(
        "/api/tasks/{task_id}/handoffs",
        response_model=HandoffResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_handoff(task_id: str, request: HandoffRequest) -> HandoffResponse:
        """Create a child task with an explicit, owner-validated memory grant."""

        parent = resolve_task(request.owner_id, task_id)
        source = resolve_npc(request.owner_id, request.source_agent_id)
        target = resolve_npc(request.owner_id, request.target_agent_id)
        if parent.assigned_agent_id != source.npc_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="the source agent must own the parent task",
            )
        if source.npc_id == target.npc_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="a handoff requires a different target agent",
            )
        if target.specialization == "primary":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="the primary agent delegates to a specialist, not another primary",
            )
        adapter = memory_adapter()
        selected_context: list[HandoffContext] = []
        seen_ids: set[str] = set()
        for memory_id in request.selected_memory_ids:
            if memory_id in seen_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="selected memory IDs must be unique",
                )
            seen_ids.add(memory_id)
            try:
                record = adapter.get(request.owner_id, memory_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            if record is None:
                raise HTTPException(status_code=404, detail=f"memory {memory_id} was not found")
            if record.npc_id != source.npc_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="a handoff can only select memories owned by its source agent",
                )
            selected_context.append(HandoffContext.from_record(record, request.objective))

        child = new_task(
            owner_id=request.owner_id,
            assigned_agent_id=target.npc_id,
            objective=request.objective,
            parent_task_id=parent.task_id,
        )
        handoff = new_handoff(
            owner_id=request.owner_id,
            source_agent_id=source.npc_id,
            target_agent_id=target.npc_id,
            parent_task_id=parent.task_id,
            child_task_id=child.task_id,
            objective=request.objective,
            selected_context=selected_context,
        )
        try:
            app.state.tasks.create(child)
            child = persist_task(child)
            app.state.handoffs.create(handoff)
            handoff = persist_handoff(handoff)
        except (TaskRuntimeError, HandoffRuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        emit_task_event(
            "task.created",
            child,
            correlation_id=handoff.handoff_id,
            extra={
                "handoff_id": handoff.handoff_id,
                "source_agent_id": source.npc_id,
                "selected_memory_ids": handoff.selected_memory_ids,
            },
        )
        emit_handoff_event("handoff.created", handoff, correlation_id=handoff.handoff_id)
        return HandoffResponse(handoff=handoff, task=child)

    @app.get("/api/handoffs", response_model=HandoffListResponse)
    async def list_handoffs(owner_id: str) -> HandoffListResponse:
        return HandoffListResponse(handoffs=app.state.handoffs.list(owner_id))

    @app.get("/api/handoffs/{handoff_id}", response_model=HandoffResponse)
    async def get_handoff(handoff_id: str, owner_id: str) -> HandoffResponse:
        handoff = resolve_handoff(owner_id, handoff_id)
        return HandoffResponse(task=resolve_task(owner_id, handoff.child_task_id), handoff=handoff)

    @app.post("/api/tasks/{task_id}/run", response_model=TaskRunResponse)
    async def run_task(task_id: str, request: RunTaskRequest) -> TaskRunResponse:
        task = resolve_task(request.owner_id, task_id)
        if task.status not in {"queued", "blocked", "review"}:
            raise HTTPException(
                status_code=409,
                detail="only queued, blocked, or review tasks can be run",
            )
        npc = resolve_npc(request.owner_id, task.assigned_agent_id)
        handoff: ScopedHandoff | None = None
        if request.handoff_id is not None:
            handoff = resolve_handoff(request.owner_id, request.handoff_id)
            if handoff.child_task_id != task.task_id or handoff.target_agent_id != npc.npc_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="handoff does not authorize this task and target agent",
                )
            if handoff.status in {"completed", "blocked"}:
                raise HTTPException(status_code=409, detail="handoff is no longer runnable")

        if request.session_id is not None:
            try:
                session = app.state.sessions.get(request.session_id)
            except SessionRuntimeError as exc:
                raise HTTPException(status_code=404, detail="task session not found") from exc
            if session.npc_id != npc.npc_id:
                raise HTTPException(status_code=403, detail="task session belongs to another NPC")
            if session.status != "active":
                raise HTTPException(status_code=409, detail="task requires an active session")
        else:
            active_sessions = [
                item
                for item in app.state.sessions.list_for_npc(npc.npc_id)
                if item.status == "active"
            ]
            session = (
                active_sessions[0] if active_sessions else app.state.sessions.start(npc.npc_id)
            )
            if not active_sessions:
                emit(
                    "npc.session_started",
                    correlation_id=session.session_id,
                    payload={
                        "owner_id": task.owner_id,
                        "npc_id": session.npc_id,
                        "session_id": session.session_id,
                        "source": "task_runtime",
                    },
                )

        if handoff is not None:
            handoff = app.state.handoffs.update(handoff.handoff_id, status="accepted")
            handoff = persist_handoff(handoff)
            emit_handoff_event(
                "handoff.accepted",
                handoff,
                correlation_id=task.task_id,
                session_id=session.session_id,
            )

        task = app.state.tasks.update(
            task.task_id,
            status="thinking",
            current_step="Reading the task objective and preparing the run",
        )
        task = persist_task(task)
        emit_task_event(
            "task.started", task, correlation_id=task.task_id, session_id=session.session_id
        )

        task = app.state.tasks.update(
            task.task_id,
            status="working",
            current_step="Searching the scoped brain for relevant context",
        )
        task = persist_task(task)
        emit_task_event(
            "task.step_changed", task, correlation_id=task.task_id, session_id=session.session_id
        )

        if handoff is not None:
            handoff = app.state.handoffs.update(handoff.handoff_id, status="working")
            handoff = persist_handoff(handoff)
            emit_handoff_event(
                "handoff.started",
                handoff,
                correlation_id=task.task_id,
                session_id=session.session_id,
            )

        adapter = getattr(app.state, "memory_adapter", None)
        retrievals: list[MemoryRetrieval] = []
        recall_id = f"task_recall_{uuid4().hex}"
        if handoff is not None:
            retrievals = [
                MemoryRetrieval(
                    record=MemoryRecord(
                        memory_id=context.memory_id,
                        owner_id=handoff.owner_id,
                        npc_id=handoff.source_agent_id,
                        source_session_id=context.source_session_id,
                        concept=context.concept,  # type: ignore[arg-type]
                        key=context.key,
                        value=context.value,
                        confidence=context.confidence,
                        created_at=context.created_at,
                        evidence_ref=context.evidence_ref or handoff.handoff_id,
                    ),
                    query=handoff.objective,
                    tier=context.tier,
                    source="abrain_scoped_handoff",
                    relevance_reason=context.relevance_reason,
                )
                for context in handoff.selected_context
            ]
            emit(
                "memory.recall_requested",
                correlation_id=recall_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "handoff_id": handoff.handoff_id,
                    "memory_ids": handoff.selected_memory_ids,
                    "source": "scoped_handoff",
                },
            )
            emit(
                "memory.recall_succeeded",
                correlation_id=recall_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "handoff_id": handoff.handoff_id,
                    "memory_ids": handoff.selected_memory_ids,
                    "source": "scoped_handoff",
                },
            )
        elif adapter is not None:
            emit(
                "memory.recall_requested",
                correlation_id=recall_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "source": "task",
                },
            )
            try:
                retrievals = adapter.recall_with_metadata(
                    task.owner_id, task.assigned_agent_id, task.objective
                )
            except MemoryAdapterError as exc:
                task = app.state.tasks.update(
                    task.task_id,
                    status="blocked",
                    current_step="Persistent recall failed; task is blocked safely",
                    result="The task could not continue because persistent brain recall failed.",
                )
                task = persist_task(task)
                emit_task_event(
                    "task.blocked",
                    task,
                    correlation_id=task.task_id,
                    session_id=session.session_id,
                    extra={"reason": "memory_recall_failed"},
                )
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            emit(
                "memory.recall_succeeded",
                correlation_id=recall_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "memory_ids": [item.record.memory_id for item in retrievals],
                    "source": "task",
                },
            )
        else:
            emit(
                "continuity.memory_disabled",
                correlation_id=recall_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "source": "task",
                },
            )

        agent_result = await run_agent(
            npc,
            session.session_id,
            task.objective,
            retrievals,
            correlation_id=task.task_id,
            task_state=task.model_dump(mode="json"),
        )
        used_memory_ids = agent_result.used_memory_ids
        requires_review = bool(
            agent_result.task_update and agent_result.task_update.get("requires_review") is True
        )
        if agent_result.needs_more_context:
            task = app.state.tasks.update(
                task.task_id,
                status="blocked",
                current_step="Waiting for the missing context before continuing",
                result=agent_result.response,
                relevant_memory_ids=used_memory_ids,
            )
            task = persist_task(task)
            emit_task_event(
                "task.blocked",
                task,
                correlation_id=task.task_id,
                session_id=session.session_id,
                extra={"reason": "agent_needs_more_context"},
            )
            if handoff is not None:
                handoff = app.state.handoffs.update(
                    handoff.handoff_id,
                    status="blocked",
                    completed_at=datetime.now(UTC),
                    result=agent_result.response,
                )
                handoff = persist_handoff(handoff)
                emit_handoff_event(
                    "handoff.blocked",
                    handoff,
                    correlation_id=task.task_id,
                    session_id=session.session_id,
                    reason="agent_needs_more_context",
                )
            return TaskRunResponse(
                task=task,
                agent_run=agent_result,
                retrievals=retrievals,
                handoff=handoff,
            )

        task = app.state.tasks.update(
            task.task_id,
            status="review" if requires_review else "completed",
            current_step=(
                "Result ready for owner review"
                if requires_review
                else "Result prepared and available to the owner"
            ),
            result=agent_result.response,
            relevant_memory_ids=used_memory_ids,
        )
        task = persist_task(task)
        emit_task_event(
            "task.step_changed",
            task,
            correlation_id=task.task_id,
            session_id=session.session_id,
        )

        persisted_result_memory_id: str | None = None
        should_persist_result = bool(
            adapter is not None
            and task.status == "completed"
            and agent_result.response
            and (
                bool(used_memory_ids)
                or bool(
                    agent_result.task_update
                    and agent_result.task_update.get("persist_result") is True
                )
            )
        )
        if should_persist_result:
            assert adapter is not None
            result_memory = MemoryRecord(
                memory_id=f"task_result_{task.task_id}",
                owner_id=task.owner_id,
                npc_id=task.assigned_agent_id,
                source_session_id=session.session_id,
                concept="decision",
                key=f"task:{task.task_id}:result",
                value=agent_result.response[:2000],
                confidence=1.0,
                created_at=datetime.now(UTC),
                evidence_ref=task.task_id,
            )
            result_write_id = f"task_result_write_{uuid4().hex}"
            emit(
                "memory.write_requested",
                correlation_id=result_write_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "memory_id": result_memory.memory_id,
                    "tier": "entity",
                    "source": "task_completion",
                },
            )
            try:
                persisted_result = adapter.write(result_memory)
            except MemoryAdapterError:
                task = app.state.tasks.update(
                    task.task_id,
                    status="blocked",
                    current_step=(
                        "Result produced, but its durable decision memory could not be verified"
                    ),
                    result=agent_result.response,
                )
                task = persist_task(task)
                emit_task_event(
                    "task.blocked",
                    task,
                    correlation_id=task.task_id,
                    session_id=session.session_id,
                    extra={"reason": "result_memory_write_failed"},
                )
                if handoff is not None:
                    handoff = app.state.handoffs.update(
                        handoff.handoff_id,
                        status="blocked",
                        completed_at=datetime.now(UTC),
                        result=agent_result.response,
                    )
                    handoff = persist_handoff(handoff)
                    emit_handoff_event(
                        "handoff.blocked",
                        handoff,
                        correlation_id=task.task_id,
                        session_id=session.session_id,
                        reason="result_memory_write_failed",
                    )
                return TaskRunResponse(
                    task=task,
                    agent_run=agent_result,
                    retrievals=retrievals,
                    handoff=handoff,
                )
            persisted_result_memory_id = persisted_result.memory_id
            emit(
                "memory.write_succeeded",
                correlation_id=result_write_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "memory_id": persisted_result.memory_id,
                    "concept": persisted_result.concept,
                    "tier": "entity",
                    "source": "task_completion",
                },
            )
            emit(
                "memory.object_materialized",
                correlation_id=result_write_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "memory_id": persisted_result.memory_id,
                    "concept": persisted_result.concept,
                    "tier": "entity",
                    "source": "task_completion",
                },
            )

        emit_task_event(
            "task.completed" if task.status == "completed" else "task.step_changed",
            task,
            correlation_id=task.task_id,
            session_id=session.session_id,
            extra={"result_memory_id": persisted_result_memory_id},
        )
        if used_memory_ids:
            emit(
                "behavior.changed_by_memory",
                correlation_id=task.task_id,
                payload={
                    "owner_id": task.owner_id,
                    "npc_id": task.assigned_agent_id,
                    "session_id": session.session_id,
                    "task_id": task.task_id,
                    "memory_ids": used_memory_ids,
                    "action": agent_result.proposed_action,
                    "source": "scoped_handoff" if handoff is not None else "task",
                    **({"handoff_id": handoff.handoff_id} if handoff is not None else {}),
                },
            )
        if handoff is not None:
            handoff = app.state.handoffs.update(
                handoff.handoff_id,
                status="completed" if task.status == "completed" else "blocked",
                completed_at=datetime.now(UTC),
                result=task.result,
            )
            handoff = persist_handoff(handoff)
            emit_handoff_event(
                "handoff.completed" if task.status == "completed" else "handoff.blocked",
                handoff,
                correlation_id=task.task_id,
                session_id=session.session_id,
                reason=None if task.status == "completed" else "requires_review",
            )
        return TaskRunResponse(
            task=task,
            agent_run=agent_result,
            retrievals=retrievals,
            persisted_result_memory_id=persisted_result_memory_id,
            handoff=handoff,
        )

    @app.post("/api/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
    async def start_session(request: StartSessionRequest) -> SessionResponse:
        resolve_npc(request.owner_id, request.npc_id)
        session = app.state.sessions.start(request.npc_id)
        emit(
            "npc.session_started",
            correlation_id=session.session_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": session.npc_id,
                "session_id": session.session_id,
            },
        )
        return SessionResponse(session=session)

    @app.get("/api/sessions", response_model=SessionListResponse)
    async def list_sessions(owner_id: str, npc_id: str) -> SessionListResponse:
        resolve_npc(owner_id, npc_id)
        return SessionListResponse(sessions=app.state.sessions.list_for_npc(npc_id))

    @app.post("/api/npcs", response_model=NpcResponse, status_code=status.HTTP_201_CREATED)
    async def create_npc(request: CreateNpcRequest) -> NpcResponse:
        existing = owner_npcs(request.owner_id)
        if any(item.specialization == "primary" for item in existing):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="an owner can have one primary agent; add a specialist instead",
            )
        if len(existing) >= 3:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A-Brain limits an owner to one primary agent and two specialists",
            )
        npc = NpcIdentity(
            npc_id=f"npc_{uuid4().hex}",
            owner_id=request.owner_id,
            name=request.name,
            appearance=request.appearance,
            role=request.role,
            personality=request.personality,
            specialization="primary",
        )
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is not None:
            try:
                npc = adapter.write_npc(npc)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            app.state.npcs.create(npc)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        emit(
            "npc.created",
            correlation_id=npc.npc_id,
            payload={
                "npc_id": npc.npc_id,
                "owner_id": npc.owner_id,
                "name": npc.name,
                "specialization": npc.specialization,
            },
        )
        return NpcResponse(npc=npc)

    @app.post(
        "/api/npcs/workers",
        response_model=NpcResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_worker(request: CreateWorkerRequest) -> NpcResponse:
        primary = resolve_npc(request.owner_id, request.primary_agent_id)
        if primary.specialization != "primary":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="specialists must be attached to the owner's primary agent",
            )
        existing = owner_npcs(request.owner_id)
        if len(existing) >= 3:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A-Brain limits an owner to one primary agent and two specialists",
            )
        role_defaults: dict[WorkerSpecialization, str] = {
            "planner": "mission planner and coordinator",
            "worker": "focused research and execution worker",
            "reviewer": "reviewer and safety guardian",
        }
        personality_defaults: dict[WorkerSpecialization, str] = {
            "planner": "structured, concise, and explicit about dependencies",
            "worker": "focused, methodical, and honest about evidence",
            "reviewer": "careful, skeptical, and clear about unresolved risk",
        }
        npc = NpcIdentity(
            npc_id=f"npc_{uuid4().hex}",
            owner_id=request.owner_id,
            name=request.name,
            appearance=request.appearance,
            role=request.role or role_defaults[request.specialization],
            personality=request.personality or personality_defaults[request.specialization],
            specialization=request.specialization,
        )
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is not None:
            try:
                npc = adapter.write_npc(npc)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            app.state.npcs.create(npc)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        emit(
            "npc.created",
            correlation_id=npc.npc_id,
            payload={
                "npc_id": npc.npc_id,
                "owner_id": npc.owner_id,
                "name": npc.name,
                "specialization": npc.specialization,
                "primary_agent_id": primary.npc_id,
            },
        )
        return NpcResponse(npc=npc)

    @app.get("/api/npcs", response_model=NpcListResponse)
    async def list_npcs(owner_id: str) -> NpcListResponse:
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is not None:
            try:
                npcs = adapter.list_npcs(owner_id)
            except MemoryAdapterError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            for npc in npcs:
                app.state.npcs.restore(npc)
            return NpcListResponse(npcs=npcs)
        return NpcListResponse(npcs=app.state.npcs.list(owner_id))

    @app.get("/api/sessions/{session_id}", response_model=SessionResponse)
    async def get_session(session_id: str, owner_id: str) -> SessionResponse:
        try:
            session = app.state.sessions.get(session_id)
            resolve_npc(owner_id, session.npc_id)
            return SessionResponse(session=session)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/sessions/{session_id}/turns", response_model=list[ConversationTurn])
    async def get_turns(session_id: str, owner_id: str) -> list[ConversationTurn]:
        try:
            session = app.state.sessions.get(session_id)
            resolve_npc(owner_id, session.npc_id)
            return app.state.sessions.turns(session_id)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/conversations/turns", response_model=TurnResponse, status_code=201)
    async def record_turn(request: TurnRequest) -> TurnResponse:
        try:
            session = app.state.sessions.get(request.session_id)
            npc = resolve_npc(request.owner_id, session.npc_id)
        except (SessionRuntimeError, KeyError) as exc:
            raise HTTPException(status_code=404, detail="active session or NPC not found") from exc
        turn = ConversationTurn(
            turn_id=f"turn_{uuid4().hex}",
            session_id=request.session_id,
            speaker="owner",
            text=request.text,
            occurred_at=datetime.now(UTC),
        )
        adapter = getattr(app.state, "memory_adapter", None)
        recalled_memories: list[MemoryRetrieval] = []
        recall_id = f"conversation_recall_{uuid4().hex}"
        continuity_request = ContinuityRequest(
            owner_id=npc.owner_id,
            npc_id=npc.npc_id,
            query=turn.text,
        )
        if adapter is not None:
            emit(
                "memory.recall_requested",
                correlation_id=recall_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "session_id": turn.session_id,
                    "source": "conversation",
                },
            )
            try:
                recalled_memories = adapter.recall_with_metadata(
                    npc.owner_id, npc.npc_id, turn.text
                )
            except MemoryAdapterError as exc:
                emit(
                    "memory.recall_failed",
                    correlation_id=recall_id,
                    payload={
                        "owner_id": npc.owner_id,
                        "npc_id": npc.npc_id,
                        "session_id": turn.session_id,
                        "source": "conversation",
                    },
                )
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        else:
            emit(
                "continuity.memory_disabled",
                correlation_id=recall_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "session_id": turn.session_id,
                    "source": "conversation",
                },
            )

        agent_result = await run_agent(
            npc,
            turn.session_id,
            turn.text,
            recalled_memories,
            correlation_id=recall_id,
        )

        decision = assemble_continuity(
            continuity_request,
            recalled_memories if adapter is not None else None,
            agent_result,
        )
        if adapter is not None:
            emit(
                "memory.recall_succeeded",
                correlation_id=recall_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "session_id": turn.session_id,
                    "memory_ids": decision.recalled_memory_ids,
                    "source": "conversation",
                },
            )
        if decision.agent_run.used_memory_ids:
            emit(
                "behavior.changed_by_memory",
                correlation_id=recall_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "session_id": turn.session_id,
                    "memory_ids": decision.agent_run.used_memory_ids,
                    "action": decision.action,
                    "source": "conversation",
                },
            )
        try:
            app.state.sessions.add_turn(turn)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        emit(
            "conversation.turn_recorded",
            correlation_id=turn.turn_id,
            payload={
                "owner_id": npc.owner_id,
                "npc_id": npc.npc_id,
                "turn_id": turn.turn_id,
                "session_id": turn.session_id,
            },
        )
        extractor = getattr(app.state, "extractor", None)
        if extractor is None:
            return TurnResponse(
                turn=turn,
                agent_response=decision.agent_response,
                memory_influenced=decision.influenced_by_memory,
                recalled_memory_ids=decision.recalled_memory_ids,
                retrievals=decision.retrievals,
                agent_run=decision.agent_run,
                extraction_status="disabled",
            )
        try:
            candidates = await extractor.extract(
                text=turn.text,
                owner_id=npc.owner_id,
                npc_id=npc.npc_id,
                session_id=turn.session_id,
                turn_id=turn.turn_id,
            )
        except ExtractionError:
            emit(
                "memory.extraction_failed",
                correlation_id=turn.turn_id,
                payload={
                    "owner_id": npc.owner_id,
                    "npc_id": npc.npc_id,
                    "turn_id": turn.turn_id,
                    "session_id": turn.session_id,
                },
            )
            return TurnResponse(
                turn=turn,
                agent_response=(
                    f"{decision.agent_response} I could not update durable memory from this turn."
                ),
                memory_influenced=decision.influenced_by_memory,
                recalled_memory_ids=decision.recalled_memory_ids,
                retrievals=decision.retrievals,
                agent_run=decision.agent_run,
                extraction_status="failed",
            )
        for candidate in candidates:
            emit(
                "memory.candidate_detected",
                correlation_id=candidate.candidate_id,
                payload={
                    "owner_id": candidate.owner_id,
                    "npc_id": candidate.npc_id,
                    "candidate_id": candidate.candidate_id,
                    "source_turn_id": candidate.source_turn_id,
                },
            )
        if candidates:
            candidate_response = (
                f"I found {len(candidates)} possible durable "
                f"memory candidate{'s' if len(candidates) != 1 else ''}. "
                "Review the Brain Vault before anything becomes persistent."
            )
            agent_response = (
                f"{decision.agent_response} {candidate_response}"
                if decision.agent_response
                else candidate_response
            )
        else:
            agent_response = decision.agent_response
        return TurnResponse(
            turn=turn,
            agent_response=agent_response,
            memory_influenced=decision.influenced_by_memory,
            recalled_memory_ids=decision.recalled_memory_ids,
            retrievals=decision.retrievals,
            agent_run=decision.agent_run,
            candidates=candidates,
            extraction_status="completed",
        )

    @app.post("/api/memory/candidates/decide", response_model=CandidateDecisionResponse)
    async def decide_candidate(
        candidate_request: PromoteCandidateRequest,
    ) -> CandidateDecisionResponse:
        candidate = candidate_request.candidate
        resolve_source_session(candidate.owner_id, candidate.npc_id, candidate.source_session_id)
        decision = decide_promotion(candidate)
        emit(
            "memory.candidate_detected",
            correlation_id=candidate.candidate_id,
            payload={
                "owner_id": candidate.owner_id,
                "npc_id": candidate.npc_id,
                "candidate_id": candidate.candidate_id,
                "disposition": decision.disposition,
                "source_turn_id": candidate.source_turn_id,
            },
        )
        return CandidateDecisionResponse(candidate=candidate, decision=decision)

    @app.post(
        "/api/memory/candidates/promote", response_model=PromoteCandidateResponse, status_code=201
    )
    async def promote_candidate(request: PromoteCandidateRequest) -> PromoteCandidateResponse:
        candidate = request.candidate
        resolve_source_session(candidate.owner_id, candidate.npc_id, candidate.source_session_id)
        decision = decide_promotion(candidate)
        if decision.disposition == "reject":
            emit(
                "memory.candidate_rejected",
                correlation_id=candidate.candidate_id,
                payload={
                    "owner_id": candidate.owner_id,
                    "npc_id": candidate.npc_id,
                    "candidate_id": candidate.candidate_id,
                    "reason": decision.reason,
                },
            )
            raise HTTPException(status_code=422, detail=decision.reason)
        if decision.disposition == "confirm" and not request.confirm:
            emit(
                "memory.candidate_confirmed",
                correlation_id=candidate.candidate_id,
                payload={
                    "owner_id": candidate.owner_id,
                    "npc_id": candidate.npc_id,
                    "candidate_id": candidate.candidate_id,
                    "required": True,
                },
            )
            raise HTTPException(status_code=409, detail=decision.reason)
        try:
            record = candidate_to_record(candidate, confirmed=request.confirm)
            emit(
                "memory.write_requested",
                correlation_id=record.memory_id,
                payload={
                    "memory_id": record.memory_id,
                    "owner_id": record.owner_id,
                    "npc_id": record.npc_id,
                },
            )
            persisted = memory_adapter().write(record)
        except MemoryAdapterError as exc:
            emit(
                "memory.write_failed",
                correlation_id=candidate.candidate_id,
                payload={
                    "owner_id": candidate.owner_id,
                    "npc_id": candidate.npc_id,
                    "memory_id": candidate.candidate_id,
                },
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        emit(
            "memory.candidate_promoted",
            correlation_id=persisted.memory_id,
            payload={
                "owner_id": persisted.owner_id,
                "npc_id": persisted.npc_id,
                "candidate_id": candidate.candidate_id,
                "memory_id": persisted.memory_id,
            },
        )
        emit(
            "memory.write_succeeded",
            correlation_id=persisted.memory_id,
            payload={
                "memory_id": persisted.memory_id,
                "owner_id": persisted.owner_id,
                "npc_id": persisted.npc_id,
                "concept": persisted.concept,
                "tier": "entity",
            },
        )
        emit(
            "memory.object_materialized",
            correlation_id=persisted.memory_id,
            payload={
                "memory_id": persisted.memory_id,
                "owner_id": persisted.owner_id,
                "npc_id": persisted.npc_id,
                "source_turn_id": candidate.source_turn_id,
                "concept": persisted.concept,
                "tier": "entity",
            },
        )
        return PromoteCandidateResponse(decision=decision, record=persisted)

    @app.get("/api/memories", response_model=MemoryListResponse)
    async def list_memories(owner_id: str, npc_id: str | None = None) -> MemoryListResponse:
        try:
            memories = memory_adapter().list(owner_id, npc_id=npc_id)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return MemoryListResponse(memories=memories)

    @app.patch("/api/memories/{memory_id}", response_model=MemoryMutationResponse)
    async def update_memory(
        memory_id: str, owner_id: str, request: UpdateMemoryRequest
    ) -> MemoryMutationResponse:
        adapter = memory_adapter()
        existing = adapter.get(owner_id, memory_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="memory not found")
        updated = existing.model_copy(
            update={"key": request.key, "value": request.value, "confidence": request.confidence}
        )
        try:
            adapter.update(updated)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        emit(
            "memory.updated",
            correlation_id=memory_id,
            payload={"memory_id": memory_id, "owner_id": owner_id, "npc_id": existing.npc_id},
        )
        return MemoryMutationResponse(memory_id=memory_id, operation="update", verified=True)

    @app.post("/api/memories/{memory_id}/archive", response_model=MemoryMutationResponse)
    async def archive_memory(
        memory_id: str, owner_id: str, reason: str | None = None
    ) -> MemoryMutationResponse:
        adapter = memory_adapter()
        existing = adapter.get(owner_id, memory_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="memory not found")
        try:
            archived = adapter.archive(owner_id, memory_id, reason)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not archived:
            raise HTTPException(status_code=404, detail="memory not found")
        emit(
            "memory.archived",
            correlation_id=memory_id,
            payload={"memory_id": memory_id, "owner_id": owner_id, "npc_id": existing.npc_id},
        )
        return MemoryMutationResponse(memory_id=memory_id, operation="archive", verified=True)

    @app.delete("/api/memories/{memory_id}", response_model=MemoryMutationResponse)
    async def delete_memory(memory_id: str, owner_id: str) -> MemoryMutationResponse:
        adapter = memory_adapter()
        existing = adapter.get(owner_id, memory_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="memory not found")
        try:
            deleted = adapter.delete(owner_id, memory_id)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="memory not found")
        emit(
            "memory.deleted",
            correlation_id=memory_id,
            payload={"memory_id": memory_id, "owner_id": owner_id, "npc_id": existing.npc_id},
        )
        return MemoryMutationResponse(memory_id=memory_id, operation="delete", verified=True)

    @app.get("/api/continuity/replay", response_model=CausalReplayResponse)
    async def causal_replay(owner_id: str, memory_id: str) -> CausalReplayResponse:
        try:
            memory = memory_adapter().get(owner_id, memory_id)
        except MemoryAdapterError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if memory is None:
            raise HTTPException(status_code=404, detail="memory not found")

        correlation_id = f"replay_{uuid4().hex}"
        emit(
            "causal.replay_requested",
            correlation_id=correlation_id,
            payload={"memory_id": memory_id, "owner_id": owner_id, "npc_id": memory.npc_id},
        )
        steps: list[CausalReplayStep] = []
        for event in app.state.events:
            payload = event.payload
            ids = [
                value
                for key in ("memory_ids", "relevant_memory_ids", "selected_memory_ids")
                if isinstance(payload.get(key), list)
                for value in payload[key]
                if isinstance(value, str)
            ]
            is_source = (
                event.event_type == "conversation.turn_recorded"
                and memory.evidence_ref is not None
                and payload.get("turn_id") == memory.evidence_ref
                and payload.get("session_id") == memory.source_session_id
            )
            is_direct_memory_event = payload.get("memory_id") == memory_id
            is_memory_set_event = memory_id in ids
            if not (is_source or is_direct_memory_event or is_memory_set_event):
                continue

            if event.event_type == "conversation.turn_recorded" and is_source:
                steps.append(
                    CausalReplayStep(
                        step="source",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=(
                            f"Owner turn {memory.evidence_ref} supplied this context "
                            f"in session {memory.source_session_id[-10:]}"
                        ),
                    )
                )
            elif event.event_type == "memory.write_succeeded" and is_direct_memory_event:
                steps.append(
                    CausalReplayStep(
                        step="persist",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=f"Sibyl confirmed memory {memory.memory_id} in the entity tier",
                    )
                )
            elif event.event_type == "memory.recall_succeeded" and is_memory_set_event:
                steps.append(
                    CausalReplayStep(
                        step="recall",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=(
                            f"Session {event.session_id[-10:] if event.session_id else 'unknown'} "
                            "retrieved this record from Sibyl"
                        ),
                    )
                )
            elif event.event_type == "behavior.changed_by_memory" and is_memory_set_event:
                steps.append(
                    CausalReplayStep(
                        step="decision",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=(
                            f"The agent changed its action using this memory: "
                            f"{payload.get('action', 'memory-influenced action')}"
                        ),
                    )
                )
            elif event.event_type in {"handoff.created", "handoff.accepted", "handoff.started"}:
                steps.append(
                    CausalReplayStep(
                        step="handoff",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=(
                            f"Scoped handoff {payload.get('handoff_id', 'unknown')} carried "
                            "this selected memory"
                        ),
                    )
                )
            elif event.event_type in {"task.started", "task.step_changed"}:
                steps.append(
                    CausalReplayStep(
                        step="worker",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail=f"Worker step: {payload.get('current_step', 'task work began')}",
                    )
                )
            elif event.event_type == "task.blocked":
                steps.append(
                    CausalReplayStep(
                        step="review",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail="The task stopped for review or additional context",
                    )
                )
            elif event.event_type in {"task.completed", "handoff.completed"}:
                steps.append(
                    CausalReplayStep(
                        step="result",
                        event_id=event.event_id,
                        event_type=event.event_type,
                        detail="The task produced a result after using this context",
                    )
                )
        emit(
            "causal.replay_completed",
            correlation_id=correlation_id,
            payload={
                "memory_id": memory_id,
                "owner_id": owner_id,
                "npc_id": memory.npc_id,
                "steps": len(steps),
            },
        )
        return CausalReplayResponse(memory=memory, steps=steps)

    @app.get("/api/events/recent", response_model=RecentEventsResponse)
    async def recent_events(
        owner_id: str | None = None, npc_id: str | None = None
    ) -> RecentEventsResponse:
        return RecentEventsResponse(
            events=[
                event.model_dump(mode="json")
                for event in app.state.events[-100:]
                if event_visible(event, owner_id, npc_id)
            ]
        )

    @app.post("/api/sessions/{session_id}/restart", response_model=RestartResponse)
    async def restart_session(session_id: str, owner_id: str) -> RestartResponse:
        try:
            session = app.state.sessions.get(session_id)
            npc = resolve_npc(owner_id, session.npc_id)
            terminated, fresh = app.state.sessions.restart(session_id)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        emit(
            "npc.session_terminated",
            correlation_id=terminated.session_id,
            payload={
                "owner_id": npc.owner_id,
                "npc_id": terminated.npc_id,
                "session_id": terminated.session_id,
            },
        )
        emit(
            "npc.session_restarted",
            correlation_id=fresh.session_id,
            payload={
                "owner_id": npc.owner_id,
                "npc_id": fresh.npc_id,
                "terminated_session_id": terminated.session_id,
                "fresh_session_id": fresh.session_id,
                "transient_turns": 0,
            },
        )
        return RestartResponse(terminated=terminated, fresh=fresh, transient_turns_after_restart=0)

    @app.post("/api/sessions/{session_id}/continuity", response_model=ContinuityResponse)
    async def restore_continuity(session_id: str, request: ContinuityRequest) -> ContinuityResponse:
        try:
            session = app.state.sessions.get(session_id)
            resolve_npc(request.owner_id, request.npc_id)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if session.status != "active":
            raise HTTPException(
                status_code=409, detail="continuity requires an active fresh session"
            )
        if session.npc_id != request.npc_id:
            raise HTTPException(status_code=403, detail="session does not belong to this NPC")

        correlation_id = f"recall_{uuid4().hex}"
        emit(
            "memory.recall_requested",
            correlation_id=correlation_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": request.npc_id,
                "session_id": session_id,
            },
        )
        adapter = getattr(app.state, "memory_adapter", None)
        if adapter is None:
            agent_result = await run_agent(
                resolve_npc(request.owner_id, request.npc_id),
                session_id,
                request.query,
                [],
                correlation_id=correlation_id,
            )
            decision = assemble_continuity(request, None, agent_result)
            emit(
                "continuity.memory_disabled",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "session_id": session_id,
                    "action": decision.action,
                },
            )
            emit(
                "continuity.failed",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "reason": "memory_disabled",
                    "session_id": session_id,
                },
            )
            return ContinuityResponse(request=request, **decision.model_dump())

        try:
            memories = adapter.recall_with_metadata(request.owner_id, request.npc_id, request.query)
        except MemoryAdapterError as exc:
            emit(
                "memory.recall_failed",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "session_id": session_id,
                },
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        agent_result = await run_agent(
            resolve_npc(request.owner_id, request.npc_id),
            session_id,
            request.query,
            memories,
            correlation_id=correlation_id,
        )
        decision = assemble_continuity(request, memories, agent_result)
        emit(
            "memory.recall_succeeded",
            correlation_id=correlation_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": request.npc_id,
                "session_id": session_id,
                "memory_ids": decision.recalled_memory_ids,
            },
        )
        if decision.agent_run.used_memory_ids:
            emit(
                "behavior.changed_by_memory",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "session_id": session_id,
                    "memory_ids": decision.agent_run.used_memory_ids,
                    "action": decision.action,
                },
            )
        return ContinuityResponse(request=request, **decision.model_dump())

    @app.post("/api/continuity/compare", response_model=ContinuityComparisonResponse)
    async def compare_continuity(
        request: ContinuityComparisonRequest,
    ) -> ContinuityComparisonResponse:
        """Run equivalent clean lanes with Sibyl enabled and explicitly disabled.

        This is an inspection tool, not a scripted judge path. The caller must provide an
        active session with no transient turns; the disabled lane is a newly created ephemeral
        session and is terminated after its decision is evaluated.
        """

        try:
            session = app.state.sessions.get(request.session_id)
            resolve_npc(request.owner_id, request.npc_id)
        except SessionRuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if session.status != "active":
            raise HTTPException(status_code=409, detail="comparison requires an active session")
        if session.npc_id != request.npc_id:
            raise HTTPException(status_code=403, detail="session does not belong to this NPC")
        if app.state.sessions.turns(request.session_id):
            raise HTTPException(
                status_code=409,
                detail="comparison requires a clean fresh session; restart before comparing",
            )

        adapter = memory_adapter()
        correlation_id = f"comparison_{uuid4().hex}"
        emit(
            "memory.recall_requested",
            correlation_id=correlation_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": request.npc_id,
                "session_id": request.session_id,
                "source": "comparison_memory_lane",
            },
        )
        try:
            memories = adapter.recall_with_metadata(request.owner_id, request.npc_id, request.query)
        except MemoryAdapterError as exc:
            emit(
                "memory.recall_failed",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "session_id": request.session_id,
                    "source": "comparison_memory_lane",
                },
            )
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        memory_request = ContinuityRequest(
            owner_id=request.owner_id,
            npc_id=request.npc_id,
            query=request.query,
        )
        memory_decision = assemble_continuity(
            memory_request,
            memories,
            await run_agent(
                resolve_npc(request.owner_id, request.npc_id),
                request.session_id,
                request.query,
                memories,
                correlation_id=correlation_id,
            ),
        )
        emit(
            "memory.recall_succeeded",
            correlation_id=correlation_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": request.npc_id,
                "session_id": request.session_id,
                "memory_ids": memory_decision.recalled_memory_ids,
                "source": "comparison_memory_lane",
            },
        )
        if memory_decision.agent_run.used_memory_ids:
            emit(
                "behavior.changed_by_memory",
                correlation_id=correlation_id,
                payload={
                    "owner_id": request.owner_id,
                    "npc_id": request.npc_id,
                    "session_id": request.session_id,
                    "memory_ids": memory_decision.agent_run.used_memory_ids,
                    "action": memory_decision.action,
                    "source": "comparison_memory_lane",
                },
            )

        disabled_session = app.state.sessions.start(request.npc_id)
        disabled_decision = assemble_continuity(
            memory_request,
            None,
            await run_agent(
                resolve_npc(request.owner_id, request.npc_id),
                disabled_session.session_id,
                request.query,
                [],
                correlation_id=correlation_id,
            ),
        )
        emit(
            "continuity.memory_disabled",
            correlation_id=correlation_id,
            payload={
                "owner_id": request.owner_id,
                "npc_id": request.npc_id,
                "session_id": disabled_session.session_id,
                "action": disabled_decision.action,
                "source": "comparison_memory_disabled_lane",
            },
        )
        terminated_disabled = app.state.sessions.terminate(disabled_session.session_id)
        disabled_lane = ContinuityComparisonLane(
            session_id=terminated_disabled.session_id,
            decision=disabled_decision,
        )
        memory_lane = ContinuityComparisonLane(
            session_id=request.session_id,
            decision=memory_decision,
        )
        return ContinuityComparisonResponse(
            request=memory_request,
            memory_lane=memory_lane,
            memory_disabled_lane=disabled_lane,
            diverged=(
                memory_decision.action != disabled_decision.action
                or memory_decision.status != disabled_decision.status
            ),
        )

    return app


app = create_app()
