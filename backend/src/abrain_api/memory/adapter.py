"""A-Brain's isolated adapter for the public Sibyl Memory API.

Application code deals in ``MemoryRecord`` values and never reaches into the
Sibyl client's SQLite implementation. Each owner maps to a separate Sibyl
tenant, so isolation is enforced by the provider query boundary as well as by
the application-level record check.
"""

from __future__ import annotations

import builtins
import hashlib
from datetime import UTC
from pathlib import Path
from typing import Any

from sibyl_memory_client import MemoryClient, Storage  # type: ignore[import-untyped]

from ..modules.handoff import ScopedHandoff
from ..modules.memory import (
    MemoryRecallOutcome,
    MemoryRecord,
    MemoryRetrieval,
    MemorySearchVerdict,
)
from ..modules.npc_identity import NpcIdentity
from ..modules.tasks import AgentTask

_CATEGORY = "abrain.memory"
_NPC_CATEGORY = "abrain.npc"


class MemoryAdapterError(RuntimeError):
    """Raised when the verified persistent memory boundary cannot complete."""


class SibylMemoryAdapter:
    """Persist and recall generic owner context through Sibyl Memory.

    The adapter intentionally opens a fresh public ``MemoryClient`` wrapper
    for each operation while sharing one provider ``Storage``. This avoids a
    mutable tenant selection leaking between concurrent owner requests.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self._storage = Storage(self.db_path)

    @staticmethod
    def _tenant_id(owner_id: str) -> str:
        if not owner_id.strip():
            raise MemoryAdapterError("owner_id must not be empty")
        digest = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()
        return f"abrain-owner-{digest}"

    def _client(self, owner_id: str) -> MemoryClient:
        return MemoryClient(self._storage, tenant_id=self._tenant_id(owner_id))

    @staticmethod
    def _entity_name(memory_id: str) -> str:
        if not memory_id.strip():
            raise MemoryAdapterError("memory_id must not be empty")
        return memory_id

    @staticmethod
    def _body(record: MemoryRecord) -> dict[str, Any]:
        return record.model_dump(mode="json")

    @staticmethod
    def _record(body: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord.model_validate(body)

    @staticmethod
    def _npc(body: dict[str, Any]) -> NpcIdentity:
        return NpcIdentity.model_validate(body)

    def write_npc(self, npc: NpcIdentity) -> NpcIdentity:
        """Persist a brain identity separately from owner-context records."""

        client = self._client(npc.owner_id)
        body = npc.model_dump(mode="json")
        try:
            client.set_entity(_NPC_CATEGORY, self._entity_name(npc.npc_id), body, status="active")
            stored = client.get_entity(_NPC_CATEGORY, self._entity_name(npc.npc_id))
        except Exception as exc:
            raise MemoryAdapterError("Sibyl NPC identity write failed") from exc
        persisted = self._npc(stored["body"])
        if persisted != npc:
            raise MemoryAdapterError("Sibyl NPC identity verification returned different identity")
        return persisted

    def get_npc(self, owner_id: str, npc_id: str) -> NpcIdentity | None:
        client = self._client(owner_id)
        try:
            entity = client.get_entity(_NPC_CATEGORY, self._entity_name(npc_id))
        except Exception as exc:
            if exc.__class__.__name__ == "NotFoundError":
                return None
            raise MemoryAdapterError("Sibyl NPC identity read failed") from exc
        npc = self._npc(entity["body"])
        return npc if npc.owner_id == owner_id and npc.npc_id == npc_id else None

    def list_npcs(self, owner_id: str) -> builtins.list[NpcIdentity]:
        client = self._client(owner_id)
        try:
            entities = client.list_entities(category=_NPC_CATEGORY, status="active", limit=10_000)
        except Exception as exc:
            raise MemoryAdapterError("Sibyl NPC identity listing failed") from exc
        return sorted(
            [npc for item in entities if (npc := self._npc(item["body"])).owner_id == owner_id],
            key=lambda item: item.npc_id,
        )

    def write(self, record: MemoryRecord) -> MemoryRecord:
        """Write a WARM entity and a COLD provenance event, then verify it."""

        client = self._client(record.owner_id)
        body = self._body(record)
        try:
            client.set_entity(_CATEGORY, self._entity_name(record.memory_id), body, status="active")
            client.set_state(
                f"brain:{record.npc_id}:current",
                {
                    "owner_id": record.owner_id,
                    "npc_id": record.npc_id,
                    "last_memory_id": record.memory_id,
                    "last_concept": record.concept,
                    "updated_at": record.created_at.isoformat(),
                },
            )
            client.write_event(
                evaluated={"operation": "memory.write", "memory_id": record.memory_id},
                acted={"status": "promoted", "concept": record.concept},
                extra={
                    "owner_id": record.owner_id,
                    "npc_id": record.npc_id,
                    "source_session_id": record.source_session_id,
                    "evidence_ref": record.evidence_ref,
                },
                ts=record.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            )
            stored = client.get_entity(_CATEGORY, self._entity_name(record.memory_id))
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory write failed") from exc
        persisted = self._record(stored["body"])
        if persisted != record:
            raise MemoryAdapterError("Sibyl write verification returned different record")
        return persisted

    def write_task_state(self, task: AgentTask) -> AgentTask:
        """Persist and verify the current task in Sibyl's HOT state tier."""

        client = self._client(task.owner_id)
        body = task.model_dump(mode="json")
        try:
            client.set_state(f"task:{task.task_id}", body)
            stored = client.get_state(f"task:{task.task_id}")
        except Exception as exc:
            raise MemoryAdapterError("Sibyl task HOT state write failed") from exc
        if stored is None:
            raise MemoryAdapterError("Sibyl task HOT state write returned no state")
        try:
            persisted = AgentTask.model_validate(stored["body"])
        except ValueError as exc:
            raise MemoryAdapterError("Sibyl task HOT state was malformed") from exc
        if persisted != task:
            raise MemoryAdapterError("Sibyl task HOT state verification returned different state")
        return persisted

    def get_task_state(self, owner_id: str, task_id: str) -> AgentTask | None:
        """Reopen one task from the provider-backed HOT state namespace."""

        client = self._client(owner_id)
        try:
            stored = client.get_state(f"task:{task_id}")
        except Exception as exc:
            raise MemoryAdapterError("Sibyl task HOT state read failed") from exc
        if stored is None:
            return None
        try:
            task = AgentTask.model_validate(stored["body"])
        except ValueError as exc:
            raise MemoryAdapterError("Sibyl task HOT state was malformed") from exc
        return task if task.owner_id == owner_id else None

    def write_handoff_state(self, handoff: ScopedHandoff) -> ScopedHandoff:
        """Persist and verify a delegated context grant in Sibyl HOT state."""

        client = self._client(handoff.owner_id)
        body = handoff.model_dump(mode="json")
        try:
            client.set_state(f"handoff:{handoff.handoff_id}", body)
            stored = client.get_state(f"handoff:{handoff.handoff_id}")
        except Exception as exc:
            raise MemoryAdapterError("Sibyl handoff HOT state write failed") from exc
        if stored is None:
            raise MemoryAdapterError("Sibyl handoff HOT state write returned no state")
        try:
            persisted = ScopedHandoff.model_validate(stored["body"])
        except ValueError as exc:
            raise MemoryAdapterError("Sibyl handoff HOT state was malformed") from exc
        if persisted != handoff:
            raise MemoryAdapterError(
                "Sibyl handoff HOT state verification returned different state"
            )
        return persisted

    def get_handoff_state(self, owner_id: str, handoff_id: str) -> ScopedHandoff | None:
        """Reopen one owner-scoped delegation grant from Sibyl HOT state."""

        client = self._client(owner_id)
        try:
            stored = client.get_state(f"handoff:{handoff_id}")
        except Exception as exc:
            raise MemoryAdapterError("Sibyl handoff HOT state read failed") from exc
        if stored is None:
            return None
        try:
            handoff = ScopedHandoff.model_validate(stored["body"])
        except ValueError as exc:
            raise MemoryAdapterError("Sibyl handoff HOT state was malformed") from exc
        return handoff if handoff.owner_id == owner_id else None

    def get(self, owner_id: str, memory_id: str) -> MemoryRecord | None:
        client = self._client(owner_id)
        try:
            entity = client.get_entity(_CATEGORY, self._entity_name(memory_id))
        except Exception as exc:
            # Avoid coupling the application to a provider exception class;
            # the public read contract is a nullable lookup.
            if exc.__class__.__name__ == "NotFoundError":
                return None
            raise MemoryAdapterError("Sibyl memory read failed") from exc
        record = self._record(entity["body"])
        return record if record.owner_id == owner_id else None

    def list(self, owner_id: str, *, npc_id: str | None = None) -> builtins.list[MemoryRecord]:
        client = self._client(owner_id)
        try:
            entities = client.list_entities(category=_CATEGORY, status="active", limit=10_000)
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory listing failed") from exc
        records = [self._record(item["body"]) for item in entities]
        scoped = [record for record in records if record.owner_id == owner_id]
        if npc_id is not None:
            scoped = [record for record in scoped if record.npc_id == npc_id]
        return sorted(scoped, key=lambda record: record.created_at, reverse=True)

    def recall(
        self, owner_id: str, npc_id: str, query: str, *, limit: int = 10
    ) -> builtins.list[MemoryRecord]:
        """Return records from the provider-backed recall path."""

        return [
            match.record
            for match in self.recall_with_metadata(owner_id, npc_id, query, limit=limit)
        ]

    def recall_with_metadata(
        self, owner_id: str, npc_id: str, query: str, *, limit: int = 10
    ) -> builtins.list[MemoryRetrieval]:
        """Return retrievals from one atomic Sibyl recall outcome."""

        return self.recall_outcome(owner_id, npc_id, query, limit=limit).retrievals

    def recall_outcome(
        self, owner_id: str, npc_id: str, query: str, *, limit: int = 10
    ) -> MemoryRecallOutcome:
        """Recall through Sibyl search and retain the provider's ranking metadata.

        A-Brain's structured records live in Sibyl's WARM ``entity`` tier, so
        only entity hits can be promoted into ``MemoryRecord`` values. HOT
        state and COLD journal entries are still written for current state and
        provenance, but are not misread as durable owner-context records.
        """

        if limit < 1:
            return MemoryRecallOutcome(
                verdict=MemorySearchVerdict(
                    code="limit_zero",
                    returned=0,
                    explanation="No records were requested from Sibyl.",
                )
            )
        if not query.strip():
            records = self.list(owner_id, npc_id=npc_id)[:limit]
            retrievals = [
                MemoryRetrieval(
                    record=record,
                    query=query,
                    tier="entity",
                    source="sibyl_entity_list",
                    relevance_reason=(
                        "Empty query requested the active owner and NPC brain entities."
                    ),
                )
                for record in records
            ]
            return MemoryRecallOutcome(
                retrievals=retrievals,
                verdict=MemorySearchVerdict(
                    code="entity_list",
                    returned=len(retrievals),
                    explanation="Sibyl listed active owner and NPC brain entities.",
                ),
            )

        client = self._client(owner_id)
        attempt = 1
        search_query = query
        try:
            hits = client.search(search_query, limit=limit * 2, tiers=("entity",))
            # Lucid's verdict is additive metadata. Only the provider may
            # identify a safe retry token; A-Brain never guesses by stripping
            # arbitrary owner words. A single retry is deliberately below
            # Sibyl's documented maximum of two agent-side retries.
            verdict = self._search_verdict(hits, search_query)
            if not hits and verdict.retryable and verdict.retry_query:
                attempt = 2
                search_query = verdict.retry_query
                hits = client.search(search_query, limit=limit * 2, tiers=("entity",))
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory search failed") from exc

        matches: builtins.list[MemoryRetrieval] = []
        seen_memory_ids: set[str] = set()
        for hit in hits:
            if hit.get("category") != _CATEGORY:
                continue
            record = self._record(hit["body"])
            if record.owner_id != owner_id or record.npc_id != npc_id:
                continue
            if record.memory_id in seen_memory_ids:
                continue
            seen_memory_ids.add(record.memory_id)
            tier = str(hit.get("tier") or "entity")
            key = str(hit.get("key") or record.memory_id)
            matches.append(
                MemoryRetrieval(
                    record=record,
                    query=query,
                    tier=tier,
                    source="sibyl_search",
                    provider_rank=float(hit["rank"])
                    if isinstance(hit.get("rank"), (int, float))
                    else None,
                    provider_snippet=hit.get("snippet")
                    if isinstance(hit.get("snippet"), str)
                    else None,
                    relevance_reason=(
                        f"Sibyl search returned the {tier} entity {key} for this query "
                        f"on attempt {attempt}."
                    ),
                    search_attempt=attempt,
                    retry_query=search_query if attempt > 1 else None,
                )
            )
            if len(matches) >= limit:
                break
        final_verdict = self._search_verdict(hits, search_query)
        if not matches and final_verdict.code == "ok":
            final_verdict = final_verdict.model_copy(
                update={
                    "code": "no_scoped_match",
                    "returned": 0,
                    "retryable": False,
                    "retry_query": None,
                    "explanation": (
                        "Sibyl found no record in this NPC's durable owner-context scope; "
                        "the agent must ask for context."
                    ),
                }
            )
        else:
            final_verdict = final_verdict.model_copy(update={"returned": len(matches)})
        return MemoryRecallOutcome(retrievals=matches, verdict=final_verdict)

    @staticmethod
    def _search_verdict(hits: object, query: str) -> MemorySearchVerdict:
        """Translate Lucid's additive verdict without coupling app code to SDK types."""

        raw = getattr(hits, "verdict", None)
        code_value = getattr(raw, "code", "unknown")
        code = str(getattr(code_value, "value", code_value))
        raw_tokens = getattr(raw, "tokens", ()) or ()
        tokens = [str(token) for token in raw_tokens if str(token).strip()][:8]
        gate_value = getattr(raw, "gate", None)
        gate = str(getattr(gate_value, "value", gate_value)) if gate_value else None
        returned_value = getattr(raw, "returned", None)
        returned = int(returned_value) if isinstance(returned_value, int) else len(hits)  # type: ignore[arg-type]

        retry_query: str | None = None
        retryable = code == "abstained_on" and bool(tokens)
        if retryable:
            blocked = tokens[0].casefold()
            remaining = [word for word in query.split() if word.casefold() != blocked]
            candidate = " ".join(remaining).strip()
            if candidate and candidate != query:
                retry_query = candidate
            else:
                retryable = False

        if code == "ok":
            explanation = "Sibyl search found matching owner-context records."
        elif retryable:
            explanation = (
                "Sibyl abstained on the original query and identified one query token that can be "
                "safely removed for one bounded retry."
            )
        elif code == "empty_store":
            explanation = (
                "Sibyl reports that this owner brain has no searchable durable entities yet."
            )
        else:
            explanation = (
                "Sibyl found no matching owner-context record; the agent must ask for context."
            )

        return MemorySearchVerdict(
            code=code,
            tokens=tokens,
            gate=gate,
            returned=returned,
            retry_query=retry_query,
            retryable=retryable,
            explanation=explanation,
        )

    def search_verdict(self, owner_id: str, query: str) -> MemorySearchVerdict:
        """Expose Sibyl's zero-result explanation without leaking stored content.

        This is useful to the agent and UI when recall returns no records. It
        does not perform the retry itself, so callers can make user-facing
        retry decisions explicitly.
        """

        client = self._client(owner_id)
        try:
            hits = client.search(query, limit=1, tiers=("entity",))
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory search failed") from exc
        verdict = self._search_verdict(hits, query)
        # A tenant also contains the persistent NPC identity entity. A valid
        # provider hit for that identity is not a valid owner-context memory
        # recall, so translate the boundary honestly without exposing it.
        has_owner_context_hit = any(
            isinstance(hit, dict) and hit.get("category") == _CATEGORY for hit in hits
        )
        if verdict.code == "ok" and not has_owner_context_hit:
            return verdict.model_copy(
                update={
                    "code": "no_scoped_match",
                    "returned": 0,
                    "retryable": False,
                    "retry_query": None,
                    "explanation": (
                        "Sibyl found no record in this NPC's durable owner-context scope; "
                        "the agent must ask for context."
                    ),
                }
            )
        return verdict

    def search(self, owner_id: str, query: str, *, limit: int = 20) -> builtins.list[MemoryRecord]:
        """Use Sibyl's cross-tier search, retaining A-Brain owner validation."""

        client = self._client(owner_id)
        try:
            hits = client.search(query, limit=limit, tiers=("entity",))
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory search failed") from exc
        result: builtins.list[MemoryRecord] = []
        for hit in hits:
            if hit.get("category") != _CATEGORY:
                continue
            record = self._record(hit["body"])
            if record.owner_id == owner_id:
                result.append(record)
        return result

    def update(self, record: MemoryRecord) -> MemoryRecord:
        """Update the WARM entity through the same verified write path."""

        if self.get(record.owner_id, record.memory_id) is None:
            raise MemoryAdapterError("cannot update a memory that does not exist")
        return self.write(record)

    def archive(self, owner_id: str, memory_id: str, reason: str | None = None) -> bool:
        record = self.get(owner_id, memory_id)
        if record is None:
            return False
        client = self._client(owner_id)
        try:
            client.archive_entity(_CATEGORY, self._entity_name(memory_id), reason)
            return self.get(owner_id, memory_id) is None
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory archive failed") from exc

    def delete(self, owner_id: str, memory_id: str) -> bool:
        client = self._client(owner_id)
        try:
            deleted = client.delete_entity(_CATEGORY, self._entity_name(memory_id))
            return bool(deleted and self.get(owner_id, memory_id) is None)
        except Exception as exc:
            raise MemoryAdapterError("Sibyl memory delete failed") from exc

    def close(self) -> None:
        self._storage.close()

    def __enter__(self) -> SibylMemoryAdapter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
