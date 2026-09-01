"""Generic agent task domain models and the ephemeral execution index."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "thinking", "working", "blocked", "review", "completed"]


class AgentTask(BaseModel):
    """A user-created mission whose current state is mirrored into Sibyl HOT state."""

    task_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    assigned_agent_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=20_000)
    status: TaskStatus
    created_at: datetime
    current_step: str = Field(min_length=1, max_length=500)
    result: str | None = Field(default=None, max_length=8_000)
    relevant_memory_ids: list[str] = Field(default_factory=list, max_length=50)
    parent_task_id: str | None = None


def task_title(objective: str) -> str:
    """Derive a readable title without introducing a fixed mission."""

    compact = " ".join(objective.split())
    return compact if len(compact) <= 72 else f"{compact[:69].rstrip()}…"


class TaskRuntimeError(RuntimeError):
    """Raised when a task lifecycle operation is invalid."""


class TaskRuntime:
    """Short-lived index for active tasks; Sibyl remains the durable HOT boundary."""

    def __init__(self) -> None:
        self._tasks: dict[str, AgentTask] = {}
        self._lock = RLock()

    def create(self, task: AgentTask) -> AgentTask:
        with self._lock:
            if task.task_id in self._tasks:
                raise TaskRuntimeError("task already exists")
            self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> AgentTask:
        with self._lock:
            try:
                return self._tasks[task_id]
            except KeyError as exc:
                raise TaskRuntimeError("task not found") from exc

    def restore(self, task: AgentTask) -> AgentTask:
        with self._lock:
            existing = self._tasks.get(task.task_id)
            if existing is not None and existing != task:
                raise TaskRuntimeError("task conflicts with the cached task")
            self._tasks[task.task_id] = task
        return task

    def update(self, task_id: str, **changes: object) -> AgentTask:
        with self._lock:
            current = self.get(task_id)
            updated = current.model_copy(update=changes)
            self._tasks[task_id] = updated
            return updated

    def list(self, owner_id: str, assigned_agent_id: str | None = None) -> list[AgentTask]:
        with self._lock:
            tasks = [task for task in self._tasks.values() if task.owner_id == owner_id]
            if assigned_agent_id is not None:
                tasks = [task for task in tasks if task.assigned_agent_id == assigned_agent_id]
        return sorted(tasks, key=lambda task: task.created_at, reverse=True)


def new_task(
    *,
    owner_id: str,
    assigned_agent_id: str,
    objective: str,
    title: str | None = None,
    parent_task_id: str | None = None,
) -> AgentTask:
    return AgentTask(
        task_id=f"task_{uuid4().hex}",
        owner_id=owner_id,
        assigned_agent_id=assigned_agent_id,
        title=title.strip() if title and title.strip() else task_title(objective),
        objective=objective.strip(),
        status="queued",
        created_at=datetime.now(UTC),
        current_step="Queued for the next agent run",
        parent_task_id=parent_task_id,
    )
