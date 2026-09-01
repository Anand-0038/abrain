from fastapi.testclient import TestClient

from abrain_api.config import Settings
from abrain_api.main import create_app


def test_npc_identity_reopens_after_backend_process_restart(tmp_path) -> None:
    settings = Settings(
        ABRAIN_ENV="test",
        ABRAIN_MEMORY_ENABLED="true",
        ABRAIN_SIBYL_DB_PATH=str(tmp_path / "memory.db"),
    )

    with TestClient(create_app(settings)) as first:
        created = first.post(
            "/api/npcs",
            json={
                "owner_id": "owner-a",
                "name": "Nova",
                "appearance": {
                    "palette": "violet",
                    "avatar_key": "orbiter",
                    "accessory_key": "antenna",
                },
            },
        ).json()["npc"]
        assert created["appearance"] == {
            "palette": "violet",
            "avatar_key": "orbiter",
            "accessory_key": "antenna",
        }
        assert first.get("/api/npcs", params={"owner_id": "owner-a"}).json()["npcs"] == [created]

    with TestClient(create_app(settings)) as reopened:
        session = reopened.post(
            "/api/sessions", json={"owner_id": "owner-a", "npc_id": created["npc_id"]}
        )
        assert session.status_code == 201
        assert session.json()["session"]["npc_id"] == created["npc_id"]

        listed = reopened.get("/api/npcs", params={"owner_id": "owner-a"})
        assert listed.status_code == 200
        assert listed.json()["npcs"] == [created]

        assert reopened.get("/api/npcs", params={"owner_id": "owner-b"}).json()["npcs"] == []
        assert (
            reopened.post(
                "/api/sessions",
                json={"owner_id": "owner-b", "npc_id": created["npc_id"]},
            ).status_code
            == 403
        )
