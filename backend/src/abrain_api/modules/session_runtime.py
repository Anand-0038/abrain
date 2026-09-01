"""Ephemeral session/runtime state.

Durable owner context belongs in Sibyl; transcripts are transient and are
destroyed when a session terminates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from .conversation import ConversationTurn
from .sessions import AgentSession


class SessionRuntimeError(RuntimeError):
    """Raised when a session operation violates its lifecycle."""


class SessionRuntime:
    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}
        self._turns: dict[str, list[ConversationTurn]] = {}
        self._lock = RLock()

    def start(self, npc_id: str) -> AgentSession:
        session = AgentSession(
            session_id=f"session_{uuid4().hex}",
            npc_id=npc_id,
            status="active",
            started_at=datetime.now(UTC),
        )
        with self._lock:
            self._sessions[session.session_id] = session
            self._turns[session.session_id] = []
        return session

    def get(self, session_id: str) -> AgentSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise SessionRuntimeError("session not found") from exc

    def terminate(self, session_id: str) -> AgentSession:
        with self._lock:
            session = self.get(session_id)
            if session.status == "terminated":
                return session
            ended = session.model_copy(
                update={"status": "terminated", "terminated_at": datetime.now(UTC)}
            )
            self._sessions[session_id] = ended
            self._turns.pop(session_id, None)
            return ended

    def restart(self, session_id: str) -> tuple[AgentSession, AgentSession]:
        old = self.terminate(session_id)
        return old, self.start(old.npc_id)

    def add_turn(self, turn: ConversationTurn) -> ConversationTurn:
        with self._lock:
            session = self.get(turn.session_id)
            if session.status != "active":
                raise SessionRuntimeError("cannot add a turn to an inactive session")
            self._turns[turn.session_id].append(turn)
            return turn

    def turns(self, session_id: str) -> list[ConversationTurn]:
        with self._lock:
            self.get(session_id)
            return list(self._turns.get(session_id, []))

    def list_for_npc(self, npc_id: str) -> list[AgentSession]:
        """Return session lineage for one persistent brain, newest first."""

        with self._lock:
            sessions = [session for session in self._sessions.values() if session.npc_id == npc_id]
        return sorted(sessions, key=lambda session: session.started_at, reverse=True)
