from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


def test_memory_list_update_archive_delete_are_provider_verified(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )
    candidate = {
        "candidate_id": "memory-1",
        "owner_id": "owner-a",
        "npc_id": "npc-a",
        "source_session_id": "session-a",
        "source_turn_id": "turn-a",
        "concept": "preference",
        "key": "style",
        "value": "minimal",
        "confidence": 0.98,
    }
    with TestClient(create_app(settings)) as client:
        npc = client.post("/api/npcs", json={"owner_id": "owner-a", "name": "Nova"}).json()["npc"]
        source_session = client.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        ).json()["session"]
        candidate["npc_id"] = npc["npc_id"]
        candidate["source_session_id"] = source_session["session_id"]
        assert (
            client.post("/api/memory/candidates/promote", json={"candidate": candidate}).status_code
            == 201
        )
        listed = client.get(
            "/api/memories", params={"owner_id": "owner-a", "npc_id": npc["npc_id"]}
        )
        assert listed.status_code == 200
        assert listed.json()["memories"][0]["memory_id"] == "memory-1"

        updated = client.patch(
            "/api/memories/memory-1",
            params={"owner_id": "owner-a"},
            json={"key": "style", "value": "minimal and calm", "confidence": 0.99},
        )
        assert updated.json()["verified"] is True
        assert (
            client.get("/api/memories", params={"owner_id": "owner-a"}).json()["memories"][0][
                "value"
            ]
            == "minimal and calm"
        )

        archived = client.post("/api/memories/memory-1/archive", params={"owner_id": "owner-a"})
        assert archived.json()["verified"] is True
        assert client.get("/api/memories", params={"owner_id": "owner-a"}).json()["memories"] == []
