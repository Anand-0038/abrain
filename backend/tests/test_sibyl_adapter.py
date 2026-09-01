from datetime import UTC, datetime

from abrain_api.memory import SibylMemoryAdapter
from abrain_api.modules.memory import MemoryRecord
from abrain_api.modules.npc_identity import NpcIdentity


def record(owner_id: str, memory_id: str, key: str, value: str) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        owner_id=owner_id,
        npc_id="nova",
        concept="preference",
        key=key,
        value=value,
        source_session_id="session-1",
        created_at=datetime.now(UTC),
        evidence_ref="turn-1",
    )


def test_sibyl_persists_across_adapter_reopen_and_isolates_owners(tmp_path) -> None:
    db_path = tmp_path / "memory.db"
    owner_a_dark = record("owner-a", "mem-a-dark", "interface", "dark interfaces")
    owner_a_japan = record("owner-a", "mem-a-japan", "goal", "visit Japan")
    owner_b_food = record("owner-b", "mem-b-food", "preference", "spicy food")

    first = SibylMemoryAdapter(db_path)
    assert first.write(owner_a_dark) == owner_a_dark
    assert first.write(owner_a_japan) == owner_a_japan
    assert first.write(owner_b_food) == owner_b_food
    assert first.recall("owner-a", "nova", "dark workspace") == [owner_a_dark]
    first.close()
    del first

    reopened = SibylMemoryAdapter(db_path)
    assert reopened.get("owner-a", owner_a_japan.memory_id) == owner_a_japan
    assert reopened.get("owner-b", owner_a_dark.memory_id) is None
    assert reopened.recall("owner-a", "nova", "Japan") == [owner_a_japan]
    assert {item.memory_id for item in reopened.list("owner-b", npc_id="nova")} == {
        owner_b_food.memory_id
    }
    assert reopened.search("owner-a", "dark") == [owner_a_dark]
    reopened.close()


def test_recall_exposes_sibyl_search_metadata(tmp_path) -> None:
    adapter = SibylMemoryAdapter(tmp_path / "retrieval.db")
    relevant = record("owner-a", "mem-relevant", "workspace", "dark interface")
    unrelated = record("owner-a", "mem-unrelated", "travel", "visit Japan")
    adapter.write(relevant)
    adapter.write(unrelated)

    matches = adapter.recall_with_metadata("owner-a", "nova", "dark interface")

    assert [item.record.memory_id for item in matches] == ["mem-relevant"]
    assert matches[0].source == "sibyl_search"
    assert matches[0].tier == "entity"
    assert matches[0].query == "dark interface"
    assert matches[0].provider_rank is not None
    assert matches[0].provider_snippet is not None
    assert "Sibyl search returned" in matches[0].relevance_reason
    assert matches[0].search_attempt == 1
    assert matches[0].retry_query is None
    adapter.close()


def test_sibyl_search_verdict_explains_empty_recall_without_exposing_other_owner(tmp_path) -> None:
    adapter = SibylMemoryAdapter(tmp_path / "verdict.db")
    adapter.write(record("owner-a", "mem-a", "workspace", "dark interface"))
    adapter.write(record("owner-b", "mem-b", "food", "spicy food"))

    assert adapter.recall("owner-a", "nova", "spicy food") == []
    verdict = adapter.search_verdict("owner-a", "spicy food")

    assert verdict.code in {"no_match", "abstained_on", "empty_store", "no_scoped_match"}
    assert verdict.returned == 0
    assert "owner-context" in verdict.explanation
    assert "spicy food" not in verdict.explanation
    adapter.close()


def test_sibyl_recall_supports_generic_project_context(tmp_path) -> None:
    adapter = SibylMemoryAdapter(tmp_path / "project.db")
    project_memory = record("owner-a", "mem-project", "project", "build A-Brain")
    project_memory = project_memory.model_copy(update={"concept": "project"})

    assert adapter.write(project_memory) == project_memory
    assert adapter.recall("owner-a", "nova", "A-Brain") == [project_memory]
    adapter.close()


def test_sibyl_update_archive_delete_are_verified(tmp_path) -> None:
    path = tmp_path / "memory.db"
    original = record("owner-a", "mem-1", "style", "dark")
    updated = original.model_copy(update={"value": "dark and compact"})
    adapter = SibylMemoryAdapter(path)

    adapter.write(original)
    assert adapter.update(updated) == updated
    assert adapter.get("owner-a", "mem-1") == updated
    assert adapter.archive("owner-a", "mem-1", "superseded") is True
    assert adapter.get("owner-a", "mem-1") is None

    adapter.write(original)
    assert adapter.delete("owner-a", "mem-1") is True
    assert adapter.delete("owner-a", "missing") is False
    adapter.close()


def test_sibyl_persists_brain_identity_separately_from_owner_memories(tmp_path) -> None:
    path = tmp_path / "identity.db"
    identity = NpcIdentity(npc_id="npc-nova", owner_id="owner-a", name="Nova")
    adapter = SibylMemoryAdapter(path)

    assert adapter.write_npc(identity) == identity
    assert adapter.get_npc("owner-a", identity.npc_id) == identity
    assert adapter.get_npc("owner-b", identity.npc_id) is None
    assert adapter.list_npcs("owner-a") == [identity]
    assert adapter.list_npcs("owner-b") == []
    assert adapter.list("owner-a") == []
    adapter.close()

    reopened = SibylMemoryAdapter(path)
    assert reopened.get_npc("owner-a", identity.npc_id) == identity
    reopened.close()
