from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from abrain_api.modules.conversation import ConversationTurn
from abrain_api.modules.memory import MemoryRecord
from abrain_api.modules.npc_identity import NpcIdentity
from abrain_api.modules.owner_identity import OwnerIdentity
from abrain_api.modules.proof import ProofStep
from abrain_api.modules.sessions import AgentSession


def test_domain_modules_accept_generic_values() -> None:
    now = datetime.now(UTC)
    owner = OwnerIdentity(owner_id="owner_1", display_name="Owner")
    npc = NpcIdentity(npc_id="npc_1", owner_id=owner.owner_id, name="Nova")
    session = AgentSession(
        session_id="session_1", npc_id=npc.npc_id, status="fresh", started_at=now
    )
    turn = ConversationTurn(
        turn_id="turn_1",
        session_id=session.session_id,
        speaker="owner",
        text="Hello",
        occurred_at=now,
    )
    record = MemoryRecord(
        memory_id="memory_1",
        owner_id=owner.owner_id,
        npc_id=npc.npc_id,
        concept="preference",
        key="interface_style",
        value="dark",
        source_session_id=session.session_id,
        created_at=now,
    )
    proof = ProofStep(step="memory.write", status="not_verified")

    assert (owner.owner_id, npc.name, turn.speaker, record.concept, proof.status) == (
        "owner_1",
        "Nova",
        "owner",
        "preference",
        "not_verified",
    )


def test_memory_rejects_empty_values() -> None:
    with pytest.raises(ValidationError):
        MemoryRecord(
            memory_id="memory_1",
            owner_id="owner_1",
            npc_id="npc_1",
            concept="goal",
            key="",
            value="",
            source_session_id="session_1",
            created_at=datetime.now(UTC),
        )
