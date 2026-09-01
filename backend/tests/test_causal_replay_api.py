from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


def test_causal_replay_returns_source_write_recall_and_decision_chain(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        source_session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        candidate = {
            "candidate_id": "memory-causal",
            "owner_id": "owner-a",
            "npc_id": npc["npc_id"],
            "source_session_id": source_session["session_id"],
            "source_turn_id": "turn-source",
            "concept": "constraint",
            "key": "release_gate",
            "value": "verify before deploy",
            "confidence": 0.99,
        }
        assert (
            client.post("/api/memory/candidates/promote", json={"candidate": candidate}).status_code
            == 201
        )
        started = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        result = client.post(
            f"/api/sessions/{started['session_id']}/continuity",
            json={"owner_id": "owner-a", "npc_id": npc["npc_id"], "query": "release"},
        )
        assert result.status_code == 200
        replay = client.get(
            "/api/continuity/replay", params={"owner_id": "owner-a", "memory_id": "memory-causal"}
        )
        assert replay.status_code == 200
        steps = replay.json()["steps"]
        # This candidate used a source-turn identifier without a matching persisted
        # conversation event, so replay must not invent an OWNER SAID node.
        assert [step["step"] for step in steps] == ["persist", "recall", "decision"]
        assert all(step["event_id"] for step in steps)
